"""
    Testing the board object implementation
"""

import unittest

from utils import Board, Move

from configuration import (
    BOARD_SIZE,
    NEIGHBORS
)


class TestFork(unittest.TestCase):
    """
    testing the fork method that create a new instance of a board and makes a move
    """
    def test_fork_ids(self):
        """
        creating a board, making a fork move

        - checking that both objects are different and that attributes were not shallow copied
        """
        # empty board
        board = Board()

        # fork-moving, placing a black stone on the top left of the board
        board_fork = board.fork_move(Move(index=0, color=1))

        # asserting that the two boards are not the same object
        self.assertIsNot(board, board_fork)

        # asserting that board attributes are different
        for attr in ('board', 'closest_moves', 'n_moves'):
            self.assertIsNot(getattr(board, attr), getattr(board_fork, attr))

    def test_fork_undo(self):
        """
        creating a board, making a fork move and undoing it

        checking that the two boards:
            - are not the same object
            - have the same configuration
            - have the same number of moves
        """
        # empty board
        board = Board()

        # Black stone placed on the top right of the board
        move = Move(index=BOARD_SIZE - 1, color=1)

        # fork-moving
        board_fork = board.fork_move(move=move)

        board_fork.undo_move(move=move)

        # asserting that the two boards are not the same object
        self.assertIsNot(board, board_fork)

        # board states must be equal
        self.assertEqual(board, board_fork)

        # number of moves should be the same (not tested in ==)
        self.assertEqual(board.n_moves, board_fork.n_moves)


class TestBoardMoves(unittest.TestCase):
    """
    testing board states when moving
    """
    def test_index(self):
        """
        testing the method that maps the coordinates of a board square and its index

        - those tests won't pass is the BOARD_SIZE constant is changed
        """
        test_cases = (
            {
                'coordinates': (0, 0),  # top left
                'index': 0
            },
            {
                'coordinates': (0, BOARD_SIZE - 1),  # top right
                'index': BOARD_SIZE - 1
            },
            {
                'coordinates': (BOARD_SIZE - 1, 0),  # bottom left
                'index': BOARD_SIZE * (BOARD_SIZE - 1)
            },
            {
                'coordinates': (BOARD_SIZE - 1, BOARD_SIZE - 1),  # bottom right
                'index': (BOARD_SIZE * BOARD_SIZE) - 1
            },
            # other examples
            {
                'coordinates': (2, 2),
                'index': 32
            },
            {
                'coordinates': (1, 2),
                'index': 17
            },
            {
                'coordinates': (2, 1),
                'index': 31
            },
            {
                'coordinates': (2, 3),
                'index': 33
            },
            {
                'coordinates': (3, 2),
                'index': 47
            },
            {
                'coordinates': (8, 4),
                'index': 124
            },
            {
                'coordinates': (4, 10),
                'index': 70
            },
        )

        for case in test_cases:
            coordinates, index = case['coordinates'], case['index']

            with self.subTest(
                    coordinates=coordinates,
                    index=index
            ):
                x, y = coordinates

                expected_index = Board.index(x, y)
                expected_coordinates = Board.coordinates(index)

                self.assertEqual(
                    index,
                    expected_index
                )

                self.assertEqual(
                    coordinates,
                    expected_coordinates
                )

    def test_all_index(self):
        """
        for all possible board square (coordinates i, j) computing its index

        - checking that no different squares do not map to the same index
        """
        d: dict[int, tuple[int, int]] = {}  # {index: coordinates}

        for i in range(BOARD_SIZE):
            for j in range(BOARD_SIZE):
                square_index = Board.index(i, j)

                if square_index not in d:
                    # not coordinates map to this precise index yet, everything is fine
                    d[square_index] = (i, j)

                else:
                    # problematic case, two different pairs of coordinates map to the same index
                    msg = f"{d[square_index]} and {(i, j)} squares map to the same index {square_index}"
                    self.fail(msg)

        self.assertEqual(len(d), BOARD_SIZE ** 2)  # checking that the correct number of indexes were computed
        pass  # if this point is reached, the test is successful

    def test_all_coordinates(self):
        """
        for all possible indexes (integers from 0 to BOARD_SIZE squared) computing associated square (coordinates)

        - checking that no pair of different indexes map to the same board square
        """
        d: dict[tuple[int, int], int] = {}  # {coordinates: indexes}

        for index in range(BOARD_SIZE ** 2):
            coordinates = Board.coordinates(index)

            if coordinates not in d:
                d[coordinates] = index

            else:
                msg = f"{d[coordinates]} and {coordinates} squares map to the same index {index}"
                self.fail(msg)

        self.assertEqual(len(d), BOARD_SIZE ** 2)

    def test_board_history(self):
        """
        testing if the history of moves of a board is congruent with the performed moves
        """
        # creating virgin board object
        board = Board()

        # performing a few moves
        moves = [
            112,  # storing moves as indexes
            113,
            114,
            115,
            116,
            117
        ]

        for j, index in enumerate(moves):
            board.move(move=Move(index=index, color=j % 2 + 1))

        self.assertEqual(moves, board.history)


class TestPlayableMoves(unittest.TestCase):
    """
    testing the method that computes playable moves, meaning moves that are "close" to already-played-stones
    """
    def test_single_moves(self):
        """
        testing playable moves from boards containing a single move
        """
        # empty board
        board = Board()

        test_cases = (
            {
                'coordinates': (0, 0),  # move coordinates
                'neighbors': {  # expected neighbors, stored in a coordinates form, indenting once per row
                    (0, 1), (0, 2),  # 0th row neighbors
                    (1, 0), (1, 1),  # 1st row neighbors
                    (2, 0)           # etc...
                }
            },
            {
                'coordinates': (2, 2),
                'neighbors': {
                    (0, 2),
                    (1, 1), (1, 2), (1, 3),
                    (2, 0), (2, 1), (2, 3), (2, 4),
                    (3, 1), (3, 2), (3, 3),
                    (4, 2)
                }
            },
            {
                'coordinates': (3, BOARD_SIZE - 1),  # 3rd row, last column
                'neighbors': {
                    (1, BOARD_SIZE - 1),
                    (2, BOARD_SIZE - 2), (2, BOARD_SIZE - 1),
                    (3, BOARD_SIZE - 3), (3, BOARD_SIZE - 2),
                    (4, BOARD_SIZE - 2), (4, BOARD_SIZE - 1),
                    (5, BOARD_SIZE - 1),
                }
            }
        )

        for case in test_cases:
            coordinates, neighbors = case['coordinates'], case['neighbors']

            with self.subTest(
                    coordinates=coordinates,
                    neighbors=neighbors
            ):
                # computing the move to perform from the coordinates
                index = board.index(*coordinates)

                # expected neighbors must be converted to indexes
                expected_neighbors = {board.coordinates(n) for n in NEIGHBORS[index]}

                self.assertEqual(neighbors, expected_neighbors)


class TestClearing(unittest.TestCase):
    """
    testing the clearing of the board as some sensitive tests are dependent on this operation
    """
    def test_clear(self):
        """
        creating a board, performing some moves, clearing it

        - checking that the cleared board is equal to an empty one freshly created
        """
        board = Board()

        board.move(
            move=Move(index=0, color=1)
        )

        board.clear()

        self.assertEqual(board, Board())


if __name__ == "__main__":
    unittest.main()
