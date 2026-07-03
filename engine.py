"""
    gomoku, Puissance 5 engine, named after AlphaZero, the famous Go engine developed by Google DeepMind
"""
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
from utils import Board, Move, cache
import logging

from configuration import (
    PATTERN_INDEXATION,
    BYPASS_TIMEOUT,
    TEMPO_FACTOR,
    EngineConfig,
    NEIGHBORS,
    PATTERNS,
    Colors,
)


class FiveZeroEngine:
    """
        Main engine class
    """
    def __init__(self, engine_color: int):
        self.config: EngineConfig = EngineConfig()

        # engine plays the following color that will be set when joining a game
        self.color = engine_color

        # board representation
        self.board = Board()

        if BYPASS_TIMEOUT:
            logging.warning(f"Engine timeout bypass is enabled")

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

    @cache
    def evaluate(self, board_bytes: bytearray, tempo: int) -> int:
        """
        evaluation function performing the scoring of the board position. The board_bytes variable must be passed by
        kwarg syntax only

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

                sign = 1 if color == self.color else -1
                tempo = TEMPO_FACTOR if color == tempo else 1.0

                # the score depends on who has the tempo
                score += int(sign * tempo * len(results) * pattern_score)

        return score

    def search(self, move_timestamp: datetime) -> Move:
        """
        TODO: explain
        """
        search_deadline = move_timestamp + timedelta(seconds=self.config.max_time)

        best_move = None

        depth = 1

        # can't exceed the maximum engine recursion parameter
        while depth <= self.config.max_depth:
            try:
                logging.info(f"Searching depth {depth}")

                best_move = self._search_depth(
                    search_deadline=search_deadline,
                    depth=depth
                )

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

        # raising if no candidate moves were found...
        assert len(candidate_moves) > 0

        logging.debug(f"Searching with depth {depth} amongst {len(candidate_moves)} possible moves")

        for move_index in candidate_moves:
            if self._timeout(search_deadline=search_deadline):
                logging.debug(f"Search timeout, returning best move")
                raise TimeoutError()

            move = Move(
                index=move_index,
                color=self.color
            )

            board_copy = self.board.fork_move(move=move)

            score = self.minimax(
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

    def minimax(
        self,
        board: Board,
        depth: int,
        maximizing: bool,
        search_deadline: datetime,
        alpha: float = float("-inf"),
        beta: float = float("inf"),
        stop_event: Optional[threading.Event] = None
    ):
        if stop_event is not None and stop_event.is_set():
            # engine pondering can be interrupted by the main thread. raising a timeout error to stop the search
            raise TimeoutError()

        if self._timeout(search_deadline=search_deadline):
            # engine thinking time exceeded
            raise TimeoutError()

        if depth == 0 or not board.closest_moves:
            # side to move at this leaf
            opp = 1 if self.color == 2 else 2
            tempo = self.color if maximizing else opp

            return self.evaluate(board_bytes=board.board, tempo=tempo)

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

                score = self.minimax(
                    board=new_board,
                    depth=depth - 1,
                    maximizing=False,
                    search_deadline=search_deadline,
                    alpha=alpha,
                    beta=beta,
                    stop_event=stop_event
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

                score = self.minimax(
                    board=new_board,
                    depth=depth - 1,
                    maximizing=True,
                    search_deadline=search_deadline,
                    alpha=alpha,
                    beta=beta,
                    stop_event=stop_event
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
