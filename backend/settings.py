"""Explicit non-secret application settings. No automatic .env loading."""
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    database_path: Path
    public_origin: str

    def __post_init__(self):
        origin = urlsplit(self.public_origin)
        if (not origin.hostname or origin.username or origin.password or origin.query or origin.fragment
                or origin.path not in ('', '/') or origin.scheme not in ('http', 'https')):
            raise ValueError('HRMS_PUBLIC_ORIGIN must be a bare origin')
        if origin.scheme == 'http' and origin.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('Public application access requires HTTPS')
        path = self.database_path.resolve()
        if path.is_relative_to(ROOT / 'frontend') or path.suffix not in ('.sqlite3', '.sqlite', '.db'):
            raise ValueError('Use a private SQLite path outside frontend')
        object.__setattr__(self, 'database_path', path)
        host = origin.hostname.lower()
        host = '[' + host + ']' if ':' in host else host
        port = origin.port
        suffix = ':' + str(port) if port is not None and port != (443 if origin.scheme == 'https' else 80) else ''
        object.__setattr__(self, 'public_origin', origin.scheme + '://' + host + suffix)

    @classmethod
    def from_env(cls):
        return cls(Path(os.environ.get('HRMS_DATABASE_PATH', ROOT / 'var/hrms/app.sqlite3')),
                   os.environ.get('HRMS_PUBLIC_ORIGIN', 'http://127.0.0.1:3000'))
