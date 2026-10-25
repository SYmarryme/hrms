from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 25, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, **kwargs):
        self.value += timedelta(**kwargs)


def migrate(settings):
    config = Config(str(ROOT / 'backend/alembic.ini'))
    config.attributes['settings'] = settings
    command.upgrade(config, 'head')


@pytest.fixture
def system(tmp_path):
    settings = Settings(tmp_path / 'identity.sqlite3', 'https://hrms.test')
    migrate(settings)
    clock = Clock()
    app = create_app(settings, clock)
    password = secrets.token_urlsafe(24)
    user_id = app.state.auth.bootstrap_admin('initial-admin', password)
    with TestClient(app, base_url=settings.public_origin, headers={'Origin': settings.public_origin}) as client:
        yield app, client, clock, password, user_id, settings


def sign_in(client, password):
    response = client.post('/api/v1/auth/login', json={'username': 'initial-admin', 'password': password})
    assert response.status_code == 200
    return response.json()['data']['access_token']
