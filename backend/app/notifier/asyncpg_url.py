from typing import Any

from sqlalchemy.engine.url import make_url


def asyncpg_connect_kwargs(database_url: str) -> dict[str, Any]:
    url = make_url(database_url)
    return {
        "host": url.host,
        "port": url.port or 5432,
        "user": url.username,
        "password": url.password or "",
        "database": url.database,
    }
