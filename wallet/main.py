import asyncio
import datetime
import decimal
import uuid

import asyncpg
import databases
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from sqlalchemy import and_
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


@app.post(
    '/wallet/create',
    summary='Create wallet',
    response_model=models.WalletId,
    responses={409: {'model': models.ErrorDetails}},
)
async def create_wallet(
        wallet_create: models.WalletCreate,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    try:
        async with db.transaction():
            wallet_id = await db.fetch_val(models.wallets.insert(values={
                'id': uuid.uuid4(),
                'user_id': user.id,
                'name': wallet_create.name,
                'balance': decimal.Decimal(0),
            }).returning(models.wallets.c.id))
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail='Wallet with this name already exists')
    return models.WalletId(
        id=wallet_id,
    )


@app.get(
    '/wallet',
    summary='Get wallet list',
    response_model=models.WalletList,
)
async def get_wallets(user: models.User = Depends(fastapi_users.get_current_user)):
    async with db.transaction():
        wallets = await db.fetch_all(
            models.wallets.select(
                models.wallets.c.user_id == user.id,
            ).with_only_columns([
                models.wallets.c.id,
                models.wallets.c.name,
            ])
        )
        return models.WalletList(
            wallets=wallets
        )


@app.get(
    '/wallet/{wallet_id}',
    summary='Get specific wallet',
    response_model=models.Wallet,
    responses={404: {'model': models.ErrorDetails}},
)
async def get_wallet(
        wallet_id: uuid.UUID,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    async with db.transaction():
        wallet = await db.fetch_one(
            models.wallets.select(
                and_(
                    models.wallets.c.id == wallet_id,
                    models.wallets.c.user_id == user.id
                )
            ).with_only_columns([
                models.wallets.c.id,
                models.wallets.c.name,
                models.wallets.c.balance,
            ])
        )
        if not wallet:
            raise HTTPException(status_code=404, detail='Wallet does not exist or user does not own it')
        return wallet


@app.post(
    '/wallet/{wallet_id}/deposit',
    summary='Deposit funds to wallet',
    response_model=models.WalletBalance,
    responses={404: {'model': models.ErrorDetails}},
)
async def deposit_to_wallet(
        wallet_id: uuid.UUID,
        wallet_deposit: models.WalletDeposit,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    now = datetime.datetime.utcnow()
    async with db.transaction():
        wallet = bool(await db.fetch_val(
            models.wallets.select(
                and_(
                    models.wallets.c.id == wallet_id,
                    models.wallets.c.user_id == user.id
                ),
                for_update=True,
            ).with_only_columns([
                models.wallets.c.id,
            ])
        ))
        if not wallet:
            raise HTTPException(status_code=404, detail='Wallet does not exist or user does not own it')
        await db.execute(
            models.wallets.update(
                models.wallets.c.id == wallet_id
            ).values(
                balance=models.wallets.c.balance + wallet_deposit.value
            )
        )
        await db.execute(models.transactions.insert(values={
            'recipient_wallet_id': wallet_id,
            'value': wallet_deposit.value,
            'timestamp': now
        }))
        new_balance = await db.fetch_val(
            models.wallets.select(
                models.wallets.c.id == wallet_id,
            ).with_only_columns([
                models.wallets.c.balance,
            ])
        )
    return models.WalletBalance(
        balance=new_balance,
    )


@app.post(
    '/wallet/{wallet_id}/transfer-to/{recipient_wallet_id}',
    summary='Transfer funds from one wallet to another',
    response_model=models.WalletBalance,
    responses={400: {'model': models.ErrorDetails}, 404: {'model': models.ErrorDetails}},
)
async def transfer(
        wallet_id: uuid.UUID,
        recipient_wallet_id: uuid.UUID,
        wallet_transfer: models.WalletTransfer,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    now = datetime.datetime.utcnow()
    async with db.transaction():
        sender_wallet = await db.fetch_one(
            models.wallets.select(
                and_(
                    models.wallets.c.id == wallet_id,
                    models.wallets.c.user_id == user.id,
                ),
                for_update=True,
            ).with_only_columns([
                models.wallets.c.id,
                models.wallets.c.balance,
            ])
        )
        if not sender_wallet:
            raise HTTPException(status_code=404, detail='Sender wallet does not exist or user does not own it')
        if sender_wallet['balance'] < wallet_transfer.value:
            raise HTTPException(status_code=400, detail='Insufficient funds')

        recipient_wallet = await db.fetch_one(
            models.wallets.select(
                models.wallets.c.id == recipient_wallet_id,
                for_update=True,
            ).with_only_columns([
                models.wallets.c.id,
                models.wallets.c.balance,
            ])
        )
        if not recipient_wallet:
            raise HTTPException(status_code=404, detail='Recipient wallet does not exist')

        await asyncio.gather(
            db.execute(
                models.wallets.update(
                    models.wallets.c.id == wallet_id
                ).values(
                    balance=models.wallets.c.balance - wallet_transfer.value,
                )
            ),
            db.execute(
                models.wallets.update(
                    models.wallets.c.id == recipient_wallet_id
                ).values(
                    balance=models.wallets.c.balance + wallet_transfer.value,
                )
            ),
            db.execute(models.transactions.insert(values={
                'sender_wallet_id': wallet_id,
                'recipient_wallet_id': recipient_wallet_id,
                'value': wallet_transfer.value,
                'timestamp': now,
            }))
        )
        new_balance = await db.fetch_val(
            models.wallets.select(
                models.wallets.c.id == wallet_id,
            ).with_only_columns([
                models.wallets.c.balance,
            ])
        )
    return models.WalletBalance(
        balance=new_balance,
    )


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8080)
