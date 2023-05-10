import os
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

app = FastAPI()
db_conn_pool: asyncpg.Pool


class AuthenticationRequest(BaseModel):
    username: str
    token: str


@app.get("/health")
async def health_check() -> str:
    await db_conn_pool.fetchval("SELECT 1")
    return "OK"


@app.on_event("startup")
async def startup() -> None:
    global db_conn_pool
    db_conn_pool = await asyncpg.create_pool(
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        database=DATABASE_DB,
        host=DATABASE_ENDPOINT,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    await db_conn_pool.close()


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


if __name__ == "__main__":
    ip = os.environ.get("NETUNICORN_AUTHENTICATION_IP", "0.0.0.0")
    port = int(os.environ.get("NETUNICORN_AUTHENTICATION_PORT", "26516"))
    logger.info(f"Starting gateway on {ip}:{port}")
    uvicorn.run(app, host=ip, port=port)
