from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from chorus.db import Base, get_engine

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def test_migrations_build_the_same_schema_as_the_models():
    Base.metadata.drop_all(get_engine())
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    with get_engine().connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []
