from typing import Optional

import uvicorn
import asyncpg

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from netunicorn.director.base.resources import get_logger, \
    DATABASE_ENDPOINT, DATABASE_USER, DATABASE_PASSWORD, DATABASE_DB

logger = get_logger('netunicorn.director.authentication')

app = FastAPI()
db_conn: Optional[asyncpg.connection.Connection] = None

USERS = {
    "simpleuser": "JbsbLIG8b4aMbnan",
    "jiamo": "nmUBa4bab204Bggas",
}


class AuthenticationRequest(BaseModel):
    username: str
    token: str


@app.get('/health')
async def health_check() -> str:
    await db_conn.get_server_version()
    return 'OK'


@app.on_event("startup")
async def startup():
    global db_conn
    db_conn = await asyncpg.connect(
        user=DATABASE_USER, password=DATABASE_PASSWORD,
        database=DATABASE_DB, host=DATABASE_ENDPOINT
    )


@app.on_event("shutdown")
async def shutdown():
    await db_conn.close()


@app.post("/auth", status_code=200)
async def auth(data: AuthenticationRequest):
    if data.username in USERS and USERS[data.username] == data.token:
        return

    raise HTTPException(
        status_code=401,
        detail="Incorrect username or token",
        headers={"WWW-Authenticate": "Basic"}
    )


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=26516)
