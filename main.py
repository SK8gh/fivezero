"""
    Gomoku application main loop, handling events and rendering the game state
"""

from __future__ import annotations

import threading
import logging
import pygame

from gomoku.players import Player, HumanPlayer, make_ai_player
from gomoku.game import GomokuGame, BLACK, WHITE, opponent
from utils import parse_arguments
import gomoku.ui as ui


class App:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Gomoku · FiveZero")
        self.screen = pygame.display.set_mode((ui.WIDTH, ui.HEIGHT))
        self.clock = pygame.time.Clock()
        self.fonts = ui.load_fonts()

        self.running = False
        self.state = "menu"
        self.menu = ui.Menu()

        self.game: GomokuGame | None = None
        self.players: dict[int, Player] = {}
        self.mode_label = ""

        # AI search launched in a different thread to avoid blocking the main loop
        self._ai_thread: threading.Thread | None = None
        self._ai_pending = False
        self._ai_result: int | None = None
        self._ai_error: Exception | None = None

    def start_human_vs_ai(self, human_color: int) -> None:
        self._close_players()

        ai_color = opponent(human_color)
        self.game = GomokuGame()

        # initializing player objects, AI & human
        self.players = {
            human_color: HumanPlayer(human_color),
            ai_color: make_ai_player(ai_color),
        }

        self.mode_label = "Human vs AI"
        self._reset_ai()
        self.state = "game"

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
            except Exception as exc:  # noqa: BLE001
                self._ai_error = exc
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

    def _handle_menu_click(self, pos) -> None:
        """
        handles clicking event ingame
        """
        action = self.menu.hit(pos)

        if action == "play_hva":
            self.start_human_vs_ai(self.menu.human_color)

        elif action == "color_black":
            self.menu.human_color = BLACK

        elif action == "color_white":
            self.menu.human_color = WHITE

    def _handle_game_click(self, pos) -> None:
        if self.game.over or not self._current_player().is_human:
            return

        idx = ui.board_pos_to_index(pos)

        if idx is not None and self.game.is_empty_cell(idx):
            self._commit_move(idx)

    def _handle_keydown(self, key) -> None:
        if key == pygame.K_q:
            self.running = False
            return

        if self.state != "game":
            return

        if key in (pygame.K_ESCAPE, pygame.K_m):
            self._close_players()
            self.state = "menu"
            self._reset_ai()

        elif key == pygame.K_r:
            human_color = next(c for c, p in self.players.items() if p.is_human)
            self.start_human_vs_ai(human_color)

    def run(self) -> None:
        # running the game
        self.running = True

        while self.running:
            mouse = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.KEYDOWN:
                    self._handle_keydown(event.key)

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.state == "menu":
                        self._handle_menu_click(event.pos)
                    else:
                        self._handle_game_click(event.pos)

            if self.state == "game":
                self._collect_ai()
                self._maybe_run_ai()
                self._draw_game(mouse)
            else:
                ui.draw_menu(self.screen, self.fonts, self.menu, mouse)

            pygame.display.flip()
            self.clock.tick(60)

        self._close_players()
        pygame.quit()

    def _draw_game(self, mouse) -> None:
        hover = None

        if not self.game.over and self._current_player().is_human:
            hover = ui.board_pos_to_index(mouse)

            if hover is not None and not self.game.is_empty_cell(hover):
                hover = None

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
