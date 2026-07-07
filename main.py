"""
    Gomoku application main loop, handling events and rendering the game state
"""

# library imports
from __future__ import annotations

import threading
import logging
import pygame
import sys
import os

# module imports
from gomoku.players import Player, build_players
from gomoku.game import GomokuGame, BLACK, WHITE
from arena.arena import Arena, build_engine
from utils import parse_arguments
import gomoku.ui as ui


def _resource_path(rel: str) -> str:
    """
    resolves a bundled asset path in dev and inside PyInstaller freezes."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class App:
    # application scaling factor (0.9 = 90% of the original window size)
    SCALE = 0.9

    # pause between two games (ms)
    PAUSE = 10

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Gomoku \u00b7 FiveZero")

        # loading the application icon as the pygame icon to avoid weird change
        try:
            icon_path = _resource_path("distribution/app.png")
            logging.info(f"Loading icon from: {icon_path}")
            logging.info(f"Exists: {os.path.exists(icon_path)}")
            icon = pygame.image.load(icon_path)
            pygame.display.set_icon(icon)
            logging.info("Icon set successfully")
        except Exception as e:
            logging.warning("Could not load window icon: %s", e)

        # the real, high-resolution window
        self.window = pygame.display.set_mode(
            (ui.WIDTH * self.SCALE, ui.HEIGHT * self.SCALE)
        )

        # everything is drawn here at logical size, then upscaled to the window;
        # ui.py keeps working in normal (1x) coordinates and needs no changes
        self.screen = pygame.Surface((ui.WIDTH, ui.HEIGHT))

        self.clock = pygame.time.Clock()
        self.fonts = ui.load_fonts()

        self.running = False
        self.state = "menu"
        self.menu = ui.Menu()
        self.ava_menu = ui.AvaMenu()

        self.game: GomokuGame | None = None
        self.players: dict[int, Player] = {}

        # remembering the current game setup so R (restart) can replay it
        self.mode: str = "pvai"
        self.human_color: int = BLACK

        # AI vs AI series state (None outside arena mode)
        self.arena: Arena | None = None
        self._arena_next_at: int | None = None

        # AI search launched in a different thread to avoid blocking the main loop
        self._ai_thread: threading.Thread | None = None
        self._ai_pending = False
        self._ai_result: int | None = None
        self._ai_error: Exception | None = None

    def _to_logical(self, pos) -> tuple[int, int]:
        """
        converts a window (high-res) position into logical (1x) coordinates used by the UI and game logic
        """
        return pos[0] // self.SCALE, pos[1] // self.SCALE

    def start_game(self, mode: str, human_color: int) -> None:
        """
        starts a new game. mode is "pvai" (human vs engine) or "pvp" (human vs human)
        """
        self._close_players()

        self.mode = mode
        self.human_color = human_color
        self.arena = None

        self.game = GomokuGame()
        self.players = build_players(mode, human_color)

        self._reset_ai()
        self.state = "game"

    def start_arena(self, spec_a, spec_b, time_ms: int, games: int) -> None:
        """
        starts an AI vs AI series between two engine versions
        """
        self._close_players()

        self.mode = "ava"
        self.arena = Arena(spec_a, spec_b, time_ms, games)

        self._start_arena_game()
        self.state = "game"

    def _start_arena_game(self) -> None:
        """
        spins up one game of the current arena pairing (colors alternate)
        """
        self._close_players()

        self.game = GomokuGame()
        black_spec, white_spec = self.arena.pairing()

        # pondering off: each engine only computes on its own move, so the time
        # budget alone decides the match (fair A/B comparison)
        self.players = {
            BLACK: build_engine(
                spec=black_spec,
                color=BLACK,
                time_ms=self.arena.time_ms
            ),

            WHITE: build_engine(
                spec=white_spec,
                color=WHITE,
                time_ms=self.arena.time_ms
            ),
        }

        self._reset_ai()
        self._arena_next_at = None

    def _reset_ai(self) -> None:
        """
        re-assigns to default values all the attributes to launch & manager the AI search thread
        """
        self._ai_thread = None
        self._ai_pending = False
        self._ai_result = None
        self._ai_error = None

    def _close_players(self) -> None:
        for player in self.players.values():
            player.close()

    def _commit_move(self, index: int) -> bool:
        color = self.game.current

        if not self.game.play(index):
            return False

        for player in self.players.values():
            player.notify_move(index, color)

        return True

    def _current_player(self):
        """
        returns the current player having the trait
        """
        return self.players[self.game.current]

    def _maybe_run_ai(self) -> None:
        if self.game.over:
            return

        player = self._current_player()

        if player.is_human or self._ai_pending:
            return

        def worker(p, g):
            try:
                self._ai_result = p.compute_move(g)
            except (Exception, ) as e:
                self._ai_error = e
                raise e
            finally:
                self._ai_pending = False

        self._ai_thread = threading.Thread(
            target=worker,
            args=(player, self.game),
            daemon=True
        )

        self._ai_pending = True
        self._ai_result = None
        self._ai_error = None
        self._ai_thread.start()

    def _collect_ai(self) -> None:
        if self._ai_thread is None or self._ai_pending:
            return
        self._ai_thread = None
        if self._ai_error is not None:
            logging.error("Engine error: %s", self._ai_error)
            return
        if self._ai_result is not None:
            self._commit_move(self._ai_result)

    def _advance_arena(self) -> None:
        """
        drives the series: once a game ends, pause so the final board is
        visible, tally the result, then auto-start the next game (or stop)
        """
        if self.arena.finished:
            return

        if not self.game.over:
            self._arena_next_at = None
            return

        now = pygame.time.get_ticks()
        if self._arena_next_at is None:
            self._arena_next_at = now + self.PAUSE
            return

        if now < self._arena_next_at:
            return

        winner = self.game.winner if self.game.winner in (BLACK, WHITE) else None
        self.arena.record(winner)

        if self.arena.finished:
            self._arena_next_at = None
        else:
            self._start_arena_game()

    def _handle_menu_click(self, pos) -> None:
        """
        handles clicking event in the menu
        """
        action = self.menu.hit(pos)

        if action == "toggle_dev":
            self.menu.dev_mode = not self.menu.dev_mode

        elif action == "play_hva":
            self.start_game("pvai", self.menu.human_color)

        elif action == "play_pvp":
            self.start_game("pvp", self.menu.human_color)

        elif action == "play_ava":
            self.state = "ava_select"

        elif action == "color_black":
            self.menu.human_color = BLACK

        elif action == "color_white":
            self.menu.human_color = WHITE

    def _handle_ava_select_click(self, pos) -> None:
        """
        handles clicking in the AI vs AI engine-selection screen
        """
        action = self.ava_menu.handle_click(pos)

        if action == "main_menu":
            self.state = "menu"

        elif action == "start":
            selection = self.ava_menu.selection()
            if selection is not None:
                spec_a, spec_b, time_ms, games = selection
                self.start_arena(spec_a, spec_b, time_ms, games)

    def _handle_game_click(self, pos) -> None:
        if self.game.over or not self._current_player().is_human:
            return

        idx = ui.board_pos_to_index(pos)

        if idx is not None and self.game.is_empty_cell(idx):
            self._commit_move(idx)

    def _handle_keydown(self, event) -> None:
        key = event.key

        if self.state == "ava_select":
            # let a focused text field consume digits / backspace first
            if self.ava_menu.handle_key(event):
                return
            if key == pygame.K_q:
                self.running = False
            elif key in (pygame.K_ESCAPE, pygame.K_m):
                self.state = "menu"
            return

        if key == pygame.K_q:
            self.running = False
            return

        if self.state != "game":
            return

        if key in (pygame.K_ESCAPE, pygame.K_m):
            self._close_players()
            self.arena = None
            self.state = "menu"
            self._reset_ai()

        elif key == pygame.K_r:
            if self.arena is not None:
                # restart the whole series with the same settings
                a = self.arena
                self.start_arena(a.spec_a, a.spec_b, a.time_ms, a.total_games)
            else:
                # restart the same matchup
                self.start_game(self.mode, self.human_color)

    def run(self) -> None:
        # running the game
        self.running = True

        while self.running:
            mouse = self._to_logical(pygame.mouse.get_pos())

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event)

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = self._to_logical(event.pos)
                    if self.state == "menu":
                        self._handle_menu_click(pos)
                    elif self.state == "ava_select":
                        self._handle_ava_select_click(pos)
                    else:
                        self._handle_game_click(pos)

            if self.state == "game":
                self._collect_ai()
                self._maybe_run_ai()
                if self.arena is not None:
                    self._advance_arena()
                self._draw_game(mouse)
            elif self.state == "ava_select":
                ui.draw_ava_select(self.screen, self.fonts, self.ava_menu, mouse)
            else:
                ui.draw_menu(self.screen, self.fonts, self.menu, mouse)

            self._present()
            self.clock.tick(60)

        self._close_players()
        pygame.quit()

    def _present(self) -> None:
        """
        upscales the logical frame to the high-resolution window with smoothing
        """
        pygame.transform.smoothscale(
            self.screen,
            (ui.WIDTH * self.SCALE, ui.HEIGHT * self.SCALE),
            self.window
        )
        pygame.display.flip()

    def _draw_game(self, mouse) -> None:
        hover = None

        # no hover cursor during an arena match (no human is playing)
        if (self.arena is None and not self.game.over
                and self._current_player().is_human):
            hover = ui.board_pos_to_index(mouse)

            if hover is not None and not self.game.is_empty_cell(hover):
                hover = None

        if self.arena is not None:
            # the scoreboard HUD owns the header, so keep the status line clear
            ui.draw_game(
                self.screen,
                self.fonts,
                self.game,
                "",
                hover,
                self.game.current,
                thinking=False,
                hint="M : menu    \u00b7    R : restart series    \u00b7    Q : quit",
            )
            ui.draw_arena_hud(self.screen, self.fonts, self.arena)
        else:
            ui.draw_game(
                self.screen,
                self.fonts,
                self.game,
                self._status_text(),
                hover,
                self.game.current,
                thinking=self._ai_pending
            )

    def _status_text(self) -> str:
        g = self.game

        if g.winner:
            return "Black wins" if g.winner == BLACK else "White wins"

        if g.is_full():
            return "Draw"

        return "Black to move" if g.current == BLACK else "White to move"


if __name__ == "__main__":
    arguments = parse_arguments()

    logging.basicConfig(
        level=arguments.log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    logging.info(f"Starting Gomoku application")

    App().run()
