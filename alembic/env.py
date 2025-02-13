from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlalchemy import pool
import os

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")

db_url = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'

config = context.config
config.set_main_option("sqlalchemy.url",db_url)


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(db_url)
    # engine_from_config(
    #     config.get_section(config.config_ini_section, {}),
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=None
        )
        with context.begin_transaction():
            context.run_migrations()


# if context.is_offline_mode():
#     run_migrations_offline()
# else:
run_migrations_online()
