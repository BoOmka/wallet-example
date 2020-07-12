import databases
from fastapi import FastAPI
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTAuthentication
from fastapi_users.db import SQLAlchemyUserDatabase

import config
import models
import tables


def setup_auth(app: FastAPI, database: databases.Database):
    user_db = SQLAlchemyUserDatabase(models.UserDB, database, tables.users)
    jwt_authentication = JWTAuthentication(
        secret=config.JWT_SECRET, lifetime_seconds=config.JWT_LIFETIME, tokenUrl="/auth/jwt/login"
    )
    fastapi_users = FastAPIUsers(
        user_db, [jwt_authentication], models.User, models.UserCreate, models.UserUpdate, models.UserDB,
    )
    app.include_router(
        fastapi_users.get_auth_router(jwt_authentication), prefix="/auth/jwt", tags=["auth"]
    )
    app.include_router(
        fastapi_users.get_register_router(), prefix="/auth", tags=["auth"]
    )
    app.include_router(
        fastapi_users.get_reset_password_router(config.JWT_SECRET),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(fastapi_users.get_users_router(), prefix="/users", tags=["users"])
    return fastapi_users
