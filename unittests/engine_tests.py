"""
    Testing the board object implementation
"""

# library imports
from time import perf_counter
import unittest

# module imports
from utils import Board, Move, deterministic_vectors, cache_hash
from engine import FiveZeroEngine, EngineSpec


class TestEnginePatternIdent(unittest.TestCase):
    """
    testing engine pattern recognition
    """
    def test_pattern_ident(self):
        """
        testing various patterns as test cases
        """
        # engine plays black
        engine = FiveZeroEngine(engine_color=1, spec=None)

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


class TestEvaluationCache(unittest.TestCase):
    """
    testing the caching mechanism of the pattern identification algorithm
    """
    def test_cache_separation(self):
        """
        testing if two different engines are hitting two different caches when calling their evaluation function

        - creating two engine objects and asserting that their evaluation cache is not the same object
        """
        # creating engine objects
        e1 = FiveZeroEngine(engine_color=1, spec=None)
        e2 = FiveZeroEngine(engine_color=2, spec=None)

        c1 = e1.evaluate.cache
        c2 = e2.evaluate.cache

        assert c1 is not c2

    def test_cache_call(self):
        """
        testing that the evaluation cache is correctly used

        - creating an engine object, performing moves on its board, evaluating the position and checking that the cache
          is in the expected state

        - evaluating again to check that the cache is being hit as expected
        """
        version = "1.0.0"

        # engine specification object
        spec = EngineSpec(
            id=version,
            blurb="PROD"
        )

        # creating engine object
        engine = FiveZeroEngine(
            engine_color=1,
            spec=spec
        )

        # performing a few moves
        moves = (
            Move(index=Board.index(7, 7), color=1),
            Move(index=Board.index(7, 8), color=2),
            Move(index=Board.index(8, 7), color=1),
            Move(index=Board.index(8, 8), color=2),
            Move(index=Board.index(7, 11), color=1),
            Move(index=Board.index(7, 12), color=2),
        )

        for move in moves:
            engine.board.move(move=move)

        # position evaluation
        r1 = engine.evaluate(board_bytes=engine.board.board, tempo=1)

        # cache forensics
        cache = engine.evaluate.cache
        hits = engine.evaluate.cache_hits()
        cache_size = engine.evaluate.cache_size()
        engine_name = engine.evaluate.engine_name

        # checking that the engine name is assigned when decorating the method
        self.assertEqual(engine_name, spec.id)

        # checking that the evaluation was indeed cached
        self.assertIn(
            cache_hash(board=engine.board.board, tempo=1),  # evaluation is located using this key
            cache
        )

        # no hits yet
        self.assertEqual(hits, 0)

        # cache now contains the empty position evaluation (done at init to JIT-warm the evaluation)
        self.assertEqual(cache_size, 2)

        # calling the evaluation on the same board to make sure the cache is being used
        r2 = engine.evaluate(board_bytes=engine.board.board, tempo=1)

        # checking that the two evaluations led to the same result
        self.assertEqual(r1, r2)

        hits = engine.evaluate.cache_hits()
        cache_size = engine.evaluate.cache_size()

        # 1 hit must have happened now
        self.assertEqual(hits, 1)

        # still the same cache size
        self.assertEqual(cache_size, 2)


class TestEvaluationPerformance(unittest.TestCase):
    """
    benchmark for the evaluation function, not a correctness test
    """
    def test_evaluation_speed(self):
        # engine object
        engine = FiveZeroEngine(
            engine_color=1,
            spec=None
        )

        # generating n_vectors random (fixed seed, deterministic values) sequences of n_moves
        n_vectors, n_moves = 5000, 10

        # using my gf birthdate as seed <3
        seed = 30111992

        move_sequences = set(
            deterministic_vectors(
                vector_size=n_moves,
                n_vectors=n_vectors,
                seed=seed
            )
        )

        start = perf_counter()

        for move_sequence in move_sequences:
            # clearing the board
            engine.board.clear()

            # performing individual moves only
            for j, index in enumerate(set(move_sequence)):
                engine.board.move(Move(index, color=j % 2 + 1))

            engine.evaluate(
                board_bytes=engine.board.board,
                tempo=len(move_sequence) % 2 + 1
            )

        elapsed = perf_counter() - start

        print(f"""
        performed {n_vectors} evaluations
        elapsed: {elapsed:.3f}s
        average: {elapsed / n_vectors * 1e3:.2f} ms/evaluation
        """)

        # cache append is still used but lookup is disabled
        assert engine.evaluate.cache_size() == n_vectors + 1

        # no hits should happen
        assert engine.evaluate.cache_hits() == 0
