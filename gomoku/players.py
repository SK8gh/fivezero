"""
implements the player abstraction and children: human & AI player. The AI is connected to an engine object via signals
"""

# library imports
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import threading
import logging

# module imports
from engine import FiveZeroEngine
from utils import Board, Move

from configuration import (
    FIRST_BLACK_MOVE_INDEX_ENGINE,
    NEIGHBORS,
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

    def notify_move(self, index: int, color: int) -> None:
        """
        signals when a move was played by either player
        """

    def close(self) -> None:
        """
        Release any background resources (threads). No-op by default
        """


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

    def __init__(self, color: int) -> None:
        super().__init__(color)

        # engine instance computing move responses
        self.engine = FiveZeroEngine(engine_color=color)

        # thread used to ponder the next move while the player is thinking
        self._ponder_thread: threading.Thread | None = None

        # event used to signal the pondering thread to stop running
        self._ponder_stop = threading.Event()

        # if set to true, pondering is enabled
        self._ponder_enabled = True

        # initializing an evaluation function cache size to keep track of the number of evaluated position while
        # the engine pondered during opponent's thinking time
        self.cache_size: int = 0

    def notify_move(self, index: int, color: int) -> None:
        """
        notifies the board of the engine of the move played by the player
        """
        logging.info(f"Notifying move: {Board.coordinates(index)}")

        # A move is about to change the position: any pondering is now stale
        self._stop_ponder()

        self.engine.board.move(Move(index=index, color=color))

        if color == self.color:
            # The engine just moved, the opponent is on the clock, triggering the pondering
            self._start_ponder()

        logging.info(f"Engine evaluation: {self.engine.evaluate(board_bytes=self.engine.board.board, tempo=color)}")

    def compute_move(self, game) -> int | None:
        board = self.engine.board

        if not board.closest_moves:
            # engine to start, the first move is predefined
            board.closest_moves = {FIRST_BLACK_MOVE_INDEX_ENGINE}

        move = self.engine.search(
            move_timestamp=datetime.now(timezone.utc)
        )

        # printing info about the evaluation cache
        msg = f"""Evaluation function cache: 
        - size: {self.engine.evaluate.cache_size()}
        - cache hits: {self.engine.evaluate.cache_hits()}
        """

        logging.info(msg)

        return None if move is None else move.index

    def _start_ponder(self) -> None:
        """
        starts the pondering thread while the opponent is thinking
        """
        logging.info(f"Engine starts pondering...")

        if not self._ponder_enabled:
            # pondering is disabled manually
            return

        # stopping any previous pondering thread if running
        self._stop_ponder()

        # re-creating a new event to signal the pondering thread to stop running
        self._ponder_stop = threading.Event()

        # setting a variable to keep track of the number of new board positions pondered during waiting time
        self.cache_size = self.engine.evaluate.cache_size()

        self._ponder_thread = threading.Thread(
            target=self._ponder_loop,
            args=(self._ponder_stop, ),
            daemon=True
        )

        # starting the pondering thread
        self._ponder_thread.start()

    def _stop_ponder(self) -> None:
        """
        stops the pondering thread if running
        """
        if self._ponder_thread is not None and self._ponder_thread.is_alive():
            # signals the pondering threading to stop running
            self._ponder_stop.set()

            # waits until the thread stops running
            self._ponder_thread.join()

        self._ponder_thread = None

        logging.info(f"Computed {self.engine.evaluate.cache_size() - self.cache_size} boards while pondering...")

    def _ponder_loop(self, stop_event: threading.Event) -> None:
        """
        warms the evaluation caches on the opponent's clock. engine.board is assumed to hold the position with the
        opponent to move. Works on forks only; engine board attribute is never mutated here
        """
        logging.info(f"Engine ponders while the opponent is thinking...")

        try:
            board = self.engine.board

            if not board.closest_moves:
                return

            opponent = Colors.WHITE if self.color == Colors.BLACK else Colors.BLACK

            # never expires: we interrupt via stop_event between replies instead
            never = datetime.now(timezone.utc) + timedelta(days=1)

            # Warm the most likely replies first (same ordering as the real search).
            replies = sorted(
                board.closest_moves,
                key=lambda i: len(NEIGHBORS[i]),
                reverse=True
            )

            # analyzing all potential replies
            for reply in replies:
                if stop_event.is_set():
                    # the pondering thread was signaled to stop running
                    return

                # forking the board to analyze the reply and avoid modifying the current board state
                after_reply = board.fork_move(Move(index=reply, color=opponent))

                if not after_reply.closest_moves:
                    # no move to analyze after the reply, skipping
                    continue

                # iterative deepening: warm depth 1, 2, 3... just like real search
                for depth in range(1, self.engine.config.max_depth + 1):
                    if stop_event.is_set():
                        return

                    self.engine.minimax(
                        board=after_reply,
                        depth=depth,  # ← was self.engine.config.max_depth
                        maximizing=True,
                        search_deadline=never,
                        alpha=float("-inf"),
                        beta=float("inf"),
                        stop_event=stop_event,
                    )

        except TimeoutError:
            # engine's own deadline
            return

        except (Exception,) as e:
            self._ponder_enabled = False
            logging.critical("Pondering was disabled following a critical event: %s", e)


def make_ai_player(color: int) -> Player:
    """
    returns an AI player object
    """
    return EnginePlayer(color)
