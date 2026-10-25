import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

import backend.auth as auth_module
from backend.auth import AuthError, AuthService
from backend.database import Database
from backend.models import audit_events, role_assignments, users
from backend.settings import Settings
from conftest import migrate


def test_bootstrap_success_audit_failure_rolls_back_all(tmp_path, monkeypatch):
    settings = Settings(tmp_path / 'bootstrap.sqlite3', 'https://hrms.test')
    migrate(settings)
    db, password = Database(settings.database_path), secrets.token_urlsafe(24)
    service = AuthService(db)
    def fail(*_args, **_kwargs):
        raise RuntimeError('controlled audit failure')
    monkeypatch.setattr(auth_module, 'audit', fail)
    with pytest.raises(RuntimeError):
        service.bootstrap_admin('initial-admin', password)
    with db.transaction() as session:
        for table in (users, role_assignments, audit_events):
            assert session.execute(select(func.count()).select_from(table)).scalar_one() == 0
    db.engine.dispose()


def test_two_concurrent_bootstrap_attempts_only_one_succeeds(tmp_path):
    settings = Settings(tmp_path / 'bootstrap.sqlite3', 'https://hrms.test')
    migrate(settings)
    db = Database(settings.database_path)
    service = AuthService(db)
    password = secrets.token_urlsafe(24)
    def attempt(number):
        try:
            service.bootstrap_admin('initial-' + str(number), password)
            return True
        except AuthError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [False, True]
    with db.transaction() as session:
        assert session.execute(select(func.count()).select_from(users)).scalar_one() == 1
        assert session.execute(select(func.count()).select_from(role_assignments)).scalar_one() == 1
    db.engine.dispose()
