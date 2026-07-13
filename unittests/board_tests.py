"""
    Testing the board object implementation
"""

import unittest

import configuration
from utils import Board, Move

from configuration import (
    FIRST_BLACK_MOVE_INDEX_ENGINE,
    BOARD_SIZE,
    NEIGHBOURS
)


class TestFork(unittest.TestCase):
    """
    testing the fork method that create a new instance of a board and makes a move
    """
    def test_fork(self):
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
        for attr in ('board', 'closest_moves', 'n_moves', 'history', ):
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

        # unique fingerprint identifying the board object
        fingerprint_before = board.fingerprint()

        # fork-moving
        board_fork = board.fork_move(move=move)

        board_fork.undo_move(move=move)

        assert board.fingerprint() == fingerprint_before


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

    def test_undo(self):
        """
        creating a board, making a move and undoing it

        checking that the two boards:
            - are not the same object
            - have the same configuration
            - have the same number of moves
        """
        # empty board
        board = Board()

        # performing the first move
        board.move(
            move=Move(
                index=FIRST_BLACK_MOVE_INDEX_ENGINE,
                color=1  # black always play first
            )
        )

        # Black stone placed on the top right of the board
        index = BOARD_SIZE - 1

        move = Move(index=index, color=2)

        # unique fingerprint identifying the board object
        fingerprint_before = board.fingerprint()

        board.move(move=move)

        board.undo_move(move=move)

        fingerprint_after = board.fingerprint()

        for key in fingerprint_before:
            v_a, v_b = fingerprint_before[key], fingerprint_after[key]

            self.assertEqual(v_a, v_b)

    def test_undo_connected(self):
        """
        creating a board, making a move and undoing it. The undone move is "close" to already performed move to
        test extra cases of the _undo_closest method of the Board object

        checking that the two boards:
            - are not the same object
            - have the same configuration
            - have the same number of moves
        """
        # empty board
        board = Board()

        # performing the first move
        board.move(
            move=Move(
                index=FIRST_BLACK_MOVE_INDEX_ENGINE,
                color=1  # black always play first
            )
        )

        # Black stone placed on the top right of the board
        index = FIRST_BLACK_MOVE_INDEX_ENGINE + 1

        move = Move(index=index, color=2)

        # unique fingerprint identifying the board object
        fingerprint_before = board.fingerprint()

        board.move(move=move)

        board.undo_move(move=move)

        fingerprint_after = board.fingerprint()

        for key in fingerprint_before:
            v_a, v_b = fingerprint_before[key], fingerprint_after[key]

            self.assertEqual(v_a, v_b)

    def test_undo_empty(self):
        """
        creating a board, making a single move and undoing it. This function tests the special case where the board is
        empty again in the _undo_closest method of the Board object

        checking that the two boards:
            - are not the same object
            - have the same configuration
            - have the same number of moves
        """
        # empty board
        board = Board()

        # performing the first move and undoing it
        move = Move(
            index=FIRST_BLACK_MOVE_INDEX_ENGINE,
            color=1  # black always play first
        )

        # unique fingerprint identifying the board object
        fingerprint_before = board.fingerprint()

        board.move(
            move=move
        )

        board.undo_move(move=move)

        fingerprint_after = board.fingerprint()

        for key in fingerprint_before:
            v_a, v_b = fingerprint_before[key], fingerprint_after[key]

            self.assertEqual(v_a, v_b,  f"fingerprints do not match for key '{key}'")

    def test_moves_1(self):
        """
        this case yielded an exception because of the neighbours count
        """
        board = Board()

        indexes = (139, 115, 143, 39, 207, 91, 168, 151, 100, 13)

        for j, index in enumerate(indexes):
            try:
                board.move(
                    Move(index=index, color=j % 2 + 1)
                )

            except (Exception, ) as e:
                self.fail(f"Moving j={j}, index={index} is not supposed to raise an exception: {e}")


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
                expected_neighbors = {board.coordinates(n) for n in NEIGHBOURS[index]}

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


class TestClone(unittest.TestCase):
    """
    testing the cloning mechanism of the board class
    """
    def test_equality(self):
        """
        b = a.clone() testing that a equals b, and that the copy is a deepcopy
        """
        # new empty board object
        a = Board()

        # performing some moves
        moves = (
            Move(index=0, color=1),
            Move(index=1, color=2),
            Move(index=2, color=1),
        )
        for move in moves:
            a.move(move=move)

        b = Board.clone(a)

        # "Board" implements __eq__
        self.assertEqual(a, b)

        # other attributes must be equal too
        self.assertEqual(a.history, b.history)
        self.assertEqual(a.n_moves, b.n_moves)

        # testing that attributes are not the same object
        self.assertIsNot(a.board, b.board)
        self.assertIsNot(a.history, b.history)
        self.assertIsNot(a.board, b.board)


if __name__ == "__main__":
    unittest.main()
