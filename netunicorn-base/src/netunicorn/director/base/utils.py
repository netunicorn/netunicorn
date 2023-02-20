import json

import asyncpg
from netunicorn.base.utils import UnicornEncoder


async def __init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=lambda x: json.dumps(x, cls=UnicornEncoder),
        decoder=json.loads,
        schema="pg_catalog",
    )
