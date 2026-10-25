"""Stateful opaque Bearer sessions; no dependency on the synthetic PoC."""
import hashlib
import secrets
from collections import deque
from datetime import datetime, timedelta, timezone
from threading import BoundedSemaphore, Lock
from uuid import uuid4

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import and_, func, insert, select, update

from backend.models import audit_events, auth_sessions, metadata, role_assignments, roles, users

ABSOLUTE = timedelta(days=30)
IDLE = timedelta(hours=24)
TOUCH_INTERVAL = timedelta(minutes=5)
MAX_SESSIONS = 5


class AuthError(Exception):
    def __init__(self, status=401, code='AUTHENTICATION_REQUIRED', message='身份认证失败或会话已失效'):
        self.status, self.code, self.message = status, code, message


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def stamp(value):
    return utc(value).isoformat().replace('+00:00', 'Z')


def audit(session, now, action, outcome, resource_id, request_id, actor=None, reason=None, details=None, resource_type='identity'):
    session.execute(insert(audit_events).values(id=str(uuid4()), occurred_at=now, actor_user_id=actor,
        action_code=action, resource_type=resource_type, resource_id=resource_id, outcome=outcome,
        request_id=request_id, reason_code=reason, metadata_redacted=details or {}))


class LoginLimiter:
    """Single-process, bounded account AND socket-peer attempt windows."""
    def __init__(self):
        self.entries = {}
        self.lock = Lock()

    def admit(self, username, peer, now):
        at = now.timestamp()
        with self.lock:
            for key in list(self.entries):
                queue = self.entries[key]
                while queue and queue[0] <= at - 60:
                    queue.popleft()
                if not queue:
                    del self.entries[key]
            keys = [('account:' + hashlib.sha256(username.encode()).hexdigest(), 10),
                    ('peer:' + hashlib.sha256(peer.encode()).hexdigest(), 60)]
            if len(self.entries) >= 4096 or any(len(self.entries.get(key, ())) >= limit for key, limit in keys):
                return False
            for key, _ in keys:
                self.entries.setdefault(key, deque()).append(at)
            return True


class AuthService:
    def __init__(self, database, clock=None):
        self.database = database
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.hasher = PasswordHasher(type=Type.ID)
        self.password_slots = BoundedSemaphore(2)
        self.dummy_hash = self.hasher.hash(secrets.token_urlsafe(32))
        self.limiter = LoginLimiter()

    def now(self):
        return utc(self.clock())

    def hash_password(self, password):
        if not 12 <= len(password) <= 128:
            raise AuthError(422, 'VALIDATION_ERROR', '新密码长度必须为12到128个字符')
        with self.password_slots:
            return self.hasher.hash(password)

    def failed_login(self, now, request_id, reason='INVALID_LOGIN'):
        # Independent from a successful business transaction; never log submitted identity/password.
        with self.database.transaction(write=True) as session:
            audit(session, now, 'auth.login', 'FAILURE', request_id, request_id, reason=reason)

    def login(self, username, password, peer, request_id):
        now = self.now()
        if not self.limiter.admit(username, peer, now):
            self.failed_login(now, request_id, 'RATE_LIMITED')
            raise AuthError(429, 'RATE_LIMITED', '尝试过于频繁，请稍后重试')
        with self.database.transaction() as session:
            row = session.execute(select(users).where(users.c.username == username)).mappings().first()
        with self.password_slots:
            try:
                valid = self.hasher.verify(row['password_hash'] if row else self.dummy_hash, password)
            except (VerificationError, InvalidHashError):
                valid = False
        if not row or not valid or row['status'] != 'ACTIVE':
            self.failed_login(now, request_id)
            raise AuthError()
        # Verify again under the write lock so a reset/disable cannot race credential issuance.
        denied = False
        raw = secrets.token_urlsafe(32)
        expires = now + ABSOLUTE
        with self.database.transaction(write=True) as session:
            now = self.now()
            expires = now + ABSOLUTE
            current = session.execute(select(users).where(users.c.id == row['id'])).mappings().first()
            if (not current or current['status'] != 'ACTIVE' or current['password_hash'] != row['password_hash']
                    or self.employee_terminated(session, current['employee_id'])):
                denied = True
                audit(session, now, 'auth.login', 'FAILURE', request_id, request_id, reason='INVALID_LOGIN')
            else:
                active = session.execute(select(auth_sessions.c.id).where(
                    auth_sessions.c.user_id == row['id'], auth_sessions.c.revoked_at.is_(None),
                    auth_sessions.c.expires_at > now,
                    func.coalesce(auth_sessions.c.last_seen_at, auth_sessions.c.created_at) > now - IDLE
                ).order_by(auth_sessions.c.created_at, auth_sessions.c.id)).scalars().all()
                if len(active) >= MAX_SESSIONS:
                    session.execute(update(auth_sessions).where(auth_sessions.c.id.in_(active[:len(active) - MAX_SESSIONS + 1]))
                                    .values(revoked_at=now))
                session_id = str(uuid4())
                session.execute(insert(auth_sessions).values(id=session_id, user_id=row['id'],
                    token_hash=hashlib.sha256(raw.encode()).hexdigest(), created_at=now, expires_at=expires,
                    revoked_at=None, last_seen_at=None, user_agent_digest=None))
                audit(session, now, 'auth.login', 'SUCCESS', session_id, request_id, row['id'])
        if denied:
            raise AuthError()
        return {'access_token': raw, 'token_type': 'Bearer', 'expires_at': stamp(expires)}

    @staticmethod
    def employee_terminated(session, employee_id):
        if employee_id is None:
            return False
        employees = metadata.tables['employees']
        return session.execute(select(employees.c.employment_status).where(employees.c.id == employee_id)).scalar_one() == 'TERMINATED'

    @staticmethod
    def effective_employment(session, employee_id, now):
        if employee_id is None:
            return False
        employees, departments, positions, assignments = (metadata.tables[name] for name in
            ('employees', 'departments', 'positions', 'employee_assignments'))
        employee = session.execute(select(employees).where(employees.c.id == employee_id)).mappings().first()
        if (not employee or employee['employment_status'] not in ('PROBATION', 'ACTIVE', 'EXIT_PROCESSING')
                or employee['hire_date'] is None or employee['hire_date'] > now.date()
                or (employee['termination_date'] is not None and employee['termination_date'] <= now.date())
                or not employee['current_department_id'] or not employee['current_position_id']):
            return False
        position = session.execute(select(positions.c.id).join(departments, departments.c.id == positions.c.department_id).where(
            positions.c.id == employee['current_position_id'], positions.c.department_id == employee['current_department_id'],
            positions.c.status == 'ACTIVE', departments.c.status == 'ACTIVE')).first()
        current = session.execute(select(assignments).where(assignments.c.employee_id == employee_id,
            assignments.c.valid_from <= now.date(),
            (assignments.c.valid_to.is_(None) | (assignments.c.valid_to >= now.date())))).mappings().all()
        return bool(position and len(current) == 1 and current[0]['department_id'] == employee['current_department_id']
                    and current[0]['position_id'] == employee['current_position_id'])

    def resolve(self, session, raw, now, touch=True):
        row = session.execute(select(auth_sessions).where(
            auth_sessions.c.token_hash == hashlib.sha256(raw.encode()).hexdigest())).mappings().first()
        if not row or row['revoked_at'] is not None:
            return None
        last = utc(row['last_seen_at'] or row['created_at'])
        if now >= utc(row['expires_at']) or now >= last + IDLE:
            session.execute(update(auth_sessions).where(auth_sessions.c.id == row['id']).values(revoked_at=now))
            return None
        user = session.execute(select(users).where(users.c.id == row['user_id'])).mappings().one()
        if (user['status'] != 'ACTIVE' or self.employee_terminated(session, user['employee_id'])
                or (user['password_changed_at'] and utc(user['password_changed_at']) > utc(row['created_at']))):
            session.execute(update(auth_sessions).where(auth_sessions.c.user_id == user['id'], auth_sessions.c.revoked_at.is_(None))
                            .values(revoked_at=now))
            return None
        if touch and now - last >= TOUCH_INTERVAL:
            session.execute(update(auth_sessions).where(auth_sessions.c.id == row['id']).values(last_seen_at=now))
        current_roles = session.execute(select(roles.c.code).join(role_assignments, role_assignments.c.role_id == roles.c.id)
            .where(role_assignments.c.user_id == user['id'], role_assignments.c.revoked_at.is_(None),
                   role_assignments.c.valid_from_at <= now,
                   (role_assignments.c.valid_to_at.is_(None) | (role_assignments.c.valid_to_at > now)))
            .order_by(roles.c.code)).scalars().all()
        return {'id': user['id'], 'username': user['username'], 'status': user['status'],
                'employee_id': user['employee_id'], 'roles': sorted(set(current_roles)),
                'session': {'id': row['id'], 'created_at': stamp(row['created_at']), 'expires_at': stamp(row['expires_at'])}}

    def me(self, raw):
        with self.database.transaction(write=True) as session:
            principal = self.resolve(session, raw, self.now())
        if principal is None:
            raise AuthError()
        return principal

    def logout(self, raw, request_id):
        with self.database.transaction(write=True) as session:
            now = self.now()
            principal = self.resolve(session, raw, now, touch=False)
            if principal is not None:
                session.execute(update(auth_sessions).where(auth_sessions.c.id == principal['session']['id']).values(revoked_at=now))
                audit(session, now, 'auth.logout', 'SUCCESS', principal['session']['id'], request_id, principal['id'])
        if principal is None:
            raise AuthError()

    def bootstrap_admin(self, username, password):
        digest, user_id = self.hash_password(password), str(uuid4())
        if not username or username != username.strip() or len(username) > 64:
            raise AuthError(422, 'VALIDATION_ERROR', '账号不能为空、超长或包含首尾空白')
        with self.database.transaction(write=True) as session:
            now = self.now()
            if (session.execute(select(func.count()).select_from(users)).scalar_one()
                    or session.execute(select(audit_events.c.id).where(audit_events.c.action_code == 'system.bootstrap.complete',
                                                                      audit_events.c.outcome == 'SUCCESS')).first()):
                raise AuthError(409, 'STATE_CONFLICT', '身份数据或初始化成功标记已存在；拒绝重新初始化')
            session.execute(insert(users).values(id=user_id, username=username, password_hash=digest,
                employee_id=None, status='ACTIVE', password_changed_at=now, version_no=1, created_at=now, updated_at=now))
            admin_role = session.execute(select(roles.c.id).where(roles.c.code == 'ADMIN')).scalar_one()
            session.execute(insert(role_assignments).values(id=str(uuid4()), user_id=user_id, role_id=admin_role,
                valid_from_at=now, valid_to_at=None, assigned_by=None, revoked_at=None, reason='Initial controlled identity bootstrap',
                bootstrap_origin=True, created_at=now, updated_at=now))
            audit(session, now, 'system.bootstrap.complete', 'SUCCESS', user_id, str(uuid4()), user_id)
        return user_id

    def reset_password(self, username, password):
        digest = self.hash_password(password)
        with self.database.transaction(write=True) as session:
            now = self.now()
            user = session.execute(select(users).where(users.c.username == username)).mappings().first()
            if user is None:
                raise AuthError(404, 'NOT_FOUND', '账号不存在')
            session.execute(update(users).where(users.c.id == user['id']).values(password_hash=digest,
                password_changed_at=now, version_no=users.c.version_no + 1, updated_at=now))
            session.execute(update(auth_sessions).where(auth_sessions.c.user_id == user['id'], auth_sessions.c.revoked_at.is_(None))
                            .values(revoked_at=now))
            audit(session, now, 'auth.password.reset', 'SUCCESS', user['id'], str(uuid4()), reason='CONTROLLED_LOCAL_CLI')

    def provision_first_hr(self, operator_username, operator_password, username, password, employee_id):
        try:
            return self._provision_first_hr(operator_username, operator_password, username, password, employee_id)
        except AuthError as error:
            if error.status != 401:  # Bad passwords already have an independent login failure audit.
                request_id = str(uuid4())
                with self.database.transaction(write=True) as session:
                    audit(session, self.now(), 'identity.hr.initialize', 'FAILURE', request_id, request_id,
                          reason=error.code, details={'source': 'CONTROLLED_FIRST_HR_CLI'})
            raise

    def _provision_first_hr(self, operator_username, operator_password, username, password, employee_id):
        """Ordinary attributed identity.role.assign, never replay the ADMIN bootstrap."""
        request_id = str(uuid4())
        if not self.limiter.admit(operator_username, 'controlled-first-hr-cli', self.now()):
            raise AuthError(429, 'RATE_LIMITED', '尝试过于频繁，请稍后重试')
        with self.database.transaction() as session:
            operator = session.execute(select(users).where(users.c.username == operator_username)).mappings().first()
        with self.password_slots:
            try:
                verified = self.hasher.verify(operator['password_hash'] if operator else self.dummy_hash, operator_password)
            except (VerificationError, InvalidHashError):
                verified = False
        if not operator or not verified:
            self.failed_login(self.now(), request_id, 'FIRST_HR_OPERATOR_AUTHENTICATION_FAILED')
            raise AuthError()
        if not username or username != username.strip() or len(username) > 64:
            raise AuthError(422, 'VALIDATION_ERROR', '独立HR账号不能为空、超长或包含首尾空白')
        digest = self.hash_password(password)
        user_id = str(uuid4())
        with self.database.transaction(write=True) as session:
            now = self.now()
            current = session.execute(select(users).where(users.c.id == operator['id'])).mappings().one()
            admin = session.execute(select(role_assignments.c.id).join(roles, roles.c.id == role_assignments.c.role_id).where(
                role_assignments.c.user_id == current['id'], roles.c.code == 'ADMIN', role_assignments.c.revoked_at.is_(None),
                role_assignments.c.valid_from_at <= now,
                (role_assignments.c.valid_to_at.is_(None) | (role_assignments.c.valid_to_at > now)))).first()
            if (current['password_hash'] != operator['password_hash'] or current['status'] != 'ACTIVE' or not admin
                    or self.employee_terminated(session, current['employee_id'])):
                raise AuthError(403, 'AUTHORIZATION_DENIED', '操作者当前不具备有效的ADMIN身份')
            hr_role = session.execute(select(roles.c.id).where(roles.c.code == 'HR')).scalar_one()
            if (session.execute(select(role_assignments.c.id).where(role_assignments.c.role_id == hr_role)).first()
                    or session.execute(select(audit_events.c.id).where(audit_events.c.action_code == 'identity.hr.initialize',
                                                                      audit_events.c.outcome == 'SUCCESS')).first()):
                raise AuthError(409, 'STATE_CONFLICT', '首次HR授予历史已存在，不能重复初始化或用于失权恢复')
            if session.execute(select(users.c.id).where(users.c.username == username)).first():
                raise AuthError(409, 'DUPLICATE_RESOURCE', '必须使用全新独立账号，不能给现有账号追加HR')
            if current['employee_id'] == employee_id or not self.effective_employment(session, employee_id, now):
                raise AuthError(409, 'HR_EMPLOYMENT_PREREQUISITE', '缺少可核验的独立在职员工及当前部门岗位；不能伪造入职生效事实')
            if session.execute(select(users.c.id).where(users.c.employee_id == employee_id)).first():
                raise AuthError(409, 'STATE_CONFLICT', '该员工已有账号，首次CLI不改写已有身份')
            session.execute(insert(users).values(id=user_id, username=username, password_hash=digest, employee_id=employee_id,
                status='ACTIVE', password_changed_at=now, version_no=1, created_at=now, updated_at=now))
            grant_id = str(uuid4())
            session.execute(insert(role_assignments).values(id=grant_id, user_id=user_id, role_id=hr_role, valid_from_at=now,
                valid_to_at=None, assigned_by=current['id'], revoked_at=None, reason='Controlled first HR assignment by authenticated ADMIN',
                bootstrap_origin=False, created_at=now, updated_at=now))
            audit(session, now, 'identity.role.assign', 'SUCCESS', grant_id, request_id, current['id'])
            audit(session, now, 'identity.hr.initialize', 'SUCCESS', user_id, request_id, current['id'],
                  details={'source': 'CONTROLLED_FIRST_HR_CLI', 'employee_bound': True})
        return user_id
