"""
    gomoku, Puissance 5 engine, named after AlphaZero, the famous Go engine developed by Google DeepMind
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
from dataclasses import dataclass, field
from utils import Board, Move
import numpy as np
import threading
import logging
import random

from configuration import (
    BYPASS_TIMEOUT,
    EngineConfig,
    TEMPO_FACTOR,
    NEIGHBOURS
)


# the four axes a pattern can run along (used by the move-ordering scorer)
_ORDER_DIRS = np.array([(0, 1), (1, 0), (1, 1), (1, -1)], dtype=np.int64)


@dataclass
class EngineSpec:
    """
    defines a selectable engine version in the UI
    """
    id: str
    blurb: str
    params: dict = field(default_factory=dict)


class FiveZeroEngine:
    """
        Main engine class
    """
    def __init__(self, engine_color: int, spec: Optional[EngineSpec]):
        self.config: EngineConfig = EngineConfig(
            extra=self._manage_spec(spec=spec)
        )

        # engine plays the following color that will be set when joining a game
        self.color = engine_color

        # number of positions evaluated during the current search (reset per search)
        self._eval_count = 0

        # board representation
        self.board = Board()

        # board maintains the running sums
        self.board.set_eval_tracking()

        # global jit-warmup
        self._jit_warmup()

        if BYPASS_TIMEOUT:
            logging.warning(f"Engine timeout bypass is enabled")

    def _jit_warmup(self):
        """
        when using jit, the function must run once to compile the jitted function once and avoid it running slowly later
        """
        logging.debug(f"Launching just-in-time (jit) warmup")

        # jit-warmup of the incremental-evaluation delta (compile on a scratch board)
        warm = Board()
        warm.set_eval_tracking()
        m = Move(index=0, color=1)
        warm.move(m)
        warm.undo_move(m)

        logging.debug(f"Done warming up jitted functions")

    @staticmethod
    def _manage_spec(spec: Optional[EngineSpec]) -> dict:
        """
        treating the engine specifications passed as argument to declare a dictionary that will be used throughout the
        engine as a complementary configuration parameter
        """
        return spec.params if spec is not None else None

    @staticmethod
    def _order_moves(board: Board) -> list[int]:
        """
        returns the candidate moves ordered best-first.

        NOTE: this always returns a *fresh list* (a snapshot). That is what
        makes in-place make/unmake safe: we iterate the snapshot while
        board.closest_moves mutates underneath us as children are made/undone.
        """
        moves = board.closest_moves

        return sorted(moves, key=lambda idx: len(NEIGHBOURS[idx]), reverse=True)

    def _evaluate_leaf(self, board: Board, tempo: int) -> int:
        """
        leaf evaluation dispatch. When incremental eval is on, this is O(1):
        it just recombines the board's running per-color sums with the tempo
        factors -- no board scan, no cache lookup. Otherwise it falls back to
        the full JIT scan (cached).

        Both paths return the exact same score for a given (position, tempo):
        incremental is a speed feature, not a strength one.
        """
        # count this position toward the current search's evaluation total
        self._eval_count += 1

        opp = 1 if self.color == 2 else 2
        engine_factor = TEMPO_FACTOR if self.color == tempo else 1.0
        opp_factor = TEMPO_FACTOR if opp == tempo else 1.0

        return int(engine_factor * board.eval_sum[self.color] - opp_factor * board.eval_sum[opp])

    def search(self, move_timestamp: datetime) -> Move:
        """
        TODO: explain
        """
        search_deadline = move_timestamp + timedelta(seconds=self.config.max_time)

        best_move = None

        # reset the per-search counter of evaluated positions
        self._eval_count = 0

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
                # exceeded engine time to answer, breaking and playing.
                # the make/unmake try/finally chain has already restored
                # self.board to its pre-search state as the exception unwound.
                break

        # depth was incremented after each completed pass, so the last fully
        # searched depth is depth - 1 (0 if even depth 1 timed out)
        reached_depth = depth - 1

        played = Board.coordinates(best_move.index) if best_move is not None else None

        logging.info(
            "Evaluated %d positions (reached depth %d) before playing %s",
            self._eval_count,
            reached_depth,
            played,
        )

        return best_move

    def _search_depth(self, depth: int, search_deadline: datetime):
        """
        one iterative-deepening pass at a fixed depth
        """
        best_score = float("-inf")

        # all root moves that reach the best score so far; one is picked at
        # random at the end (see below)
        best_moves: list[Move] = []

        candidate_moves = self._order_moves(self.board)

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

            score = self.minimax(
                board=self.board.fork_move(move=move),
                depth=depth - 1,
                maximizing=False,
                search_deadline=search_deadline,
                alpha=float("-inf"),
                beta=float("inf")
            )

            if score > best_score:
                best_score = score
                best_moves = [move]

            elif score == best_score:
                best_moves.append(move)

        # Pick uniformly at random among all equally-best moves. This is
        # strength-neutral (every choice has the same evaluation) but makes
        # otherwise-identical games diverge -- without it two engines replay the
        # exact same game every time, which makes A/B benchmarking meaningless.
        # Seed `random` once at program start if you want reproducible runs.
        return random.choice(best_moves) if best_moves else None

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
        """
        alpha-beta search. Forks a fresh board per move. A pondering caller running concurrently with the main
        thread must pass its OWN clone.
        """
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

            return self._evaluate_leaf(board, tempo)

        moves = self._order_moves(board)

        if maximizing:
            value = float("-inf")

            for move_index in moves:
                move = Move(
                    index=move_index,
                    color=self.color
                )

                score = self.minimax(
                    board=board.fork_move(move),
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

                score = self.minimax(
                    board=board.fork_move(move),
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
