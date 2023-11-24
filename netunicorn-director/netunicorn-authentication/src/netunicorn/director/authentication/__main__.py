import os
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg
import bcrypt
import uvicorn
from fastapi import FastAPI, HTTPException
from netunicorn.director.base.resources import (
    DATABASE_DB,
    DATABASE_ENDPOINT,
    DATABASE_PASSWORD,
    DATABASE_USER,
    get_logger,
)
from pydantic import BaseModel

logger = get_logger("netunicorn.director.authentication")


@asynccontextmanager
async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
    global db_conn_pool
    db_conn_pool = await asyncpg.create_pool(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        host=DATABASE_ENDPOINT,
    )
    yield
    await db_conn_pool.close()


app = FastAPI(lifespan=lifespan)
db_conn_pool: asyncpg.Pool


class AuthenticationRequest(BaseModel):
    username: str
    token: str


@app.get("/health")
async def health_check() -> str:
    await db_conn_pool.fetchval("SELECT 1")
    return "OK"


@app.post("/auth", status_code=200)
async def auth(data: AuthenticationRequest) -> None:
    sql_query = "SELECT hash FROM authentication WHERE username = $1"
    result: Optional[str] = await db_conn_pool.fetchval(sql_query, data.username)
    if result is not None:
        if bcrypt.checkpw(data.token.encode(), result.encode()):
            return

    raise HTTPException(
        status_code=401,
        detail="Incorrect username or token",
        headers={"WWW-Authenticate": "Basic"},
    )


@app.get("/verify_sudo", status_code=200)
async def verify_sudo(username: str) -> bool:
    sql_query = "SELECT sudo FROM authentication WHERE username = $1"
    result: Optional[bool] = bool(await db_conn_pool.fetchval(sql_query, username))
    return result


if __name__ == "__main__":
    ip = os.environ.get("NETUNICORN_AUTHENTICATION_IP", "0.0.0.0")
    port = int(os.environ.get("NETUNICORN_AUTHENTICATION_PORT", "26516"))
    logger.info(f"Starting gateway on {ip}:{port}")

    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"][
        "fmt"
    ] = "%(asctime)s - %(levelname)s - %(message)s"
    log_config["formatters"]["default"][
        "fmt"
    ] = "%(asctime)s - %(levelname)s - %(message)s"

    uvicorn.run(app, host=ip, port=port)
