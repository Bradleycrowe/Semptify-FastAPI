"""
Alembic Environment Configuration
Configured for SQLAlchemy with Semptify models.
"""

from logging.config import fileConfig

from sqlalchemy import pool, engine_from_config
from sqlalchemy.engine import Connection

from alembic import context

# Import your models and Base
from app.core.database import Base
from app.models.models import (
    User, 
    LinkedProvider,
    Document,
    TimelineEvent,
    RentPayment,
    CalendarEvent,
    Complaint,
    WitnessStatement,
    CertifiedMail,
    Session,
    StorageConfig,
    FraudAnalysisResult,
    PressReleaseRecord,
    ResearchProfile,
    Contact,
    ContactInteraction,
)
from app.core.config import get_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set sqlalchemy.url from settings
settings = get_settings()
# Convert async driver to sync for Alembic
sync_url = settings.database_url
if "+aiosqlite" in sync_url:
    sync_url = sync_url.replace("+aiosqlite", "")
elif "+asyncpg" in sync_url:
    sync_url = sync_url.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", sync_url)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine,
    useful for generating SQL scripts without database access.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using sync engine."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
