
import logging
import asyncio
import asyncpg

from asyncio import StreamReader, StreamWriter
from asyncpg import Pool

from src.server import setting


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
           '[%(filename)s:%(lineno)d - %(funcName)s]'
)

logger = logging.getLogger()



class VMServer:

    def __init__(self):
        self.clients: dict = {}
        """
        Хранит список клиентов в формате
        
        ('192.168.1.10', 54321): '550e8400-e29b-41d4-a716-446655440000'
        """
        self.db_pool: Pool = None
        """Пул соединений с базой данных"""

    async def connect_client(self, reader: StreamReader, writer: StreamWriter):
        address = writer.get_extra_info("peername")
        logger.info(f"New connection: {address}")

        data = await reader.read(setting.MESSAGE_LIMIT)
        message = data.decode().strip()
        logger.info(f"Message: {message}, from {address}")



