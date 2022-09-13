import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from netunicorn.director.base.resources import get_logger, redis_connection

logger = get_logger('netunicorn.director.authorization')

app = FastAPI()

USERS = {
    "simpleuser": "JbsbLIG8b4aMbnan",
    "jiamo": "nmUBa4bab204Bggas",
}


class AuthorizationRequest(BaseModel):
    username: str
    token: str


@app.get('/health')
async def health_check() -> str:
    await redis_connection.ping()
    return 'OK'


@app.post("/auth", status_code=200)
async def auth(data: AuthorizationRequest):
    if data.username in USERS and USERS[data.username] == data.token:
        return

    raise HTTPException(
        status_code=401,
        detail="Incorrect username or token",
        headers={"WWW-Authenticate": "Basic"}
    )


if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=26516)
