"""
    Implements the object interacting with the Game Hub API
"""

from engine import FiveZeroEngine
from utils import parse_arguments
from fivezero import FiveZeroBot
from client import GameClient
import logging
import time


if __name__ == '__main__':
    arguments = parse_arguments()

    logging.basicConfig(
        level=arguments.log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    client = GameClient(arguments.password)

    engine = FiveZeroEngine(
        client=client
    )

    bot = FiveZeroBot(engine=engine, client=client)

    time.sleep(3)

    room: str = 'RRRRR'

    client.join_room(room)

    time.sleep(10000)
