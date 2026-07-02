"""
Minimalist pygame front-end: a spare menu, a warm wooden board, plain stones
"""

# library imports
from __future__ import annotations

import pygame.gfxdraw
import pygame
import math

# module imports
from gomoku.game import BOARD_SIZE, BLACK, WHITE, EMPTY, coordinates

# Layout variables
CELL = 42
MARGIN = 46
HEADER = 88
FOOTER = 56
GRID = CELL * (BOARD_SIZE - 1)
WIDTH = GRID + 2 * MARGIN
ORIGIN_X = MARGIN
ORIGIN_Y = HEADER
HEIGHT = ORIGIN_Y + GRID + FOOTER
STONE_R = 17

# Color palette
MENU_BG = (244, 242, 237)           # warm off-white (menu)
GAME_BG = (224, 190, 143)           # light wood (board)
LINE = (156, 120, 80)               # board grid on wood
STAR = (120, 90, 58)
STONE_B = (38, 38, 41)
STONE_W = (250, 249, 246)
STONE_W_E = (176, 150, 116)         # white-stone rim, warm
GHOST_W = (238, 235, 228)           # white ghost body on wood
ACCENT = (168, 74, 47)              # last-move ring / selection
TEXT = (56, 52, 46)
TEXT_SUB = (150, 144, 134)
TEXT_FAINT = (198, 193, 184)
DOT = (70, 64, 56)                  # thinking animation
GAME_OVERLAY = (224, 190, 143, 208) # wood-tinted veil

STAR_POINTS = ((3, 3), (3, 11), (11, 3), (11, 11), (7, 7))


def load_fonts() -> dict[str, pygame.font.Font]:
    """
    creates font objects
    """
    def pick(size: int) -> pygame.font.Font:
        return pygame.font.SysFont("Helvetica,Arial,DejaVu Sans", size)

    return {
        "title": pick(56),
        "mode": pick(26),
        "status": pick(23),
        "small": pick(16),
        "hint": pick(14),
    }


def _inter_px(row: int, col: int) -> tuple[int, int]:
    return ORIGIN_X + col * CELL, ORIGIN_Y + row * CELL


def board_pos_to_index(pos) -> int | None:
    """
    Nearest intersection to the cursor, or None if too far
    """
    mx, my = pos

    col = round((mx - ORIGIN_X) / CELL)
    row = round((my - ORIGIN_Y) / CELL)

    if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
        px, py = _inter_px(row, col)

        if (px - mx) ** 2 + (py - my) ** 2 <= (CELL * 0.5) ** 2:
            return row * BOARD_SIZE + col

    return None


def _filled_circle(surface, x, y, r, color) -> None:
    pygame.gfxdraw.filled_circle(surface, int(x), int(y), int(r), color)
    pygame.gfxdraw.aacircle(surface, int(x), int(y), int(r), color)


def _alpha_circle(surface, center, r, color, alpha, rim=None) -> None:
    """
    anti-aliased filled circle with an alpha, blotted at center
    """
    c = r + 2

    tmp = pygame.Surface((c * 2, c * 2), pygame.SRCALPHA)

    pygame.gfxdraw.filled_circle(tmp, c, c, r, (*color, alpha))
    pygame.gfxdraw.aacircle(tmp, c, c, r, (*color, alpha))

    if rim is not None:
        pygame.gfxdraw.aacircle(tmp, c, c, r, (*rim, alpha))

    surface.blit(tmp, (center[0] - c, center[1] - c))


def _text(surface, font, text, color, center) -> pygame.Rect:
    surf = font.render(text, True, color)
    rect = surf.get_rect(center=center)
    surface.blit(surf, rect)
    return rect


def _draw_stone(surface, index, color) -> None:
    row, col = coordinates(index)
    x, y = _inter_px(row, col)
    if color == BLACK:
        _filled_circle(surface, x, y, STONE_R, STONE_B)
    else:
        _filled_circle(surface, x, y, STONE_R, STONE_W)
        pygame.gfxdraw.aacircle(surface, int(x), int(y), STONE_R, STONE_W_E)


def _draw_grid(surface) -> None:
    for i in range(BOARD_SIZE):
        pygame.draw.line(surface, LINE, _inter_px(i, 0), _inter_px(i, BOARD_SIZE - 1), 1)
        pygame.draw.line(surface, LINE, _inter_px(0, i), _inter_px(BOARD_SIZE - 1, i), 1)
    for r, c in STAR_POINTS:
        x, y = _inter_px(r, c)
        _filled_circle(surface, x, y, 3, STAR)


def _draw_thinking(surface, center) -> None:
    """Three softly pulsing dots — a discreet 'engine is thinking' cue."""
    t = pygame.time.get_ticks() / 1000.0
    spacing = 16
    r = 4
    cx, cy = center
    for i in range(3):
        wave = (math.sin(t * 3.2 - i * 0.7) + 1) / 2      # 0..1
        alpha = int(55 + wave * 175)
        _alpha_circle(surface, (cx + (i - 1) * spacing, cy), r, DOT, alpha)


def _result(game) -> str:
    """
    computes the result string for the game
    """
    if game.winner == BLACK:
        return "Black wins"

    elif game.winner == WHITE:
        return "White wins"

    else:
        return "Draw"


def draw_game(surface, fonts, game, status, hover_idx, current_color, thinking=False) -> None:
    surface.fill(GAME_BG)

    if thinking and not game.over:
        _draw_thinking(surface, (WIDTH // 2, HEADER // 2))
    else:
        _text(surface, fonts["status"], status, TEXT, (WIDTH // 2, HEADER // 2))

    _draw_grid(surface)

    if hover_idx is not None:
        row, col = coordinates(hover_idx)
        body = STONE_B if current_color == BLACK else GHOST_W
        _alpha_circle(surface, _inter_px(row, col), STONE_R, body, 70)

    for idx, v in enumerate(game.cells):
        if v != EMPTY:
            _draw_stone(surface, idx, v)

    if game.last_move is not None:
        row, col = coordinates(game.last_move)
        x, y = _inter_px(row, col)

        pygame.gfxdraw.aacircle(surface, int(x), int(y), STONE_R + 4, ACCENT)
        pygame.gfxdraw.aacircle(surface, int(x), int(y), STONE_R + 5, ACCENT)

    _text(surface, fonts["hint"],
          "click : play    ·    R : restart    ·    M : menu    ·    Q : quit",
          TEXT, (WIDTH // 2, HEIGHT - FOOTER // 2))

    if game.over:
        veil = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        veil.fill(GAME_OVERLAY)
        surface.blit(veil, (0, 0))
        _text(surface, fonts["title"], _result(game), TEXT, (WIDTH // 2, HEIGHT // 2 - 18))
        _text(surface, fonts["small"], "R to play again   ·   M for menu",
              TEXT_SUB, (WIDTH // 2, HEIGHT // 2 + 34))


class Menu:
    """
    game menu to choosing the mode and colors
    """
    STONE_R = 24
    _GAP = 46

    def __init__(self) -> None:
        # default human player
        self.human_color = BLACK

        self._regions: dict[str, pygame.Rect] = {}

    def _compute_regions(self, fonts) -> dict[str, pygame.Rect]:
        cx = WIDTH // 2
        R = self.STONE_R

        regions = {
            "color_black": pygame.Rect(cx - self._GAP - R, 320 - R, 2 * R, 2 * R),
            "color_white": pygame.Rect(cx + self._GAP - R, 320 - R, 2 * R, 2 * R),
            "play_hva": fonts["mode"].render("Human vs AI", True, TEXT)
                        .get_rect(center=(cx, 452)),
            "mode_ai": fonts["mode"].render("AI vs AI", True, TEXT_FAINT)
                       .get_rect(center=(cx, 504)),
        }

        self._regions = regions

        return regions

    def _stone(self, surface, center, color, selected, hovered) -> None:
        R = self.STONE_R

        alpha = 255 if selected else (165 if hovered else 90)
        body = STONE_B if color == BLACK else STONE_W
        rim = STONE_W_E if color == WHITE else None

        _alpha_circle(surface, center, R, body, alpha, rim=rim)

        if selected:
            pygame.gfxdraw.aacircle(surface, center[0], center[1], R + 7, ACCENT)
            pygame.gfxdraw.aacircle(surface, center[0], center[1], R + 8, ACCENT)

        elif hovered:
            pygame.gfxdraw.aacircle(surface, center[0], center[1], R + 7, TEXT_FAINT)

    def draw(self, surface, fonts, mouse) -> None:
        surface.fill(MENU_BG)
        cx = WIDTH // 2

        _text(surface, fonts["title"], "Gomoku", TEXT, (cx, 168))

        r = self._compute_regions(fonts)

        _text(surface, fonts["hint"], "you play", TEXT_SUB, (cx, 268))

        self._stone(
            surface,
            r["color_black"].center,
            BLACK,
            self.human_color == BLACK,
            r["color_black"].collidepoint(mouse)
        )

        self._stone(
            surface,
            r["color_white"].center,
            WHITE,
            self.human_color == WHITE,
            r["color_white"].collidepoint(mouse)
        )

        hovered = r["play_hva"].collidepoint(mouse)

        _text(
            surface,
            fonts["mode"],
            "Human vs AI",
            TEXT if hovered else TEXT_SUB,
            r["play_hva"].center
        )

        if hovered:
            y = r["play_hva"].bottom + 4
            pygame.draw.line(surface, TEXT, (r["play_hva"].left, y), (r["play_hva"].right, y), 2)

        _text(
            surface,
            fonts["mode"],
            "AI vs AI",
            TEXT_FAINT,
            r["mode_ai"].center
        )

        _text(
            surface,
            fonts["hint"],
            "soon",
            TEXT_FAINT,
            (r["mode_ai"].centerx, r["mode_ai"].bottom + 13)
        )

    def hit(self, pos) -> str | None:
        for key, rect in self._regions.items():
            if rect.collidepoint(pos):
                return key
        return None


def draw_menu(surface, fonts, menu, mouse) -> None:
    menu.draw(surface, fonts, mouse)
