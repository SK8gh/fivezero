"""
    gomoku, Puissance 5 engine, named after AlphaZero, the famous Go engine developed by Google DeepMind
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
from dataclasses import dataclass, field
from utils import Board, Move, cache
from numba import njit
import numpy as np
import threading
import logging
import random

from configuration import (
    PATTERN_INDEXATION,
    BYPASS_TIMEOUT,
    EngineConfig,
    TEMPO_FACTOR,
    EVAL_TABLES,
    BOARD_SIZE,
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

        # whether candidate moves are ordered by a local threat score before
        # the alpha-beta descent (A/B-testable). Off -> old geometric ordering.
        self.ordering = bool(self.config.get('ordering'))

        # board representation
        self.board = Board()

        # decorating the evaluation method at inception of the engine object
        self.evaluate = cache(spec.id if spec is not None else None)(self.evaluate)

        # global jit-warmup
        self._jit_warmup()

        if BYPASS_TIMEOUT:
            logging.warning(f"Engine timeout bypass is enabled")

    def _jit_warmup(self):
        """
        when using jit, the function must run once to compile the jitted function once and avoid it running slowly later
        """
        logging.debug(f"Launching just-in-time (jit) warmup")

        # jit-warmup of the evaluation
        self.evaluate(board_bytes=self.board.board, tempo=self.color)

        # jit-warmup of the move-ordering scorer
        _order_indices(
            np.frombuffer(self.board.board, dtype=np.uint8),
            np.fromiter(self.board.closest_moves, dtype=np.int64,
                        count=len(self.board.closest_moves)),
            self.color
        )

        logging.debug(f"Done warming up jitted functions")

    @staticmethod
    def _manage_spec(spec: Optional[EngineSpec]) -> dict:
        """
        treating the engine specifications passed as argument to declare a dictionary that will be used throughout the
        engine as a complementary configuration parameter
        """
        return spec.params if spec is not None else None

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

    def _order_moves(self, board: Board, depth: int) -> list[int]:
        """
        returns the candidate moves ordered best-first.

        With ordering enabled (and enough depth left for pruning to pay off),
        moves are ranked by a fast local threat score: for each of the 4 axes
        through the square, how far it extends the engine's own line (offense)
        and how far it touches the opponent's line (defense). Forcing moves
        (fours, then threes) come first, which is what makes alpha-beta cut
        early. Otherwise we fall back to the cheap geometric ordering.
        """
        moves = board.closest_moves

        if not self.ordering or depth < 2:
            return sorted(moves, key=lambda idx: len(NEIGHBOURS[idx]), reverse=True)

        board_np = np.frombuffer(board.board, dtype=np.uint8)
        cands = np.fromiter(moves, dtype=np.int64, count=len(moves))
        ordered = _order_indices(board_np, cands, self.color)
        return [int(i) for i in ordered]

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
                logging.debug(f"Searching depth {depth}")

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
        best_score = float("-inf")

        # all root moves that reach the best score so far; one is picked at
        # random at the end (see below)
        best_moves: list[Move] = []

        candidate_moves = self._order_moves(self.board, depth)

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

        moves = self._order_moves(board, depth)

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

    def evaluate(self, board_bytes: bytearray, tempo: int) -> int:
        """
        tempo-aware board scoring, JIT-accelerated.

        Same scoring semantics as before (sum of pattern scores, engine positive /
        opponent negative, side-to-move amplified by TEMPO_FACTOR), but:
          - signatures are base-3 ints (no string building)
          - each segment scanned once for both colors
          - empty segments skipped
          - score looked up in a dense table
          - the whole scan runs as Numba-compiled native code
        NOTE: this also fixes the old `tempo` variable shadowing — the factor is now
        applied correctly per color (it previously stayed 1.0 after the first pattern).
        """
        opp = 1 if self.color == 2 else 2
        engine_factor = TEMPO_FACTOR if self.color == tempo else 1.0
        opp_factor = TEMPO_FACTOR if opp == tempo else 1.0

        # zero-copy view over the bytearray buffer
        board_np = np.frombuffer(board_bytes, dtype=np.uint8)

        score = 0.0

        for seg_idx, score_table in EVAL_TABLES:
            score += _eval_length(
                board_np=board_np,
                seg_idx=seg_idx,
                score_table=score_table,
                engine_color=self.color,
                engine_factor=engine_factor,
                opp_factor=opp_factor
            )

        return int(score)


@njit(cache=True, nogil=True)
def _line_len(board_np, x, y, dx, dy, color):
    """
    number of consecutive `color` stones adjacent to (x, y) along the (dx, dy)
    axis, counting BOTH directions -- i.e. how long a run a stone placed at
    (x, y) would connect on that axis (excluding the placed stone itself).
    """
    n = 0
    nx = x + dx
    ny = y + dy
    while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board_np[nx * BOARD_SIZE + ny] == color:
        n += 1
        nx += dx
        ny += dy
    nx = x - dx
    ny = y - dy
    while 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board_np[nx * BOARD_SIZE + ny] == color:
        n += 1
        nx -= dx
        ny -= dy
    return n


@njit(cache=True, nogil=True)
def _threat(run_len):
    """cheap super-linear weight: longer runs are disproportionately urgent."""
    if run_len >= 5:
        return 1000000.0

    elif run_len == 4:
        return 10000.0

    elif run_len == 3:
        return 1000.0

    elif run_len == 2:
        return 100.0

    else:
        return 1.0


@njit(cache=True, nogil=True)
def _order_indices(board_np, cands, engine_color):
    """
    Score each candidate square by the local threat a stone there would create
    (own lines) and neutralise (opponent lines), summed over the 4 axes, then
    return the candidate indices sorted best-first. Runs as native code so it's
    cheap enough to call at every ordered node.
    """
    opp = 1 if engine_color == 2 else 2
    m = cands.shape[0]
    scores = np.empty(m, dtype=np.float64)

    for k in range(m):
        c = cands[k]
        x = c // BOARD_SIZE
        y = c % BOARD_SIZE
        s = 0.0
        for d in range(4):
            dx = _ORDER_DIRS[d, 0]
            dy = _ORDER_DIRS[d, 1]
            eng_run = _line_len(board_np, x, y, dx, dy, engine_color) + 1   # + placed stone
            opp_run = _line_len(board_np, x, y, dx, dy, opp) + 1
            s += _threat(eng_run) + _threat(opp_run)
        scores[k] = s

    order = np.argsort(-scores)      # descending
    return cands[order]


@njit(cache=True, nogil=True)
def _eval_length(
        board_np,
        seg_idx,
        score_table,
        engine_color,
        engine_factor,
        opp_factor
):
    """
    JIT-compiled scan of every segment of one length. For each segment it builds
    both color signatures (base-3 int) in a single pass, skips empty segments,
    and looks the score up in a dense table. nogil=True lets this run outside the
    GIL (useful later for threaded root search).
    """
    total = 0.0
    n_seg, length = seg_idx.shape
    for s in range(n_seg):
        sig_e = 0
        sig_o = 0
        any_stone = False
        for j in range(length):
            v = board_np[seg_idx[s, j]]
            if v == 0:
                code_e = 0
                code_o = 0
            elif v == engine_color:
                code_e = 1
                code_o = 2
                any_stone = True
            else:
                code_e = 2
                code_o = 1
                any_stone = True
            sig_e = sig_e * 3 + code_e
            sig_o = sig_o * 3 + code_o
        if any_stone:
            se = score_table[sig_e]
            if se != 0:
                total += engine_factor * se
            so = score_table[sig_o]
            if so != 0:
                total -= opp_factor * so
    return total
