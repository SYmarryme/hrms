import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, insert, select, update

import backend.auth as auth_module
from backend.auth import AuthError
from backend.models import audit_events, metadata, role_assignments, roles, users
from test_departments import employee_fixture


def provision(system, **overrides):
    app, _, clock, password, _, _ = system
    employee, _ = employee_fixture(app, clock)
    values = {'operator_username': 'initial-admin', 'operator_password': password, 'username': 'independent-hr',
              'password': secrets.token_urlsafe(24), 'employee_id': employee, **overrides}
    return app.state.auth.provision_first_hr(**values)


def test_first_hr_is_distinct_bound_attributed_and_once(system):
    app, _, _, _, admin_id, _ = system
    hr_id = provision(system)
    with app.state.database.transaction() as session:
        account = session.execute(select(users).where(users.c.id == hr_id)).mappings().one()
        grant = session.execute(select(role_assignments).where(role_assignments.c.user_id == hr_id)).mappings().one()
        assert account['employee_id'] is not None and hr_id != admin_id
        assert grant['assigned_by'] == admin_id and grant['bootstrap_origin'] is False
        assert session.execute(select(func.count()).select_from(audit_events).where(audit_events.c.action_code == 'identity.hr.initialize', audit_events.c.outcome == 'SUCCESS')).scalar_one() == 1
    with pytest.raises(AuthError) as error:
        app.state.auth.provision_first_hr('initial-admin', system[3], 'another-hr', secrets.token_urlsafe(24), account['employee_id'])
    assert error.value.status == 409


def test_wrong_admin_credentials_do_not_create_hr(system):
    with pytest.raises(AuthError) as error:
        provision(system, operator_password=secrets.token_urlsafe(24))
    assert error.value.status == 401
    with system[0].state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(users)).scalar_one() == 1


def test_admin_cannot_give_itself_hr(system):
    with pytest.raises(AuthError) as error:
        provision(system, username='initial-admin')
    assert error.value.status == 409


def test_pre_hire_is_not_valid_hr_employment(system):
    app, _, clock, password, _, _ = system
    employee, _ = employee_fixture(app, clock)
    with app.state.database.transaction(write=True) as session:
        session.execute(update(metadata.tables['employees']).where(metadata.tables['employees'].c.id == employee).values(employment_status='PRE_HIRE'))
    with pytest.raises(AuthError) as error:
        app.state.auth.provision_first_hr('initial-admin', password, 'independent-hr', secrets.token_urlsafe(24), employee)
    assert error.value.status == 409


def test_first_hr_audit_failure_rolls_back_identity_and_role(system, monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError('controlled audit failure')
    monkeypatch.setattr(auth_module, 'audit', fail)
    with pytest.raises(RuntimeError):
        provision(system)
    with system[0].state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(users)).scalar_one() == 1


def test_concurrent_hr_initialization_has_one_winner(system):
    app, _, clock, password, _, _ = system
    employee, _ = employee_fixture(app, clock)
    def attempt(number):
        try:
            app.state.auth.provision_first_hr('initial-admin', password, 'hr-' + str(number), secrets.token_urlsafe(24), employee)
            return True
        except AuthError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [False, True]


def test_missing_employment_does_not_create_fake_employee(system):
    from uuid import uuid4
    app, _, _, password, _, _ = system
    with pytest.raises(AuthError) as error:
        app.state.auth.provision_first_hr('initial-admin', password, 'independent-hr', secrets.token_urlsafe(24), str(uuid4()))
    assert error.value.code == 'HR_EMPLOYMENT_PREREQUISITE'
    with app.state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(users)).scalar_one() == 1
        assert session.execute(select(func.count()).select_from(metadata.tables['employees'])).scalar_one() == 0
