"""
    gomoku, Puissance 5 engine, named after AlphaZero, the famous Go engine developed by Google DeepMind
"""

import logging
import random

from configuration import EngineConfig
from client import GameClient


class FiveZeroEngine:
    """
        Main engine class
    """
    def __init__(self, config: EngineConfig, client: GameClient):
        self._config: EngineConfig = config
        self._client: GameClient = client

        # engine plays the following color that will be set when joining a game
        self.color = None

    def set_color(self, color: str) -> None:
        assert color in ("Black", "White")

        self.color = color

    def best_move(self, move_data: dict):
        return [random.randint(0, 17), random.randint(0, 17)]
