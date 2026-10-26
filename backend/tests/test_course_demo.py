"""Only fictional data; all databases are pytest-owned temporary files."""
import secrets
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from backend.app import create_app
from backend.models import metadata, users, audit_events
from backend.settings import Settings


def test_demo_is_new_isolated_and_uses_real_auth(tmp_path):
    from backend.course_demo import create_demo, demo_path
    passwords = {role: secrets.token_urlsafe(24) for role in ('admin', 'hr', 'manager', 'employee')}
    path = demo_path('class-one', root=tmp_path)
    settings = Settings(path, 'https://hrms.test')
    create_demo(settings, passwords, root=tmp_path)
    app = create_app(settings)
    with TestClient(app, base_url=settings.public_origin, headers={'Origin': settings.public_origin}) as client:
        assert client.get('/api/v1/departments').status_code == 401
        for role, password in passwords.items():
            login = client.post('/api/v1/auth/login', json={'username': 'fixture-' + role, 'password': password})
            assert login.status_code == 200
            headers = {'Authorization': 'Bearer ' + login.json()['data']['access_token']}
            profile = client.get('/api/v1/auth/me', headers=headers).json()['data']
            assert profile['roles'] == [role.upper()]
            result = client.post('/api/v1/departments', headers=headers, json={'code': role, 'name': '虚构测试部门'})
            assert result.status_code == (201 if role == 'hr' else 403)
    before = path.read_bytes()
    with pytest.raises((ValueError, FileExistsError)):
        create_demo(settings, passwords, root=tmp_path)
    assert path.read_bytes() == before
    with app.state.database.transaction() as session:
        assert session.execute(select(func.count()).select_from(users)).scalar_one() == 4
        assert session.execute(select(func.count()).select_from(metadata.tables['employee_assignments'])).scalar_one() == 3
        assert session.execute(select(audit_events.c.id).where(audit_events.c.action_code == 'course.fixture.initialize')).first()


def test_demo_refuses_ambiguous_or_business_path(tmp_path):
    from backend.course_demo import create_demo, demo_path
    for name in ('', '..', '../formal', 'one/two', 'C:\\formal'):
        with pytest.raises(ValueError):
            demo_path(name, root=tmp_path)
    with pytest.raises(ValueError):
        create_demo(Settings(tmp_path / 'business.sqlite3', 'https://hrms.test'), {}, root=tmp_path)
