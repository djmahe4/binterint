"""
Tests for binterint.cpp_bridge — covers both native C++ and pure-Python fallback paths.
"""
import sys
import pytest

from binterint.cpp_bridge import (
    NATIVE_AVAILABLE,
    Cell,
    Rect,
    ScreenBuffer,
    TerminalEmulator,
    FontEngine,
    RenderResult,
    GlyphMetrics,
    TextOrientation,
)


# ---------------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------------

class TestCell:
    def test_defaults(self):
        c = Cell()
        assert c.char_data == " "
        assert c.bold      is False
        assert c.italic    is False
        assert c.underline is False
        assert c.dirty     is True

    def test_set_fields(self):
        c = Cell()
        c.char_data = "X"
        c.bold      = True
        c.fg_color  = 0xFF0000FF
        assert c.char_data == "X"
        assert c.bold      is True
        assert c.fg_color  == 0xFF0000FF


# ---------------------------------------------------------------------------
# ScreenBuffer
# ---------------------------------------------------------------------------

class TestScreenBuffer:
    def test_dimensions(self):
        buf = ScreenBuffer(80, 24)
        assert buf.columns == 80
        assert buf.rows    == 24

    def test_initial_dirty(self):
        buf = ScreenBuffer(10, 5)
        rects = buf.get_dirty_rects()
        assert len(rects) == 1, "All cells should be dirty after construction"

    def test_write_and_get(self):
        buf = ScreenBuffer(10, 5)
        buf.clear_dirty()
        c = Cell()
        c.char_data = "Z"
        c.bold      = True
        buf.write(3, 2, c)
        got = buf.get_cell(3, 2)
        assert got.char_data == "Z"
        assert got.bold      is True

    def test_dirty_rect_tracking(self):
        buf = ScreenBuffer(20, 10)
        buf.clear_dirty()
        assert buf.get_dirty_rects() == [] or len(buf.get_dirty_rects()) == 0

        c = Cell(); c.char_data = "A"
        buf.write(2, 1, c)
        buf.write(5, 3, c)

        rects = buf.get_dirty_rects()
        assert len(rects) == 1
        r = rects[0]
        assert r.x      == 2
        assert r.y      == 1
        assert r.width  == 4   # columns 2–5
        assert r.height == 3   # rows 1–3

    def test_clear_dirty(self):
        buf = ScreenBuffer(10, 5)
        buf.clear_dirty()
        assert len(buf.get_dirty_rects()) == 0

    def test_resize(self):
        buf = ScreenBuffer(10, 5)
        buf.resize(20, 10)
        assert buf.columns == 20
        assert buf.rows    == 10
        assert len(buf.get_dirty_rects()) > 0  # all dirty after resize

    def test_write_out_of_bounds_ignored(self):
        buf = ScreenBuffer(5, 5)
        buf.clear_dirty()
        c = Cell(); c.char_data = "Q"
        buf.write(-1, 0, c)   # should silently ignore
        buf.write(5,  0, c)   # should silently ignore
        buf.write(0, -1, c)
        buf.write(0,  5, c)
        assert len(buf.get_dirty_rects()) == 0


# ---------------------------------------------------------------------------
# TerminalEmulator
# ---------------------------------------------------------------------------

class TestTerminalEmulator:
    def test_creation(self):
        emu = TerminalEmulator(80, 24)
        assert emu.get_screen().columns == 80
        assert emu.get_screen().rows    == 24

    def test_feed_plain_text(self):
        emu = TerminalEmulator(40, 10)
        emu.feed("Hello")
        text = emu.get_text_content()
        assert "Hello" in text

    def test_feed_ansi_colors(self):
        emu = TerminalEmulator(40, 10)
        emu.feed("\x1b[1;32mGreen Bold\x1b[0m")
        text = emu.get_text_content()
        assert "Green Bold" in text

    def test_resize(self):
        emu = TerminalEmulator(40, 10)
        emu.resize(80, 24)
        assert emu.get_screen().columns == 80
        assert emu.get_screen().rows    == 24

    def test_screen_dirty_after_feed(self):
        emu = TerminalEmulator(40, 10)
        emu.get_screen().clear_dirty()
        emu.feed("X")
        rects = emu.get_screen().get_dirty_rects()
        assert len(rects) > 0


# ---------------------------------------------------------------------------
# FontEngine
# ---------------------------------------------------------------------------

class TestFontEngine:
    @pytest.fixture
    def font_path(self):
        import os
        p = os.path.join(os.path.dirname(__file__), "..",
                         "binterint", "fonts", "RobotoMono-Regular.ttf")
        if not os.path.exists(p):
            pytest.skip("RobotoMono-Regular.ttf not present")
        return os.path.abspath(p)

    def test_load_font(self, font_path):
        fe = FontEngine()
        handle = fe.load_font(font_path, 18)
        assert isinstance(handle, int)
        assert handle >= 0

    def test_measure_text(self, font_path):
        fe = FontEngine()
        handle = fe.load_font(font_path, 18)
        w, h = fe.measure_text(handle, "Hello")
        assert w > 0
        assert h > 0

    def test_render_text_ltr(self, font_path):
        fe = FontEngine()
        handle = fe.load_font(font_path, 18)
        result = fe.render_text(handle, "Hello", 0, 0.0)
        assert result.width  > 0
        assert result.height > 0
        assert len(result.pixels) == result.width * result.height * 4

    def test_render_text_vertical_ttb(self, font_path):
        fe = FontEngine()
        handle = fe.load_font(font_path, 18)
        ltr = fe.render_text(handle, "Hi", int(TextOrientation.HORIZONTAL_LTR), 0.0)
        vtb = fe.render_text(handle, "Hi", int(TextOrientation.VERTICAL_TTB), 0.0)
        # Vertical rendering should transpose width ↔ height of the LTR render.
        assert vtb.width  == ltr.height
        assert vtb.height == ltr.width

    def test_render_text_vertical_btt(self, font_path):
        fe = FontEngine()
        handle = fe.load_font(font_path, 18)
        ltr = fe.render_text(handle, "Hi", int(TextOrientation.HORIZONTAL_LTR), 0.0)
        btt = fe.render_text(handle, "Hi", int(TextOrientation.VERTICAL_BTT), 0.0)
        assert btt.width  == ltr.height
        assert btt.height == ltr.width

    def test_render_text_diagonal(self, font_path):
        fe = FontEngine()
        handle = fe.load_font(font_path, 18)
        d45 = fe.render_text(handle, "Hi", int(TextOrientation.DIAGONAL_45), 0.0)
        assert d45.width  > 0
        assert d45.height > 0

    def test_get_glyph_metrics(self, font_path):
        fe = FontEngine()
        handle = fe.load_font(font_path, 18)
        m = fe.get_glyph_metrics(handle, ord("A"))
        assert m.width    > 0
        assert m.height   > 0
        assert m.advance_x > 0

    def test_list_loaded_fonts(self, font_path):
        fe = FontEngine()
        handle = fe.load_font(font_path, 18)
        fonts = fe.list_loaded_fonts()
        assert any(h == handle for h, _ in fonts)

    def test_empty_text(self, font_path):
        fe = FontEngine()
        handle = fe.load_font(font_path, 18)
        result = fe.render_text(handle, "", 0, 0.0)
        # Empty text produces an empty result — no crash.
        assert result.width * result.height * 4 == len(result.pixels)


# ---------------------------------------------------------------------------
# TextOrientation enum values
# ---------------------------------------------------------------------------

class TestTextOrientation:
    def test_values(self):
        assert int(TextOrientation.HORIZONTAL_LTR) == 0
        assert int(TextOrientation.HORIZONTAL_RTL) == 1
        assert int(TextOrientation.VERTICAL_TTB)   == 2
        assert int(TextOrientation.VERTICAL_BTT)   == 3
        assert int(TextOrientation.DIAGONAL_45)    == 4
        assert int(TextOrientation.DIAGONAL_135)   == 5


# ---------------------------------------------------------------------------
# Summary: check NATIVE_AVAILABLE flag is accessible
# ---------------------------------------------------------------------------

def test_native_available_flag():
    assert isinstance(NATIVE_AVAILABLE, bool)
    if NATIVE_AVAILABLE:
        print("\n[INFO] Running with native C++ acceleration")
    else:
        print("\n[INFO] Running with pure-Python fallback")
