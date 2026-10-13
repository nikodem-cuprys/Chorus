"""Unit tests run without Docker: SQLite instead of PostgreSQL, Celery tasks run in-process,
and published events are collected in a list instead of going to Redis.

The tests in `integration/` run against the real Compose stack instead.
"""

import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="chorus-test-"))
os.environ.setdefault("CHORUS_DATABASE_URL", f"sqlite:///{(_tmp / 'test.db').as_posix()}")
os.environ.setdefault("CHORUS_DEV", "true")
os.environ.setdefault("CHORUS_FRONTEND_DIST", str(_tmp / "no-frontend"))
os.environ.setdefault("CHORUS_DATA_DIR", str(_tmp / "data"))

import pytest  # noqa: E402

from chorus import events  # noqa: E402
from chorus.db import Base, get_engine  # noqa: E402
from chorus.jobs import celery_app  # noqa: E402

celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = False


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    yield


@pytest.fixture(autouse=True)
def published(monkeypatch) -> list[dict]:
    sent: list[dict] = []
    monkeypatch.setattr(
        events, "publish", lambda event, data: sent.append({"event": event, **data})
    )
    return sent
