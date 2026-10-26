"""Formal ASGI app factory: uvicorn backend.app:create_app --factory."""
from contextlib import asynccontextmanager
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.auth import AuthError, AuthService
from backend.database import Database
from backend.departments import DepartmentService, make_router
from backend.settings import Settings
from backend.course import CourseService, make_router as make_course_router


class LoginInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


class LoginBodyLimit:
    """Bound login JSON before validation, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope['type'] != 'http' or scope.get('method') not in ('POST', 'PATCH', 'PUT')
                or not scope.get('path', '').startswith('/api/v1/')):
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            limit = 2 * 1024 * 1024 if scope.get('path') == '/api/v1/employees/import' else 4096
            if len(body) > limit:
                response = JSONResponse({'error': {'code': 'INVALID_REQUEST', 'message': '请求过大'}, 'request_id': str(uuid4())},
                                        status_code=413, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
                return await response(scope, receive, send)
            if not message.get('more_body', False):
                break
        sent = False
        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)


def bearer(request):
    values = request.headers.getlist('authorization')
    scheme, separator, value = values[0].partition(' ') if len(values) == 1 else ('', '', '')
    if not separator or scheme.lower() != 'bearer' or not value or len(value) > 256 or any(c.isspace() for c in value):
        raise AuthError()
    return value


def create_app(settings=None, clock=None):
    settings = settings or Settings.from_env()
    database = Database(settings.database_path)
    auth = AuthService(database, clock)

    @asynccontextmanager
    async def lifespan(_app):
        database.check_revision()
        yield
        database.engine.dispose()

    app = FastAPI(title='HRMS', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.auth = auth
    app.state.database = database
    app.state.departments = DepartmentService(database, auth)
    app.state.course = CourseService(database, auth)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlsplit(settings.public_origin).hostname, '127.0.0.1', 'localhost'])

    def failure(request, status, code, message):
        headers = {'WWW-Authenticate': 'Bearer'} if status == 401 else {}
        return JSONResponse({'error': {'code': code, 'message': message}, 'request_id': request.state.request_id},
                            status_code=status, headers=headers)

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        request.state.request_id = str(uuid4())
        if request.url.path.startswith('/api/'):
            origin = request.headers.get('origin')
            referer = request.headers.get('referer')
            ref_origin = None
            if referer:
                try:
                    parsed = urlsplit(referer)
                    ref_origin = f'{parsed.scheme}://{parsed.netloc}' if not parsed.username and not parsed.password else None
                except ValueError:
                    ref_origin = None
            source_bad = origin is not None and origin != settings.public_origin
            write = request.method not in ('GET', 'HEAD', 'OPTIONS')
            source_missing = write and origin is None and ref_origin != settings.public_origin
            if (source_bad or source_missing or request.headers.get('sec-fetch-site') in ('cross-site', 'same-site')):
                response = failure(request, 403, 'AUTHORIZATION_DENIED', '请求来源不被允许')
            elif request.url.path.startswith('/api/v1/auth/') and request.url.query:
                response = failure(request, 400, 'INVALID_REQUEST', '认证接口不接受查询参数')
            elif ((request.url.path == '/api/v1/auth/login' or request.url.path.startswith('/api/v1/departments'))
                  and request.method in ('POST', 'PATCH')
                  and request.headers.get('content-type', '').split(';')[0].lower() != 'application/json'):
                response = failure(request, 415, 'INVALID_REQUEST', '写入请求必须使用JSON')
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                                 'X-Frame-Options': 'DENY', 'X-Request-ID': request.state.request_id})
        return response

    @app.exception_handler(AuthError)
    async def auth_error(request, error):
        return failure(request, error.status, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, _error):
        return failure(request, 422, 'VALIDATION_ERROR', '请求字段或格式不正确')

    @app.exception_handler(SQLAlchemyError)
    async def database_unavailable(request, _error):
        return failure(request, 503, 'DEPENDENCY_UNAVAILABLE', '必要服务暂不可用，请稍后重试')

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return failure(request, error.status_code, 'NOT_FOUND' if error.status_code == 404 else 'INVALID_REQUEST', '请求不可用')

    @app.get('/api/v1/health')
    def health():
        database.check_revision()
        return {'status': 'ok', 'application': 'hrms', 'schema': 'course_0003'}

    @app.post('/api/v1/auth/login')
    def login(payload: LoginInput, request: Request):
        reply = auth.login(payload.username, payload.password.get_secret_value(),
                           request.client.host if request.client else 'unknown', request.state.request_id)
        return {'data': reply}

    @app.get('/api/v1/auth/me')
    def me(request: Request):
        # Identity is always selected from the server session, never a client employee/user ID.
        return {'data': auth.me(bearer(request),touch=request.headers.get('X-HRMS-Session-Probe')!='1')}

    @app.post('/api/v1/auth/logout', status_code=204)
    def logout(request: Request):
        auth.logout(bearer(request), request.state.request_id)
        return Response(status_code=204)

    app.include_router(make_router(bearer))
    app.include_router(make_course_router(bearer))
    app.add_middleware(LoginBodyLimit)
    return app
