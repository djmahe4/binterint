"""
Tests for binterint.font_manager — FontManager, FontConfig, TextOrientation,
HorizontalAlign, VerticalAlign, and TextBlock.
"""
import os
import pytest

from binterint.font_manager import (
    FontManager,
    FontConfig,
    TextBlock,
    TextOrientation,
    HorizontalAlign,
    VerticalAlign,
    FontNotFoundError,
    RenderResult,
)


@pytest.fixture
def mgr():
    return FontManager()


@pytest.fixture
def default_cfg():
    return FontConfig(family="roboto-mono", size=18)


@pytest.fixture
def font_available():
    """Skip tests if bundled fonts are not present."""
    font_dir = os.path.join(os.path.dirname(__file__), "..", "binterint", "fonts")
    if not os.path.isfile(os.path.join(font_dir, "RobotoMono-Regular.ttf")):
        pytest.skip("Bundled fonts not present")


# ---------------------------------------------------------------------------
# FontConfig
# ---------------------------------------------------------------------------

class TestFontConfig:
    def test_defaults(self):
        cfg = FontConfig()
        assert cfg.family         == "roboto-mono"
        assert cfg.size           == 18
        assert cfg.weight         == "regular"
        assert cfg.orientation    == TextOrientation.HORIZONTAL_LTR
        assert cfg.h_align        == HorizontalAlign.LEFT
        assert cfg.v_align        == VerticalAlign.TOP
        assert cfg.letter_spacing == 0.0

    def test_custom_values(self):
        cfg = FontConfig(
            family="fira-code",
            size=24,
            weight="bold",
            orientation=TextOrientation.VERTICAL_TTB,
            letter_spacing=1.5,
        )
        assert cfg.family         == "fira-code"
        assert cfg.size           == 24
        assert cfg.orientation    == TextOrientation.VERTICAL_TTB
        assert cfg.letter_spacing == 1.5


# ---------------------------------------------------------------------------
# FontManager.load_font
# ---------------------------------------------------------------------------

class TestFontManagerLoadFont:
    def test_load_roboto_mono(self, mgr, font_available):
        cfg    = FontConfig(family="roboto-mono", size=18)
        handle = mgr.load_font(cfg)
        assert isinstance(handle, int)

    def test_caching_same_handle(self, mgr, font_available):
        cfg = FontConfig(family="roboto-mono", size=18)
        h1  = mgr.load_font(cfg)
        h2  = mgr.load_font(cfg)
        assert h1 == h2

    def test_different_sizes_different_handles(self, mgr, font_available):
        cfg18 = FontConfig(family="roboto-mono", size=18)
        cfg24 = FontConfig(family="roboto-mono", size=24)
        h18   = mgr.load_font(cfg18)
        h24   = mgr.load_font(cfg24)
        assert h18 != h24

    def test_fira_code(self, mgr, font_available):
        cfg    = FontConfig(family="fira-code", size=18)
        handle = mgr.load_font(cfg)
        assert isinstance(handle, int)

    def test_hack_font(self, mgr, font_available):
        cfg    = FontConfig(family="hack", size=18)
        handle = mgr.load_font(cfg)
        assert isinstance(handle, int)

    def test_jetbrains_mono(self, mgr, font_available):
        cfg    = FontConfig(family="jetbrains-mono", size=18)
        handle = mgr.load_font(cfg)
        assert isinstance(handle, int)

    def test_missing_font_falls_back_or_raises(self, mgr):
        cfg = FontConfig(family="totally-nonexistent-xyz123", size=18)
        try:
            handle = mgr.load_font(cfg)
            # If it falls back to a bundled font — acceptable.
            assert isinstance(handle, int)
        except FontNotFoundError:
            pass  # Correct behaviour when no font at all is found.


# ---------------------------------------------------------------------------
# FontManager.render_text
# ---------------------------------------------------------------------------

class TestFontManagerRenderText:
    def test_basic_render(self, mgr, default_cfg, font_available):
        result = mgr.render_text("Hello", default_cfg)
        assert isinstance(result, RenderResult)
        assert result.width  > 0
        assert result.height > 0
        assert len(result.pixels) == result.width * result.height * 4

    def test_render_empty_string(self, mgr, default_cfg, font_available):
        result = mgr.render_text("", default_cfg)
        # Should not crash; pixels may be empty or minimal.
        assert len(result.pixels) == result.width * result.height * 4

    def test_render_all_orientations(self, mgr, font_available):
        orientations = [
            TextOrientation.HORIZONTAL_LTR,
            TextOrientation.HORIZONTAL_RTL,
            TextOrientation.VERTICAL_TTB,
            TextOrientation.VERTICAL_BTT,
            TextOrientation.DIAGONAL_45,
            TextOrientation.DIAGONAL_135,
        ]
        for orient in orientations:
            cfg    = FontConfig(family="roboto-mono", size=18, orientation=orient)
            result = mgr.render_text("AB", cfg)
            assert result.width * result.height * 4 == len(result.pixels), \
                f"Pixel buffer size mismatch for {orient}"

    def test_vertical_ttb_transposes_dimensions(self, mgr, font_available):
        cfg_h   = FontConfig(family="roboto-mono", size=18,
                             orientation=TextOrientation.HORIZONTAL_LTR)
        cfg_v   = FontConfig(family="roboto-mono", size=18,
                             orientation=TextOrientation.VERTICAL_TTB)
        ltr     = mgr.render_text("Hi", cfg_h)
        vtb     = mgr.render_text("Hi", cfg_v)
        assert vtb.width  == ltr.height
        assert vtb.height == ltr.width

    def test_letter_spacing_widens_result(self, mgr, font_available):
        cfg     = FontConfig(family="roboto-mono", size=18, letter_spacing=0.0)
        cfg_sp  = FontConfig(family="roboto-mono", size=18, letter_spacing=5.0)
        normal  = mgr.render_text("Hello", cfg)
        spaced  = mgr.render_text("Hello", cfg_sp)
        assert spaced.width >= normal.width


# ---------------------------------------------------------------------------
# FontManager.measure_text
# ---------------------------------------------------------------------------

class TestFontManagerMeasureText:
    def test_returns_positive_dimensions(self, mgr, default_cfg, font_available):
        w, h = mgr.measure_text("Test", default_cfg)
        assert w > 0
        assert h > 0

    def test_longer_text_is_wider(self, mgr, default_cfg, font_available):
        w_short, _ = mgr.measure_text("Hi", default_cfg)
        w_long,  _ = mgr.measure_text("Hello World", default_cfg)
        assert w_long > w_short


# ---------------------------------------------------------------------------
# TextBlock
# ---------------------------------------------------------------------------

class TestTextBlock:
    def test_render_block(self, mgr, default_cfg, font_available):
        block  = TextBlock(text="BlockTest", config=default_cfg, position=(5, 3))
        result = mgr.render_block(block)
        assert result.width  > 0
        assert result.height > 0


# ---------------------------------------------------------------------------
# FontManager.list_loaded_fonts
# ---------------------------------------------------------------------------

class TestListLoadedFonts:
    def test_after_load(self, mgr, font_available):
        cfg = FontConfig(family="roboto-mono", size=18)
        mgr.load_font(cfg)
        fonts = mgr.list_loaded_fonts()
        assert len(fonts) >= 1
        handles, paths = zip(*fonts)
        assert all(isinstance(h, int)  for h in handles)
        assert all(isinstance(p, str)  for p in paths)
        assert any("RobotoMono" in p for p in paths)
