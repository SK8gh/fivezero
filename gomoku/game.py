"""
game logic, independent of other components
"""

from __future__ import annotations

from configuration import (
    WINNING_LENGTH,
    coordinates,
    BOARD_SIZE,
    DIRECTIONS,
    Colors,
    index
)

from utils import Board

BLACK, WHITE, EMPTY = Colors.BLACK, Colors.WHITE, Board.EMPTY


def opponent(color: int) -> int:
    return WHITE if color == BLACK else BLACK


class GomokuGame:
    """
    Game state object keeping track of the board state, player turn, last move & winner
    """
    def __init__(self) -> None:
        # initializing attributes
        self.cells, self.current, self.last_move, self.winner, self.moves_played = [], 0, None, None, 0

        self.reset()

    def reset(self) -> None:
        # keeping track the board state
        self.cells: list[int] = [EMPTY] * (BOARD_SIZE * BOARD_SIZE)

        # current player having the trait
        self.current: int = BLACK

        # last move played on the board
        self.last_move: int | None = None

        # game winner
        self.winner: int | None = None

        # counter of move played
        self.moves_played: int = 0

    @property
    def over(self) -> bool:
        """
        returns true if the game is over, either by victory of draw
        """
        return self.winner is not None or self.is_full()

    def is_full(self) -> bool:
        """
        returns true if the board is filled
        """
        return self.moves_played >= BOARD_SIZE * BOARD_SIZE

    def is_empty_cell(self, i: int) -> bool:
        """
        returns true if a cell is empty, false otherwise
        """
        return self.cells[i] == EMPTY

    def play(self, j: int) -> bool:
        """
        plays move, returns true if the move was legal, false otherwise
        """
        if self.over or not (0 <= j < len(self.cells)) or self.cells[j] != EMPTY:
            """
            game is over, or move is out of bounds, or cell is already occupied
            """
            return False

        # color of the current player
        color = self.current

        # assigning the player color to the cell
        self.cells[j] = color

        # updating the last move value
        self.last_move = j

        # incrementing the moves played counter
        self.moves_played += 1

        if self._wins_at(j, color):
            self.winner = color
        else:
            self.current = opponent(color)
        return True

    def _wins_at(self, j: int, color: int) -> bool:
        """
        checks if the move is winning
        """
        row, col = coordinates(j)

        for dr, dc in DIRECTIONS:
            count = 1
            for sign in (1, -1):
                r, c = row + sign * dr, col + sign * dc

                while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and self.cells[index(r, c)] == color:
                    count += 1
                    r += sign * dr
                    c += sign * dc

            if count >= WINNING_LENGTH:
                # more than 5 stones of the same color are lined up, returning true
                return True

        return False
