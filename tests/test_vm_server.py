import pytest
import asyncpg
from asyncpg import Pool
from asyncpg.pool import PoolConnectionProxy
from unittest.mock import MagicMock, AsyncMock, patch

import pytest_asyncio

from src.server.server import VMServer

@pytest_asyncio.fixture
async def db_pool():
    pool = await asyncpg.create_pool(
        user="test_user",
        password="test_password",
        database="test_db",
        host="localhost",
        port=5432,
    )
    yield pool
    await pool.close()

@pytest_asyncio.fixture
async def server(db_pool):
    return VMServer(db_pool)


@pytest.mark.asyncio
@pytest.mark.parametrize("login, password", [
    ("test1", "pass1"),
    ("test2", "pass2"),
    ("test3", "pass3"),
    ("test4", "pass4"),
    ("test5", "pass5")
])
async def test_add_user_real_db(server: VMServer, db_pool: Pool, login, password):
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE login = $1", login)

    writer_mock = AsyncMock()
    await server.add_user(login, password, writer_mock)

    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT login FROM users WHERE login = $1", login)
        password_hash = await conn.fetchrow("SELECT password_hash FROM users WHERE login = $1", login)

    assert user is not None
    assert password_hash is not None
    assert user["login"] == login
    writer_mock.write.assert_called_once_with(f"User {login} created successfully\n".encode())

@pytest.mark.asyncio
async def test_list_users(server: VMServer, db_pool: Pool):
    writer_mock = AsyncMock()
    await server.list_users(writer_mock)

    assert writer_mock.write.call_count == 1

    users = ["test1", "test2", "test3", "test4", "test5"]
    called_args = writer_mock.write.call_args_list[0][0][0].decode()

    for user in users:
        assert user in called_args


@pytest.mark.asyncio
@pytest.mark.parametrize("login, password", [
    ("test1", "pass1"),
    ("test2", "pass2"),
    ("test3", "pass3"),
    ("test4", "pass4"),
    ("test5", "pass5")
])
async def test_authenticate(server: VMServer, db_pool: Pool, login, password):
    with patch("src.server.server.logger") as logger_mock:
        result = await server.authenticate(login, password)
        assert result is True
        logger_mock.info.assert_called_with("Authentication successful for %s", login)


@pytest.mark.asyncio
@pytest.mark.parametrize("ram, cpu, disk_size", [
    (1024, 16, 2048),
    (2048, 32, 4096),
    (1024, 32, 8192)
])
async def test_add_vm(server: VMServer, db_pool: Pool, ram, cpu, disk_size):
    async with db_pool.acquire() as connect:
        await connect.execute("DELETE FROM virtual_machines")
    write_mock = AsyncMock()
    await server.add_vm(ram, cpu, disk_size, write_mock)


