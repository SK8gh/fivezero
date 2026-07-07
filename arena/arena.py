"""
    AI-vs-AI arena: a small benchmark harness that pits two engine versions
    against each other over a series of games, so you can see which one is
    stronger before shipping it.

    Design notes
    ------------
    * Pondering is OFF (see build_engine): each engine only searches on its own
      move. That keeps the comparison fair AND means only one engine thinks at a
      time -- which is what lets us safely reuse the singleton EngineConfig,
      re-pointing max_depth / max_time at the side-to-move right before its search.
    * The engine's internal Board is kept in sync incrementally with fork_move()
      in notify_move(), so we never rebuild it from scratch.

    What you customise
    ------------------
    * MODEL_CATALOG  -> the engine versions offered in the selection screen. Here
                        they differ by search-depth cap; encode your real
                        differences in `params` (or subclass FiveZeroEngine and
                        branch in build_engine).
    * build_engine() -> how a version is instantiated and configured.
"""

# library imports
from __future__ import annotations

from gomoku.game import GomokuGame, BLACK, WHITE
from engine import FiveZeroEngine, EngineSpec
from datetime import datetime, timezone
from math import comb, erf, sqrt

# module imports
from utils import Move

from configuration import (
    FIRST_BLACK_MOVE_INDEX_ENGINE
)


class _EnginePlayer:
    """
    wraps a FiveZeroEngine so it satisfies the interface main.py relies on:
        is_human, compute_move(game), notify_move(index, color), close()

    Heavy engine imports are done lazily so that importing this module (e.g.
    from ui.py, just to list the catalog) doesn't drag in numba / numpy.
    """
    is_human = False

    def __init__(
            self, spec: EngineSpec,
            color: int,
            time_ms: int,
            name: str
    ) -> None:
        self.spec = spec
        self.name = name
        self.color = color
        self.time_ms = time_ms
        self.max_depth = spec.params.get("max_depth")
        self._center = FIRST_BLACK_MOVE_INDEX_ENGINE

        # constructing the engine also JIT-warms the evaluator (can be slow once)
        self.engine = FiveZeroEngine(
            engine_color=color,
            spec=spec
        )

    def compute_move(self, game: GomokuGame) -> "int | None":
        # opening move: an empty board has no candidate neighbours to search
        move = self.engine.search(datetime.now(timezone.utc))

        if move is None:
            raise RuntimeError(f"Search timed-out without finding a move to play")

        return move.index

    def notify_move(self, index: int, color: int) -> None:
        """
        updating board and returning
        """
        self.engine.board = self.engine.board.fork_move(Move(index=index, color=color))

    def close(self) -> None:
        pass


def build_engine(spec: EngineSpec, color: int, time_ms: int):
    """
    builds a playable engine for `spec`, playing `color`, allotted `time_ms`
    per move. `ponder=False` means it must not think on the opponent's time --
    essential for a fair A/B comparison.
    """
    return _EnginePlayer(
        spec=spec,
        color=color,
        time_ms=time_ms,
        name=spec.id
    )


class Arena:
    """
    Tracks a series between two engine versions. Colors are swapped every
    game so neither side keeps the first-move advantage.
    """

    def __init__(
            self,
            spec_a: EngineSpec,
            spec_b: EngineSpec,
            time_ms: int,
            total_games: int
    ) -> None:
        self.spec_a = spec_a
        self.spec_b = spec_b
        self.time_ms = time_ms
        self.total_games = total_games

        self.games_played = 0
        self.wins_a = 0
        self.wins_b = 0
        self.draws = 0

        self.black_is_a = True

        # two-sided binomial p-value, computed once when the series ends
        self.p: float | None = None

    @property
    def finished(self) -> bool:
        return self.total_games != 0 and self.games_played >= self.total_games

    def pairing(self) -> "tuple[EngineSpec, EngineSpec]":
        """(black_spec, white_spec) for the current game."""
        if self.black_is_a:
            return self.spec_a, self.spec_b
        return self.spec_b, self.spec_a

    def color_of(self, which: str) -> int:
        """Color ('a' or 'b') is playing this game -> BLACK / WHITE."""
        if which == "a":
            return BLACK if self.black_is_a else WHITE
        return WHITE if self.black_is_a else BLACK

    def record(self, winner_color: "int | None") -> None:
        """Log one finished game. winner_color is BLACK, WHITE, or None (draw)."""
        self.games_played += 1

        if winner_color is None:
            self.draws += 1
        else:
            winner_is_a = (winner_color == BLACK) == self.black_is_a
            if winner_is_a:
                self.wins_a += 1
            else:
                self.wins_b += 1

        self.black_is_a = not self.black_is_a   # swap sides for next game

        if self.finished:
            self.p = self._compute_p_value()

    def _compute_p_value(self) -> float:
        """
        Two-sided binomial p-value under H0 'the two engines are equally strong'
        (each decisive game is a fair coin flip, p=0.5). Draws are excluded.
        Exact below 1000 decisive games, normal approximation above (fast + precise
        at that scale).
        """
        n = self.wins_a + self.wins_b  # decisive games only

        if n == 0:
            return 1.0

        k = max(self.wins_a, self.wins_b)

        if n <= 1000:
            p_ge = sum(comb(n, i) for i in range(k, n + 1)) / (2 ** n)
        else:
            z = (k - 0.5 - n / 2) / sqrt(n / 4)  # continuity-corrected
            p_ge = 0.5 * (1 - erf(z / sqrt(2)))

        return min(1.0, 2 * p_ge)
