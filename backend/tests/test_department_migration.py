from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select, text
from sqlalchemy.exc import IntegrityError

from backend.auth import AuthService
from backend.database import Database
from backend.models import audit_events, metadata, users
from backend.settings import Settings
from conftest import ROOT


def test_incremental_upgrade_preserves_existing_admin_and_audit(tmp_path):
    import secrets
    settings = Settings(tmp_path / 'upgrade.sqlite3', 'https://hrms.test')
    config = Config(str(ROOT / 'backend/alembic.ini'))
    config.attributes['settings'] = settings
    command.upgrade(config, 'identity_0001')
    database = Database(settings.database_path)
    # Seed the historical schema through its immutable definition, not current auth code.
    from backend.migrations.schema_v1 import build_metadata
    from datetime import datetime, timezone
    from backend.auth import audit
    old_users = build_metadata().tables['users']
    account = str(uuid4()); now = datetime.now(timezone.utc)
    digest = AuthService(database).hash_password(secrets.token_urlsafe(24))
    with database.transaction(write=True) as session:
        session.execute(insert(old_users).values(id=account, username='existing-admin', password_hash=digest,
            employee_id=None, status='ACTIVE', password_changed_at=now, version_no=1, created_at=now, updated_at=now))
        audit(session, now, 'system.bootstrap.complete', 'SUCCESS', account, str(uuid4()), account)
        original = dict(session.execute(select(old_users).where(old_users.c.id == account)).mappings().one())
        original_audit = dict(session.execute(select(audit_events)).mappings().one())
    command.upgrade(config, 'head')
    database.check_revision()
    with database.transaction() as session:
        current = dict(session.execute(select(users).where(users.c.id == account)).mappings().one())
        preserved = {key: current[key] for key in original} == original
        assert current['must_change_password'] is False
        assert preserved, 'Existing identity data must be preserved'
        assert dict(session.execute(select(audit_events)).mappings().one()) == original_audit
    database.engine.dispose()


def test_unknown_old_department_status_aborts_upgrade(tmp_path):
    from datetime import datetime, timezone
    settings = Settings(tmp_path / 'invalid-status.sqlite3', 'https://hrms.test')
    config = Config(str(ROOT / 'backend/alembic.ini'))
    config.attributes['settings'] = settings
    command.upgrade(config, 'identity_0001')
    database = Database(settings.database_path)
    now = datetime.now(timezone.utc)
    with database.transaction(write=True) as session:
        session.execute(insert(metadata.tables['departments']).values(id=str(uuid4()), code='LEGACY', name='Synthetic',
            status='UNKNOWN', version_no=1, created_at=now, updated_at=now))
    with pytest.raises(RuntimeError):
        command.upgrade(config, 'head')
    with database.transaction() as session:
        assert session.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == 'identity_0001'
    database.engine.dispose()


def test_database_guards_department_status_and_first_hr_marker(system):
    app, _, clock, _, user_id, _ = system
    from backend.auth import audit
    with pytest.raises(IntegrityError):
        with app.state.database.transaction(write=True) as session:
            session.execute(insert(metadata.tables['departments']).values(id=str(uuid4()), code='BAD', name='Synthetic',
                status='UNKNOWN', version_no=1, created_at=clock(), updated_at=clock()))
    with app.state.database.transaction(write=True) as session:
        audit(session, clock(), 'identity.hr.initialize', 'SUCCESS', user_id, str(uuid4()), user_id)
    with pytest.raises(IntegrityError):
        with app.state.database.transaction(write=True) as session:
            audit(session, clock(), 'identity.hr.initialize', 'SUCCESS', user_id, str(uuid4()), user_id)
