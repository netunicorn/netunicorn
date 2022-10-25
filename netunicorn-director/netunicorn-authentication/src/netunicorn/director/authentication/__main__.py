from typing import Optional

import uvicorn
import asyncpg

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from netunicorn.director.base.resources import get_logger, \
    DATABASE_ENDPOINT, DATABASE_USER, DATABASE_PASSWORD, DATABASE_DB

logger = get_logger('netunicorn.director.authentication')

app = FastAPI()
db_conn_pool: Optional[asyncpg.Pool] = None


class AuthenticationRequest(BaseModel):
    username: str
    token: str


@app.get('/health')
async def health_check() -> str:
    await db_conn_pool.fetchval('SELECT 1')
    return 'OK'


@app.on_event("startup")
async def startup():
    global db_conn_pool
    db_conn_pool = await asyncpg.create_pool(
        user=DATABASE_USER, password=DATABASE_PASSWORD,
        database=DATABASE_DB, host=DATABASE_ENDPOINT
    )


@app.on_event("shutdown")
async def shutdown():
    await db_conn_pool.close()


@app.post("/auth", status_code=200)
async def auth(data: AuthenticationRequest):
    sql_query = 'SELECT EXISTS(SELECT 1 FROM authentication WHERE username = $1 AND token = $2)'
    if await db_conn_pool.fetchval(sql_query, data.username, data.token):
        return

    raise HTTPException(
        status_code=401,
        detail="Incorrect username or token",
        headers={"WWW-Authenticate": "Basic"}
    )


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=26516)
