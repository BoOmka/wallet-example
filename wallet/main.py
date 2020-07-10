import asyncio
import csv
import datetime
import decimal
import uuid
from io import StringIO

import asyncpg
import databases
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from sqlalchemy import and_, or_
from starlette.responses import RedirectResponse, StreamingResponse
from starlette.staticfiles import StaticFiles

import config
import enums
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
    responses={
        403: {'model': models.ErrorDetails},
        404: {'model': models.ErrorDetails},
    },
)
async def get_wallet(
        wallet_id: uuid.UUID,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    wallet = await db.fetch_one(
        models.wallets.select(
            models.wallets.c.id == wallet_id,
        )
    )
    if not wallet:
        raise HTTPException(status_code=404, detail='Wallet does not exist')
    if wallet['user_id'] != user.id:
        raise HTTPException(status_code=403, detail='User does not own the wallet')
    return models.Wallet(**wallet)


@app.post(
    '/wallet/{wallet_id}/deposit',
    summary='Deposit funds to wallet',
    response_model=models.WalletValueBalance,
    responses={404: {'model': models.ErrorDetails}},
)
async def deposit_to_wallet(
        wallet_id: uuid.UUID,
        wallet_deposit: models.WalletDeposit,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    now = datetime.datetime.utcnow()
    async with db.transaction():
        wallet = await db.fetch_one(
            models.wallets.select(
                models.wallets.c.id == wallet_id,
                for_update=True,
            ).with_only_columns([
                models.wallets.c.id,
                models.wallets.c.user_id,
            ])
        )
        if not wallet:
            raise HTTPException(status_code=404, detail='Wallet does not exist')
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
        if wallet['user_id'] == user.id:
            new_balance = await db.fetch_val(
                models.wallets.select(
                    models.wallets.c.id == wallet_id,
                ).with_only_columns([
                    models.wallets.c.balance,
                ])
            )
            return models.WalletValueBalance(
                value=wallet_deposit.value,
                balance=new_balance,
            )
        else:
            return models.WalletValueBalance(
                value=wallet_deposit.value,
            )


@app.post(
    '/wallet/{wallet_id}/transfer-to/{recipient_wallet_id}',
    summary='Transfer funds from one wallet to another',
    response_model=models.WalletValueBalance,
    responses={
        400: {'model': models.ErrorDetails},
        403: {'model': models.ErrorDetails},
        404: {'model': models.ErrorDetails},
    },
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
                models.wallets.c.id == wallet_id,
                for_update=True,
            ).with_only_columns([
                models.wallets.c.id,
                models.wallets.c.user_id,
                models.wallets.c.balance,
            ])
        )
        if not sender_wallet:
            raise HTTPException(status_code=404, detail='Sender wallet does not exist')
        if sender_wallet['user_id'] != user.id:
            raise HTTPException(status_code=403, detail='User does not own the sender wallet')
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
    return models.WalletValueBalance(
        value=wallet_transfer.value,
        balance=new_balance,
    )


@app.get(
    '/wallet/{wallet_id}/operations',
    summary='Get wallet operations',
    response_class=StreamingResponse,
    responses={
        200: {'content': {'text/csv': {}}},
        403: {'model': models.ErrorDetails},
        404: {'model': models.ErrorDetails}
    },
)
async def get_wallet_operations(
        wallet_id: uuid.UUID,
        from_timestamp: datetime.datetime = None,
        to_timestamp: datetime.datetime = None,
        side: enums.TransferSide = None,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    wallet = await db.fetch_one(
        models.wallets.select(
            models.wallets.c.id == wallet_id,
        ).with_only_columns([
            models.wallets.c.id,
            models.wallets.c.user_id,
        ])
    )
    if not wallet:
        raise HTTPException(status_code=404, detail='Wallet does not exist')
    if wallet['user_id'] != user.id:
        raise HTTPException(status_code=403, detail='User does not own the wallet')

    and_conditions = []
    filename_suffixes = [str(wallet_id)]
    if not side:
        and_conditions.append(or_(
            models.transactions.c.sender_wallet_id == wallet_id,
            models.transactions.c.recipient_wallet_id == wallet_id,
        ))
        filename_suffixes.append('both')
    elif side is enums.TransferSide.deposit:
        and_conditions.append(models.transactions.c.recipient_wallet_id == wallet_id)
        filename_suffixes.append(side.value)
    elif side is enums.TransferSide.withdraw:
        and_conditions.append(models.transactions.c.sender_wallet_id == wallet_id)
        filename_suffixes.append(side.value)
    if from_timestamp:
        and_conditions.append(models.transactions.c.timestamp >= from_timestamp)
        filename_suffixes.append('from' + str(from_timestamp).replace(' ', '_'))
    if to_timestamp:
        and_conditions.append(models.transactions.c.timestamp >= to_timestamp)
        filename_suffixes.append('to' + str(to_timestamp).replace(' ', '_'))
    transactions = await db.fetch_all(
        models.transactions.select(and_(
            *and_conditions
        )).with_only_columns([
            models.transactions.c.sender_wallet_id,
            models.transactions.c.recipient_wallet_id,
            models.transactions.c.value,
            models.transactions.c.timestamp,
        ]).order_by(models.transactions.c.timestamp)
    )

    io = StringIO()
    writer = csv.DictWriter(io, fieldnames=('sender_wallet_id', 'recipient_wallet_id', 'value', 'timestamp'))
    writer.writeheader()
    for transaction in transactions:
        transaction = dict(transaction)
        if not transaction['sender_wallet_id']:
            transaction['sender_wallet_id'] = 'EXTERNAL_DEPOSIT'
        writer.writerow(transaction)
    io.seek(0)

    filename_suffix = '-'.join(filename_suffixes)
    filename = f'export-{filename_suffix}.csv'

    return StreamingResponse(
        io,
        media_type='text/csv',
        headers={
            'Content-Disposition': f'attachment;filename={filename}'
        }
    )



@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8080)
