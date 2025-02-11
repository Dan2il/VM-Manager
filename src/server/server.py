"""
Модуль содержит реалицаию имитации
серверной части оркестратора VM
"""

import logging
import asyncio
from uuid import uuid4, UUID
from asyncio import StreamReader, StreamWriter
import asyncpg
import bcrypt

from asyncpg import Pool


from src.server import setting
from src.server.virtual_machine import VirtualMachine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
           '[%(filename)s:%(lineno)d - %(funcName)s]'
)

logger = logging.getLogger()


class VMServer:
    """Класс, для управления VM"""
    def __init__(self, db_pool):
        """Инициализирует VMServer"""

        self.db_pool: Pool = db_pool
        """Пул соединений с базой данных"""
        self.connected_vms: dict[UUID, VirtualMachine] = {}
        """
        Словарь, хранит id и объект подключенной виртуальной машины
        """

        self.authenticated_vms: set[UUID] = set()
        """
        Хранит успешно авторизированных VM
        
        Нужно, для проверки, что виртуальная машина может выполнять определенные команды
        """

        self.all_connected_vms: dict[UUID, VirtualMachine] = {}
        """
        Хранит все когда-либо подключенные VM
        Словарь, хранит id и объект подключенной виртуальной машины
        """

    async def connect_client(self, reader: StreamReader, writer: StreamWriter):
        """
        Обрабатывает команды от клиента
        :param reader:
        :param writer:
        :return:
        """
        address = writer.get_extra_info("peername")
        logger.info("New connection: %s", address)

        try:
            while True:
                try:
                    data = await asyncio.wait_for(reader.read(setting.MESSAGE_LIMIT),
                                                  timeout=setting.TIMEOUT_SERVER)
                    if not data:
                        logger.info("Client %s disconnected", address)
                        break
                except asyncio.TimeoutError:
                    logger.error("Timeout waiting for data from client")
                    break

                message = data.decode().strip().split()
                logger.info("Message: %s, from %s", message, address)

                command = message[0]
                try:
                    if command == "ADD_USER" and len(message) == 3:
                        login, password = message[1], message[2]
                        await self.add_user(login, password, writer)
                    elif command == "LIST_USERS":
                        await self.list_users(writer)
                    elif command == "AUTH" and len(message) == 4:
                        vm_id, login, password = message[1], message[2], message[3]
                        if await self.authenticate(login, password):
                            self.authenticated_vms.add(vm_id)
                            writer.write(b"AUTHENTICATE_SUCCESS\n")
                        else:
                            writer.write(b"AUTHENTICATE_FAIL\n")
                        await writer.drain()
                    elif command == "ADD_VM" and len(message) > 3:
                        ram, cpu, disk_size = message[1], message[2], message[3]

                        disk_id = None
                        if len(message) == 5:
                            disk_id = UUID(message[4])
                        await self.add_vm(ram, cpu, disk_size, writer, disk_id)
                    elif command == "LIST_CON_VM":
                        await self.list_connect_vm(writer)
                    elif command == "LIST_AU_VM":
                        await self.list_authenticated_vm(writer)
                    elif command == "LIST_ALL_VM":
                        await self.get_all_vm(writer)
                    elif command == "UPDATE_VM":
                        vm_id, ram, cpu = message[1], message[2], message[3]
                        await self.update_vm(vm_id, ram, cpu, writer)
                    elif command == "LOGOUT_VM":
                        vm_id = UUID(message[1])
                        await self.logout_vm(vm_id, writer)
                    elif command == "LIST_DISKS":
                        await self.list_disks(writer)
                    else:
                        writer.write(b"UNKNOWN_COMMAND\n")
                    await writer.drain()
                except Exception as e:
                    logger.error("Error handling client request: %s", str(e))
                    writer.write(b"ERROR: Something went wrong\n")
                    await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info("Connection %s closed", address)

    async def add_user(self, login, password, writer: StreamWriter):
        """
        Добавляет пользователя
        :param login:
        :param password:
        :param writer:
        :return:
        """
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

    async def list_users(self, writer: StreamWriter):
        """
        Отправляет в writer список пользователей
        :param writer:
        :return:
        """
        async with self.db_pool.acquire() as connect:
            data = await connect.fetch(
                "SELECT id, login FROM users"
            )
            response = "\n".join(
                [f"User {row['id']}: {row['login']}" for row in data]
            )
            writer.write(response.encode() + b"\n")
        await writer.drain()

    async def authenticate(self, login, password):
        """
        Аутентифицирует пользовтеля
        :param login:
        :param password:
        :return:
        """
        async with self.db_pool.acquire() as connect:
            data = await connect.fetchrow(
                "SELECT password_hash FROM users WHERE login = $1", login
            )
            if data:
                stored_password_hash = data['password_hash']
                if bcrypt.checkpw(password.encode('utf-8'), stored_password_hash.encode('utf-8')):
                    logger.info("Authentication successful for %s", login)
                    return True
                logger.error("Authentication failed for %s: incorrect password", login)
            else:
                logger.error("Authentication failed for %s: user not found", login)
        return False

    async def add_vm(self, ram, cpu, disk_size, writer, disk_id=None):
        """
        Добавляет VM
        :param ram:
        :param cpu:
        :param disk_size:
        :param writer:
        :param disk_id:
        :return:
        """
        async with self.db_pool.acquire() as connect:
            vm_id = uuid4()
            new_disk_id = uuid4()
            vm = VirtualMachine(vm_id=vm_id,
                                ram=ram,
                                cpu=cpu,
                                disks={disk_id: disk_size} if disk_id else {new_disk_id: disk_size})

            await connect.execute(
                "INSERT INTO virtual_machines (vm_id, ram, cpu) VALUES ($1, $2, $3)",
                vm.vm_id, int(vm.ram), int(vm.cpu)
            )

            if disk_id:
                existing_disk = await connect.fetchrow(
                    "SELECT disk_id FROM disks WHERE disk_id = $1", disk_id
                )
                if existing_disk:
                    await connect.execute(
                        "INSERT INTO vm_disks (vm_id, disk_id) VALUES ($1, $2)",
                        vm.vm_id, disk_id
                    )
                    writer.write(f"VM {vm.vm_id} add to exist disk {disk_id}\n".encode())
                else:
                    await connect.execute(
                        "INSERT INTO disks (disk_id, size) VALUES ($1, $2)",
                        new_disk_id, int(disk_size)
                    )
                    await connect.execute(
                        "INSERT INTO vm_disks (vm_id, disk_id) VALUES ($1, $2)",
                        vm.vm_id, new_disk_id
                    )
                    writer.write(f"VM {vm.vm_id} add to new disk {new_disk_id}\n".encode())
            else:
                await connect.execute(
                    "INSERT INTO disks (disk_id, size) VALUES ($1, $2)",
                    new_disk_id, int(disk_size)
                )

                await connect.execute(
                    "INSERT INTO vm_disks (vm_id, disk_id) VALUES ($1, $2)",
                    vm.vm_id, new_disk_id
                )
                writer.write(f"VM {vm.vm_id} add to new disk {new_disk_id}\n".encode())

            self.connected_vms[vm_id] = vm
            self.all_connected_vms[vm_id] = vm

            writer.write(str(vm).encode())

    async def list_connect_vm(self, writer):
        """
        Отправляет в writer список подключенных VM
        :param writer:
        :return:
        """
        result = "".join([f"{repr(vm)}\n" for _, vm in self.connected_vms.items()])
        if len(result) == 0:
            result = "no connect VM"
        writer.write(result.encode() + b"\n")

    async def list_authenticated_vm(self, writer: StreamWriter):
        """
        Отправляет в writer список аутентифицированных VM
        :param writer:
        :return:
        """
        result = "".join([f"{repr(vm)}\n" for vm in self.authenticated_vms])
        if len(result) == 0:
            result = "no authenticate VM"
        writer.write(result.encode() + b"\n")

    async def get_all_vm(self, writer: StreamWriter):
        """
        Отправляет в writer список всех когда либо подключенных VM
        :param writer:
        :return:
        """
        result = "".join([f"{repr(vm)}\n" for _, vm in self.all_connected_vms.items()])
        if len(result) == 0:
            result = "no authenticate VM"
        writer.write(result.encode() + b"\n")

    async def update_vm(self, vm_id, ram, cpu, writer: StreamWriter):
        """
        Обновляет ram и|или cpu у VM с vm_id
        :param vm_id:
        :param ram:
        :param cpu:
        :param writer:
        :return:
        """
        if vm_id not in self.authenticated_vms:
            writer.write(f"VM {vm_id} not found\n".encode())
        else:
            async with self.db_pool.acquire() as connect:
                await connect.execute(
                    "UPDATE virtual_machines SET ram = $1, cpu = $2 WHERE vm_id = $3",
                    ram, cpu, vm_id
                )
                if vm_id in self.connected_vms:
                    self.connected_vms[vm_id].ram = ram
                    self.connected_vms[vm_id].cpu = cpu
                writer.write(f"VM {vm_id} updated: RAM={ram}, CPU={cpu}\n".encode())

    async def logout_vm(self, vm_id, writer: StreamWriter):
        """
        Выходит из VM с vm_id
        :param vm_id:
        :param writer:
        :return:
        """
        if vm_id in self.authenticated_vms:
            self.authenticated_vms.remove(vm_id)
            writer.write(f"VM {vm_id} logout\n".encode())
        else:
            writer.write(f"VM {vm_id} not found\n".encode())
        await writer.drain()

    async def list_disks(self, writer: StreamWriter):
        """
        Отправляет в writer список дисков
        :param writer:
        :return:
        """
        async with self.db_pool.acquire() as connect:
            rows = await connect.fetch("SELECT disk_id, vm_id, size FROM disks")
            response = "\n".join([f"Disk {row['disk_id']}:"
                                  f"VM={row['vm_id']}, Size={row['size']}" for row in rows])
            writer.write(response.encode() + b"\n")


async def start_server(user="admin", password="admin",
                       database="vm_manager", host="localhost"):
    """
    Запускает реализацию VMserver

    Подключается к базе данных
    """
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
        logger.error("invalid password authentication for user\n")
        raise
    server = VMServer(db_pool)

    server_coroutine = await asyncio.start_server(
        server.connect_client, '127.0.0.1', 8888
    )

    addr = server_coroutine.sockets[0].getsockname()
    logger.info("Serving on %s\n", addr)

    async with server_coroutine:
        await server_coroutine.serve_forever()


if __name__ == '__main__':
    asyncio.run(start_server())
