import secrets,hashlib
from datetime import datetime,timezone
from uuid import uuid4
import pytest
from alembic import command
from alembic.config import Config
from alembic.operations import Operations
from sqlalchemy import insert,select,text,update
from backend.settings import Settings
from backend.database import Database
from backend.auth import AuthService
from backend.models import users,metadata
from backend.migrations.schema_v1 import build_metadata
from backend.migrations.course_schema import extend
from conftest import ROOT

def old_database(tmp_path):
 settings=Settings(tmp_path/'legacy.sqlite3','https://hrms.test');config=Config(str(ROOT/'backend/alembic.ini'));config.attributes['settings']=settings;command.upgrade(config,'course_0003')
 database=Database(settings.database_path);old=extend(build_metadata());now=datetime.now(timezone.utc);uid=str(uuid4());password=secrets.token_urlsafe(24);digest=AuthService(database).hash_password(password)
 with database.transaction(write=True) as session:
  session.execute(insert(old.tables['users']).values(id=uid,username='legacy-admin',password_hash=digest,employee_id=None,status='ACTIVE',password_changed_at=now,version_no=1,created_at=now,updated_at=now))
  rid=session.execute(select(old.tables['roles'].c.id).where(old.tables['roles'].c.code=='ADMIN')).scalar_one()
  session.execute(insert(old.tables['role_assignments']).values(id=str(uuid4()),user_id=uid,role_id=rid,valid_from_at=now,assigned_by=None,bootstrap_origin=True,reason='SYNTHETIC_MIGRATION_TEST',created_at=now,updated_at=now))
  row=dict(session.execute(select(old.tables['users'])).mappings().one())
 return settings,config,database,uid,password,row

def test_old_course_accounts_preserved_and_not_forced_then_upgrade_is_repeatable(tmp_path):
 settings,config,database,uid,password,before=old_database(tmp_path)
 command.upgrade(config,'head');database.check_revision()
 with database.transaction() as session:
  after=dict(session.execute(select(users).where(users.c.id==uid)).mappings().one());assert {key:after[key] for key in before}==before;assert after['must_change_password'] is False
 login=AuthService(database).login('legacy-admin',password,'test-peer',str(uuid4()));assert login['must_change_password'] is False
 with database.transaction(write=True) as session:session.execute(update(users).where(users.c.id==uid).values(must_change_password=True))
 command.upgrade(config,'head')
 with database.transaction() as session:
  assert session.execute(select(users.c.must_change_password).where(users.c.id==uid)).scalar_one() is True
  assert session.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='password_0004'
 database.engine.dispose()

def test_migration_failure_rolls_back_column_and_revision_without_losing_account(tmp_path,monkeypatch):
 _,config,database,uid,_,before=old_database(tmp_path);original=Operations.add_column
 def fail(self,*args,**kwargs):original(self,*args,**kwargs);raise RuntimeError('injected migration failure')
 with monkeypatch.context() as patch:
  patch.setattr(Operations,'add_column',fail)
  with pytest.raises(RuntimeError):command.upgrade(config,'head')
 with database.transaction() as session:
  assert session.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='course_0003'
  assert 'must_change_password' not in {row[1] for row in session.connection().exec_driver_sql('PRAGMA table_info(users)')}
  original_user=dict(session.execute(text('SELECT * FROM users WHERE id=:id'),{'id':uid}).mappings().one());assert original_user['password_hash']==before['password_hash']
 command.upgrade(config,'head');database.check_revision();database.engine.dispose()

def test_new_application_refuses_unmigrated_revision(tmp_path):
 _,_,database,_,_,_=old_database(tmp_path)
 with pytest.raises(RuntimeError):database.check_revision()
 database.engine.dispose()
