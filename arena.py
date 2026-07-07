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

from engine import FiveZeroEngine, EngineSpec
from gomoku.game import EMPTY, BLACK, WHITE
from dataclasses import dataclass, field
from datetime import datetime, timezone

# module imports
from configuration import (
    FIRST_BLACK_MOVE_INDEX_ENGINE,
    EngineConfig
)


@dataclass
class ModelSpec:
    """One selectable engine version."""
    id: str
    blurb: str
    params: dict = field(default_factory=dict)   # forwarded to build_engine


# The stock engine (configuration.ENGINE_DEPTH) caps depth at 4. These entries
# compare different depth caps under the SAME per-move time budget picked in the
# UI. Swap `params` for whatever actually distinguishes your versions.
MODEL_CATALOG: list[ModelSpec] = [
    # main production version: depth and all parameters as configured
    ModelSpec(
        id="1.0",
        blurb="PROD"
    ),

    # model implementing the centrality evaluation term
    ModelSpec(
        id="1.0.1",
        blurb="+c",
        params={
            "central_term": True
        }
    )
]


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
            time_ms: int
    ) -> None:
        self.spec = spec
        self.color = color
        self.time_ms = time_ms
        self.max_depth = spec.params.get("max_depth")   # None -> engine default
        self._center = FIRST_BLACK_MOVE_INDEX_ENGINE

        # constructing the engine also JIT-warms the evaluator (can be slow once)
        self.engine = FiveZeroEngine(
            engine_color=color,
            spec=spec
        )

    def compute_move(self, game) -> "int | None":
        # opening move: an empty board has no candidate neighbours to search
        if all(v == EMPTY for v in game.cells):
            return self._center

        cfg = EngineConfig()
        cfg.max_time = self.time_ms / 1000.0
        if self.max_depth is not None:
            cfg.max_depth = self.max_depth

        move = self.engine.search(datetime.now(timezone.utc))

        if move is None or move.index is None:
            # time budget too tight to complete even depth 1 -> safe fallback
            return self._fallback(game)
        return move.index

    def notify_move(self, index: int, color: int) -> None:
        # keep the engine's internal board in sync with every move played.
        #
        # Pondering hook: with ponder=True a real engine could kick off a
        # background search here (interruptible via the minimax stop_event).
        # With ponder=False (the arena default) it must NOT -- so we only
        # update the board and return.
        from utils import Move
        self.engine.board = self.engine.board.fork_move(Move(index=index, color=color))

    def _fallback(self, game) -> "int | None":
        empties = [i for i, v in enumerate(game.cells) if v == EMPTY]
        return empties[0] if empties else None

    def close(self) -> None:
        pass


def build_engine(spec: ModelSpec, color: int, time_ms: int):
    """
    builds a playable engine for `spec`, playing `color`, allotted `time_ms`
    per move. `ponder=False` means it must not think on the opponent's time --
    essential for a fair A/B comparison.
    """
    return _EnginePlayer(spec, color, time_ms)


class Arena:
    """
    Tracks a series between two engine versions. Colors are swapped every
    game so neither side keeps the first-move advantage.
    """

    def __init__(
            self,
            spec_a: ModelSpec,
            spec_b: ModelSpec,
            time_ms: int,
            total_games: int
    ) -> None:
        self.spec_a = spec_a
        self.spec_b = spec_b
        self.time_ms = time_ms
        self.total_games = total_games      # 0 == endless

        self.games_played = 0
        self.wins_a = 0
        self.wins_b = 0
        self.draws = 0

        self.black_is_a = True              # who plays black this game

    @property
    def finished(self) -> bool:
        return self.total_games != 0 and self.games_played >= self.total_games

    def pairing(self) -> "tuple[ModelSpec, ModelSpec]":
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
