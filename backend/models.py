"""Current SQLAlchemy table models; synchronous Session transactions in services."""
from backend.migrations.schema_v1 import build_metadata

metadata = build_metadata()
users = metadata.tables['users']
roles = metadata.tables['roles']
role_assignments = metadata.tables['role_assignments']
auth_sessions = metadata.tables['auth_sessions']
audit_events = metadata.tables['audit_events']
