from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from functools import wraps
from numba import njit
import numpy as np
import logging

from configuration import (
    FIRST_BLACK_MOVE_INDEX_ENGINE,
    COORDINATE_TO_INDEX,
    INDEX_TO_COORDINATE,
    BOARD_SIZE,
    NEIGHBOURS,
    EVAL_TABLES,
    SCORE_ALL,
    SQ_ROWS,
    SQ_LEN,
    SQ_OFF
)


def parse_arguments() -> Namespace:
    """
    parses arguments from the run/debug configuration
    """
    parser = ArgumentParser()

    parser.add_argument(
        "--log_level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO"
    )

    return parser.parse_args()


@dataclass(slots=True, frozen=True)
class Move:
    # index of the move on the flatly represented board
    index: int

    # integer representing the color of the move (1 for black, 2 for white)
    color: int

    def __repr__(self):
        return f"Move(index={self.index}, color={self.color})"


@dataclass(slots=True)
class Board:
    EMPTY = 0  # stores the 'empty' value

    # automatically initialized from the default factory to a bytearray of correct size
    board: bytearray = field(
        default_factory=lambda: bytearray(BOARD_SIZE * BOARD_SIZE)
    )

    # "playable" closest moves, a set of empty squares at a maximum distance of a placed stone
    closest_moves: set[int] = field(
        default_factory=lambda: {FIRST_BLACK_MOVE_INDEX_ENGINE, }
    )

    n_moves: int = 0  # number of moves

    history: list[int] = field(
        default_factory=lambda: []
    )

    # per-square count of occupied neighbours; a square is a 'closest move'
    # iff it is empty and this count is > 0
    neighbour_count: bytearray = field(
        default_factory=lambda: bytearray(BOARD_SIZE * BOARD_SIZE)
    )

    # incremental evaluation state (only maintained when tracking is enabled).
    # eval_sum[c] = sum over all segments of the pattern score seen from color c
    # (tempo-independent). Indexed by color: eval_sum[1] black, eval_sum[2] white.
    eval_sum: list = field(default_factory=lambda: [0, 0, 0])

    # LIFO stack of (delta_black, delta_white) pushed on move, popped on undo,
    # so undo costs nothing (no rescan, no jit call)
    _eval_stack: list = field(default_factory=list)

    def __eq__(self, other: "Board"):
        """
        testing the equality between two boards. Criteria: equal position
        """
        return self.board == other.board

    @staticmethod
    def index(x: int, y: int) -> int:
        """
        converts 2D coordinates (x, y) to a 1D index for the flat board representation
        """
        # using a pre-computed cache containing all the possible coordinates mapped to indexes
        return COORDINATE_TO_INDEX[(x, y)]

    @staticmethod
    def coordinates(index: int) -> tuple[int, int]:
        """
        converts a 1D index to 2D coordinates (x, y) for the board
        """
        # using a pre-computed cache containing all the possible indexes mapped to coordinates
        return INDEX_TO_COORDINATE[index]

    def get_index(self, index: int) -> int:
        """
        returns the value at the given index on the board
        """
        return self.board[index]

    def set_index(self, index: int, value: int) -> None:
        """
        sets the value at the given index on the board
        """
        self.board[index] = value

    def set_eval_tracking(self) -> None:
        """
        turns on incremental evaluation for this board: computes the initial
        per-color pattern sums once (full scan), then keeps them up to date on
        every move()/undo_move(). O(1) leaf evaluation reads eval_sum directly.
        """
        self.eval_sum = [0, 0, 0]
        self._eval_stack = []

        board_np = np.frombuffer(self.board, dtype=np.uint8)
        s_black, s_white = _full_pattern_sums(board_np)
        self.eval_sum[1] = int(s_black)
        self.eval_sum[2] = int(s_white)

    def _apply_eval_delta(self, index: int, color: int) -> None:
        """
        updates the running per-color sums for a stone of `color` placed at
        `index`, and stores the delta so undo_move can reverse it for free.
        """
        board_np = np.frombuffer(self.board, dtype=np.uint8)

        d_black, d_white = _eval_delta(
            board_np, SQ_ROWS[index], SQ_LEN[index], SQ_OFF[index], SCORE_ALL, index, color
        )

        self.eval_sum[1] += d_black
        self.eval_sum[2] += d_white
        self._eval_stack.append((d_black, d_white))

    def move(self, move: Move) -> None:
        """
        making a move on the board, making sure the square is empty before assigning the color
        """
        # invalid move, the board square is already occupied
        assert self.get_index(move.index) == self.EMPTY, f"Board square {self.coordinates(move.index)} is not empty"

        # assigning
        self.set_index(index=move.index, value=move.color)

        # adding 1 to the count of moves
        self.n_moves += 1

        self.history.append(move.index)

        # updating board 'closest moves' attribute
        self._update_closest(move=move)

        # keeping the incremental evaluation in sync (only if enabled)
        self._apply_eval_delta(move.index, move.color)

    def undo_move(self, move: Move) -> None:
        """
        undoing move
        """
        index = move.index

        assert self.get_index(index) != self.EMPTY

        # undoing move
        self.set_index(index=index, value=self.EMPTY)

        # removing 1 to the count of moves
        self.n_moves -= 1

        # removing the move from history
        self.history.remove(index)

        # updating the closest moves attribute
        self._undo_closest(index=index)

        # reversing the incremental evaluation with the stored delta (no rescan)
        d_black, d_white = self._eval_stack.pop()
        self.eval_sum[1] -= d_black
        self.eval_sum[2] -= d_white

    def _undo_closest(self, index: int) -> None:
        """
        reverses _update_closest in O(K): decrement the occupied-neighbour count of each neighbour, and drop it from
        closest_moves only when its count hits 0
        """
        for n in NEIGHBOURS[index]:
            self.neighbour_count[n] -= 1

            # lost its last adjacent stone -> no longer playable
            if self.neighbour_count[n] == 0 and self.get_index(n) == self.EMPTY:
                self.closest_moves.discard(n)

        # the removed square is empty again: a candidate iff it still touches a stone
        if self.neighbour_count[index] > 0:
            self.closest_moves.add(index)
        else:
            self.closest_moves.discard(index)

        # fully empty board: restoring the opening seed
        if not self.n_moves:
            self.closest_moves = {FIRST_BLACK_MOVE_INDEX_ENGINE}

    def _update_closest(self, move: Move) -> None:
        """
        updating the closest "moves" attribute, storing the "playable" moves that are at a maximum distance of a placed
        stone on the board
        """
        index = move.index

        for n in NEIGHBOURS[index]:
            self.neighbour_count[n] += 1

            # any empty neighbour now touches a stone -> it's playable
            if self.get_index(n) == self.EMPTY:
                self.closest_moves.add(n)

        # the square just played is no longer a candidate
        self.closest_moves.discard(index)

    @staticmethod
    def clone(instance: "Board") -> "Board":
        """
        clones the board in a more optimized way than using deepcopy
        """
        return Board(
            closest_moves=instance.closest_moves.copy(),
            history=instance.history.copy(),
            board=instance.board.copy(),
            n_moves=instance.n_moves,
            neighbour_count=instance.neighbour_count.copy(),
            eval_sum=instance.eval_sum.copy(),
            _eval_stack=instance._eval_stack.copy()
        )

    def fork_move(self, move: Move) -> "Board":
        """
        generating a new board state after making a move, without modifying the original board
        """
        # cloning the board with our custom clone method to avoid deepcopy overhead
        new_board = Board.clone(self)

        # moving
        new_board.move(move)

        return new_board

    def set(self, x: int, y: int, value: int) -> None:
        """
        sets the value at the given (x, y) coordinates on the board
        """
        self.board[self.index(x, y)] = value

    def get(self, x: int, y: int) -> int:
        """
        returns the value at the given (x, y) coordinates on the board
        """
        return self.board[self.index(x, y)]

    def clear(self) -> None:
        """
        clearing the board and all attributes, used for testing purposes only to avoid recreating objects
        """
        # does not recreate a new bytearray object
        self.board[:] = b"\x00" * len(self.board)

        # resetting the neighbour counter too, otherwise it accumulates across reuses
        self.neighbour_count[:] = b"\x00" * len(self.neighbour_count)

        # clearing allowed moves & move history
        self.closest_moves.clear(), self.history.clear()

        self.n_moves = 0

        # resetting incremental evaluation state (empty board -> zero sums)
        self.eval_sum[:] = [0, 0, 0]
        self._eval_stack.clear()

    def fingerprint(self) -> dict:
        """
        board fingerprint, unique for unique boards
        """
        return {
            'board': bytes(self.board),
            'closest': frozenset(self.closest_moves),
            'history': tuple(self.history),
            'n_moves': self.n_moves
        }


def _full_pattern_sums(board_np) -> tuple[int, int]:
    """
    one-time full scan computing the tempo-independent per-color pattern sums
    (black, white). Not on the hot path -- only called when tracking is enabled.
    """
    s_black = 0
    s_white = 0

    for seg_idx, score_table in EVAL_TABLES:
        n_seg, length = seg_idx.shape
        for s in range(n_seg):
            sig_b = 0
            sig_w = 0
            for j in range(length):
                v = board_np[seg_idx[s, j]]
                # black perspective: black stone = 1, white = 2
                cb = 0 if v == 0 else (1 if v == 1 else 2)
                # white perspective: white stone = 1, black = 2
                cw = 0 if v == 0 else (1 if v == 2 else 2)
                sig_b = sig_b * 3 + cb
                sig_w = sig_w * 3 + cw
            s_black += int(score_table[sig_b])
            s_white += int(score_table[sig_w])

    return s_black, s_white


@njit(cache=True, nogil=True)
def _eval_delta(board_np, rows, lens, offs, score_all, idx, color):
    """
    Change to the two tempo-independent per-color pattern sums (black, white)
    when board[idx] goes from empty to `color`. Only rescans the segments
    passing through idx (rows/lens/offs come from the precomputed per-square
    map). The target square is treated as empty in the "old" signature and as
    `color` in the "new" one, so this is valid whether or not the stone has
    already been written to the board.
    """
    d_black = 0
    d_white = 0

    k_max = rows.shape[0]
    for k in range(k_max):
        length = lens[k]
        if length == 0:      # padding row -> no more segments through this square
            break

        off = offs[k]
        old_b = 0
        old_w = 0
        new_b = 0
        new_w = 0

        for j in range(length):
            cell = rows[k, j]

            if cell == idx:
                # old: empty on both perspectives
                ob = 0
                ow = 0
                # new: the placed stone
                if color == 1:
                    nb = 1
                    nw = 2
                else:
                    nb = 2
                    nw = 1
            else:
                v = board_np[cell]
                ob = 0 if v == 0 else (1 if v == 1 else 2)
                ow = 0 if v == 0 else (1 if v == 2 else 2)
                nb = ob
                nw = ow

            old_b = old_b * 3 + ob
            old_w = old_w * 3 + ow
            new_b = new_b * 3 + nb
            new_w = new_w * 3 + nw

        d_black += score_all[off + new_b] - score_all[off + old_b]
        d_white += score_all[off + new_w] - score_all[off + old_w]

    return d_black, d_white


def cache_key(board: bytearray, tempo: int) -> tuple:
    """
    computes a hash of the board position to be used as a key in the cache
    """
    return bytes(board), tempo


def cache(engine_name: str):
    """
    decorates the evaluation function, caching the results of the evaluation for a given board position to avoid
    redundant computations
    """
    def decorator(evaluation_function):
        _cache: dict = {}
        _hits = 0

        @wraps(evaluation_function)
        def wrapper(board_bytes: bytearray, tempo: int):
            nonlocal _hits

            h = cache_key(board_bytes, tempo)

            if h not in _cache:
                _cache[h] = evaluation_function(
                    board_bytes=board_bytes,
                    tempo=tempo
                )
            else:
                _hits += 1

                logging.debug(
                    "[%s] Cache hit (%d entries, %d hits)",
                    engine_name or "default",
                    len(_cache),
                    _hits,
                )

            return _cache[h]

        wrapper.cache = _cache
        wrapper.cache_hits = lambda: _hits
        wrapper.cache_size = lambda: len(_cache)
        wrapper.engine_name = engine_name

        return wrapper

    return decorator


def deterministic_vectors(vector_size: int, n_vectors: int, seed: int) -> list[tuple[int]]:
    """
    generates deterministic vectors of random numbers based on a given seed
    """
    rng = np.random.default_rng(seed)

    vectors = rng.integers(
        low=0,
        high=BOARD_SIZE ** 2,
        size=(n_vectors, vector_size),
        dtype=np.int64
    )

    return [
        tuple(int(x) for x in row)
        for row in vectors
    ]