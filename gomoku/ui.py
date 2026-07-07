"""
Minimalist pygame front-end: a spare menu, a warm wooden board, plain stones
"""

# library imports
from __future__ import annotations

import pygame
import math

# module imports
from gomoku.game import BOARD_SIZE, BLACK, WHITE, EMPTY, coordinates
from arena import MODEL_CATALOG

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
TOGGLE_OFF = (208, 205, 198)        # switch track, off (soft neutral grey)
TOGGLE_ON = (45, 125, 200)          # switch track, on (blue)
KNOB_BODY = (255, 255, 255)         # white knob
KNOB_SHADOW = (28, 24, 18)          # soft drop shadow (drawn with low alpha)
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
        "label": pick(20),
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


# --------------------------------------------------------------------------
# Smooth (anti-aliased) circle rendering.
#
# pygame.gfxdraw.aacircle only draws a 1px outline, so filled discs come out
# with hard edges and "rings" faked by stacking two aacircles look jagged --
# especially once the whole frame is downscaled (SCALE = 0.9).
#
# Instead we render each circle/ring on a buffer _SS times larger with
# pygame.draw.circle (which supports a real width), then smoothscale it down.
# The result is genuinely anti-aliased. Rendered surfaces are cached because
# the same (radius, color, alpha, width) combos recur every frame.
# --------------------------------------------------------------------------

_SS = 4                       # supersampling factor (4 = smooth & cheap)
_circle_cache: dict = {}


def _circle_surface(layers):
    """
    layers: list of (color, alpha, radius, width) drawn outer-to-inner on a
    single supersampled buffer (width=0 means filled). Returns a cached,
    downscaled, anti-aliased RGBA surface.
    """
    key = tuple((tuple(c), int(a), int(r), int(w)) for c, a, r, w in layers)
    surf = _circle_cache.get(key)
    if surf is not None:
        return surf

    outer = max(int(r) for _, _, r, _ in layers)
    pad = 2
    size = (outer + pad) * 2 * _SS

    buf = pygame.Surface((size, size), pygame.SRCALPHA)
    c = size // 2
    for color, alpha, r, w in layers:
        pygame.draw.circle(buf, (*tuple(color), int(alpha)),
                           (c, c), int(r) * _SS, int(w) * _SS)

    surf = pygame.transform.smoothscale(buf, (size // _SS, size // _SS))
    _circle_cache[key] = surf
    return surf


def _blit_centered(surface, surf, center) -> None:
    surface.blit(surf, surf.get_rect(center=(int(center[0]), int(center[1]))))


def _filled_circle(surface, x, y, r, color) -> None:
    _blit_centered(surface, _circle_surface([(color, 255, r, 0)]), (x, y))


def _alpha_circle(surface, center, r, color, alpha, rim=None) -> None:
    """
    anti-aliased filled circle with an alpha, blotted at center
    """
    layers = [(color, alpha, r, 0)]
    if rim is not None:
        layers.append((rim, alpha, r, 2))     # subtle colored edge
    _blit_centered(surface, _circle_surface(layers), center)


def _ring(surface, center, r, color, width=2) -> None:
    """anti-aliased ring; outer edge sits at radius r"""
    _blit_centered(surface, _circle_surface([(color, 255, r, width)]), center)


_rrect_cache: dict = {}


def _round_rect(surface, rect, color, radius) -> None:
    """anti-aliased rounded rectangle (supersampled + cached)"""
    key = (rect.width, rect.height, tuple(color), int(radius))
    surf = _rrect_cache.get(key)
    if surf is None:
        w, h = rect.width * _SS, rect.height * _SS
        buf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(buf, color, (0, 0, w, h), border_radius=int(radius) * _SS)
        surf = pygame.transform.smoothscale(buf, (rect.width, rect.height))
        _rrect_cache[key] = surf
    surface.blit(surf, rect.topleft)


def _lerp(a, b, f):
    return tuple(int(round(a[i] + (b[i] - a[i]) * f)) for i in range(3))


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


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
        surf = _circle_surface([
            (STONE_W, 255, STONE_R, 0),
            (STONE_W_E, 255, STONE_R, 2),      # warm rim
        ])
        _blit_centered(surface, surf, (x, y))


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


def draw_game(surface, fonts, game, status, hover_idx, current_color, thinking=False, hint=None) -> None:
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
        _ring(surface, (x, y), STONE_R + 5, ACCENT, 2)

    _text(surface, fonts["hint"],
          hint or "click : play    ·    R : restart    ·    M : menu    ·    Q : quit",
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
    game menu: pick a color, then choose an opponent (AI or a second human).
    A discreet 'Developer mode' toggle (top-right) reveals an 'AI vs AI' option.
    """
    STONE_R = 24
    _GAP = 46          # horizontal gap between the two color stones
    _BTN_GAP = 34      # horizontal gap between the two mode buttons

    # god-mode switch (top-right corner), iOS-style
    _TG_W = 46          # track width
    _TG_H = 28          # track height
    _TG_MARGIN = 22
    _TG_X = WIDTH - _TG_MARGIN - _TG_W
    _TG_Y = 26
    _TG_PAD = 3         # gap between knob and track edge
    _TG_TRAVEL_MS = 160 # slide duration

    # vertical layout: three blocks evenly spaced around the window's center,
    # so the stones sit dead-center and title / buttons are equidistant
    _CENTER_Y = (HEADER + HEIGHT - FOOTER) // 2
    _STEP = 132
    _TITLE_Y = _CENTER_Y - _STEP
    _STONES_Y = _CENTER_Y
    _BUTTONS_Y = _CENTER_Y + _STEP

    def __init__(self) -> None:
        # default human color (relevant for the vs-AI mode; black always starts)
        self.human_color = BLACK

        # developer / god mode: reveals the AI vs AI option
        self.dev_mode = False

        # switch slide animation state (0 = off, 1 = on)
        self._anim = 0.0
        self._last_ticks = 0

        self._regions: dict[str, pygame.Rect] = {}

    def _compute_regions(self, fonts) -> dict[str, pygame.Rect]:
        cx = WIDTH // 2
        R = self.STONE_R

        # the switch, plus its 'god mode' label to the left — both clickable
        switch = pygame.Rect(self._TG_X, self._TG_Y, self._TG_W, self._TG_H)
        label_w = fonts["small"].size("god mode")[0]
        toggle_hit = pygame.Rect(
            switch.left - label_w - 12, switch.top,
            self._TG_W + label_w + 12, self._TG_H
        )
        regions = {"toggle_dev": toggle_hit}
        self._switch_rect = switch

        if self.dev_mode:
            # colors are irrelevant for AI vs AI: no color picker, single centered option
            regions["play_ava"] = fonts["mode"].render("AI vs AI", True, TEXT) \
                .get_rect(center=(cx, self._STONES_Y))
        else:
            # color stones
            regions["color_black"] = pygame.Rect(cx - self._GAP - R, self._STONES_Y - R, 2 * R, 2 * R)
            regions["color_white"] = pygame.Rect(cx + self._GAP - R, self._STONES_Y - R, 2 * R, 2 * R)

            # two mode buttons, centered as a group
            s_ai = fonts["mode"].render("vs AI", True, TEXT)
            s_pvp = fonts["mode"].render("vs Human", True, TEXT)
            total = s_ai.get_width() + self._BTN_GAP + s_pvp.get_width()
            left = cx - total // 2
            regions["play_hva"] = s_ai.get_rect(midleft=(left, self._BUTTONS_Y))
            regions["play_pvp"] = s_pvp.get_rect(
                midleft=(left + s_ai.get_width() + self._BTN_GAP, self._BUTTONS_Y)
            )

        self._regions = regions

        return regions

    def _stone(self, surface, center, color, selected, hovered) -> None:
        R = self.STONE_R

        alpha = 255 if selected else (165 if hovered else 90)
        body = STONE_B if color == BLACK else STONE_W
        rim = STONE_W_E if color == WHITE else None

        _alpha_circle(surface, center, R, body, alpha, rim=rim)

        if selected:
            _ring(surface, center, R + 8, ACCENT, 2)
        elif hovered:
            _ring(surface, center, R + 7, TEXT_FAINT, 2)

    def _button(self, surface, fonts, rect, label, mouse) -> None:
        hovered = rect.collidepoint(mouse)
        _text(surface, fonts["mode"], label,
              TEXT if hovered else TEXT_SUB, rect.center)
        if hovered:
            y = rect.bottom + 4
            pygame.draw.line(surface, TEXT, (rect.left, y), (rect.right, y), 2)

    def _draw_toggle(self, surface, fonts) -> None:
        rect = self._switch_rect

        # advance the slide animation toward the current state
        now = pygame.time.get_ticks()
        dt = (now - self._last_ticks) if self._last_ticks else 16
        self._last_ticks = now
        target = 1.0 if self.dev_mode else 0.0
        step = dt / self._TG_TRAVEL_MS
        if self._anim < target:
            self._anim = min(target, self._anim + step)
        elif self._anim > target:
            self._anim = max(target, self._anim - step)
        f = _smoothstep(self._anim)

        # label to the left of the switch, vertically centered
        label = fonts["small"].render("god mode", True, TEXT_SUB)
        surface.blit(label, label.get_rect(midright=(rect.left - 12, rect.centery)))

        # flat track, color blended between off/on as it slides
        track = _lerp(TOGGLE_OFF, TOGGLE_ON, f)
        _round_rect(surface, rect, track, rect.height // 2)

        # white knob with a soft drop shadow, sliding left <-> right
        kr = rect.height // 2 - self._TG_PAD
        cy = rect.centery
        left_cx = rect.left + self._TG_PAD + kr
        right_cx = rect.right - self._TG_PAD - kr
        cx = left_cx + (right_cx - left_cx) * f

        _alpha_circle(surface, (cx, cy + 1), kr + 1, KNOB_SHADOW, 40)
        _filled_circle(surface, cx, cy, kr, KNOB_BODY)

    def draw(self, surface, fonts, mouse) -> None:
        surface.fill(MENU_BG)
        cx = WIDTH // 2

        _text(surface, fonts["title"], "Gomoku", TEXT, (cx, self._TITLE_Y))

        r = self._compute_regions(fonts)

        self._draw_toggle(surface, fonts)

        if self.dev_mode:
            self._button(surface, fonts, r["play_ava"], "AI vs AI", mouse)
        else:
            self._stone(
                surface, r["color_black"].center, BLACK,
                self.human_color == BLACK, r["color_black"].collidepoint(mouse)
            )
            self._stone(
                surface, r["color_white"].center, WHITE,
                self.human_color == WHITE, r["color_white"].collidepoint(mouse)
            )
            self._button(surface, fonts, r["play_hva"], "vs AI", mouse)
            self._button(surface, fonts, r["play_pvp"], "vs Human", mouse)

    def hit(self, pos) -> str | None:
        for key, rect in self._regions.items():
            if rect.collidepoint(pos):
                return key
        return None


def draw_menu(surface, fonts, menu, mouse) -> None:
    menu.draw(surface, fonts, mouse)


# ==========================================================================
# AI vs AI : engine-selection screen + live scoreboard
# ==========================================================================

def _pill(surface, fonts, rect, label, active, mouse, font_key="small") -> None:
    """small rounded button; ACCENT fill when active, hover-lit otherwise."""
    hovered = rect.collidepoint(mouse)
    if active:
        _round_rect(surface, rect, ACCENT, rect.height // 2)
        color = MENU_BG
    else:
        _round_rect(surface, rect, (236, 233, 227) if hovered else (244, 242, 237),
                    rect.height // 2)
        color = TEXT if hovered else TEXT_SUB
    _text(surface, fonts[font_key], label, color, rect.center)


class AvaMenu:
    """
    Pick two engine versions (rolling selectors), then type a per-move time
    budget in ms and a number of games.
    """

    _COL_A = 0.30
    _COL_B = 0.70
    _SEL_Y = 190            # selector name baseline
    _ARROW_DX = 78          # arrow offset from a column centre
    _FIELD_W = 150
    _FIELD_H = 40

    def __init__(self) -> None:
        # rolling indices into MODEL_CATALOG (always valid)
        self.a_idx = 0
        self.b_idx = 1 % len(MODEL_CATALOG)

        # free-typed values; time is always in milliseconds
        self.time_text = "100"
        self.games_text = "10"

        self.focus: str | None = None       # None | "time" | "games"
        self._regions: dict[str, pygame.Rect] = {}

    # ---- state helpers ---------------------------------------------------

    @staticmethod
    def _to_int(text: str):
        try:
            return int(text)
        except ValueError:
            return None

    @property
    def ready(self) -> bool:
        t = self._to_int(self.time_text)
        g = self._to_int(self.games_text)
        return t is not None and t >= 1 and g is not None and g >= 1

    def selection(self):
        """(spec_a, spec_b, time_ms, games) or None if the fields are invalid."""
        if not self.ready:
            return None
        return (MODEL_CATALOG[self.a_idx], MODEL_CATALOG[self.b_idx],
                int(self.time_text), int(self.games_text))

    # ---- layout ----------------------------------------------------------

    def _compute_regions(self, fonts) -> None:
        reg: dict[str, pygame.Rect] = {}
        ax = int(WIDTH * self._COL_A)
        bx = int(WIDTH * self._COL_B)

        for side, cx in (("a", ax), ("b", bx)):
            prev = pygame.Rect(0, 0, 34, 34)
            prev.center = (cx - self._ARROW_DX, self._SEL_Y)
            reg[f"{side}_prev"] = prev
            nxt = pygame.Rect(0, 0, 34, 34)
            nxt.center = (cx + self._ARROW_DX, self._SEL_Y)
            reg[f"{side}_next"] = nxt

        tf = pygame.Rect(0, 0, self._FIELD_W, self._FIELD_H)
        tf.center = (WIDTH // 2, 322)
        reg["time_field"] = tf

        gf = pygame.Rect(0, 0, self._FIELD_W, self._FIELD_H)
        gf.center = (WIDTH // 2, 400)
        reg["games_field"] = gf

        start = pygame.Rect(0, 0, 220, 48)
        start.center = (WIDTH // 2, 476)
        reg["start"] = start

        main_menu = pygame.Rect(0, 0, 160, 32)
        main_menu.center = (WIDTH // 2, HEIGHT - 34)
        reg["main_menu"] = main_menu

        self._regions = reg

    # ---- drawing ---------------------------------------------------------

    def draw(self, surface, fonts, mouse) -> None:
        surface.fill(MENU_BG)
        self._compute_regions(fonts)
        cx = WIDTH // 2

        _text(surface, fonts["title"], "AI vs AI", TEXT, (cx, 78))

        self._selector(surface, fonts, "a", self.a_idx, mouse)
        self._selector(surface, fonts, "b", self.b_idx, mouse)

        self._field(surface, fonts, "time_field", self.time_text,
                    self.focus == "time", mouse, "ms / move", suffix="ms")
        self._field(surface, fonts, "games_field", self.games_text,
                    self.focus == "games", mouse, "games")

        # start
        start = self._regions["start"]
        if self.ready:
            _pill(surface, fonts, start, "Start match", False, mouse, "mode")
        else:
            _round_rect(surface, start, (233, 231, 226), start.height // 2)
            _text(surface, fonts["mode"], "Start match", TEXT_FAINT, start.center)

        # main menu link, pinned to the bottom
        mm = self._regions["main_menu"]
        hovered = mm.collidepoint(mouse)
        _text(surface, fonts["small"], "Main menu",
              TEXT if hovered else TEXT_SUB, mm.center)

    def _selector(self, surface, fonts, side, idx, mouse) -> None:
        cx = int(WIDTH * (self._COL_A if side == "a" else self._COL_B))
        spec = MODEL_CATALOG[idx]

        for key, glyph in ((f"{side}_prev", "‹"), (f"{side}_next", "›")):
            rect = self._regions[key]
            hovered = rect.collidepoint(mouse)
            _text(surface, fonts["mode"], glyph, TEXT if hovered else TEXT_SUB,
                  rect.center)

        _text(surface, fonts["mode"], spec.id, TEXT, (cx, self._SEL_Y))
        _text(surface, fonts["hint"], spec.blurb, TEXT_FAINT, (cx, self._SEL_Y + 24))

    def _field(self, surface, fonts, key, text, focused, mouse, label, suffix="") -> None:
        rect = self._regions[key]
        hovered = rect.collidepoint(mouse)

        _text(surface, fonts["small"], label, TEXT_SUB, (rect.centerx, rect.top - 16))

        if focused:
            fill = (236, 233, 227)
        else:
            fill = (238, 236, 231) if hovered else (249, 248, 245)
        _round_rect(surface, rect, fill, 12)

        shown = text if text else ("" if focused else "—")
        if focused and (pygame.time.get_ticks() // 500) % 2 == 0:
            shown = shown + "|"
        color = TEXT if (text or focused) else TEXT_FAINT
        _text(surface, fonts["label"], shown, color, rect.center)

        if suffix:
            _text(surface, fonts["small"], suffix, TEXT_FAINT,
                  (rect.right + 22, rect.centery))

    # ---- input -----------------------------------------------------------

    def handle_click(self, pos) -> str | None:
        """Mutates state; returns 'start' or 'main_menu' when those are hit."""
        n = len(MODEL_CATALOG)
        for key, rect in self._regions.items():
            if not rect.collidepoint(pos):
                continue
            if key == "main_menu":
                return "main_menu"
            if key == "start":
                return "start" if self.ready else None
            if key == "a_prev":
                self.a_idx = (self.a_idx - 1) % n
            elif key == "a_next":
                self.a_idx = (self.a_idx + 1) % n
            elif key == "b_prev":
                self.b_idx = (self.b_idx - 1) % n
            elif key == "b_next":
                self.b_idx = (self.b_idx + 1) % n
            elif key == "time_field":
                self.focus = "time"
            elif key == "games_field":
                self.focus = "games"
            return None

        # clicked empty space -> drop focus
        self.focus = None
        return None

    def handle_key(self, event) -> bool:
        """Text editing for the focused field. Returns True if the key was consumed."""
        if self.focus is None:
            return False

        attr = "time_text" if self.focus == "time" else "games_text"
        text = getattr(self, attr)

        if event.key == pygame.K_BACKSPACE:
            setattr(self, attr, text[:-1])
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.focus = None
        elif event.key == pygame.K_TAB:
            self.focus = "games" if self.focus == "time" else "time"
        elif event.unicode.isdigit() and len(text) < 7:
            setattr(self, attr, text + event.unicode)

        return True


def draw_ava_select(surface, fonts, ava_menu, mouse) -> None:
    ava_menu.draw(surface, fonts, mouse)


def draw_arena_hud(surface, fonts, arena) -> None:
    """Scoreboard banner drawn over the board header during an arena match."""
    panel = pygame.Rect(16, 8, WIDTH - 32, 68)
    _round_rect(surface, panel, (250, 249, 246), 16)

    cx = WIDTH // 2
    a_black = arena.black_is_a

    # engine A (left) and B (right), each tagged with its color this game
    ax, bx = panel.left + 78, panel.right - 78
    _filled_circle(surface, ax - 62, panel.centery,
                   6, STONE_B if a_black else STONE_W)
    _text(surface, fonts["label"], arena.spec_a.id, TEXT, (ax, panel.centery))
    _filled_circle(surface, bx + 62, panel.centery,
                   6, STONE_W if a_black else STONE_B)
    _text(surface, fonts["label"], arena.spec_b.id, TEXT, (bx, panel.centery))

    # score + game counter in the middle
    score = f"{arena.wins_a}  –  {arena.draws}  –  {arena.wins_b}"
    _text(surface, fonts["status"], score, TEXT, (cx, panel.centery - 8))

    if arena.finished:
        sub = f"Done playing · {arena.games_played} games"

    else:
        total = "∞" if arena.total_games == 0 else str(arena.total_games)
        sub = f"game {arena.games_played + 1} / {total}"
    _text(surface, fonts["hint"], sub, TEXT_SUB, (cx, panel.centery + 16))
