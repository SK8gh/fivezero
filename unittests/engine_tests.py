"""
    Exhaustive testing of the FiveZero engine (incremental evaluation + fork search).
"""

# library imports
from datetime import datetime, timezone
from time import perf_counter
import unittest

# module imports
from utils import deterministic_vectors, Move, Board
from engine import FiveZeroEngine, EngineSpec

from configuration import (
    FIRST_BLACK_MOVE_INDEX_ENGINE,
    BOARD_SIZE,
    FIVE,
    Colors,
)


def make_engine(
        color: int = Colors.BLACK,
        depth: int = 2,
        max_time: float = 10.0
) -> FiveZeroEngine:
    """
    builds an engine with a bounded, fully-searchable configuration so tactical tests reach a deterministic result
    (large time budget -> never times out mid-search at these shallow depths)
    """
    return FiveZeroEngine(
        engine_color=int(color),
        spec=EngineSpec(
            id="test",
            blurb="test",
            params={
                "depth": depth,
                "max_time": max_time
            }
        ),
    )


def tracked_board() -> Board:
    """
    fresh board with incremental evaluation enabled (as the engine uses it)
    """
    board = Board()
    board.set_eval_tracking()
    return board


def play(board: Board, moves: list[tuple[int, int]]) -> None:
    """
    applies a list of (index, color) moves to a board
    """
    for idx, color in moves:
        board.move(Move(index=idx, color=color))


def random_moves(seed: int, n: int) -> list[tuple[int, int]]:
    """
    reproducible list of (index, color) with DISTINCT squares, colors alternating
    black/white. Uses deterministic_vectors so runs are repeatable.
    """
    vector = deterministic_vectors(vector_size=n, n_vectors=1, seed=seed)[0]

    seen: set[int] = set()
    moves: list[tuple[int, int]] = []
    color = Colors.BLACK

    for idx in vector:
        if idx in seen:
            continue
        seen.add(idx)
        moves.append((int(idx), int(color)))
        color = Colors.WHITE if color == Colors.BLACK else Colors.BLACK

    return moves


def now() -> datetime:
    return datetime.now(timezone.utc)


class TestEngineConstruction(unittest.TestCase):
    def test_builds_for_both_colors(self):
        """
        the engine constructs (and JIT-warms) for either color
        """
        for color in (Colors.BLACK, Colors.WHITE):
            with self.subTest(color=color):
                engine = make_engine(color)
                self.assertEqual(engine.color, int(color))

    def test_starts_on_empty_tracked_board(self):
        """
        a fresh engine has an empty board with eval tracking on and zero sums
        """
        engine = make_engine(Colors.BLACK)

        self.assertEqual(engine.board.n_moves, 0)
        self.assertEqual(engine.board.eval_sum[Colors.BLACK], 0)
        self.assertEqual(engine.board.eval_sum[Colors.WHITE], 0)


class TestEvaluation(unittest.TestCase):
    def test_empty_board(self):
        """
        no stones -> no patterns -> evaluation is exactly 0 for any tempo
        """
        engine = make_engine(Colors.BLACK)
        board = tracked_board()

        for tempo in (Colors.BLACK, Colors.WHITE):
            with self.subTest(tempo=tempo):
                self.assertEqual(engine._evaluate_leaf(board, int(tempo)), 0)

    def test_tempo_ordering(self):
        """
        eval(tempo = engine) >= eval(tempo = opponent) on any position
        """
        engine = make_engine(Colors.BLACK)
        opp = Colors.WHITE

        n_sample, n_moves = 100, 20

        for seed in range(n_sample):
            board = tracked_board()

            play(
                board,
                random_moves(seed=seed, n=n_moves)
            )

            with self.subTest(seed=seed):
                self.assertGreaterEqual(
                    engine._evaluate_leaf(
                        board=board,
                        tempo=int(engine.color)
                    ),
                    engine._evaluate_leaf(
                        board=board,
                        tempo=int(opp)
                    ),
                )

    def test_color_negation(self):
        """
        the same position evaluated by a Black engine and a White engine gives
        exact opposites -- validates the color/tempo handling end to end.
        """
        black = make_engine(Colors.BLACK)
        white = make_engine(Colors.WHITE)

        n_positions, n_moves = 100, 15

        for seed in range(n_positions):
            board = tracked_board()

            play(
                board,
                random_moves(seed=seed, n=15)
            )

            for tempo in (Colors.BLACK, Colors.WHITE):
                with self.subTest(seed=seed, tempo=tempo):
                    self.assertEqual(
                        black._evaluate_leaf(board, int(tempo)),
                        - white._evaluate_leaf(board, int(tempo))
                    )

    def test_engine_advantage_is_positive(self):
        """
        a lone engine stone group (opponent absent) scores strictly positive
        """
        engine = make_engine(Colors.BLACK)
        board = tracked_board()

        # a black open three, no white stones
        play(board,
             [
                 (Board.index(7, 5), Colors.BLACK),
                 (Board.index(7, 6), Colors.BLACK),
                 (Board.index(7, 7), Colors.BLACK)
             ]
             )

        self.assertGreater(engine._evaluate_leaf(board, int(engine.color)), 0)

    def test_five_dominates(self):
        """
        a completed five makes the evaluation exceed the FIVE constant
        """
        engine = make_engine(Colors.BLACK)
        board = tracked_board()
        play(board, [(Board.index(7, c), Colors.BLACK) for c in range(3, 8)])  # five in a row
        self.assertGreater(engine._evaluate_leaf(board, int(engine.color)), FIVE)

    def test_eval_is_move_order_independent(self):
        """
        the incremental sums depend only on the position, not the move order
        """
        moves = random_moves(seed=42, n=16)

        forward = tracked_board()
        play(forward, moves)

        backward = tracked_board()
        play(backward, list(reversed(moves)))

        self.assertEqual(forward.eval_sum, backward.eval_sum)

    def test_fork_matches_sequential(self):
        """
        building a position by chained fork_move (what search does) yields the same running sums as mutating a single
        board in place.
        """
        moves = random_moves(seed=7, n=16)

        sequential = tracked_board()
        play(sequential, moves)

        forked = tracked_board()
        for idx, color in moves:
            forked = forked.fork_move(Move(index=idx, color=color))

        self.assertEqual(forked.eval_sum, sequential.eval_sum)


class TestSearchLegality(unittest.TestCase):
    def test_empty_returns_center(self):
        """
        the only legal opening candidate is the center, so search returns it
        """
        engine = make_engine(Colors.BLACK)
        move = engine.search(move_timestamp=now())

        self.assertIsNotNone(move)
        self.assertEqual(move.index, FIRST_BLACK_MOVE_INDEX_ENGINE)
        self.assertEqual(move.color, engine.color)

    def test_returns_legal_candidate(self):
        """
        the chosen move is an empty square drawn from the candidate set
        """
        n_tests, n_moves, seed = 100, 10, 99

        for j in range(n_tests):
            with self.subTest():
                # recreating the
                engine = make_engine(Colors.BLACK)
                play(engine.board, random_moves(seed=seed + j, n=n_moves))

                candidates_before = set(engine.board.closest_moves)
                move = engine.search(move_timestamp=now())

                self.assertIsNotNone(move)
                self.assertIn(move.index, candidates_before)
                self.assertEqual(engine.board.get_index(move.index), Board.EMPTY)
                self.assertEqual(move.color, engine.color)
                self.assertTrue(0 <= move.index < BOARD_SIZE ** 2)

    def test_search_does_not_mutate_engine_board(self):
        """
        search works on forks: the engine's own board and sums are untouched
        """
        engine = make_engine(Colors.BLACK, depth=3)
        play(engine.board, random_moves(seed=2, n=6))

        fingerprint_before = engine.board.fingerprint()
        sums_before = list(engine.board.eval_sum)

        engine.search(move_timestamp=now())

        self.assertEqual(engine.board.fingerprint(), fingerprint_before)
        self.assertEqual(list(engine.board.eval_sum), sums_before)


class TestTactics(unittest.TestCase):
    def test_takes_immediate_win(self):
        """
        black has four in a row, left end blocked by white -> the only five-making
        square is the open right end, which the engine must play.
        """
        engine = make_engine(Colors.BLACK, depth=2)
        play(engine.board, [
            (Board.index(7, 3), Colors.BLACK),
            (Board.index(7, 4), Colors.BLACK),
            (Board.index(7, 5), Colors.BLACK),
            (Board.index(7, 6), Colors.BLACK),
            (Board.index(7, 2), Colors.WHITE),   # blocks the left end
        ])

        move = engine.search(move_timestamp=now())
        self.assertEqual(move.index, Board.index(7, 7))

    def test_blocks_opponent_four(self):
        """
        white has a four with the left end already blocked by black -> black must
        block the single open end to avoid losing next ply.
        """
        engine = make_engine(Colors.BLACK, depth=2)
        play(engine.board, [
            (Board.index(7, 3), Colors.WHITE),
            (Board.index(7, 4), Colors.WHITE),
            (Board.index(7, 5), Colors.WHITE),
            (Board.index(7, 6), Colors.WHITE),
            (Board.index(7, 2), Colors.BLACK),   # black already caps the left end
        ])

        move = engine.search(move_timestamp=now())
        self.assertEqual(move.index, Board.index(7, 7))


class TestPerformance(unittest.TestCase):
    def test_search_respects_deadline(self):
        """
        with a deep cap but a short time budget, search must stop near the deadline
        (iterative deepening breaks out via TimeoutError) and still return a move.
        """
        budget = 0.3
        engine = make_engine(Colors.BLACK, depth=12, max_time=budget)
        play(engine.board, random_moves(seed=5, n=10))

        start = perf_counter()
        move = engine.search(move_timestamp=now())
        elapsed = perf_counter() - start

        self.assertIsNotNone(move)
        # generous slack for the in-flight depth iteration + CI jitter
        self.assertLess(elapsed, budget + 2.0)

    def test_incremental_maintenance_is_cheap(self):
        """
        smoke benchmark: repeatedly building a ~40-move position via incremental make() stays fast
        Loose, machine-independent upper bound
        """
        moves = random_moves(seed=9, n=60)

        start = perf_counter()

        n_tests = 50

        for _ in range(n_tests):
            with self.subTest():
                board = tracked_board()

                for idx, color in moves:
                    board.move(Move(index=idx, color=color))

                elapsed = perf_counter() - start

                self.assertLess(elapsed, 10.0)


if __name__ == "__main__":
    unittest.main()
