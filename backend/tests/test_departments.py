import secrets
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, update

import backend.departments as department_module
from backend.auth import AuthError
from backend.models import audit_events, metadata, role_assignments, roles, users
from conftest import sign_in


def employee_fixture(app, clock):
    """Synthetic pre-existing employment facts, never production bootstrap data."""
    department_id, position_id, employee_id = (str(uuid4()) for _ in range(3))
    with app.state.database.transaction(write=True) as session:
        common = {'created_at': clock(), 'updated_at': clock(), 'version_no': 1}
        session.execute(insert(metadata.tables['departments']).values(id=department_id, code='HR-BASE', name='Synthetic HR', status='ACTIVE', **common))
        session.execute(insert(metadata.tables['positions']).values(id=position_id, department_id=department_id,
            code='HR-STAFF', name='Synthetic staff', grade_code='G1', status='ACTIVE', **common))
        session.execute(insert(metadata.tables['employees']).values(id=employee_id, employee_no='SYNTHETIC-HR', full_name='Synthetic person',
            current_department_id=department_id, current_position_id=position_id, employment_status='ACTIVE', hire_date=clock().date(), **common))
        session.execute(insert(metadata.tables['employee_assignments']).values(id=str(uuid4()), employee_id=employee_id,
            department_id=department_id, position_id=position_id, valid_from=clock().date(), created_at=clock(), updated_at=clock()))
    return employee_id, department_id


@pytest.fixture
def hr(system):
    app, client, clock, admin_password, _, _ = system
    employee_id, home_department = employee_fixture(app, clock)
    password = secrets.token_urlsafe(24)
    app.state.auth.provision_first_hr('initial-admin', admin_password, 'independent-hr', password, employee_id)
    reply = client.post('/api/v1/auth/login', json={'username': 'independent-hr', 'password': password})
    assert reply.status_code == 200
    return app, client, clock, {'Authorization': 'Bearer ' + reply.json()['data']['access_token']}, home_department


def create(client, headers, code='D01', **extra):
    return client.post('/api/v1/departments', headers=headers, json={'code': code, 'name': 'Synthetic department', **extra})


def test_hr_create_list_detail_edit_and_audit(hr):
    app, client, _, headers, _ = hr
    created = create(client, headers)
    assert created.status_code == 201
    item = created.json()['data']
    detail = client.get('/api/v1/departments/' + item['id'], headers=headers)
    assert detail.status_code == 200 and detail.headers['etag'] == '"v1"'
    changed = client.patch('/api/v1/departments/' + item['id'], headers={**headers, 'If-Match': detail.headers['etag']}, json={'name': 'Renamed'})
    assert changed.status_code == 200 and changed.json()['data']['version_no'] == 2
    assert client.get('/api/v1/departments/' + item['id'], headers=headers).headers['etag'] == '"v2"'
    assert client.get('/api/v1/departments', headers=headers).json()['data']['total'] == 2
    with app.state.database.transaction() as session:
        actions = session.execute(select(audit_events.c.action_code).where(audit_events.c.resource_id == item['id'])).scalars().all()
        assert len(actions) == 2 and set(actions) == {'org.department.create', 'org.department.update'}


def test_missing_identity_and_admin_cannot_write(system):
    _, client, _, password, _, _ = system
    assert create(client, {}).status_code == 401
    assert client.get('/api/v1/departments').status_code == 401
    headers = {'Authorization': 'Bearer ' + sign_in(client, password)}
    assert client.get('/api/v1/departments', headers=headers).status_code == 200
    assert create(client, headers).status_code == 403


@pytest.mark.parametrize('body', [
    {'code': '', 'name': 'Name'}, {'code': 'X', 'name': '   '}, {'code': 12, 'name': 'Name'},
    {'code': 'X', 'name': 'Name', 'status': 'ARCHIVED'}, {'code': 'X', 'name': 'Name', 'version_no': 9},
    {'code': 'X', 'name': 'Name', 'parent_id': 'invalid'}, {'code': 'X', 'name': 'x' * 129},
])
def test_input_validation(hr, body):
    _, client, _, headers, _ = hr
    assert client.post('/api/v1/departments', headers=headers, json=body).status_code == 422


def test_duplicate_search_pagination_and_query_validation(hr):
    _, client, _, headers, _ = hr
    assert create(client, headers, 'MATCH-1', name='Alpha').status_code == 201
    assert create(client, headers, 'MATCH-2', name='Beta').status_code == 201
    assert create(client, headers, 'MATCH-1').status_code == 409
    result = client.get('/api/v1/departments?q=MATCH&page=2&page_size=1', headers=headers).json()['data']
    assert result['total'] == 2 and len(result['items']) == 1 and result['items'][0]['code'] == 'MATCH-2'
    assert client.get('/api/v1/departments?q=Alpha', headers=headers).json()['data']['total'] == 1
    assert client.get('/api/v1/departments?q=%25', headers=headers).json()['data']['total'] == 0
    for query in ('page=0', 'page_size=101', 'sort=sql', 'status=UNKNOWN', 'page=1&page=2'):
        assert client.get('/api/v1/departments?' + query, headers=headers).status_code == 422


def test_etag_missing_stale_and_wrong_resource(hr):
    _, client, _, headers, _ = hr
    item = create(client, headers).json()['data']
    path = '/api/v1/departments/' + item['id']
    assert client.patch(path, headers=headers, json={'name': 'New'}).status_code == 428
    assert client.patch(path, headers={**headers, 'If-Match': 'W/"v1"'}, json={'name': 'New'}).status_code == 412
    assert client.patch(path, headers={**headers, 'If-Match': '"v1"'}, json={'name': 'New'}).status_code == 200
    assert client.patch(path, headers={**headers, 'If-Match': '"v1"'}, json={'name': 'Lost'}).status_code == 412
    assert client.get('/api/v1/departments/' + str(uuid4()), headers=headers).status_code == 404


def test_hierarchy_cycle_inactive_parent_and_state_transitions(hr):
    _, client, _, headers, _ = hr
    root = create(client, headers, 'ROOT').json()['data']
    child = create(client, headers, 'CHILD', parent_id=root['id']).json()['data']
    root_path = '/api/v1/departments/' + root['id']
    assert client.patch(root_path, headers={**headers, 'If-Match': '"v1"'}, json={'parent_id': child['id']}).status_code == 409
    assert client.patch(root_path, headers={**headers, 'If-Match': '"v1"'}, json={'status': 'DISABLED'}).status_code == 409
    child_path = '/api/v1/departments/' + child['id']
    assert client.patch(child_path, headers={**headers, 'If-Match': '"v1"'}, json={'status': 'DISABLED'}).status_code == 200
    assert client.patch(root_path, headers={**headers, 'If-Match': '"v1"'}, json={'status': 'DISABLED'}).status_code == 200
    assert create(client, headers, 'NEW', parent_id=root['id']).status_code == 409
    assert client.patch(child_path, headers={**headers, 'If-Match': '"v2"'}, json={'status': 'ACTIVE'}).status_code == 409
    assert client.patch(root_path, headers={**headers, 'If-Match': '"v2"'}, json={'status': 'ACTIVE'}).status_code == 200


def test_disable_protects_employee_and_counts_without_pii(hr):
    _, client, _, headers, home = hr
    result = client.get('/api/v1/departments/' + home, headers=headers)
    data = client.get('/api/v1/departments?q=HR-BASE', headers=headers).json()['data']['items'][0]
    assert data['direct_employee_count'] == 1 and data['subtree_employee_count'] == 1
    assert 'full_name' not in data and 'employee_ids' not in data
    assert client.patch('/api/v1/departments/' + home, headers={**headers, 'If-Match': result.headers['etag']}, json={'status': 'DISABLED'}).status_code == 409


def test_revoked_hr_role_is_checked_on_each_request(hr):
    app, client, clock, headers, _ = hr
    with app.state.database.transaction(write=True) as session:
        hr_id = session.execute(select(roles.c.id).where(roles.c.code == 'HR')).scalar_one()
        session.execute(update(role_assignments).where(role_assignments.c.role_id == hr_id).values(revoked_at=clock()))
    assert create(client, headers).status_code == 403


def test_concurrent_patch_only_one_wins(hr):
    app, client, _, headers, _ = hr
    item = create(client, headers).json()['data']
    raw = headers['Authorization'].split(' ', 1)[1]
    def change(number):
        try:
            app.state.departments.change(raw, item['id'], {'name': 'Name ' + str(number)}, '"v1"', str(uuid4()))
            return 200
        except AuthError as error:
            return error.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(change, range(2))) == [200, 412]


def test_write_audit_failure_rolls_back_department(hr, monkeypatch):
    app, _, _, headers, _ = hr
    def fail(*_args, **_kwargs):
        raise RuntimeError('controlled audit failure')
    monkeypatch.setattr(department_module, 'audit', fail)
    with pytest.raises(RuntimeError):
        app.state.departments.create(headers['Authorization'].split(' ', 1)[1], {'code': 'ROLLBACK', 'name': 'Name'}, str(uuid4()))
    with app.state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(metadata.tables['departments']).where(metadata.tables['departments'].c.code == 'ROLLBACK')).scalar_one() == 0


def test_no_department_delete_route(hr):
    _, client, _, headers, _ = hr
    item = create(client, headers).json()['data']
    assert client.delete('/api/v1/departments/' + item['id'], headers=headers).status_code == 405


def test_future_authorization_tables_fail_closed_on_disable(hr):
    app, client, _, headers, _ = hr
    item = create(client, headers).json()['data']
    with app.state.database.transaction(write=True) as session:
        session.connection().exec_driver_sql('CREATE TABLE management_grants(id TEXT PRIMARY KEY)')
    assert client.patch('/api/v1/departments/' + item['id'], headers={**headers, 'If-Match': '"v1"'}, json={'status': 'DISABLED'}).status_code == 409


def test_outbox_failure_rolls_back_department_and_success_audit(hr, monkeypatch):
    app, _, _, headers, _ = hr
    def fail(*_args, **_kwargs):
        raise RuntimeError('controlled outbox failure')
    monkeypatch.setattr(app.state.departments, 'enqueue', fail)
    with pytest.raises(RuntimeError):
        app.state.departments.create(headers['Authorization'].split(' ', 1)[1], {'code': 'ROLLBACK', 'name': 'Name'}, str(uuid4()))
    with app.state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(metadata.tables['departments']).where(metadata.tables['departments'].c.code == 'ROLLBACK')).scalar_one() == 0
        assert session.execute(select(func.count()).select_from(audit_events).where(audit_events.c.action_code == 'org.department.create', audit_events.c.outcome == 'SUCCESS')).scalar_one() == 0


def test_strong_detail_etag_excludes_mutable_parent_name_and_counts(hr):
    _, client, _, headers, _ = hr
    root = create(client, headers, 'ROOT').json()['data']
    child = create(client, headers, 'CHILD', parent_id=root['id']).json()['data']
    path = '/api/v1/departments/' + child['id']
    before = client.get(path, headers=headers)
    assert client.patch('/api/v1/departments/' + root['id'], headers={**headers, 'If-Match': '"v1"'}, json={'name': 'Parent renamed'}).status_code == 200
    after = client.get(path, headers=headers)
    assert before.content == after.content and before.headers['etag'] == after.headers['etag']
    assert set(after.json()['data']).isdisjoint({'parent_name', 'direct_employee_count', 'subtree_employee_count'})


def test_known_target_failure_audit_has_department_type_and_id(hr):
    app, client, _, headers, _ = hr
    item = create(client, headers).json()['data']
    assert client.patch('/api/v1/departments/' + item['id'], headers=headers, json={'name': 'Name'}).status_code == 428
    with app.state.database.transaction() as session:
        record = session.execute(select(audit_events).where(audit_events.c.action_code == 'org.department.update',
            audit_events.c.outcome == 'FAILURE')).mappings().one()
        assert record['resource_type'] == 'department' and record['resource_id'] == item['id']


def test_changing_list_headcount_does_not_change_detail_representation(hr):
    app, client, _, headers, home = hr
    path = '/api/v1/departments/' + home
    before = client.get(path, headers=headers)
    employee_id = str(uuid4())
    with app.state.database.transaction(write=True) as session:
        employee = dict(session.execute(select(metadata.tables['employees'])).mappings().one())
        employee.update(id=employee_id, employee_no='SYNTHETIC-SECOND')
        session.execute(insert(metadata.tables['employees']).values(**employee))
        assignment = dict(session.execute(select(metadata.tables['employee_assignments'])).mappings().one())
        assignment.update(id=str(uuid4()), employee_id=employee_id)
        session.execute(insert(metadata.tables['employee_assignments']).values(**assignment))
    assert client.get('/api/v1/departments?q=HR-BASE', headers=headers).json()['data']['items'][0]['direct_employee_count'] == 2
    after = client.get(path, headers=headers)
    assert before.content == after.content and before.headers['etag'] == after.headers['etag']


@pytest.mark.parametrize('invalid_fact', ['expired_assignment', 'disabled_position', 'missing_current_department'])
def test_hr_employment_facts_are_rechecked_for_each_mutation(hr, invalid_fact):
    from datetime import timedelta
    app, client, clock, headers, _ = hr
    with app.state.database.transaction(write=True) as session:
        if invalid_fact == 'expired_assignment':
            session.execute(update(metadata.tables['employee_assignments']).values(valid_from=clock().date() - timedelta(days=2), valid_to=clock().date() - timedelta(days=1)))
        elif invalid_fact == 'disabled_position':
            session.execute(update(metadata.tables['positions']).values(status='DISABLED'))
        else:
            session.execute(update(metadata.tables['employees']).values(current_department_id=None))
    assert create(client, headers).status_code == 403
