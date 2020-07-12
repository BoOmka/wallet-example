import typing as t
from unittest import mock
from unittest.mock import _CallList


class AsyncContextManagerMock(mock.MagicMock):
    async def __aenter__(self):
        return self.aenter

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def async_mock(*args, **kwargs):
    m = mock.MagicMock(*args, **kwargs)

    async def mock_coro(*inner_args, **inner_kwargs):
        return m(*inner_args, **inner_kwargs)

    mock_coro.mock = m
    return mock_coro


def get(client, url, *args, **kwargs):
    delimiter = '&' if '?' in url else '?'
    return client.get(f'{url}{delimiter}args=a&kwargs=b', *args, **kwargs)


def post(client, url, *args, **kwargs):
    delimiter = '&' if '?' in url else '?'
    return client.post(f'{url}{delimiter}args=a&kwargs=b', *args, **kwargs)


def compile_sql_statement(sql_statement) -> str:
    return str(sql_statement.compile(compile_kwargs={"literal_binds": True}))


def call_args_to_sql_strings(call_args_list: _CallList) -> t.List[str]:
    return [compile_sql_statement(call.args[0]) for call in call_args_list]
