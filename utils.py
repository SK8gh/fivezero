from argparse import ArgumentParser, Namespace
from dataclasses import dataclass, field
from functools import wraps
import numpy as np
import logging

from configuration import (
    FIRST_BLACK_MOVE_INDEX_ENGINE,
    COORDINATE_TO_INDEX,
    INDEX_TO_COORDINATE,
    CENTER_WEIGHTS,
    CENTRAL_COEF,
    BOARD_SIZE,
    NEIGHBORS,
    Colors
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

    # centrality score of the board, used for evaluation
    centrality: int = 0

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

        # updating the centrality score
        self.centrality += (1 if move.color == Colors.BLACK else -1) * CENTER_WEIGHTS[move.index] * CENTRAL_COEF

        self.history.append(move.index)

        # updating board 'closest moves' attribute
        self._update_closest(move=move)

    def undo_move(self, move: Move) -> None:
        """
        undoing move
        """
        assert self.get_index(move.index) != self.EMPTY

        # undoing move
        self.set_index(index=move.index, value=self.EMPTY)

        # removing 1 to the count of moves
        self.n_moves -= 1

        # updating the centrality score
        self.centrality -= (1 if move.color == Colors.BLACK else -1) * CENTER_WEIGHTS[move.index] * CENTRAL_COEF

        # removing the move from history
        self.history.remove(move.index)

    def _update_closest(self, move: Move) -> None:
        """
        updating the closest "moves" attribute, storing the "playable" moves that are at a maximum distance of a placed
            stone on the board
        """
        neighbors = NEIGHBORS[move.index]

        # correcting the neighbors with allowed values (empty squares only)
        allowed = set((n for n in neighbors if self.get_index(n) == self.EMPTY))

        # adding new closest (possible) moves
        self.closest_moves.update(allowed)

        # removing the move being played from possible moves
        self.closest_moves.discard(move.index)

    @staticmethod
    def clone(instance: "Board") -> "Board":
        """
        clones the board in a more optimized way than using deepcopy
        """
        return Board(
            closest_moves=instance.closest_moves.copy(),
            history=instance.history.copy(),
            board=instance.board.copy(),
            n_moves=instance.n_moves
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

        # clearing allowed moves & move history
        self.closest_moves.clear(), self.history.clear()

        self.n_moves = 0


def cache_hash(board: bytearray, tempo: int) -> tuple:
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
        def wrapper(*args, **kwargs):
            nonlocal _hits

            board: bytearray = kwargs["board_bytes"]
            tempo: int = kwargs["tempo"]

            h = cache_hash(board, tempo)

            if h not in _cache:
                _cache[h] = evaluation_function(*args, **kwargs)
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
