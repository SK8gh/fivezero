"""
    project configuration storing constants & initializing pre-computed values for performance enhancement
"""

from profilehooks import timecall
from typing import Optional
from enum import IntEnum
import numpy as np
import logging

# number of stones to line up to win
WINNING_LENGTH = 5

# Game board size
BOARD_SIZE = 15

# Maximum thinking time (ms)
MAX_TIME = 1500  # prod version

# Using the following variable to bypass the timeout mechanism, for testing purposes only
BYPASS_TIMEOUT = False

# Move pruning maximum distance
MOVE_MAX_DISTANCE = 2

# holds the neighbors of each index representing a square
NEIGHBOURS = {index: set() for index in range(BOARD_SIZE * BOARD_SIZE)}

# Maximum number of moves to look ahead for
ENGINE_DEPTH = 5

# Tempo factor, used to evaluate positions based on who has the trait
TEMPO_FACTOR = 1.2

# Can't play more moves that the number of squares on the board
MAX_NUMBER_MOVES = BOARD_SIZE * BOARD_SIZE

# Pattern directions
DIRECTIONS = (
    (0, 1),  # same row, different column
    (1, 0),  # different row, same column
    (1, 1),  # diagonal
    (1, -1)  # anti-diagonal
)

INDEX_TO_COORDINATE, COORDINATE_TO_INDEX = dict(), dict()

FIVE = 1_000_000_000
OPEN_FOUR = 10_000_000
SIMPLE_FOUR = 1_000_000
OPEN_THREE = 50_000
BROKEN_THREE = 20_000
OPEN_TWO = 2_000
BROKEN_TWO = 300
DOUBLE_FOUR = 5000000
FOUR_THREE = 1500000
DOUBLE_THREE = 500000
BROKEN_FOUR = 80000
CAPPED_THREE = 8000

PATTERNS = {
    # Five
    "11111": FIVE,

    # Open Four
    "011110": OPEN_FOUR,

    # Closed Four / Simple Four
    "11110": SIMPLE_FOUR,
    "01111": SIMPLE_FOUR,
    "11011": SIMPLE_FOUR,
    "10111": SIMPLE_FOUR,
    "11101": SIMPLE_FOUR,

    # broken four variants
    "011011": BROKEN_FOUR,
    "110110": BROKEN_FOUR,

    # capped three (one side blocked by opponent, still worth something)
    "211100": CAPPED_THREE,
    "001112": CAPPED_THREE,
    "211010": CAPPED_THREE,
    "010112": CAPPED_THREE,

    # Open Three
    "01110": OPEN_THREE,

    # Broken Three / Jump Three
    "011010": BROKEN_THREE,
    "010110": BROKEN_THREE,

    # Open Two
    "001100": OPEN_TWO,
    "011000": OPEN_TWO,
    "000110": OPEN_TWO,

    # Broken Two
    "0010100": BROKEN_TWO,
    "0001010": BROKEN_TWO,
}

# The following stores, for each length of patterns, a tuple containing the pre-computed set of indexes that will be
# checked to look for a pattern. Exemple:
#
# pattern:     positions to check on the board:
# 111          1 1 1 0   0 1 1 1   0 0 0 0   1 0 0 0   0 1 0 0   0 0 1 0   0 0 0 1
#              0 0 0 0   0 0 0 0   1 1 1 0   0 1 0 0   0 0 1 0   0 1 0 0   0 0 1 0
#              0 0 0 0   0 0 0 0   0 0 0 0   0 0 1 0   0 0 0 1   1 0 0 0   0 1 0 0
#              0 0 0 0   0 0 0 0   0 0 0 0   0 0 0 0   0 0 0 0   0 0 0 0   1 0 0 0
PATTERN_INDEXATION = {}


class Colors(IntEnum):
    BLACK: int = 1
    WHITE: int = 2


class EngineConfig:
    def __init__(self, extra: Optional[dict]):
        """
        engine configuration, including "extra" parameters coming from a specification object
        """
        extra = extra if extra is not None else {}

        # checking that only the allowed keys are present in the "extra" dictionary
        for key in extra:
            assert key in ('depth', 'max_time', 'incremental', )

        # maximum engine depth when performing searches
        self.max_depth: int = extra.get('depth', ENGINE_DEPTH)

        # maximum thinking time in seconds when performing searches
        self.max_time: float = extra.get('max_time', MAX_TIME / 1000)  # milliseconds

        # the "extra" attribute can be empty
        self.extra = extra or {}

        logging.debug(f"Built engine configuration correctly")

    def get(self, param: str):
        """
        getting configuration parameter from "extra"
        """
        # safe get
        return self.extra.get(param)


def index(x: int, y: int) -> int:
    """
    converts 2D coordinates (x, y) to a 1D index for the flat board representation
    """
    return x * BOARD_SIZE + y


def coordinates(j: int) -> tuple[int, int]:
    """
    converts a 1D index to 2D coordinates (x, y) for the board
    """
    return j // BOARD_SIZE, j % BOARD_SIZE


def cache_squares():
    """
    filling the two index-to-coordinates & coordinates-to-index caches defined above
    """
    for i in range(BOARD_SIZE * BOARD_SIZE):
        c = coordinates(i)  # computed coordinates from the index, appending both caches

        INDEX_TO_COORDINATE[i] = c
        COORDINATE_TO_INDEX[c] = i

    assert len(INDEX_TO_COORDINATE) == len(COORDINATE_TO_INDEX) == BOARD_SIZE * BOARD_SIZE


def _compute_square_neighbors(row: int, column: int):
    """
    computes neighbors for an individual square
    """
    neighbors = set()

    for dx in range(-MOVE_MAX_DISTANCE, MOVE_MAX_DISTANCE + 1):
        for dy in range(-MOVE_MAX_DISTANCE, MOVE_MAX_DISTANCE + 1):
            if abs(dx) + abs(dy) > MOVE_MAX_DISTANCE or (not dx and not dy):
                continue  # the Manhattan distance exceeds the limit, or is 0 (a square can't be its own neighbor)

            new_row, new_col = (row + dx, column + dy)

            if 0 <= new_row < BOARD_SIZE and 0 <= new_col < BOARD_SIZE:
                neighbors.add(new_row * BOARD_SIZE + new_col)

    return neighbors


def _compute_neighbors():
    """
    precomputes neighbors of each square of the board to avoid losing time computing it multiple times at game time
    """
    for index in range(BOARD_SIZE * BOARD_SIZE):
        row, column = index // BOARD_SIZE, index % BOARD_SIZE

        # computing neighbors for each index separately
        index_neighbors = _compute_square_neighbors(row=row, column=column)

        for neighbor in index_neighbors:
            NEIGHBOURS[index].add(neighbor)


def _compute_pattern_indexation():
    """
    pre-computes all the indexes to check for a given pattern size, as explained above in the object description
    """
    # making sure that the pattern indexation object is not yet filled, and that the necessary data is present in the
    # coordinates/index mapping (performance enhancement)
    assert (COORDINATE_TO_INDEX and not PATTERN_INDEXATION)

    for length in set(map(len, PATTERNS)):
        # making sure that this unique length was not yet treated
        assert length not in PATTERN_INDEXATION

        segments = []

        for x in range(BOARD_SIZE):
            for y in range(BOARD_SIZE):
                # looping on each square of the board
                for dx, dy in DIRECTIONS:
                    # each pattern can appear in different directions
                    end_x, end_y = (
                        x + (length - 1) * dx,
                        y + (length - 1) * dy
                    )

                    # pattern falls out of board bounds
                    if not (
                        0 <= end_x < BOARD_SIZE and
                        0 <= end_y < BOARD_SIZE
                    ):
                        continue

                    segment = tuple(
                        index(
                            x + i * dx,
                            y + i * dy
                        )
                        for i in range(length)
                    )

                    segments.append(segment)

        PATTERN_INDEXATION[length] = tuple(segments)


CENTER = BOARD_SIZE // 2

# first engine move if engine plays black is set in advance
FIRST_BLACK_MOVE_INDEX_ENGINE = index(CENTER, CENTER)


# Base-3 encoding of a pattern string. "01110" -> 0*81+1*27+1*9+1*3+0 = 39.
def _encode_pattern(pattern: str) -> int:
    result = 0
    for c in pattern:
        result = result * 3 + int(c)
    return result


# Numpy structures consumed by the JIT-compiled evaluator.
#   SEG_INDICES[length] : int32 array of shape (n_segments, length) — flat board indices
#   SCORE_ARRAY[length] : int64 array indexed by the base-3 signature -> pattern score (0 = none)
#   EVAL_TABLES         : flat [(SEG_INDICES[L], SCORE_ARRAY[L]), ...] the engine loops over
SEG_INDICES = {}
SCORE_ARRAY = {}
EVAL_TABLES = []


def _compute_eval_tables():
    """Must run AFTER _compute_pattern_indexation(): derives numpy tables from it."""
    for length, segments in PATTERN_INDEXATION.items():
        SEG_INDICES[length] = np.array(segments, dtype=np.int32)
        table = np.zeros(3 ** length, dtype=np.int64)
        for pattern, score in PATTERNS.items():
            if len(pattern) == length:
                table[_encode_pattern(pattern)] = score
        SCORE_ARRAY[length] = table
    EVAL_TABLES.clear()
    for length in sorted(SEG_INDICES):
        EVAL_TABLES.append((SEG_INDICES[length], SCORE_ARRAY[length]))


# ---------------------------------------------------------------------------
# incremental-evaluation tables
#
# For O(1) leaf evaluation the board keeps, per color, a running sum of pattern
# scores and updates only the segments passing through the played square on
# move/undo. These feed the Numba delta in utils.py:
#   SCORE_ALL    : all per-length SCORE_ARRAY tables concatenated, indexed by
#                  (offset-of-length + base-3 signature)
#   SQ_ROWS[idx] : (K_MAX, MAX_SEG_LEN) int32, flat cell indices of every segment
#                  passing through `idx` (rows padded with -1)
#   SQ_LEN[idx]  : (K_MAX,) int32, true length of each such segment (0 = padding)
#   SQ_OFF[idx]  : (K_MAX,) int64, offset into SCORE_ALL for that segment's length
# ---------------------------------------------------------------------------
SCORE_ALL = None
SQ_ROWS = None
SQ_LEN = None
SQ_OFF = None


def _compute_incremental_tables():
    """Must run AFTER _compute_eval_tables(): builds the per-square segment map."""
    global SCORE_ALL, SQ_ROWS, SQ_LEN, SQ_OFF

    lengths = sorted(SCORE_ARRAY)

    # offset of each length's table inside the concatenated SCORE_ALL
    offset = {}
    running = 0
    for length in lengths:
        offset[length] = running
        running += 3 ** length

    SCORE_ALL = np.concatenate([SCORE_ARRAY[length] for length in lengths]).astype(np.int64)

    max_len = max(lengths)

    # for each square, collect the segments that pass through it
    per_square = {i: [] for i in range(BOARD_SIZE * BOARD_SIZE)}
    for length, segments in PATTERN_INDEXATION.items():
        off = offset[length]
        for seg in segments:
            for cell in seg:
                per_square[cell].append((seg, length, off))

    k_max = max(len(v) for v in per_square.values())

    n = BOARD_SIZE * BOARD_SIZE
    SQ_ROWS = np.full((n, k_max, max_len), -1, dtype=np.int32)
    SQ_LEN = np.zeros((n, k_max), dtype=np.int32)
    SQ_OFF = np.zeros((n, k_max), dtype=np.int64)

    for idx in range(n):
        for k, (seg, length, off) in enumerate(per_square[idx]):
            for j, cell in enumerate(seg):
                SQ_ROWS[idx, k, j] = cell
            SQ_LEN[idx, k] = length
            SQ_OFF[idx, k] = off

    logging.debug("Built incremental-evaluation tables (K_MAX=%d)", k_max)


@timecall
def initialize_config():
    # pre-computing neighbors ahead of plays
    _compute_neighbors()

    # also pre-computing a cache storing index/coordinates values
    cache_squares()

    # pre-computing pattern indexation lookup
    _compute_pattern_indexation()

    _compute_eval_tables()

    # pre-computing the per-square segment map used by the incremental evaluator
    _compute_incremental_tables()


initialize_config()
