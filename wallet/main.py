import asyncio
import datetime
import typing as t

import databases
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic.types import UUID4
from starlette.responses import RedirectResponse, StreamingResponse
from starlette.staticfiles import StaticFiles

import adapters
import config
import enums
import models
from auth import setup_auth
from services import make_csv_stream, make_filename


db = databases.Database(config.POSTGRES_DSN)

app = FastAPI()
fastapi_users = setup_auth(app, db)
wallet_db_adapter = adapters.WalletDatabaseAdapter(models.WalletDB, db, models.wallets)
transaction_db_adapter = adapters.TransactionDatabaseAdapter(models.TransactionDB, db, models.transactions)

app.mount('/static', StaticFiles(directory='static'), name='static')


def make_simple_error_message(msg: str, **kwargs) -> t.List[t.Dict[str, t.Any]]:
    kwargs = kwargs.copy()
    kwargs['msg'] = msg
    return [kwargs]


@app.get('/docs', include_in_schema=False)
async def custom_swagger_ui_html():  # pragma: no cover
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + ' - Swagger UI',
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url='/static/swagger-ui-bundle.js',
        swagger_css_url='/static/swagger-ui.css',
    )


@app.get('/', include_in_schema=False)
async def root():  # pragma: no cover
    return RedirectResponse('/docs')


@app.post(
    '/wallet',
    summary='Create wallet',
    response_model=models.WalletId,
    responses={409: {'model': models.ErrorDetails}},
)
async def create_wallet(
        wallet_create: models.WalletCreate,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    try:
        new_wallet_id = await wallet_db_adapter.create(wallet_create, user.id)
    except ValueError:
        raise HTTPException(status_code=409, detail='Wallet with this name already exists')
    return models.WalletId(
        id=new_wallet_id,
    )


@app.get(
    '/wallet',
    summary='Get wallet list',
    response_model=models.WalletList,
)
async def get_wallets(user: models.User = Depends(fastapi_users.get_current_user)):
    wallets = await wallet_db_adapter.get_many(user_id=user.id)
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
        wallet_id: UUID4,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    wallet = await wallet_db_adapter.get(wallet_id=wallet_id)
    if not wallet:
        raise HTTPException(
            status_code=404,
            detail=make_simple_error_message('Wallet does not exist', entity='wallet'),
        )
    if wallet.user_id != user.id:
        raise HTTPException(status_code=403, detail=make_simple_error_message('User does not own the wallet'))
    return wallet


@app.post(
    '/wallet/{wallet_id}/deposit',
    summary='Deposit funds to wallet',
    response_model=models.WalletValueBalance,
    responses={404: {'model': models.ErrorDetails}},
)
async def deposit_to_wallet(
        wallet_id: UUID4,
        wallet_deposit: models.WalletDeposit,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    now = datetime.datetime.utcnow()
    async with db.transaction():
        wallet = await wallet_db_adapter.lock(wallet_id)
        if not wallet:
            raise HTTPException(
                status_code=404,
                detail=make_simple_error_message('Wallet does not exist', entity='wallet'),
            )
        new_balance = await wallet_db_adapter.increase_balance(wallet_id, wallet_deposit.value)
        await transaction_db_adapter.create(models.TransactionDB(
            recipient_wallet_id=wallet_id,
            value=wallet_deposit.value,
            timestamp=now,
        ))
    if wallet.user_id == user.id:
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
        wallet_id: UUID4,
        recipient_wallet_id: UUID4,
        wallet_transfer: models.WalletTransfer,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    now = datetime.datetime.utcnow()
    if wallet_id == recipient_wallet_id:
        raise HTTPException(status_code=400, detail='Cannot transfer to self')
    async with db.transaction():
        sender_wallet, recipient_wallet = await asyncio.gather(
            wallet_db_adapter.lock(wallet_id),
            wallet_db_adapter.lock(recipient_wallet_id),
        )
        if not sender_wallet:
            raise HTTPException(
                status_code=404,
                detail=make_simple_error_message('Sender wallet does not exist', entity='sender_wallet'),
            )
        if sender_wallet.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail=make_simple_error_message('User does not own the sender wallet'),
            )
        if sender_wallet.balance < wallet_transfer.value:
            raise HTTPException(status_code=400, detail=make_simple_error_message('Insufficient funds'))
        if not recipient_wallet:
            raise HTTPException(
                status_code=404,
                detail=make_simple_error_message('Recipient wallet does not exist', entity='recipient_wallet'),
            )

        new_balance, _, _ = await asyncio.gather(
            wallet_db_adapter.decrease_balance(wallet_id, wallet_transfer.value),
            wallet_db_adapter.increase_balance(recipient_wallet_id, wallet_transfer.value),
            transaction_db_adapter.create(models.TransactionDB(
                sender_wallet_id=wallet_id,
                recipient_wallet_id=recipient_wallet_id,
                value=wallet_transfer.value,
                timestamp=now,
            )),
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
        wallet_id: UUID4,
        from_timestamp: datetime.datetime = None,
        to_timestamp: datetime.datetime = None,
        side: enums.TransferSide = None,
        user: models.User = Depends(fastapi_users.get_current_user),
):
    wallet = await wallet_db_adapter.get(wallet_id)
    if not wallet:
        raise HTTPException(
            status_code=404,
            detail=make_simple_error_message('Wallet does not exist', entity='wallet'),
        )
    if wallet.user_id != user.id:
        raise HTTPException(status_code=403, detail=make_simple_error_message('User does not own the wallet'))

    transactions = await transaction_db_adapter.get_many(
        wallet_id=wallet_id,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        transfer_side=side,
    )

    io = make_csv_stream(transactions)
    filename = make_filename(wallet_id, from_timestamp, to_timestamp, side)

    return StreamingResponse(
        io,
        media_type='text/csv',
        headers={
            'Content-Disposition': f'attachment;filename={filename}'
        }
    )


@app.on_event("startup")
async def startup():  # pragma: no cover
    await db.connect()


@app.on_event("shutdown")
async def shutdown():  # pragma: no cover
    await db.disconnect()


if __name__ == '__main__':  # pragma: no cover
    uvicorn.run(app, host='0.0.0.0', port=8080)
