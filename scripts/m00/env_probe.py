"""Print tool versions only; never dump environment variables or credentials."""
import importlib.metadata
import json
import platform
import sqlite3
import sys

errors = []
report = {
    'platform': platform.system(),
    'architecture': platform.machine(),
    'python': platform.python_version(),
    'sqlite_python': sqlite3.sqlite_version,
    'packages': {},
}
if sys.version_info < (3, 11):
    errors.append('Python >=3.11 required by this PoC; provisional target')
for package in ('pip', 'SQLAlchemy', 'alembic', 'pytest'):
    try:
        report['packages'][package] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        errors.append(f'Missing package: {package}')
report['errors'] = errors
print(json.dumps(report, indent=2))
sys.exit(bool(errors))
