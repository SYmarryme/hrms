"""Course MVP operations. All authorization, business writes and audits share one SQLite transaction."""
import calendar
import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator, SecretStr
from sqlalchemy import select, insert, update, delete, func, or_, and_

from backend.auth import AuthError, audit, utc
from backend.models import metadata, users, roles, role_assignments, auth_sessions

T = metadata.tables
EMPLOYED = ('PROBATION', 'ACTIVE', 'EXIT_PROCESSING')
SHANGHAI = ZoneInfo('Asia/Shanghai')


def reject(status=409, message='当前操作不符合业务约束', code='BUSINESS_RULE_CONFLICT'):
    raise AuthError(status, code, message)


def row_by(session, table, item_id):
    row = session.execute(select(table).where(table.c.id == item_id)).mappings().first()
    if not row:
        reject(404, '记录不存在', 'NOT_FOUND')
    return dict(row)


def version(row, if_match):
    if if_match is None:
        reject(428, '请先读取最新详情', 'PRECONDITION_REQUIRED')
    if if_match != f'"v{row["version_no"]}"':
        reject(412, '记录已变化，请重新加载', 'VERSION_MISMATCH')


def changed(session, table, row, values, now):
    result = session.execute(update(table).where(table.c.id == row['id'], table.c.version_no == row['version_no'])
        .values(**values, version_no=row['version_no'] + 1, updated_at=now))
    if result.rowcount != 1:
        reject(412, '记录已变化，请重新加载', 'VERSION_MISMATCH')
    return row_by(session, table, row['id'])


def text(value):
    value = value.strip()
    if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Use meaningful text without controls')
    return value


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PositionInput(Input):
    department_id: UUID
    code: StrictStr = Field(min_length=1, max_length=64)
    name: StrictStr = Field(min_length=1, max_length=128)
    grade_code: StrictStr = Field(min_length=1, max_length=64)
    status: Literal['ACTIVE', 'DISABLED'] = 'ACTIVE'
    _text = field_validator('code', 'name', 'grade_code')(text)


class EmployeeInput(Input):
    employee_no: StrictStr = Field(min_length=1, max_length=64)
    full_name: StrictStr = Field(min_length=1, max_length=128)
    current_department_id: UUID
    current_position_id: UUID
    hire_date: date
    employment_status: Literal['PRE_HIRE', 'PROBATION', 'ACTIVE', 'EXIT_PROCESSING'] = 'ACTIVE'
    _text = field_validator('employee_no', 'full_name')(text)


class TransferInput(Input):
    department_id: UUID
    position_id: UUID


class RuleInput(Input):
    effective_from: date
    weekdays: list[int] = Field(min_length=1, max_length=5)
    start_time: StrictStr
    end_time: StrictStr
    grace_minutes: int = Field(ge=0, le=120, strict=True)

    @model_validator(mode='after')
    def valid(self):
        if len(set(self.weekdays)) != len(self.weekdays) or any(type(x) is not int or x not in range(5) for x in self.weekdays):
            raise ValueError('Only Monday to Friday')
        if not all(re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value) for value in (self.start_time, self.end_time)):
            raise ValueError('Use HH:MM')
        if self.end_time <= self.start_time:
            raise ValueError('Fixed daytime shift required')
        if (datetime.combine(date.min, time.fromisoformat(self.end_time)) - datetime.combine(date.min, time.fromisoformat(self.start_time))).total_seconds() <= self.grace_minutes * 60:
            raise ValueError('Grace must be shorter than shift')
        return self


class LeaveInput(Input):
    start_date: date
    end_date: date
    leave_type: Literal['ANNUAL', 'SICK', 'PERSONAL', 'OTHER']
    reason: StrictStr = Field(min_length=1, max_length=500)
    _text = field_validator('reason')(text)

    @model_validator(mode='after')
    def dates(self):
        if self.end_date < self.start_date or (self.end_date - self.start_date).days > 366:
            raise ValueError('Leave date range invalid')
        return self


class DecisionInput(Input):
    status: Literal['APPROVED', 'REJECTED']
    opinion: StrictStr = Field(min_length=1, max_length=500)
    _text = field_validator('opinion')(text)


class SalaryInput(Input):
    employee_id: UUID
    month: StrictStr
    amount: StrictStr

    @field_validator('month')
    @classmethod
    def month_valid(cls, value):
        month_dates(value)
        return value

    @field_validator('amount')
    @classmethod
    def amount_valid(cls, value):
        if not re.fullmatch(r'(?:0|[1-9]\d{0,9})(?:\.\d{1,2})?', value):
            raise ValueError('Nonnegative decimal string with at most 2 decimal places required')
        return value


class UserInput(Input):
    username: StrictStr = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=12, max_length=128)
    employee_id: UUID | None = None
    roles: list[Literal['EMPLOYEE', 'MANAGER', 'HR', 'ADMIN']] = Field(min_length=1, max_length=4)
    department_ids: list[UUID] = Field(default_factory=list, max_length=100)
    _text = field_validator('username')(text)


class UserPatch(Input):
    employee_id: UUID | None = None
    roles: list[Literal['EMPLOYEE', 'MANAGER', 'HR', 'ADMIN']] = Field(max_length=4)
    department_ids: list[UUID] = Field(default_factory=list, max_length=100)
    status: Literal['ACTIVE', 'DISABLED']


class PasswordInput(Input):
    password: SecretStr = Field(min_length=12, max_length=128)


def values(model):
    return {k: str(v) if isinstance(v, UUID) else v for k, v in model.model_dump().items()}


def month_dates(month):
    if not re.fullmatch(r'20\d\d-(?:0[1-9]|1[0-2])', month):
        reject(422, '月份须为2000至2099年的YYYY-MM', 'VALIDATION_ERROR')
    year, number = map(int, month.split('-'))
    return date(year, number, 1), date(year, number, calendar.monthrange(year, number)[1])


class CourseService:
    def __init__(self, database, auth):
        self.db, self.auth = database, auth

    def run(self, raw, request_id, action, operation, allowed=None, write=False):
        principal, denied = None, None
        try:
            with self.db.transaction(write=True) as session:
                now = self.auth.now()
                principal = self.auth.resolve(session, raw, now)
                if principal is None:
                    denied = AuthError()
                else:
                    if allowed is not None and not set(principal['roles']).intersection(allowed):
                        reject(403, '当前角色无权执行此操作', 'AUTHORIZATION_DENIED')
                    if allowed and 'ADMIN' not in allowed and not self.auth.effective_employment(session, principal['employee_id'], now):
                        reject(403, '当前员工任职已失效', 'AUTHORIZATION_DENIED')
                    result = operation(session, principal, now)
                    if write:
                        # No names, passwords, file contents, salary amounts or tokens in audit metadata.
                        audit(session, now, action, 'SUCCESS', result.get('id', 'collection') if isinstance(result, dict) else 'collection',
                              request_id, principal['id'], resource_type='course')
        except AuthError as error:
            if principal:
                with self.db.transaction(write=True) as session:
                    audit(session, self.auth.now(), action, 'FAILURE', 'collection', request_id, principal['id'], error.code, resource_type='course')
            raise
        if denied:
            raise denied
        return result

    @staticmethod
    def manager_departments(session, principal):
        if 'MANAGER' not in principal['roles']:
            return []
        table = T['course_manager_departments']
        return list(session.execute(select(table.c.department_id).join(T['departments'],T['departments'].c.id==table.c.department_id)
            .where(table.c.user_id == principal['id'],T['departments'].c.status=='ACTIVE')).scalars())

    def employee_scope(self, session, principal, table=None):
        table = table if table is not None else T['employees']
        if 'HR' in principal['roles']:
            return True
        deps = self.manager_departments(session, principal)
        return or_(table.c.id == principal['employee_id'], table.c.current_department_id.in_(deps))

    @staticmethod
    def active_position(session, department_id, position_id=None):
        department = row_by(session, T['departments'], department_id)
        if department['status'] != 'ACTIVE':
            reject(message='部门必须启用')
        if position_id:
            position = row_by(session, T['positions'], position_id)
            if position['department_id'] != department_id or position['status'] != 'ACTIVE':
                reject(message='职位须启用且属于所选部门')

    def positions(self, session, q='', department_id=None, grade_code=None, status=None, page=1, page_size=20):
        table = T['positions']; conditions = []
        if q: conditions.append(or_(table.c.code.contains(q, autoescape=True), table.c.name.contains(q, autoescape=True)))
        for key, val in [('department_id', department_id), ('grade_code', grade_code), ('status', status)]:
            if val: conditions.append(table.c[key] == val)
        total = session.execute(select(func.count()).select_from(table).where(*conditions)).scalar_one()
        rows = [dict(r) for r in session.execute(select(table).where(*conditions).order_by(table.c.code, table.c.id).offset((page-1)*page_size).limit(page_size)).mappings()]
        for row in rows:
            row['employee_count'] = session.execute(select(func.count()).select_from(T['employees']).where(
                T['employees'].c.current_position_id == row['id'], T['employees'].c.employment_status.in_(EMPLOYED))).scalar_one()
        return {'items': rows, 'total': total, 'page': page, 'page_size': page_size}

    def save_position(self, session, now, data, item_id=None, etag=None):
        table = T['positions']; current = row_by(session, table, item_id) if item_id else None
        if current: version(current, etag)
        self.active_position(session, data['department_id'])
        if session.execute(select(table.c.id).where(table.c.department_id == data['department_id'], table.c.code == data['code'], table.c.id != item_id if item_id else True)).first():
            reject(message='同一部门内职位编号已存在')
        if current and (data['department_id'] != current['department_id'] or data['status'] == 'DISABLED'):
            if session.execute(select(T['employees'].c.id).where(T['employees'].c.current_position_id == item_id, T['employees'].c.employment_status.in_(EMPLOYED))).first():
                reject(message='仍有在职员工使用职位')
        if current: return changed(session, table, current, data, now)
        item_id = str(uuid4()); session.execute(insert(table).values(id=item_id, **data, version_no=1, created_at=now, updated_at=now))
        return row_by(session, table, item_id)

    def employees(self, session, principal, q='', department_id=None, status=None, page=1, page_size=20):
        table = T['employees']; conditions = [self.employee_scope(session, principal)]
        if q: conditions.append(or_(table.c.employee_no.contains(q, autoescape=True), table.c.full_name.contains(q, autoescape=True)))
        if department_id: conditions.append(table.c.current_department_id == department_id)
        if status: conditions.append(table.c.employment_status == status)
        total = session.execute(select(func.count()).select_from(table).where(*conditions)).scalar_one()
        items = [dict(r) for r in session.execute(select(table).where(*conditions).order_by(table.c.employee_no, table.c.id).offset((page-1)*page_size).limit(page_size)).mappings()]
        return {'items': items, 'total': total, 'page': page, 'page_size': page_size}

    def employee(self, session, principal, item_id):
        row = row_by(session, T['employees'], item_id)
        if 'HR' not in principal['roles'] and row['id'] != principal['employee_id'] and row['current_department_id'] not in self.manager_departments(session, principal):
            reject(403, '不能访问该员工', 'AUTHORIZATION_DENIED')
        return row

    def employment_event(self, session, now, item_id, old, data, action):
        event_id = str(uuid4())
        session.execute(insert(T['employee_lifecycle_events']).values(id=event_id, created_at=now, employee_id=item_id,
            event_type=action, old_status=old['employment_status'] if old else None, new_status=data['employment_status'],
            effective_date=now.astimezone(SHANGHAI).date(), reason='COURSE_MVP', executed_at=now,
            payload_snapshot={'old_department_id': old['current_department_id'] if old else None,
                'old_position_id': old['current_position_id'] if old else None, 'department_id': data['current_department_id'], 'position_id': data['current_position_id']}))
        return event_id

    def assign(self, session, now, item_id, data, event_id):
        table = T['employee_assignments']; today = now.astimezone(SHANGHAI).date()
        old = session.execute(select(table).where(table.c.employee_id == item_id, table.c.valid_to.is_(None))).mappings().all()
        for row in old:
            if row['valid_from'] == today:
                session.execute(update(table).where(table.c.id == row['id']).values(department_id=data['current_department_id'],
                    position_id=data['current_position_id'], change_event_id=event_id, updated_at=now))
                return  # Same-day intraday moves are preserved in immutable lifecycle snapshots.
            session.execute(update(table).where(table.c.id == row['id']).values(valid_to=today-timedelta(days=1), updated_at=now))
        session.execute(insert(table).values(id=str(uuid4()), employee_id=item_id, department_id=data['current_department_id'],
            position_id=data['current_position_id'], valid_from=max(data['hire_date'], today) if old else data['hire_date'],
            change_event_id=event_id, created_at=now, updated_at=now))

    def save_employee(self, session, now, data, item_id=None, etag=None):
        table = T['employees']; current = row_by(session, table, item_id) if item_id else None
        if current:
            version(current, etag)
            if current['employment_status'] == 'TERMINATED': reject(message='离职档案不可重新激活或改写')
            if data['hire_date'] != current['hire_date']: reject(message='建档后入职日期保留，不通过编辑重写历史')
            if data['current_department_id'] != current['current_department_id'] or data['current_position_id'] != current['current_position_id']:
                reject(message='请使用调动操作变更部门职位')
        self.active_position(session, data['current_department_id'], data['current_position_id'])
        if data['employment_status'] in EMPLOYED and data['hire_date'] > now.astimezone(SHANGHAI).date():
            reject(422, '在职员工入职日不能在未来', 'VALIDATION_ERROR')
        if session.execute(select(table.c.id).where(table.c.employee_no == data['employee_no'], table.c.id != item_id if item_id else True)).first():
            reject(message='员工工号已存在')
        if current:
            result = changed(session, table, current, data, now)
        else:
            item_id = str(uuid4()); session.execute(insert(table).values(id=item_id, **data, version_no=1, created_at=now, updated_at=now))
            result = row_by(session, table, item_id)
        event_id = self.employment_event(session, now, item_id, current, result, 'COURSE_EMPLOYEE_EDIT' if current else 'COURSE_EMPLOYEE_CREATE')
        if not current or (current['employment_status'] == 'PRE_HIRE' and result['employment_status'] in EMPLOYED):
            self.assign(session, now, item_id, result, event_id)
        return result

    def transfer(self, session, now, item_id, data, etag):
        current = row_by(session, T['employees'], item_id); version(current, etag)
        if current['employment_status'] not in EMPLOYED: reject(message='只有在职员工可调动')
        self.active_position(session, data['department_id'], data['position_id'])
        proposed = {'current_department_id': data['department_id'], 'current_position_id': data['position_id']}
        result = changed(session, T['employees'], current, proposed, now)
        event_id = self.employment_event(session, now, item_id, current, result, 'COURSE_TRANSFER')
        self.assign(session, now, item_id, result, event_id)
        return result

    def archive(self, session, now, item_id, etag):
        current = row_by(session, T['employees'], item_id); version(current, etag)
        if current['employment_status'] == 'TERMINATED': reject(message='员工已离职')
        result = changed(session, T['employees'], current, {'employment_status': 'TERMINATED', 'termination_date': now.astimezone(SHANGHAI).date()}, now)
        self.employment_event(session, now, item_id, current, result, 'COURSE_TERMINATION')
        table = T['employee_assignments']
        for row in session.execute(select(table).where(table.c.employee_id == item_id, table.c.valid_to.is_(None))).mappings():
            session.execute(update(table).where(table.c.id == row['id']).values(valid_to=max(row['valid_from'], now.astimezone(SHANGHAI).date()-timedelta(days=1)), updated_at=now))
        bound = select(users.c.id).where(users.c.employee_id == item_id)
        session.execute(update(auth_sessions).where(auth_sessions.c.user_id.in_(bound), auth_sessions.c.revoked_at.is_(None)).values(revoked_at=now))
        return result

    @staticmethod
    def rule(session, day):
        table = T['course_attendance_rules']
        row = session.execute(select(table).where(table.c.effective_from <= day).order_by(table.c.effective_from.desc())).mappings().first()
        return dict(row) if row else {'id': None, 'effective_from': date(2000,1,1), 'weekdays': [0,1,2,3,4],
                                     'start_time': '09:00', 'end_time': '18:00', 'grace_minutes': 10}

    def workdays(self, session, start, end):
        days = set(); day = start
        while day <= end:
            if day.weekday() in self.rule(session, day)['weekdays']: days.add(day)
            if day==end:break
            day += timedelta(days=1)
        return days

    def save_rule(self, session, now, data):
        today = now.astimezone(SHANGHAI).date()
        if data['effective_from'] <= today:
            reject(message='新规则只能次日或以后生效，不能重算历史打卡')
        table = T['course_attendance_rules']
        if session.execute(select(table.c.id).where(table.c.effective_from == data['effective_from'])).first():
            reject(message='该生效日期已有规则')
        item_id = str(uuid4()); session.execute(insert(table).values(id=item_id, **data, created_at=now, updated_at=now, version_no=1))
        return row_by(session, table, item_id)

    def punch(self, session, principal, now, action):
        eid = principal['employee_id']; day = now.astimezone(SHANGHAI).date()
        if not self.workdays(session, day, day): reject(message='当日不是计划工作日')
        table = T['course_attendance']
        row = session.execute(select(table).where(table.c.employee_id == eid, table.c.work_date == day)).mappings().first()
        if action == 'in':
            if row: reject(message='当日已上班打卡')
            item_id = str(uuid4()); session.execute(insert(table).values(id=item_id, employee_id=eid, work_date=day, clock_in_at=now, created_at=now, updated_at=now, version_no=1))
            return row_by(session, table, item_id)
        if not row or row['clock_out_at'] is not None: reject(message='未上班打卡或已下班打卡')
        if now < utc(row['clock_in_at']): reject(message='服务器时间异常，无法完成打卡')
        return changed(session, table, dict(row), {'clock_out_at': now}, now)

    def attendance(self, session, principal, now, month, employee_id=None):
        start, end = month_dates(month); eid = employee_id or principal['employee_id']
        if not eid: reject(422, '请选择员工', 'VALIDATION_ERROR')
        if eid != principal['employee_id'] and 'HR' not in principal['roles']: reject(403, '只能查询本人考勤', 'AUTHORIZATION_DENIED')
        employee = row_by(session, T['employees'], eid)
        table = T['course_attendance']
        records = [dict(row) for row in session.execute(select(table).where(table.c.employee_id == eid, table.c.work_date.between(start,end)).order_by(table.c.work_date)).mappings()]
        approved = session.execute(select(T['course_leaves']).where(T['course_leaves'].c.employee_id == eid,
            T['course_leaves'].c.status == 'APPROVED', T['course_leaves'].c.start_date <= end, T['course_leaves'].c.end_date >= start)).mappings().all()
        leave_days = set()
        for leave in approved: leave_days |= self.workdays(session, max(start,leave['start_date']), min(end,leave['end_date']))
        planned = self.workdays(session, max(start, employee['hire_date'] or start), min(end, (employee['termination_date']-timedelta(days=1)) if employee['termination_date'] else end))
        expected = planned - leave_days
        today = now.astimezone(SHANGHAI).date(); due = {d for d in expected if d <= today}
        late, early, complete = 0,0,set(); missing = 0
        for row in records:
            rule = self.rule(session,row['work_date']); incoming = utc(row['clock_in_at']).astimezone(SHANGHAI)
            shift = datetime.combine(row['work_date'], time.fromisoformat(rule['start_time']), SHANGHAI)
            row['late'] = incoming > shift + timedelta(minutes=rule['grace_minutes'])
            row['early'] = bool(row['clock_out_at'] and utc(row['clock_out_at']).astimezone(SHANGHAI).time().replace(tzinfo=None) < time.fromisoformat(rule['end_time']))
            row['missing'] = row['clock_out_at'] is None and (row['work_date'] < today or now.astimezone(SHANGHAI).time().replace(tzinfo=None) >= time.fromisoformat(rule['end_time']))
            if row['work_date'] in expected:
                late += int(row['late']); early += int(row['early'])
                if row['clock_out_at']: complete.add(row['work_date'])
        by_day = {row['work_date']:row for row in records}
        for day in due:
            rule = self.rule(session,day)
            ended = day < today or now.astimezone(SHANGHAI).time().replace(tzinfo=None) >= time.fromisoformat(rule['end_time'])
            if ended and (day not in by_day or by_day[day]['clock_out_at'] is None): missing += 1
        denominator = len(expected)
        return {'employee_id':eid, 'month':month, 'items':records, 'summary':{'planned_days':len(planned), 'leave_days':len(leave_days & planned),
            'expected_days':denominator, 'complete_days':len(complete), 'late_days':late, 'early_days':early, 'missing_days':missing,
            'attendance_rate':str((Decimal(len(complete))*100/Decimal(denominator)).quantize(Decimal('0.01'))) if denominator else None}}

    def leaves(self, session, principal, scope, page=1, page_size=20):
        table = T['course_leaves']; conditions = [table.c.employee_id == principal['employee_id']]
        if scope == 'approval':
            if 'MANAGER' not in principal['roles']: reject(403, '需要主管权限', 'AUTHORIZATION_DENIED')
            # Both submitted department and CURRENT department must be authorized (moves fail closed).
            deps = self.manager_departments(session, principal)
            current = select(T['employees'].c.id).where(T['employees'].c.current_department_id.in_(deps))
            conditions = [table.c.department_id.in_(deps), table.c.employee_id.in_(current), table.c.employee_id != principal['employee_id']]
        total = session.execute(select(func.count()).select_from(table).where(*conditions)).scalar_one()
        rows = [dict(r) for r in session.execute(select(table).where(*conditions).order_by(table.c.created_at.desc(),table.c.id).offset((page-1)*page_size).limit(page_size)).mappings()]
        return {'items':rows,'total':total,'page':page,'page_size':page_size}

    def leave_create(self, session, principal, now, data):
        days = self.workdays(session, data['start_date'], data['end_date'])
        if not days: reject(message='日期范围没有工作日')
        employee = row_by(session,T['employees'],principal['employee_id'])
        if data['start_date'] < employee['hire_date']: reject(message='不能申请入职前的请假')
        table = T['course_leaves']
        others = session.execute(select(table).where(table.c.employee_id==principal['employee_id'], table.c.status.in_(('PENDING','APPROVED')),
            table.c.start_date <= data['end_date'], table.c.end_date >= data['start_date'])).mappings()
        if any(days & self.workdays(session,r['start_date'],r['end_date']) for r in others): reject(message='与待审或已批准的工作日请假重叠')
        item_id = str(uuid4()); session.execute(insert(table).values(id=item_id,employee_id=principal['employee_id'],department_id=employee['current_department_id'],
            **data,status='PENDING',created_at=now,updated_at=now,version_no=1))
        return row_by(session,table,item_id)

    def leave_decide(self, session, principal, now, item_id, data, etag, cancel=False):
        table=T['course_leaves']; row=row_by(session,table,item_id)
        if cancel:
            if row['employee_id'] != principal['employee_id']: reject(403,'只能取消本人申请','AUTHORIZATION_DENIED')
        else:
            employee=row_by(session,T['employees'],row['employee_id']); deps=self.manager_departments(session,principal)
            if row['employee_id']==principal['employee_id'] or row['department_id'] not in deps or employee['current_department_id'] not in deps:
                reject(403,'禁止自审或跨部门审批','AUTHORIZATION_DENIED')
        version(row,etag)
        if row['status']!='PENDING': reject(message='仅待审申请可以处理')
        return changed(session,table,row, {'status':'CANCELLED' if cancel else data['status'], 'opinion':None if cancel else data['opinion'],
            'decided_by':principal['id'],'decided_at':now},now)

    def salaries(self, session, principal, month=None, employee_id=None, page=1,page_size=20):
        table=T['course_salaries']; cond=[]
        if 'HR' not in principal['roles']:
            if employee_id and employee_id!=principal['employee_id']: reject(403,'只能查询本人工资','AUTHORIZATION_DENIED')
            cond.append(table.c.employee_id==principal['employee_id'])
        elif employee_id: cond.append(table.c.employee_id==employee_id)
        if month: month_dates(month); cond.append(table.c.month==month)
        total=session.execute(select(func.count()).select_from(table).where(*cond)).scalar_one()
        rows=[dict(r) for r in session.execute(select(table).where(*cond).order_by(table.c.month.desc(),table.c.employee_id).offset((page-1)*page_size).limit(page_size)).mappings()]
        for row in rows: row['amount']=f'{Decimal(row.pop("amount_cents"))/100:.2f}'
        return {'items':rows,'total':total,'page':page,'page_size':page_size}

    def save_salary(self,session,principal,now,data,etag):
        row_by(session,T['employees'],data['employee_id'])
        table=T['course_salaries']; current=session.execute(select(table).where(table.c.employee_id==data['employee_id'],table.c.month==data['month'])).mappings().first()
        cents=int(Decimal(data['amount'])*100)
        if current:
            version(current,etag); result=changed(session,table,dict(current),{'amount_cents':cents},now)
        else:
            if etag is not None: reject(412,'记录尚不存在，请刷新','VERSION_MISMATCH')
            item_id=str(uuid4()); session.execute(insert(table).values(id=item_id,employee_id=data['employee_id'],month=data['month'],amount_cents=cents,created_at=now,updated_at=now,version_no=1))
            result=row_by(session,table,item_id)
        session.execute(insert(T['course_salary_history']).values(id=str(uuid4()),salary_id=result['id'],version_no=result['version_no'],
            amount_cents=cents,actor_user_id=principal['id'],recorded_at=now))
        result['amount']=f'{Decimal(result.pop("amount_cents"))/100:.2f}'
        return result

    def dashboard(self,session,principal,now,month):
        start,end=month_dates(month); e=T['employees']; p=T['positions']
        scope=self.employee_scope(session,principal); active=and_(scope,e.c.employment_status.in_(EMPLOYED))
        count=lambda cond:session.execute(select(func.count()).select_from(e).where(cond)).scalar_one()
        deps=[{'id':r[0],'name':r[1],'count':r[2]} for r in session.execute(select(T['departments'].c.id,T['departments'].c.name,func.count(e.c.id))
            .join(e,e.c.current_department_id==T['departments'].c.id).where(active).group_by(T['departments'].c.id,T['departments'].c.name))]
        grades=[{'name':r[0],'count':r[1]} for r in session.execute(select(p.c.grade_code,func.count(e.c.id)).join(e,e.c.current_position_id==p.c.id).where(active).group_by(p.c.grade_code))]
        scoped_ids=select(e.c.id).where(scope)
        l=T['course_leaves']; leave_stats=[{'name':r[0],'count':r[1]} for r in session.execute(select(l.c.leave_type,func.count()).where(
            l.c.employee_id.in_(scoped_ids),l.c.status=='APPROVED',l.c.start_date<=end,l.c.end_date>=start).group_by(l.c.leave_type))]
        # Attendance summaries reuse the same SQL-backed rule/leave calculation; no fake metrics.
        attendance={'expected_days':0,'complete_days':0,'late_days':0,'early_days':0,'missing_days':0}
        for eid in session.execute(scoped_ids).scalars():
            summary=self.attendance(session,{**principal,'roles':['HR']},now,month,eid)['summary']
            for key in attendance: attendance[key]+=summary[key]
        result={'employee_count':count(active),'hired_this_month':count(and_(scope,e.c.hire_date.between(start,end))),
            'terminated_this_month':count(and_(scope,e.c.termination_date.between(start,end))),'departments':deps,'grades':grades,'leave_types':leave_stats,'attendance':attendance}
        if 'HR' in principal['roles']:
            months=[]; y,m=start.year,start.month
            for _ in range(6):
                months.append(f'{y:04}-{m:02}'); m-=1
                if m==0:y-=1;m=12
            table=T['course_salaries']; sums=dict(session.execute(select(table.c.month,func.sum(table.c.amount_cents)).where(table.c.month.in_(months)).group_by(table.c.month)).all())
            result['salary_trend']=[{'month':v,'amount':f'{Decimal(sums.get(v,0))/100:.2f}'} for v in reversed(months)]
        return result

    def user_list(self,session,q='',page=1,page_size=20):
        cond=users.c.username.contains(q,autoescape=True)
        total=session.execute(select(func.count()).select_from(users).where(cond)).scalar_one()
        rows=[dict(r) for r in session.execute(select(users.c.id,users.c.username,users.c.employee_id,users.c.status,users.c.version_no).where(cond).order_by(users.c.username).offset((page-1)*page_size).limit(page_size)).mappings()]
        now=self.auth.now()
        for row in rows:
            row['roles']=list(session.execute(select(roles.c.code).join(role_assignments,role_assignments.c.role_id==roles.c.id).where(
                role_assignments.c.user_id==row['id'],role_assignments.c.revoked_at.is_(None),role_assignments.c.valid_from_at<=now,
                or_(role_assignments.c.valid_to_at.is_(None),role_assignments.c.valid_to_at>now))).scalars())
            row['department_ids']=list(session.execute(select(T['course_manager_departments'].c.department_id).where(T['course_manager_departments'].c.user_id==row['id'])).scalars())
        return {'items':rows,'total':total,'page':page,'page_size':page_size}

    def save_user(self,session,principal,now,data,item_id=None,etag=None):
        current=row_by(session,users,item_id) if item_id else None
        if current:
            if item_id==principal['id']: reject(403,'不能修改本人角色、绑定或停用本人','AUTHORIZATION_DENIED')
            version(current,etag)
        role_codes=set(data['roles']); eid=data['employee_id']
        disabling=current and data.get('status')=='DISABLED'
        if disabling:
            # Deactivation keeps historical identity/employee binding; never use it to grant new privileges.
            existing=set(session.execute(select(roles.c.code).join(role_assignments,role_assignments.c.role_id==roles.c.id).where(
                role_assignments.c.user_id==item_id,role_assignments.c.revoked_at.is_(None),role_assignments.c.valid_from_at<=now,
                or_(role_assignments.c.valid_to_at.is_(None),role_assignments.c.valid_to_at>now))).scalars())
            scopes=set(session.execute(select(T['course_manager_departments'].c.department_id).where(T['course_manager_departments'].c.user_id==item_id)).scalars())
            if role_codes!=existing or eid!=current['employee_id'] or set(map(str,data['department_ids']))!=scopes:
                reject(message='停用只保留现有角色与员工绑定，请分别操作授权变更')
            result=changed(session,users,current,{'status':'DISABLED'},now)
            session.execute(update(auth_sessions).where(auth_sessions.c.user_id==item_id,auth_sessions.c.revoked_at.is_(None)).values(revoked_at=now))
            return {'id':item_id,'version_no':result['version_no']}
        elif role_codes-{'ADMIN'} and not self.auth.effective_employment(session,eid,now):
            reject(message='业务角色须绑定有效在职员工')
        if not role_codes: reject(422,'启用账号至少需要一个角色','VALIDATION_ERROR')
        if eid and session.execute(select(users.c.id).where(users.c.employee_id==eid,users.c.id!=item_id if item_id else True)).first(): reject(message='员工已绑定账号')
        if len(role_codes)!=len(data['roles']): reject(422,'角色重复','VALIDATION_ERROR')
        if data['department_ids'] and 'MANAGER' not in role_codes: reject(message='只有主管可以绑定负责部门')
        if 'MANAGER' in role_codes and not data['department_ids']: reject(message='主管必须绑定直接负责部门')
        for dep in data['department_ids']: self.active_position(session,str(dep))
        if not current:
            if session.execute(select(users.c.id).where(users.c.username==data['username'])).first(): reject(message='账号已存在')
            item_id=str(uuid4()); session.execute(insert(users).values(id=item_id,username=data['username'],password_hash=self.auth.hash_password(data['password'].get_secret_value()),
                employee_id=eid,status='ACTIVE',password_changed_at=now,created_at=now,updated_at=now,version_no=1))
        else:
            changed(session,users,current,{'employee_id':eid,'status':data['status']},now)
            session.execute(update(role_assignments).where(role_assignments.c.user_id==item_id,role_assignments.c.revoked_at.is_(None)).values(revoked_at=now,updated_at=now))
            session.execute(delete(T['course_manager_departments']).where(T['course_manager_departments'].c.user_id==item_id))
            session.execute(update(auth_sessions).where(auth_sessions.c.user_id==item_id,auth_sessions.c.revoked_at.is_(None)).values(revoked_at=now))
        ids=dict(session.execute(select(roles.c.code,roles.c.id)).all())
        for code in role_codes:
            session.execute(insert(role_assignments).values(id=str(uuid4()),user_id=item_id,role_id=ids[code],valid_from_at=now,assigned_by=principal['id'],
                bootstrap_origin=False,reason='COURSE_ADMIN_ASSIGNMENT',created_at=now,updated_at=now))
        for dep in set(map(str,data['department_ids'])):
            session.execute(insert(T['course_manager_departments']).values(user_id=item_id,department_id=dep))
        return {'id':item_id,'version_no':current['version_no']+1 if current else 1}


def make_router(bearer):
    router=APIRouter(prefix='/api/v1')
    def run(request,action,operation,allowed=None,write=False):
        return request.app.state.course.run(bearer(request),request.state.request_id,action,operation,allowed,write)
    def reply(data,status=200):
        return JSONResponse({'data':jsonable_encoder(data)},status_code=status,
            headers={'ETag':f'"v{data["version_no"]}"'} if isinstance(data,dict) and 'version_no' in data else {})
    def match(request):
        matches=request.headers.getlist('if-match'); return matches[0] if len(matches)==1 else None
    def service(request): return request.app.state.course

    @router.get('/positions')
    def positions(request:Request,q:str=Query('',max_length=128),department_id:UUID|None=None,grade_code:str|None=Query(None,max_length=64),status:Literal['ACTIVE','DISABLED']|None=None,
                  page:int=Query(1,ge=1,le=2147483647),page_size:int=Query(20,ge=1,le=100)):
        return reply(run(request,'position.read',lambda s,p,n:service(request).positions(s,q,str(department_id) if department_id else None,grade_code,status,page,page_size)))
    @router.post('/positions')
    def position_create(payload:PositionInput,request:Request):
        return reply(run(request,'position.create',lambda s,p,n:service(request).save_position(s,n,values(payload)),{'HR'},True),201)
    @router.get('/positions/{item_id}')
    def position_detail(item_id:UUID,request:Request):
        return reply(run(request,'position.read',lambda s,p,n:row_by(s,T['positions'],str(item_id))))
    @router.patch('/positions/{item_id}')
    def position_patch(item_id:UUID,payload:PositionInput,request:Request):
        return reply(run(request,'position.update',lambda s,p,n:service(request).save_position(s,n,values(payload),str(item_id),match(request)),{'HR'},True))

    @router.get('/employees')
    def employees(request:Request,q:str=Query('',max_length=128),department_id:UUID|None=None,status:Literal['PRE_HIRE','PROBATION','ACTIVE','EXIT_PROCESSING','TERMINATED']|None=None,
                  page:int=Query(1,ge=1,le=2147483647),page_size:int=Query(20,ge=1,le=100)):
        return reply(run(request,'employee.read',lambda s,p,n:service(request).employees(s,p,q,str(department_id) if department_id else None,status,page,page_size),{'HR','MANAGER','EMPLOYEE'}))
    @router.post('/employees')
    def employee_create(payload:EmployeeInput,request:Request):
        return reply(run(request,'employee.create',lambda s,p,n:service(request).save_employee(s,n,values(payload)),{'HR'},True),201)

    @router.get('/employees/template')
    def employee_template(request:Request,format:Literal['csv','xlsx']='csv'):
        from backend.course_files import encode_sheet, COLUMNS, media
        content=run(request,'employee.template',lambda s,p,n:encode_sheet([COLUMNS],format),{'HR'})
        return Response(content,media_type=media(format),headers={'Content-Disposition':f'attachment; filename="employees-template.{format}"'})
    @router.post('/employees/import')
    async def employee_import(request:Request,format:Literal['csv','xlsx']='csv',mode:Literal['preflight','commit']='preflight'):
        from backend.course_files import import_employees
        content=await request.body()
        return reply(run(request,'employee.import.'+mode,lambda s,p,n:import_employees(service(request),s,n,content,format,mode),{'HR'},True))
    @router.get('/employees/export')
    def employee_export(request:Request,format:Literal['csv','xlsx']='csv',q:str=Query('',max_length=128)):
        from backend.course_files import export_employees,media
        content=run(request,'employee.export',lambda s,p,n:export_employees(service(request),s,p,q,format),{'HR','MANAGER','EMPLOYEE'},True)
        return Response(content,media_type=media(format),headers={'Content-Disposition':f'attachment; filename="employees.{format}"'})
    @router.get('/employees/{item_id}')
    def employee_detail(item_id:UUID,request:Request):
        def detail(s,p,n):
            row=service(request).employee(s,p,str(item_id))
            row['history']=[dict(r) for r in s.execute(select(T['employee_lifecycle_events']).where(T['employee_lifecycle_events'].c.employee_id==str(item_id)).order_by(T['employee_lifecycle_events'].c.created_at)).mappings()]
            return row
        return reply(run(request,'employee.read',detail,{'HR','MANAGER','EMPLOYEE'}))
    @router.patch('/employees/{item_id}')
    def employee_patch(item_id:UUID,payload:EmployeeInput,request:Request):
        return reply(run(request,'employee.update',lambda s,p,n:service(request).save_employee(s,n,values(payload),str(item_id),match(request)),{'HR'},True))
    @router.post('/employees/{item_id}/transfer')
    def employee_transfer(item_id:UUID,payload:TransferInput,request:Request):
        return reply(run(request,'employee.transfer',lambda s,p,n:service(request).transfer(s,n,str(item_id),values(payload),match(request)),{'HR'},True))
    @router.post('/employees/{item_id}/archive')
    def employee_archive(item_id:UUID,payload:Input,request:Request):
        return reply(run(request,'employee.archive',lambda s,p,n:service(request).archive(s,n,str(item_id),match(request)),{'HR'},True))

    @router.get('/attendance/rules')
    def rule_list(request:Request):
        return reply(run(request,'attendance.rule.read',lambda s,p,n:{'current':service(request).rule(s,n.astimezone(SHANGHAI).date()),
            'items':[dict(r) for r in s.execute(select(T['course_attendance_rules']).order_by(T['course_attendance_rules'].c.effective_from.desc())).mappings()]}, {'HR','EMPLOYEE','MANAGER'}))
    @router.post('/attendance/rules')
    def rule_create(payload:RuleInput,request:Request):
        return reply(run(request,'attendance.rule.create',lambda s,p,n:service(request).save_rule(s,n,values(payload)),{'HR'},True),201)
    @router.post('/attendance/clock-{action}')
    def punch(action:Literal['in','out'],payload:Input,request:Request):
        return reply(run(request,'attendance.clock.'+action,lambda s,p,n:service(request).punch(s,p,n,action),{'HR','MANAGER','EMPLOYEE'},True))
    @router.get('/attendance')
    def attendance(request:Request,month:str,employee_id:UUID|None=None):
        return reply(run(request,'attendance.read',lambda s,p,n:service(request).attendance(s,p,n,month,str(employee_id) if employee_id else None),{'HR','MANAGER','EMPLOYEE'}))
    @router.get('/leaves')
    def leave_list(request:Request,scope:Literal['mine','approval']='mine',page:int=Query(1,ge=1,le=2147483647),page_size:int=Query(20,ge=1,le=100)):
        return reply(run(request,'leave.read',lambda s,p,n:service(request).leaves(s,p,scope,page,page_size),{'HR','MANAGER','EMPLOYEE'}))
    @router.post('/leaves')
    def leave_create(payload:LeaveInput,request:Request):
        return reply(run(request,'leave.create',lambda s,p,n:service(request).leave_create(s,p,n,values(payload)),{'HR','MANAGER','EMPLOYEE'},True),201)
    @router.post('/leaves/{item_id}/cancel')
    def leave_cancel(item_id:UUID,payload:Input,request:Request):
        return reply(run(request,'leave.cancel',lambda s,p,n:service(request).leave_decide(s,p,n,str(item_id),{},match(request),True),{'HR','MANAGER','EMPLOYEE'},True))
    @router.post('/leaves/{item_id}/decision')
    def leave_decision(item_id:UUID,payload:DecisionInput,request:Request):
        return reply(run(request,'leave.decision',lambda s,p,n:service(request).leave_decide(s,p,n,str(item_id),values(payload),match(request)),{'MANAGER'},True))
    @router.get('/salaries')
    def salary_list(request:Request,month:str|None=None,employee_id:UUID|None=None,page:int=Query(1,ge=1,le=2147483647),page_size:int=Query(20,ge=1,le=100)):
        return reply(run(request,'salary.read',lambda s,p,n:service(request).salaries(s,p,month,str(employee_id) if employee_id else None,page,page_size),{'HR','MANAGER','EMPLOYEE'}))
    @router.put('/salaries')
    def salary_save(payload:SalaryInput,request:Request):
        return reply(run(request,'salary.update',lambda s,p,n:service(request).save_salary(s,p,n,values(payload),match(request)),{'HR'},True))
    @router.get('/salaries/{item_id}/history')
    def salary_history(item_id:UUID,request:Request):
        def history(s,p,n):
            row_by(s,T['course_salaries'],str(item_id))
            rows=[dict(r) for r in s.execute(select(T['course_salary_history']).where(T['course_salary_history'].c.salary_id==str(item_id)).order_by(T['course_salary_history'].c.version_no)).mappings()]
            for row in rows:row['amount']=f'{Decimal(row.pop("amount_cents"))/100:.2f}'
            return {'items':rows}
        return reply(run(request,'salary.history',history,{'HR'}))
    @router.get('/dashboard')
    def dashboard(request:Request,month:str):
        return reply(run(request,'dashboard.read',lambda s,p,n:service(request).dashboard(s,p,n,month),{'HR','MANAGER','EMPLOYEE'}))
    @router.get('/users')
    def user_list(request:Request,q:str=Query('',max_length=64),page:int=Query(1,ge=1,le=2147483647),page_size:int=Query(20,ge=1,le=100)):
        return reply(run(request,'identity.read',lambda s,p,n:service(request).user_list(s,q,page,page_size),{'ADMIN'}))
    @router.get('/users/audit-events')
    def audit_list(request:Request,page:int=Query(1,ge=1,le=2147483647),page_size:int=Query(20,ge=1,le=100)):
        def listing(s,p,n):
            a=T['audit_events']
            fields=[a.c.id,a.c.occurred_at,a.c.actor_user_id,a.c.action_code,a.c.resource_type,a.c.resource_id,a.c.outcome,a.c.request_id]
            rows=[dict(r) for r in s.execute(select(*fields).order_by(a.c.occurred_at.desc(),a.c.id).offset((page-1)*page_size).limit(page_size)).mappings()]
            return {'items':rows,'total':s.execute(select(func.count()).select_from(a)).scalar_one(),'page':page,'page_size':page_size}
        return reply(run(request,'audit.read',listing,{'ADMIN'}))
    @router.get('/users/employee-options')
    def user_employee_options(request:Request,page:int=Query(1,ge=1,le=2147483647),page_size:int=Query(100,ge=1,le=100)):
        def options(s,p,n):
            e=T['employees']
            rows=[dict(r) for r in s.execute(select(e.c.id,e.c.employee_no,e.c.full_name,e.c.current_department_id,e.c.employment_status)
                .order_by(e.c.employee_no).offset((page-1)*page_size).limit(page_size)).mappings()]
            return {'items':rows,'total':s.execute(select(func.count()).select_from(e)).scalar_one(),'page':page,'page_size':page_size}
        return reply(run(request,'identity.employee.binding.options',options,{'ADMIN'}))
    @router.post('/users')
    def user_create(payload:UserInput,request:Request):
        return reply(run(request,'identity.create',lambda s,p,n:service(request).save_user(s,p,n,values(payload)),{'ADMIN'},True),201)
    @router.patch('/users/{item_id}')
    def user_patch(item_id:UUID,payload:UserPatch,request:Request):
        return reply(run(request,'identity.role.assign',lambda s,p,n:service(request).save_user(s,p,n,values(payload),str(item_id),match(request)),{'ADMIN'},True))
    @router.post('/users/{item_id}/password')
    def user_password(item_id:UUID,payload:PasswordInput,request:Request):
        def reset(s,p,n):
            row=row_by(s,users,str(item_id)); version(row,match(request))
            result=changed(s,users,row,{'password_hash':service(request).auth.hash_password(payload.password.get_secret_value()),'password_changed_at':n},n)
            s.execute(update(auth_sessions).where(auth_sessions.c.user_id==str(item_id),auth_sessions.c.revoked_at.is_(None)).values(revoked_at=n))
            return {'id':str(item_id),'version_no':result['version_no']}
        return reply(run(request,'identity.password.reset',reset,{'ADMIN'},True))
    return router
