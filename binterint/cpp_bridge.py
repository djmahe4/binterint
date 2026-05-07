"""
binterint.cpp_bridge
====================
Thin Python wrapper around the compiled ``_binterint_core`` pybind11 extension.

If the extension is not available (C++ build not compiled or libraries absent)
the module falls back to pure-Python equivalents built on top of *pyte* and
*Pillow* so that the rest of the package works in any environment.

Usage
-----
    from binterint.cpp_bridge import (
        NATIVE_AVAILABLE,
        ScreenBuffer, Cell, Rect,
        TerminalEmulator,
        FontEngine, RenderResult, GlyphMetrics, TextOrientation,
    )
"""
from __future__ import annotations

import logging

logger = logging.getLogger("binterint.cpp_bridge")

# ---------------------------------------------------------------------------
# Try importing the compiled extension
# ---------------------------------------------------------------------------
try:
    from binterint._binterint_core import (  # type: ignore[import]
        Cell,
        Rect,
        ScreenBuffer,
        TerminalEmulator,
        GlyphMetrics,
        RenderResult,
        FontEngine,
        TextOrientation,
    )
    NATIVE_AVAILABLE = True
    logger.debug("_binterint_core loaded — native C++ acceleration active")
except ImportError as _exc:
    NATIVE_AVAILABLE = False
    logger.debug("_binterint_core not available (%s); using pure-Python fallback", _exc)

# ---------------------------------------------------------------------------
# Pure-Python fallback classes (used when NATIVE_AVAILABLE is False)
# ---------------------------------------------------------------------------
if not NATIVE_AVAILABLE:
    from dataclasses import dataclass, field
    from enum import IntEnum
    from typing import List, Tuple

    @dataclass
    class Cell:  # type: ignore[no-redef]
        """Pure-Python terminal cell."""
        char_data: str   = " "
        fg_color:  int   = 0xFFFFFFFF
        bg_color:  int   = 0x000000FF
        bold:      bool  = False
        italic:    bool  = False
        underline: bool  = False
        dirty:     bool  = True

        def __repr__(self) -> str:
            return f"<Cell '{self.char_data}'>"

    @dataclass
    class Rect:  # type: ignore[no-redef]
        x:      int = 0
        y:      int = 0
        width:  int = 0
        height: int = 0

    class ScreenBuffer:  # type: ignore[no-redef]
        """Pure-Python ScreenBuffer — wraps a flat list of Cells."""

        def __init__(self, cols: int, rows: int) -> None:
            self._cols = cols
            self._rows = rows
            self._cells: List[Cell] = [Cell() for _ in range(cols * rows)]
            self._dirty_min_x = 0
            self._dirty_min_y = 0
            self._dirty_max_x = cols
            self._dirty_max_y = rows
            self._has_dirty   = True

        @property
        def columns(self) -> int:
            return self._cols

        @property
        def rows(self) -> int:
            return self._rows

        def write(self, x: int, y: int, cell: Cell) -> None:
            if x < 0 or x >= self._cols or y < 0 or y >= self._rows:
                return
            self._cells[y * self._cols + x] = cell
            self._cells[y * self._cols + x].dirty = True
            self._dirty_min_x = min(self._dirty_min_x, x)
            self._dirty_min_y = min(self._dirty_min_y, y)
            self._dirty_max_x = max(self._dirty_max_x, x + 1)
            self._dirty_max_y = max(self._dirty_max_y, y + 1)
            self._has_dirty = True

        def get_cell(self, x: int, y: int) -> Cell:
            return self._cells[y * self._cols + x]

        def get_dirty_rects(self) -> List[Rect]:
            if not self._has_dirty:
                return []
            return [Rect(
                self._dirty_min_x,
                self._dirty_min_y,
                self._dirty_max_x - self._dirty_min_x,
                self._dirty_max_y - self._dirty_min_y,
            )]

        def clear_dirty(self) -> None:
            for c in self._cells:
                c.dirty = False
            self._dirty_min_x = self._cols
            self._dirty_min_y = self._rows
            self._dirty_max_x = 0
            self._dirty_max_y = 0
            self._has_dirty   = False

        def resize(self, cols: int, rows: int) -> None:
            self._cols  = cols
            self._rows  = rows
            self._cells = [Cell() for _ in range(cols * rows)]
            self._dirty_min_x = 0
            self._dirty_min_y = 0
            self._dirty_max_x = cols
            self._dirty_max_y = rows
            self._has_dirty   = True

    class TerminalEmulator:  # type: ignore[no-redef]
        """Pure-Python TerminalEmulator — uses *pyte* under the hood."""

        def __init__(self, cols: int, rows: int) -> None:
            import pyte  # noqa: PLC0415
            self._screen = pyte.Screen(cols, rows)
            self._stream = pyte.Stream(self._screen)
            self._buffer = ScreenBuffer(cols, rows)

        def feed(self, data: str) -> None:
            self._stream.feed(data)
            self._sync_all()

        def resize(self, cols: int, rows: int) -> None:
            self._screen.resize(rows, cols)
            self._buffer.resize(cols, rows)
            self._sync_all()

        def get_screen(self) -> ScreenBuffer:
            return self._buffer

        def get_text_content(self) -> str:
            return "\n".join(self._screen.display)

        def _sync_all(self) -> None:
            cols = self._screen.columns
            rows = self._screen.lines
            for y in range(rows):
                for x in range(cols):
                    try:
                        pyte_cell = self._screen.buffer[y][x]
                    except (KeyError, IndexError):
                        continue
                    cell = Cell()
                    cell.char_data = pyte_cell.data if pyte_cell.data else " "
                    cell.bold      = pyte_cell.bold
                    cell.italic    = pyte_cell.italics
                    cell.underline = pyte_cell.underscore
                    self._buffer.write(x, y, cell)

    @dataclass
    class GlyphMetrics:  # type: ignore[no-redef]
        width:     int = 0
        height:    int = 0
        bearing_x: int = 0
        bearing_y: int = 0
        advance_x: int = 0
        advance_y: int = 0

    @dataclass
    class RenderResult:  # type: ignore[no-redef]
        pixels: bytes = b""
        width:  int   = 0
        height: int   = 0

    class TextOrientation(IntEnum):  # type: ignore[no-redef]
        HORIZONTAL_LTR = 0
        HORIZONTAL_RTL = 1
        VERTICAL_TTB   = 2
        VERTICAL_BTT   = 3
        DIAGONAL_45    = 4
        DIAGONAL_135   = 5

    class FontEngine:  # type: ignore[no-redef]
        """Pure-Python FontEngine — uses Pillow for rendering."""

        def __init__(self) -> None:
            self._fonts: dict = {}
            self._paths: dict = {}
            self._next   = 0

        def load_font(self, path: str, size_px: int) -> int:
            from PIL import ImageFont  # noqa: PLC0415
            handle = self._next
            self._next += 1
            try:
                self._fonts[handle] = ImageFont.truetype(path, size=size_px)
            except Exception:
                self._fonts[handle] = ImageFont.load_default()
            self._paths[handle] = path
            return handle

        def get_glyph_metrics(self, handle: int, codepoint: int) -> GlyphMetrics:
            font = self._fonts.get(handle)
            if font is None:
                return GlyphMetrics()
            try:
                char = chr(codepoint)
                adv = int(font.getlength(char))
                asc, dsc = font.getmetrics()
                return GlyphMetrics(width=adv, height=asc + dsc, advance_x=adv)
            except Exception:
                return GlyphMetrics()

        def measure_text(self, handle: int, text: str,
                         letter_spacing: float = 0.0) -> Tuple[int, int]:
            font = self._fonts.get(handle)
            if font is None:
                return (0, 0)
            try:
                w = int(font.getlength(text))
                asc, dsc = font.getmetrics()
                return (w, asc + dsc)
            except Exception:
                return (0, 0)

        def render_text(self, handle: int, text: str,
                        orientation: int = 0,
                        letter_spacing: float = 0.0) -> RenderResult:
            from PIL import Image, ImageDraw  # noqa: PLC0415
            font = self._fonts.get(handle)
            if font is None:
                return RenderResult()

            try:
                w, h = self.measure_text(handle, text, letter_spacing)
                if w <= 0 or h <= 0:
                    return RenderResult()
                img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.text((0, 0), text, font=font, fill=(255, 255, 255, 255))

                # Apply orientation transform
                orient = TextOrientation(orientation)
                if orient == TextOrientation.HORIZONTAL_RTL:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                elif orient == TextOrientation.VERTICAL_TTB:
                    img = img.rotate(-90, expand=True)
                elif orient == TextOrientation.VERTICAL_BTT:
                    img = img.rotate(90, expand=True)
                elif orient == TextOrientation.DIAGONAL_45:
                    img = img.rotate(45, expand=True)
                elif orient == TextOrientation.DIAGONAL_135:
                    img = img.rotate(-45, expand=True)

                return RenderResult(
                    pixels=img.tobytes(),
                    width=img.width,
                    height=img.height,
                )
            except Exception as exc:
                logger.warning("FontEngine.render_text fallback failed: %s", exc)
                return RenderResult()

        def list_loaded_fonts(self) -> List[Tuple[int, str]]:
            return list(self._paths.items())


__all__ = [
    "NATIVE_AVAILABLE",
    "Cell",
    "Rect",
    "ScreenBuffer",
    "TerminalEmulator",
    "GlyphMetrics",
    "RenderResult",
    "FontEngine",
    "TextOrientation",
]
