"""Department metadata only; authenticated reads and HR-only organization writes."""
from uuid import UUID, uuid4
from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator
from sqlalchemy import func, insert, or_, select, text, update

from backend.auth import AuthError, audit, stamp
from backend.models import metadata

departments = metadata.tables['departments']
employees = metadata.tables['employees']
assignments = metadata.tables['employee_assignments']
EMPLOYED = ('PROBATION', 'ACTIVE', 'EXIT_PROCESSING')


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: StrictStr = Field(min_length=1, max_length=64)
    name: StrictStr = Field(min_length=1, max_length=128)
    parent_id: UUID | None = None
    status: Literal['ACTIVE', 'DISABLED'] = 'ACTIVE'

    @field_validator('code', 'name')
    @classmethod
    def meaningful_text(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('Use non-empty text without control characters')
        return value


class DepartmentPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: StrictStr | None = Field(default=None, min_length=1, max_length=64)
    name: StrictStr | None = Field(default=None, min_length=1, max_length=128)
    parent_id: UUID | None = None
    status: Literal['ACTIVE', 'DISABLED'] | None = None

    @model_validator(mode='after')
    def valid_patch(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set - {'parent_id'}):
            raise ValueError('Supply at least one non-null editable field')
        for key in ('code', 'name'):
            value = getattr(self, key)
            if value is not None:
                setattr(self, key, DepartmentCreate.meaningful_text(value))
        return self


def dto_values(model):
    values = model.model_dump(exclude_unset=True)
    if 'parent_id' in values and values['parent_id'] is not None:
        values['parent_id'] = str(values['parent_id'])
    return values


class DepartmentService:
    def __init__(self, database, auth):
        self.database, self.auth = database, auth

    def run(self, raw, write, action, request_id, operation, resource_id='collection'):
        principal, denied = None, None
        try:
            # Session resolution and authorization share the same write lock as the mutation.
            with self.database.transaction(write=True) as session:
                now = self.auth.now()
                principal = self.auth.resolve(session, raw, now)
                if principal is None:
                    denied = AuthError()
                elif write and ('HR' not in principal['roles'] or principal['employee_id'] is None):
                    denied = AuthError(403, 'AUTHORIZATION_DENIED', '部门变更需要当前有效的独立HR身份')
                    audit(session, now, action, 'FAILURE', resource_id, request_id, principal['id'], 'AUTHORIZATION_DENIED', resource_type='department')
                else:
                    if write and not self.auth.effective_employment(session, principal['employee_id'], now):
                        raise AuthError(403, 'AUTHORIZATION_DENIED', 'HR员工当前任职事实或部门岗位已失效')
                    result = operation(session, principal, now)
        except AuthError as error:
            if principal is not None:
                with self.database.transaction(write=True) as session:
                    audit(session, self.auth.now(), action, 'FAILURE', resource_id, request_id, principal['id'], error.code, resource_type='department')
            raise
        # Commit expiration/revocation before returning a 401, rather than rolling it back.
        if denied is not None:
            raise denied
        return result

    @staticmethod
    def hierarchy(session):
        return {row['id']: dict(row) for row in session.execute(select(departments)).mappings()}

    @staticmethod
    def descendants(tree, target):
        children = {}
        for row in tree.values():
            children.setdefault(row['parent_id'], []).append(row['id'])
        found, pending = set(), [target]
        while pending:
            item = pending.pop()
            if item in found:
                raise AuthError(409, 'BUSINESS_RULE_CONFLICT', '现有部门层级异常，请先核查数据')
            found.add(item)
            pending.extend(children.get(item, []))
        return found

    def project(self, session, rows, tree):
        counts = dict(session.execute(select(employees.c.current_department_id, func.count()).where(
            employees.c.employment_status.in_(EMPLOYED)).group_by(employees.c.current_department_id)).all())
        result = []
        for row in rows:
            result.append(self.resource(row) | {
                'parent_name': tree[row['parent_id']]['name'] if row['parent_id'] in tree else None,
                'direct_employee_count': counts.get(row['id'], 0),
                'subtree_employee_count': sum(counts.get(key, 0) for key in self.descendants(tree, row['id']))})
        return result

    @staticmethod
    def resource(row):
        return {key: row[key] for key in ('id', 'code', 'name', 'parent_id', 'status', 'version_no')} | {
            'created_at': stamp(row['created_at']), 'updated_at': stamp(row['updated_at'])}

    def listing(self, raw, q, page, page_size, status, request_id):
        def operation(session, _principal, _now):
            condition = []
            if q:
                condition.append(or_(departments.c.code.contains(q, autoescape=True), departments.c.name.contains(q, autoescape=True)))
            if status:
                condition.append(departments.c.status == status)
            total = session.execute(select(func.count()).select_from(departments).where(*condition)).scalar_one()
            rows = session.execute(select(departments).where(*condition).order_by(departments.c.code, departments.c.id)
                                   .offset((page - 1) * page_size).limit(page_size)).mappings().all()
            return {'items': self.project(session, rows, self.hierarchy(session)), 'total': total, 'page': page, 'page_size': page_size}
        return self.run(raw, False, 'org.department.read', request_id, operation)

    def detail(self, raw, item_id, request_id):
        def operation(session, _principal, _now):
            tree = self.hierarchy(session)
            if item_id not in tree:
                raise AuthError(404, 'NOT_FOUND', '部门不存在')
            return self.resource(tree[item_id])
        return self.run(raw, False, 'org.department.read', request_id, operation, item_id)

    def validate_hierarchy(self, tree, item_id, values):
        parent, visited = values.get('parent_id'), {item_id}
        while parent is not None:
            if parent in visited:
                raise AuthError(409, 'BUSINESS_RULE_CONFLICT', '部门不能归属于自身或其下级')
            if parent not in tree:
                raise AuthError(409, 'BUSINESS_RULE_CONFLICT', '上级部门不存在')
            visited.add(parent)
            if values.get('status', 'ACTIVE') == 'ACTIVE' and tree[parent]['status'] != 'ACTIVE':
                raise AuthError(409, 'BUSINESS_RULE_CONFLICT', '启用部门的上级链必须全部启用')
            parent = tree[parent]['parent_id']

    @staticmethod
    def protect_unimplemented_grants(session):
        # These approved tables have not been migrated in this application yet.
        # Never assume that future grants are absent simply because this service cannot evaluate them.
        names = set(session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
        if names.intersection({'management_grants', 'special_grants', 'management_appointments', 'project_grants'}):
            raise AuthError(409, 'BUSINESS_RULE_CONFLICT', '当前版本尚不能核验新增授权表的组织影响，拒绝层级调整或停用')

    def protect_disable(self, session, tree, item_id, now):
        scope = self.descendants(tree, item_id)
        if any(tree[key]['status'] == 'ACTIVE' for key in scope - {item_id}):
            raise AuthError(409, 'BUSINESS_RULE_CONFLICT', '请先处理仍启用的下级部门')
        occupied = session.execute(select(employees.c.id).where(employees.c.current_department_id.in_(scope),
            employees.c.employment_status.in_(EMPLOYED)).limit(1)).first()
        assigned = session.execute(select(assignments.c.id).join(employees, employees.c.id == assignments.c.employee_id).where(
            assignments.c.department_id.in_(scope), employees.c.employment_status.in_(EMPLOYED),
            assignments.c.valid_from <= now.date(),
            or_(assignments.c.valid_to.is_(None), assignments.c.valid_to >= now.date())).limit(1)).first()
        if occupied or assigned:
            raise AuthError(409, 'BUSINESS_RULE_CONFLICT', '仍有在职员工或有效任职归属，不能停用')
        self.protect_unimplemented_grants(session)

    def create(self, raw, values, request_id):
        def operation(session, principal, now):
            data = {'parent_id': None, 'status': 'ACTIVE', **values}
            item_id = str(uuid4())
            self.validate_hierarchy(self.hierarchy(session), item_id, data)
            if session.execute(select(departments.c.id).where(departments.c.code == data['code'])).first():
                raise AuthError(409, 'DUPLICATE_RESOURCE', '部门编号已存在')
            session.execute(insert(departments).values(id=item_id, **data, version_no=1, created_at=now, updated_at=now))
            audit(session, now, 'org.department.create', 'SUCCESS', item_id, request_id, principal['id'], resource_type='department')
            self.enqueue(session, item_id, 1, now)
            tree = self.hierarchy(session)
            return self.resource(tree[item_id])
        return self.run(raw, True, 'org.department.create', request_id, operation)

    def change(self, raw, item_id, values, if_match, request_id):
        def operation(session, principal, now):
            tree = self.hierarchy(session)
            if item_id not in tree:
                raise AuthError(404, 'NOT_FOUND', '部门不存在')
            current = tree[item_id]
            if if_match is None:
                raise AuthError(428, 'PRECONDITION_REQUIRED', '请先读取部门详情后再编辑')
            if if_match != f'"v{current["version_no"]}"':
                raise AuthError(412, 'VERSION_MISMATCH', '部门已被修改，请重新加载详情后编辑')
            proposed = {**current, **values}
            self.validate_hierarchy(tree, item_id, proposed)
            if proposed['parent_id'] != current['parent_id']:
                self.protect_unimplemented_grants(session)
            if proposed['status'] == 'DISABLED' and current['status'] != 'DISABLED':
                self.protect_disable(session, tree, item_id, now)
            if session.execute(select(departments.c.id).where(departments.c.code == proposed['code'], departments.c.id != item_id)).first():
                raise AuthError(409, 'DUPLICATE_RESOURCE', '部门编号已存在')
            updated = session.execute(update(departments).where(departments.c.id == item_id, departments.c.version_no == current['version_no'])
                .values(**values, version_no=current['version_no'] + 1, updated_at=now))
            if updated.rowcount != 1:
                raise AuthError(412, 'VERSION_MISMATCH', '部门版本冲突，请重新加载')
            audit(session, now, 'org.department.update', 'SUCCESS', item_id, request_id, principal['id'], resource_type='department')
            self.enqueue(session, item_id, current['version_no'] + 1, now)
            tree = self.hierarchy(session)
            return self.resource(tree[item_id])
        return self.run(raw, True, 'org.department.update', request_id, operation, item_id)

    @staticmethod
    def enqueue(session, item_id, version, now):
        session.execute(insert(metadata.tables['outbox_events']).values(id=str(uuid4()), event_type='organization.department.changed',
            object_type='department', object_id=item_id, idempotency_key=f'department:{item_id}:v{version}',
            payload_redacted={'department_id': item_id, 'version_no': version}, status='PENDING', attempts=0, created_at=now))


def make_router(bearer):
    router = APIRouter(prefix='/api/v1/departments')

    def reply(data, request, status=200, resource=False):
        body = {'data': data} if resource else {'data': data, 'request_id': request.state.request_id}
        return JSONResponse(body, status_code=status, headers={'ETag': f'"v{data["version_no"]}"'} if resource else {})

    @router.get('')
    def listing(request: Request, q: str = Query(default='', max_length=128), page: int = Query(default=1, ge=1, le=2147483647),
                page_size: int = Query(default=20, ge=1, le=100), status: Literal['ACTIVE', 'DISABLED'] | None = None):
        raw = bearer(request)
        keys = list(request.query_params.keys())
        if (set(keys) - {'q', 'page', 'page_size', 'status'} or any(len(request.query_params.getlist(key)) != 1 for key in keys)
                or any(ord(char) < 32 for char in q)):
            raise AuthError(422, 'VALIDATION_ERROR', '查询参数不正确')
        return {'data': request.app.state.departments.listing(raw, q.strip(), page, page_size, status, request.state.request_id),
                'request_id': request.state.request_id}

    @router.post('', status_code=201)
    def create(payload: DepartmentCreate, request: Request):
        if request.url.query:
            raise AuthError(422, 'VALIDATION_ERROR', '新增接口不接受查询参数')
        return reply(request.app.state.departments.create(bearer(request), dto_values(payload), request.state.request_id), request, 201)

    @router.get('/{item_id}')
    def detail(item_id: UUID, request: Request):
        if request.url.query:
            raise AuthError(422, 'VALIDATION_ERROR', '详情接口不接受查询参数')
        return reply(request.app.state.departments.detail(bearer(request), str(item_id), request.state.request_id), request, resource=True)

    @router.patch('/{item_id}')
    def change(item_id: UUID, payload: DepartmentPatch, request: Request):
        if request.url.query:
            raise AuthError(422, 'VALIDATION_ERROR', '编辑接口不接受查询参数')
        matches = request.headers.getlist('if-match')
        return reply(request.app.state.departments.change(bearer(request), str(item_id), dto_values(payload),
                     matches[0] if len(matches) == 1 else None, request.state.request_id), request)

    return router
