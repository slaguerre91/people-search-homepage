"""Database URL helpers."""


def normalize_database_url(database_url: str) -> str:
    """Return a SQLAlchemy async URL for PostgreSQL connection strings."""
    database_url = database_url.strip()

    if database_url.startswith("postgres://"):
        return f"postgresql+asyncpg://{database_url[len('postgres://'):]}"

    if database_url.startswith("postgresql://"):
        return f"postgresql+asyncpg://{database_url[len('postgresql://'):]}"

    return database_url
