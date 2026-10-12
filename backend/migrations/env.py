from alembic import context

from chorus import models  # noqa: F401  (registers the tables on Base.metadata)
from chorus.db import Base, get_engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_engine().url.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
