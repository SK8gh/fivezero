from singleton_decorator import singleton
from profilehooks import timecall
from enum import IntEnum


# Engine name
USERNAME = "FiveZero"

# number of stones to line up to win
WINNING_LENGTH = 5

# Game board size
BOARD_SIZE = 15

# Maximum thinking time
MAX_TIME = 1.5

# Using the following variable to bypass the timeout mechanism, for testing purposes only
BYPASS_TIMEOUT = False

# If set to true, the engine will not use the evaluation cache
BYPASS_EVALUATION_CACHE = True

# Move pruning maximum distance
MOVE_MAX_DISTANCE = 2

# holds the neighbors of each index representing a square
NEIGHBORS = {index: set() for index in range(BOARD_SIZE * BOARD_SIZE)}

# Maximum number of moves to look ahead for
ENGINE_DEPTH = 5

# Parallelization factor of root moves
PARALLEL = 8

# Tempo factor, used to evaluate positions based on who has the trait
TEMPO_FACTOR = 1.5

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

PATTERNS = {
    # Five
    "11111": 100_000_000,

    # Open Four
    "011110": 1_000_000,

    # Closed Four / Simple Four
    "11110": 100_000,
    "01111": 100_000,
    "11011": 100_000,
    "10111": 100_000,
    "11101": 100_000,

    # Open Three
    "01110": 10_000,

    # Broken Three / Jump Three
    "011010": 5_000,
    "010110": 5_000,

    # Open Two
    "001100": 1_000,
    "011000": 1_000,
    "000110": 1_000,

    # Broken Two
    "0010100": 100,
    "0001010": 100,
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


@singleton
class EngineConfig:
    def __init__(self):
        # maximum engine depth when performing searches
        self.max_depth: int = ENGINE_DEPTH

        # maximum thinking time in seconds when performing searches
        self.max_time: float = MAX_TIME


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
            NEIGHBORS[index].add(neighbor)


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


# first engine move if engine plays black is set in advance
FIRST_BLACK_MOVE_INDEX_ENGINE = index(BOARD_SIZE // 2, BOARD_SIZE // 2)


@timecall
def initialize_config():
    # pre-computing neighbors ahead of plays
    _compute_neighbors()

    # also pre-computing a cache storing index/coordinates values
    cache_squares()

    # pre-computing pattern indexation lookup
    _compute_pattern_indexation()


initialize_config()
