import asyncio
import logging

from src.server import setting


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
           '[%(filename)s:%(lineno)d - %(funcName)s]'
)

logger = logging.getLogger()


async def send_command(reader, writer, command):
    logger.info(f"Send command: {command}")
    try:
        writer.write(command.encode())
        await writer.drain()

        data = await reader.read(setting.MESSAGE_LIMIT)
        if data:
            logger.info(f"Response from server: {data.decode()}")
        else:
            logger.error("No response from server.")
    except ConnectionResetError:
        logger.error("Connection was reset by server.")
        raise
    except asyncio.CancelledError:
        logger.error("The connection was cancelled.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during command send: {e}")
        raise


async def handle_input(reader, writer):
    print("------- Welcome to VM Manager -------")
    print("Type your commands below (use 'exit' to quit):")

    while True:
        try:
            command = input("> ")
            if command.lower() == 'exit':
                print("Exiting...")
                break
            await send_command(reader, writer, command)
        except Exception as e:
            logger.error(f"Error during input handling: {e}")
            break


async def main():
    reader, writer = await asyncio.open_connection('localhost',
                                                   8888)
    logger.info("Connect server")

    await handle_input(reader, writer)

    writer.close()
    await writer.wait_closed()


if __name__ == '__main__':
    asyncio.run(main())
