"""Explicit fictional fixtures in a NEW dedicated course database; no auth bypass."""
import argparse
import getpass
import json
import re
import sys
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select

from backend.auth import AuthService, audit
from backend.database import Database
from backend.models import metadata, users, roles, role_assignments
from backend.settings import ROOT, Settings

DEMO_ROOT = ROOT / 'var/course-demo'
CLASSIFICATION = 'FICTIONAL_COURSE_FIXTURE'


def demo_path(name, root=DEMO_ROOT):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}', name):
        raise ValueError('演示名称只能为小写字母、数字和连字符，1至40位')
    path = root / name / 'app.sqlite3'
    if path.resolve() != root.resolve() / name / 'app.sqlite3':
        raise ValueError('演示路径存在链接或不明确')
    for part in (root, root / name, path):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('演示目录不允许链接')
    return path.resolve()


def seed_fixture(session, auth, passwords):
    """All fictional identities and employment facts commit together, only on an empty DB."""
    if session.execute(select(users.c.id)).first():
        raise ValueError('数据库已有身份，拒绝重新初始化')
    now = auth.now()
    common = {'created_at': now, 'updated_at': now, 'version_no': 1}
    department_id, position_id = str(uuid4()), str(uuid4())
    session.execute(insert(metadata.tables['departments']).values(id=department_id, code='FIXTURE-DEV',
        name='[虚构课程]研发部', status='ACTIVE', **common))
    session.execute(insert(metadata.tables['positions']).values(id=position_id, department_id=department_id,
        code='FIXTURE-STAFF', name='[虚构课程]职员', grade_code='G1', status='ACTIVE', **common))
    role_ids = dict(session.execute(select(roles.c.code, roles.c.id)).all())
    ids = {role: str(uuid4()) for role in passwords}
    for role in ('admin', 'hr', 'manager', 'employee'):
        employee_id = None
        if role != 'admin':
            employee_id = str(uuid4())
            session.execute(insert(metadata.tables['employees']).values(id=employee_id, employee_no='FIXTURE-' + role.upper(),
                full_name='[虚构课程]' + role, current_department_id=department_id, current_position_id=position_id,
                employment_status='ACTIVE', hire_date=now.date(), **common))
            session.execute(insert(metadata.tables['employee_assignments']).values(id=str(uuid4()), employee_id=employee_id,
                department_id=department_id, position_id=position_id, valid_from=now.date(), created_at=now, updated_at=now))
        session.execute(insert(users).values(id=ids[role], username='fixture-' + role, password_hash=auth.hash_password(passwords[role]),
            employee_id=employee_id, status='ACTIVE', password_changed_at=now, **common))
        session.execute(insert(role_assignments).values(id=str(uuid4()), user_id=ids[role], role_id=role_ids[role.upper()],
            valid_from_at=now, assigned_by=None if role == 'admin' else ids['admin'], bootstrap_origin=role == 'admin',
            reason=CLASSIFICATION, created_at=now, updated_at=now))
        audit(session, now, 'identity.role.assign', 'SUCCESS', ids[role], str(uuid4()), ids['admin'], details={'source': CLASSIFICATION})
    # Course manager scope is an explicit binding, independent of enterprise CEO governance.
    if 'course_manager_departments' in metadata.tables:
        session.execute(insert(metadata.tables['course_manager_departments']).values(user_id=ids['manager'], department_id=department_id))
    audit(session, now, 'system.bootstrap.complete', 'SUCCESS', ids['admin'], str(uuid4()), ids['admin'])
    audit(session, now, 'course.fixture.initialize', 'SUCCESS', ids['admin'], str(uuid4()), ids['admin'], details={'classification': CLASSIFICATION})


def create_demo(settings, passwords, root=DEMO_ROOT, clock=None):
    name = settings.database_path.parent.name
    if settings.database_path != demo_path(name, root=root):
        raise ValueError('只允许在专用演示目录建立新库')
    if set(passwords) != {'admin', 'hr', 'manager', 'employee'} or len(set(passwords.values())) != 4:
        raise ValueError('必须分别提供四个不同密码')
    if any(not 12 <= len(value) <= 128 for value in passwords.values()):
        raise ValueError('密码长度为12至128位')
    # Exclusive directory allocation: a failed/incomplete run is never silently reused.
    settings.database_path.parent.mkdir(parents=True, exist_ok=False, mode=0o700)
    config = Config(str(ROOT / 'backend/alembic.ini'))
    config.attributes['settings'] = settings
    command.upgrade(config, 'head')
    database = Database(settings.database_path)
    try:
        with database.transaction(write=True) as session:
            seed_fixture(session, AuthService(database, clock), passwords)
        manifest = {'classification': CLASSIFICATION, 'name': name, 'database': 'app.sqlite3'}
        with (settings.database_path.parent / 'manifest.json').open('x', encoding='utf-8') as output:
            json.dump(manifest, output)
    finally:
        database.engine.dispose()


def validate_demo(name, root=DEMO_ROOT):
    path = demo_path(name, root)
    manifest = path.parent / 'manifest.json'
    if not path.is_file() or not manifest.is_file() or path.stat().st_nlink != 1:
        raise ValueError('隔离演示库或完成标记不存在')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    if data != {'classification': CLASSIFICATION, 'name': name, 'database': 'app.sqlite3'}:
        raise ValueError('演示标记不匹配')
    db = Database(path)
    try:
        db.check_revision()
        with db.transaction() as session:
            if not session.execute(select(metadata.tables['audit_events'].c.id).where(
                    metadata.tables['audit_events'].c.action_code == 'course.fixture.initialize')).first():
                raise ValueError('缺少虚构数据审计标记')
    finally:
        db.engine.dispose()
    return path


def main():
    parser = argparse.ArgumentParser(description='创建全新虚构课程库；不接触原业务库')
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error('密码必须通过交互终端输入')
    passwords = {}
    for role in ('admin', 'hr', 'manager', 'employee'):
        password = getpass.getpass(f'fixture-{role} 新密码（至少12位）：')
        if password != getpass.getpass('确认密码：'):
            parser.error('两次密码不一致')
        passwords[role] = password
    create_demo(Settings(demo_path(args.name), 'http://127.0.0.1:3000'), passwords)
    print('已创建独立虚构课程库。账号：fixture-admin / fixture-hr / fixture-manager / fixture-employee')
    print('密码未保存到配置或日志；本操作不是正式企业初始化。')


if __name__ == '__main__':
    main()
