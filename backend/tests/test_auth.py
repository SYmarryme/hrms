import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import IntegrityError

import backend.auth as auth_module
from backend.auth import AuthError, utc
from backend.models import audit_events, auth_sessions, metadata, role_assignments, users
from conftest import migrate, sign_in


def headers(value):
    return {'Authorization': 'Bearer ' + value}


def test_real_login_me_logout_and_no_secret_at_rest(system):
    app, client, _, password, user_id, _ = system
    token = sign_in(client, password)
    response = client.get('/api/v1/auth/me', headers=headers(token))
    assert response.status_code == 200
    profile = response.json()['data']
    assert profile['id'] == user_id and profile['roles'] == ['ADMIN']
    with app.state.database.transaction() as session:
        account = session.execute(select(users)).mappings().one()
        record = session.execute(select(auth_sessions)).mappings().one()
        safe = account['password_hash'].startswith('$argon2id$') and token not in str(record) and password not in str(account)
        assert safe, 'Credentials must not be stored as plaintext'
        assert len(record['token_hash']) == 64
        stored_hash = record['token_hash']
    assert client.get('/api/v1/auth/me', headers=headers(stored_hash)).status_code == 401
    assert client.post('/api/v1/auth/logout', headers=headers(token)).status_code == 204
    assert client.get('/api/v1/auth/me', headers=headers(token)).status_code == 401


def test_wrong_unknown_missing_and_cookie_only_are_401(system):
    _, client, _, password, _, _ = system
    wrong = secrets.token_urlsafe(23)
    errors = []
    for username in ('initial-admin', 'not-an-account'):
        response = client.post('/api/v1/auth/login', json={'username': username, 'password': wrong})
        assert response.status_code == 401
        errors.append(response.json()['error'])
    assert errors[0] == errors[1]
    token = sign_in(client, password)
    client.cookies.set('session', token)
    assert client.get('/api/v1/auth/me').status_code == 401
    response = client.get('/api/v1/auth/me', headers=headers(wrong))
    assert response.status_code == 401 and response.headers['www-authenticate'] == 'Bearer'


def test_query_identity_and_duplicate_credentials_are_not_accepted(system):
    _, client, _, password, _, _ = system
    token = sign_in(client, password)
    assert client.get('/api/v1/auth/me?user_id=someone-else', headers=headers(token)).status_code == 400
    assert client.get('/api/v1/auth/me', headers=[('Authorization', 'Bearer ' + token), ('Authorization', 'Bearer ' + token)]).status_code == 401


def test_validation_never_echoes_password_and_no_public_bootstrap(system):
    _, client, _, password, _, _ = system
    response = client.post('/api/v1/auth/login', json={'username': [], 'password': password, 'extra': password})
    assert response.status_code == 422
    safe = password not in response.text
    assert safe, 'Validation responses must be redacted'
    for path in ('/api/v1/register', '/api/v1/bootstrap', '/api/v1/auth/csrf', '/api/v1/poc/bearer-probes'):
        assert client.post(path, json={}).status_code in (404, 405)


def test_chunked_oversized_login_is_rejected_without_reflection(system):
    _, client, _, _, _, _ = system
    def oversized():
        yield b'x' * 3000
        yield b'x' * 3000
    response = client.post('/api/v1/auth/login', content=oversized(), headers={'Content-Type': 'application/json'})
    assert response.status_code == 413


def test_origin_rejection_is_403_not_authentication_success(system):
    _, client, _, password, _, _ = system
    response = client.post('/api/v1/auth/login', headers={'Origin': 'https://untrusted.invalid'},
                           json={'username': 'initial-admin', 'password': password})
    assert response.status_code == 403 and response.json()['error']['code'] == 'AUTHORIZATION_DENIED'
    assert client.get('/api/v1/auth/me').status_code == 401


def test_last_seen_five_minute_throttle_and_fixed_expiry(system):
    app, client, clock, password, _, _ = system
    token = sign_in(client, password)
    def record():
        with app.state.database.transaction() as session:
            return dict(session.execute(select(auth_sessions)).mappings().one())
    initial = record()
    assert utc(initial['expires_at']) - utc(initial['created_at']) == timedelta(days=30)
    clock.advance(minutes=4)
    assert client.get('/api/v1/auth/me', headers=headers(token)).status_code == 200
    assert record()['last_seen_at'] is None
    clock.advance(minutes=1)
    assert client.get('/api/v1/auth/me', headers=headers(token)).status_code == 200
    first_touch = record()['last_seen_at']
    clock.advance(minutes=4)
    client.get('/api/v1/auth/me', headers=headers(token))
    assert record()['last_seen_at'] == first_touch
    clock.advance(minutes=1)
    client.get('/api/v1/auth/me', headers=headers(token))
    assert utc(record()['last_seen_at']) == clock()
    assert record()['expires_at'] == initial['expires_at']


def test_null_last_seen_expires_at_24_hour_boundary(system):
    _, client, clock, password, _, _ = system
    token = sign_in(client, password)
    clock.advance(hours=24)
    assert client.get('/api/v1/auth/me', headers=headers(token)).status_code == 401


def test_absolute_thirty_day_boundary_even_with_recent_activity(system):
    app, client, clock, password, _, _ = system
    token = sign_in(client, password)
    clock.advance(days=30)
    with app.state.database.transaction(write=True) as session:
        session.execute(update(auth_sessions).values(last_seen_at=clock() - timedelta(seconds=1)))
    assert client.get('/api/v1/auth/me', headers=headers(token)).status_code == 401


def test_sixth_login_revokes_oldest_effective_session(system):
    _, client, clock, password, _, _ = system
    tokens = []
    for _ in range(6):
        tokens.append(sign_in(client, password))
        clock.advance(seconds=1)
    assert client.get('/api/v1/auth/me', headers=headers(tokens[0])).status_code == 401
    assert all(client.get('/api/v1/auth/me', headers=headers(value)).status_code == 200 for value in tokens[1:])


def test_concurrent_logins_never_exceed_five(system):
    app, client, clock, password, _, _ = system
    for _ in range(5):
        sign_in(client, password)
        clock.advance(seconds=1)
    def login(_):
        return app.state.auth.login('initial-admin', password, 'isolated-test-peer', str(uuid4()))['token_type']
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(login, range(2))) == ['Bearer', 'Bearer']
    with app.state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(auth_sessions).where(auth_sessions.c.revoked_at.is_(None))).scalar_one() == 5


def test_password_reset_revokes_all_old_sessions(system):
    app, client, clock, password, _, _ = system
    old = [sign_in(client, password) for _ in range(2)]
    replacement = secrets.token_urlsafe(24)
    clock.advance(seconds=1)
    app.state.auth.reset_password('initial-admin', replacement)
    assert all(client.get('/api/v1/auth/me', headers=headers(value)).status_code == 401 for value in old)
    assert client.post('/api/v1/auth/login', json={'username': 'initial-admin', 'password': password}).status_code == 401
    assert client.get('/api/v1/auth/me', headers=headers(sign_in(client, replacement))).status_code == 200


def test_disable_and_role_changes_use_current_server_state(system):
    app, client, clock, password, user_id, _ = system
    token = sign_in(client, password)
    with app.state.database.transaction(write=True) as session:
        session.execute(update(role_assignments).where(role_assignments.c.user_id == user_id).values(revoked_at=clock()))
    assert client.get('/api/v1/auth/me', headers=headers(token)).json()['data']['roles'] == []
    with app.state.database.transaction(write=True) as session:
        session.execute(update(users).where(users.c.id == user_id).values(status='DISABLED'))
    assert client.get('/api/v1/auth/me', headers=headers(token)).status_code == 401


def test_login_rate_limit_and_failure_audit(system):
    app, client, _, _, _, _ = system
    wrong = secrets.token_urlsafe(20)
    statuses = [client.post('/api/v1/auth/login', json={'username': 'initial-admin', 'password': wrong}).status_code for _ in range(11)]
    assert statuses[:10] == [401] * 10 and statuses[10] == 429
    with app.state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(audit_events).where(audit_events.c.outcome == 'FAILURE')).scalar_one() == 11


def test_bootstrap_cannot_be_replayed_and_audit_is_immutable(system):
    app, _, _, _, _, _ = system
    with pytest.raises(AuthError) as error:
        app.state.auth.bootstrap_admin('another-admin', secrets.token_urlsafe(24))
    assert error.value.status == 409
    with app.state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(audit_events).where(audit_events.c.action_code == 'system.bootstrap.complete')).scalar_one() == 1
    with pytest.raises(IntegrityError):
        with app.state.database.transaction(write=True) as session:
            session.execute(update(audit_events).values(outcome='CHANGED'))


def test_initial_success_index_rejects_duplicate_but_allows_failure_history(system):
    app, _, clock, _, user_id, _ = system
    with pytest.raises(IntegrityError):
        with app.state.database.transaction(write=True) as session:
            auth_module.audit(session, clock(), 'system.bootstrap.complete', 'SUCCESS', user_id, str(uuid4()), user_id)
    with app.state.database.transaction(write=True) as session:
        auth_module.audit(session, clock(), 'system.bootstrap.complete', 'FAILURE', user_id, str(uuid4()), user_id)


def test_migration_idempotence_fk_closure_and_wal(system):
    app, _, _, _, _, settings = system
    migrate(settings)
    with app.state.database.transaction() as session:
        assert session.connection().exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert session.connection().exec_driver_sql('PRAGMA journal_mode').scalar_one() == 'wal'
        assert session.connection().exec_driver_sql('PRAGMA foreign_key_check').all() == []
    from backend.migrations.schema_v1 import build_metadata
    assert len(build_metadata().tables) == 13  # Frozen enterprise identity baseline remains unchanged.
    assert set(metadata.tables) - set(build_metadata().tables) == {
        'course_manager_departments', 'course_attendance_rules', 'course_attendance',
        'course_leaves', 'course_salaries', 'course_salary_history'}
    assert all(fk.column.table.name in metadata.tables for table in metadata.tables.values() for fk in table.foreign_keys)


def test_success_audit_failure_rolls_back_login(system, monkeypatch):
    app, _, _, password, _, _ = system
    def fail(*_args, **_kwargs):
        raise RuntimeError('controlled audit failure')
    monkeypatch.setattr(auth_module, 'audit', fail)
    with pytest.raises(RuntimeError):
        app.state.auth.login('initial-admin', password, 'isolated-test-peer', str(uuid4()))
    with app.state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(auth_sessions)).scalar_one() == 0
