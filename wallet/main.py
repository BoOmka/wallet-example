import decimal
import uuid

import databases
import uvicorn
from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

import config
import models
from auth import setup_auth


db = databases.Database(config.POSTGRES_DSN)

app = FastAPI()
fastapi_users = setup_auth(app, db)

app.mount('/static', StaticFiles(directory='./static'), name='static')


@app.get('/docs', include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + ' - Swagger UI',
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url='/static/swagger-ui-bundle.js',
        swagger_css_url='/static/swagger-ui.css',
    )


@app.get('/', include_in_schema=False)
async def root():
    return RedirectResponse('/docs')


@app.post('/wallet/create', response_model=models.WalletId)
async def create_wallet(
        wallet_create: models.WalletCreate,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    async with db.transaction():
        wallet_id = await db.fetch_val(models.wallets.insert(values={
            'id': uuid.uuid4(),
            'user_id': user.id,
            'name': wallet_create.name,
            'balance': decimal.Decimal(0),
        }).returning(models.wallets.c.id))
    return models.WalletId(
        id=wallet_id,
    )


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8080)
