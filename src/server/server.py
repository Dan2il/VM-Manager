
import logging
import asyncio
import asyncpg
import bcrypt
import traceback

from asyncio import StreamReader, StreamWriter
from asyncpg import Pool

from uuid import uuid4

from src.server import setting
from src.server.virtual_machine import VirtualMachine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
           '[%(filename)s:%(lineno)d - %(funcName)s]'
)

logger = logging.getLogger()



class VMServer:

    def __init__(self, db_pool):
        self.db_pool: Pool = db_pool
        """Пул соединений с базой данных"""
        self.connected_vms: dict[uuid4, VirtualMachine] = {}
        """
        Словарь, хранит id и объект подключенной виртуальной машины
        """

        self.authenticated_vms: set[uuid4] = set()
        """
        Хранит успешно авторизированных VM
        
        Нужно, для проверки, что виртуальная машина может выполнять определенные команды
        """

        self.all_connected_vms: dict[uuid4, VirtualMachine] = {}
        """
        Хранит все когда-либо подключенные VM
        Словарь, хранит id и объект подключенной виртуальной машины
        """

    async def connect_client(self, reader: StreamReader, writer: StreamWriter):
        address = writer.get_extra_info("peername")
        logger.info(f"New connection: {address}")

        try:
            while True:
                try:
                    data = await asyncio.wait_for(reader.read(setting.MESSAGE_LIMIT),
                                                  timeout=setting.TIMEOUT_SERVER)
                    if not data:
                        logger.info(f"Client {address} disconnected.")
                        break
                except asyncio.TimeoutError:
                    logger.error("Timeout waiting for data from client")
                    break

                message = data.decode().strip().split()
                logger.info(f"Message: {message}, from {address}")

                try:
                    if "ADD_USER" in message[0] and len(message) == 3:
                        login, password = message[1], message[2]
                        await self.add_user(login, password, writer)
                    elif "AUTH" in message[0] and len(message) == 4:
                        vm_id, login, password = message[1], message[2], message[3]
                        if await self.authenticate(login, password):
                            self.authenticated_vms.add(vm_id)
                            writer.write(b"AUTHENTICATE_SUCCESS\n")
                        else:
                            writer.write(b"AUTHENTICATE_FAIL\n")
                        await writer.drain()
                    else:
                        writer.write(b"UNKNOWN_COMMAND\n")
                    await writer.drain()
                except Exception as e:
                    logger.error(f"Error handling client request: {e}")
                    writer.write(b"ERROR: Something went wrong\n")
                    print(traceback.format_exc())
                    await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"Connection {address} closed.")


    async def add_user(self, login, password, writer: StreamWriter):
        async with self.db_pool.acquire() as connect:
            existing_user = await connect.fetchrow(
                "SELECT id FROM users WHERE login = $1", login
            )
            if existing_user:
                writer.write(b"User already exists\n")
                await writer.drain()
                return

            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            await connect.execute(
                "INSERT INTO users (login, password_hash) VALUES ($1, $2)",
                login, hashed_password.decode('utf-8')
            )
            writer.write(f"User {login} created successfully\n".encode())
            await writer.drain()

    async def authenticate(self, login, password):
        async with self.db_pool.acquire() as connect:
            data = await connect.fetchrow(
                "SELECT password_hash FROM users WHERE login = $1", login
            )
            if data:
                stored_password_hash = data['password_hash']
                if bcrypt.checkpw(password.encode('utf-8'), stored_password_hash.encode('utf-8')):
                    logger.info(f"Authentication successful for {login}")
                    return True
                else:
                    logger.warning(f"Authentication failed for {login}: incorrect password")
            else:
                logger.warning(f"Authentication failed for {login}: user not found")
        return False

    async def add_vm(self, reader: StreamReader, writer: StreamWriter):
        data = await reader.read(setting.MESSAGE_LIMIT)
        message = data.decode().strip().split()

        vm_id, ram, cpu, disk_id, disk_size = message[1], message[2], message[3], message[4], message[5]

        async with self.db_pool.acquire() as connect:
            vm = VirtualMachine(vm_id=vm_id, ram=ram, cpu=cpu, disks={disk_id: disk_size})
            await connect.execute(
                "INSERT INTO virtual_machines (vm_id, ram, cpu) VALUES ($1 $2 $3)",
                vm.vm_id, vm.ram, vm.cpu
            )
            await connect.execute(
                "INSERT INTO disks (disk_id, vm_id, size) VALUES ($1, $2, $3)",
                disk_id, vm.vm_id, disk_size
            )

            self.connected_vms[vm_id] = vm
            self.all_connected_vms[vm_id] = vm

            writer.write(f"VM {vm_id} add\n".encode())
            await writer.drain()


async def start_server(user="admin", password="admin",
                       database="vm_manager", host="localhost"):
    try:
        db_pool = await asyncpg.create_pool(
            user=user,
            password=password,
            database=database,
            host=host
        )
    except asyncpg.exceptions.InvalidCatalogNameError:
        logger.error("DB not found\n")
        raise
    except asyncpg.exceptions.InvalidPasswordError:
        logger.error(f"invalid password authentication for user\n")
        raise
    server = VMServer(db_pool)

    server_coroutine = await asyncio.start_server(
        server.connect_client, '127.0.0.1', 8888
    )

    addr = server_coroutine.sockets[0].getsockname()
    logger.info(f"Serving on {addr}\n")

    async with server_coroutine:
        await server_coroutine.serve_forever()


if __name__ == '__main__':
    asyncio.run(start_server())