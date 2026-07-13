"""
implements the player abstraction and children: human & AI player. The AI is connected to an engine object via signals
"""

# library imports
from __future__ import annotations

from datetime import datetime, timezone
import logging

# module imports
from engine import FiveZeroEngine, EngineSpec
from utils import Board, Move

from configuration import (
    Colors
)


class Player:
    kind = "player"
    is_human = False
    name = "Player"

    def __init__(self, color: int) -> None:
        self.color = color

    def compute_move(self, game) -> int | None:
        """
        returns AI move
        """
        raise NotImplementedError

    def close(self) -> None:
        """
        Release any background resources (threads). No-op by default
        """
        pass

    def notify_move(self, index: int, color: int) -> None:
        """
        signals when a move was played by either player
        """
        pass


class HumanPlayer(Player):
    kind = "human"
    is_human = True
    name = "Human"


class EnginePlayer(Player):
    """
    FiveZero engine adapter
    """
    kind = "engine"
    name = "FiveZero"

    ENGINE_PARAMS = {
        'incremental': True,
    }

    def __init__(self, color: int) -> None:
        super().__init__(color)

        spec = EngineSpec(
            id="pvai",
            blurb="pvai",
            params=dict(self.ENGINE_PARAMS)
        )

        # engine instance computing move responses
        self.engine = FiveZeroEngine(
            engine_color=color,
            spec=spec
        )

        # initializing an evaluation function cache size to keep track of the number of evaluated position while
        # the engine pondered during opponent's thinking time
        self.cache_size: int = 0

    def notify_move(self, index: int, color: int) -> None:
        """
        notifies the board of the engine of the move played by the player
        """
        logging.info(f"Notifying move: {Board.coordinates(index)}")

        # advance the engine's own board; when incremental eval is enabled this
        # also keeps the running per-color sums in sync
        self.engine.board.move(Move(index=index, color=color))

        # informational only: score the current position from the engine's view.
        # _evaluate_leaf uses the O(1) incremental path when enabled, else the
        # full JIT scan -- both return the same value.
        score = self.engine._evaluate_leaf(self.engine.board, tempo=color)

        logging.info(f"Engine evaluation: {score}")

    def compute_move(self, game) -> int | None:
        move = self.engine.search(
            move_timestamp=datetime.now(timezone.utc)
        )

        return None if move is None else move.index


def make_ai_player(color: int) -> Player:
    """
    returns an AI player object
    """
    return EnginePlayer(color)


def build_players(mode: str, human_color: int = Colors.BLACK) -> dict[int, Player]:
    """
    Builds the {color: Player} mapping for a new game. Black always moves first.

    mode:
        "pvai" -> human vs FiveZero engine (human_color chooses the human's side)
        "pvp"  -> human vs human (human_color is ignored, both sides are humans)
    """
    black, white = Colors.BLACK, Colors.WHITE

    if mode == "pvp":
        return {black: HumanPlayer(black), white: HumanPlayer(white)}

    if mode == "pvai":
        ai_color = white if human_color == black else black
        return {
            human_color: HumanPlayer(human_color),
            ai_color: make_ai_player(ai_color),
        }

    raise ValueError(f"unknown game mode: {mode!r}")
