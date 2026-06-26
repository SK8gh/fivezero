"""
    Testing the board object implementation
"""

from unittest.mock import MagicMock, patch
from engine import FiveZeroEngine
from client import GameClient
from utils import Board, Move
import unittest

from configuration import Colors


class TestEnginePatternIdent(unittest.TestCase):
    """
    testing engine pattern recognition
    """
    @patch.object(GameClient, "_login")
    @patch.object(GameClient, "_create_hub")
    def test_pattern_ident(self, mock_create_hub, mock_login):
        """
        testing various patterns as test cases
        """
        mock_login.return_value = "token"

        fake_hub = MagicMock()
        mock_create_hub.return_value = fake_hub

        client = GameClient("fake_password")

        engine = FiveZeroEngine(client=client)

        board = engine.board

        test_cases = (
            {
                # 5 in a row from the origin
                'moves': (
                    Move(index=Board.index(0, 0), color=1),
                    Move(index=Board.index(0, 1), color=1),
                    Move(index=Board.index(0, 2), color=1),
                    Move(index=Board.index(0, 3), color=1),
                    Move(index=Board.index(0, 4), color=1)
                ),
                'pattern': '11111',
                'color': 1,
                'coordinates': [
                    (0, 1, 2, 3, 4)
                ]
            },
            {
                # offset 5 in a row
                'moves': (
                    Move(index=Board.index(5, 5), color=1),
                    Move(index=Board.index(5, 6), color=1),
                    Move(index=Board.index(5, 7), color=1),
                    Move(index=Board.index(5, 8), color=1),
                    Move(index=Board.index(5, 9), color=1)
                ),
                'pattern': '11111',
                'color': 1,
                'coordinates': [
                    (80, 81, 82, 83, 84)
                ]
            },
            {
                # white stones diagonal five in a row
                'moves': (
                    Move(index=Board.index(1, 1), color=2),
                    Move(index=Board.index(2, 2), color=2),
                    Move(index=Board.index(3, 3), color=2),
                    Move(index=Board.index(4, 4), color=2),
                    Move(index=Board.index(5, 5), color=2)
                ),
                'pattern': '11111',
                'color': 2,
                'coordinates': [
                    (16, 32, 48, 64, 80)
                ]
            },
            {
                # white stones anti-diagonal five in a row
                'moves': (
                    Move(index=Board.index(5, 10), color=2),
                    Move(index=Board.index(6, 9), color=2),
                    Move(index=Board.index(7, 8), color=2),
                    Move(index=Board.index(8, 7), color=2),
                    Move(index=Board.index(9, 6), color=2)
                ),
                'pattern': '11111',
                'color': 2,
                'coordinates': [
                    (85, 99, 113, 127, 141)
                ]
            },
            {
                # no match - 5 in a row
                'moves': (
                    Move(index=Board.index(0, 0), color=2),
                    Move(index=Board.index(1, 1), color=2),
                    Move(index=Board.index(2, 2), color=2),
                    Move(index=Board.index(3, 3), color=2),
                ),
                'pattern': '11111',
                'color': 2,
                'coordinates': []
            },
            {
                # closed four pattern
                'moves': (
                    Move(index=Board.index(0, 0), color=2),
                    Move(index=Board.index(1, 1), color=2),
                    Move(index=Board.index(2, 2), color=2),
                    Move(index=Board.index(4, 4), color=2),
                ),
                'pattern': '11101',
                'color': 2,
                'coordinates': [
                    (0, 16, 32, 48, 64)
                ]
            },
            {
                # closed four pattern
                'moves': (
                    Move(index=Board.index(10, 10), color=2),
                    Move(index=Board.index(11, 10), color=2),
                    Move(index=Board.index(12, 10), color=2),
                    Move(index=Board.index(13, 10), color=2),
                    Move(index=Board.index(14, 10), color=2),
                ),
                'pattern': '11111',
                'color': 2,
                'coordinates': [
                    (160, 175, 190, 205, 220)
                ]
            }
        )

        for test_case in test_cases:
            moves, pattern, color, coordinates = (test_case[k] for k in ('moves', 'pattern', 'color', 'coordinates'))

            with self.subTest(
                    moves=moves,
                    pattern=pattern,
                    color=color,
                    coordinates=coordinates
            ):
                # clearing the board before running the test
                board.clear()

                # performing the moves
                for move in moves:
                    board.move(move=move)

                # identifying the patterns
                result = engine._ident_pattern(
                    board_bytes=board.board,
                    pattern=pattern,
                    color=color
                )

                # checking the result against the expectation
                self.assertEqual(result, coordinates)


class TestBoardCache(unittest.TestCase):
    """
    testing the caching mechanism of the pattern identification algorithm
    """
    def test_cache(self):
        """
        testing if the caching mechanisms of board evaluation is correctly implemented

        - creating boards, calling the evaluation on the same boards to test the cache
        """
        pass

    def test_measure_cache_usage(self):
        """

        """
        pass
