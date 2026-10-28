"""Current SQLAlchemy table models; synchronous Session transactions in services."""
from backend.migrations.schema_v1 import build_metadata
from backend.migrations.course_schema import extend

from backend.migrations.password_schema import extend as extend_password

CURRENT_REVISION='password_0004'
metadata = extend_password(extend(build_metadata()))
users = metadata.tables['users']
roles = metadata.tables['roles']
role_assignments = metadata.tables['role_assignments']
auth_sessions = metadata.tables['auth_sessions']
audit_events = metadata.tables['audit_events']
