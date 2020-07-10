import databases
import uvicorn
from fastapi import FastAPI

import config
from auth import setup_auth


database = databases.Database(config.POSTGRES_DSN)

app = FastAPI()
fastapi_users = setup_auth(app, database)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8080)
