"""
    gomoku, Puissance 5 engine, named after AlphaZero, the famous Go engine developed by Google DeepMind
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
from client import GameClient
from utils import Board, Move
import logging

from configuration import (
    PATTERN_INDEXATION,
    BYPASS_TIMEOUT,
    EngineConfig,
    NEIGHBORS,
    PATTERNS,
    Colors,
)


class FiveZeroEngine:
    """
        Main engine class
    """
    def __init__(self, client: GameClient):
        self._config: EngineConfig = EngineConfig()
        self._client: GameClient = client

        # engine plays the following color that will be set when joining a game
        self.color = None

        # board representation
        self.board = Board()

        if BYPASS_TIMEOUT:
            logging.warning(f"Engine timeout bypass is enabled")

    def set_color(self, color: int) -> None:
        self.color = color

    def _ident_pattern(self, pattern: str, color: int, board_bytes: Optional[bytearray]) -> List[Tuple[int]]:
        """
        TODO: write docstring
        """
        # initializing necessary variables
        board, pattern_length, empty_value = (
            self.board.board if board_bytes is None else board_bytes,  # can either identify patterns in a board
                                                                       # passed as argument or in the engine's board
            len(pattern),
            self.board.EMPTY  # assigning to avoid accessing multiple times
        )

        segments = PATTERN_INDEXATION.get(pattern_length)

        # making sure that the squares used to identify the pattern were pre-computed
        assert segments is not None

        results = []

        for segment in segments:
            values = tuple(board[index] for index in segment)

            signature = "".join(
                "0" if v == empty_value
                else "1" if v == color
                else "2"
                for v in values
            )

            if signature == pattern:
                results.append(segment)

        return results

    def evaluate(self, board_bytes: bytearray) -> int:
        """
        evaluation function performing the scoring of the board position

        TODO: enhance readme, particularly on evaluate methods
        """
        # initializing the score
        score = 0

        # performing the evaluation for each color
        for color in Colors:
            for pattern, pattern_score in PATTERNS.items():
                results = self._ident_pattern(
                    board_bytes=board_bytes,
                    pattern=pattern,
                    color=color
                )

                factor = 1 if color == self.color else -1

                score += factor * len(results) * pattern_score

        return score

    def search(self, move_timestamp: datetime) -> Move:
        """
        TODO: explain
        """
        search_deadline = move_timestamp + timedelta(seconds=self._config.max_time)

        best_move = None

        depth = 1

        # can't exceed the maximum engine recursion parameter
        while depth <= self._config.max_depth:
            try:
                best_move = self._search_depth(
                    search_deadline=search_deadline,
                    depth=depth
                )

                logging.info(f"Depth {depth} completed")

                depth += 1

            except TimeoutError:
                # exceeded engine time to answer, breaking and playing
                break

        return best_move

    def _search_depth(self, depth: int, search_deadline: datetime):
        """
        TODO: explain
        """
        best_move = None
        best_score = float("-inf")

        candidate_moves = sorted(
            self.board.closest_moves,
            key=lambda idx: len(NEIGHBORS[idx]),
            reverse=True
        )

        for move_index in candidate_moves:
            if self._timeout(search_deadline=search_deadline):
                logging.info(f"Search timeout, returning best move")
                raise TimeoutError()

            move = Move(
                index=move_index,
                color=self.color
            )

            board_copy = self.board.fork_move(move=move)

            score = self._minimax(
                board=board_copy,
                depth=depth - 1,
                maximizing=False,
                search_deadline=search_deadline,
                alpha=float("-inf"),
                beta=float("inf")
            )

            if score > best_score:
                best_score = score
                best_move = move

        return best_move

    def _minimax(
        self,
        board: Board,
        depth: int,
        maximizing: bool,
        search_deadline: datetime,
        alpha: float = float("-inf"),
        beta: float = float("inf")
    ):
        if self._timeout(search_deadline=search_deadline):
            raise TimeoutError()

        if depth == 0 or not board.closest_moves:
            return self.evaluate(board)

        moves = sorted(
            board.closest_moves,
            key=lambda idx: len(NEIGHBORS[idx]),
            reverse=True
        )

        if maximizing:
            value = float("-inf")

            for move_index in moves:
                move = Move(
                    index=move_index,
                    color=self.color
                )

                new_board = board.fork_move(move)

                score = self._minimax(
                    board=new_board,
                    depth=depth - 1,
                    maximizing=False,
                    search_deadline=search_deadline,
                    alpha=alpha,
                    beta=beta
                )

                value = max(value, score)

                alpha = max(alpha, value)

                if alpha >= beta:
                    break

            return value

        else:
            value = float("inf")

            opp_color = 1 if self.color == 2 else 2

            for move_index in moves:
                move = Move(
                    index=move_index,
                    color=opp_color
                )

                new_board = board.fork_move(move)

                score = self._minimax(
                    board=new_board,
                    depth=depth - 1,
                    maximizing=True,
                    search_deadline=search_deadline,
                    alpha=alpha,
                    beta=beta
                )

                value = min(value, score)

                beta = min(beta, value)

                if alpha >= beta:
                    break

            return value

    @staticmethod
    def _timeout(search_deadline):
        """
        checks if the engine should time out and return the best move found so far
        """
        now = datetime.now(timezone.utc)

        # caution, if the bypass timeout global variable is set to true, the engine will never time out
        return now >= search_deadline and not BYPASS_TIMEOUT
