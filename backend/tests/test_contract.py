import secrets
import sqlite3
from sqlalchemy import func, select, update

from backend.models import auth_sessions
from backend.settings import Settings
from conftest import sign_in


def test_public_origin_is_canonical_and_http_public_is_rejected(tmp_path):
    assert Settings(tmp_path / 'a.db', 'https://EXAMPLE.invalid:443/').public_origin == 'https://example.invalid'
    import pytest
    with pytest.raises(ValueError):
        Settings(tmp_path / 'a.db', 'http://example.invalid')


def test_expired_sessions_do_not_consume_five_effective_slots(system):
    app, client, clock, password, _, _ = system
    for _ in range(5):
        sign_in(client, password)
        clock.advance(seconds=1)
    clock.advance(hours=24)
    current = sign_in(client, password)
    assert client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + current}).status_code == 200
    # Issuing one fresh session should not evict already-idle rows as if still effective.
    with app.state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(auth_sessions)).scalar_one() == 6
        assert session.execute(select(func.count()).select_from(auth_sessions).where(auth_sessions.c.revoked_at.is_not(None))).scalar_one() == 0


def test_migration_refuses_to_adopt_existing_unversioned_data(tmp_path):
    import pytest
    from conftest import migrate
    path = tmp_path / 'existing.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE existing_content(id INTEGER PRIMARY KEY)')
        connection.execute('INSERT INTO existing_content VALUES(7)')
    with pytest.raises(RuntimeError):
        migrate(Settings(path, 'https://hrms.test'))
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT id FROM existing_content').fetchall() == [(7,)]


def test_partial_versioned_database_is_rejected_at_migration_and_startup(tmp_path):
    import pytest
    from conftest import migrate
    from backend.database import Database
    settings = Settings(tmp_path / 'partial.db', 'https://hrms.test')
    migrate(settings)
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute('DROP TABLE auth_sessions')
    with pytest.raises(RuntimeError):
        migrate(settings)
    database = Database(settings.database_path)
    try:
        with pytest.raises(RuntimeError):
            database.check_revision()
    finally:
        database.engine.dispose()
