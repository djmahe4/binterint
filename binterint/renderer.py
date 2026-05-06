import os
import logging
from pathlib import Path
from typing import Optional

import pyte
from PIL import Image, ImageDraw, ImageFont

from .font_manager import FontConfig, FontManager, TextOrientation

logger = logging.getLogger("binterint.renderer")


class TerminalRenderer:
    """Renders the state of a pyte Screen into a PIL Image for analysis.

    Rendering uses the bundled :class:`~binterint.font_manager.FontManager` so
    that all font files and orientation modes supported by Phase 2 are
    available out of the box.  The legacy Pillow-only path is retained as a
    fallback when no font file can be resolved.
    """

    # Extended ANSI colors based on standard console themes
    PALETTE = {
        "black":         "#000000",
        "red":           "#AA0000",
        "green":         "#00AA00",
        "yellow":        "#AA5500",
        "blue":          "#0000AA",
        "magenta":       "#AA00AA",
        "cyan":          "#00AAAA",
        "white":         "#AAAAAA",
        "brightblack":   "#555555",
        "brightred":     "#FF5555",
        "brightgreen":   "#55FF55",
        "brightyellow":  "#FFFF55",
        "brightblue":    "#5555FF",
        "brightmagenta": "#5555FF",
        "brightcyan":    "#55FFFF",
        "brightwhite":   "#FFFFFF",
        "default":       "#FFFFFF",
    }

    BG_PALETTE = {**PALETTE, "default": "#000000"}

    def __init__(
        self,
        font_config: Optional[FontConfig] = None,
        font_size:   int = 18,
    ) -> None:
        """
        Args:
            font_config: Optional :class:`~binterint.font_manager.FontConfig`
                for advanced font selection and orientation control.  When
                ``None`` a default Roboto Mono regular config is used.
            font_size: Pixel height of rendered glyphs (ignored when
                *font_config* is provided).
        """
        self._font_manager = FontManager()
        self._font_config  = font_config or FontConfig(
            family="roboto-mono",
            size=font_size,
            orientation=TextOrientation.HORIZONTAL_LTR,
        )

        # Load PIL font for the glyph-by-glyph renderer path.
        self.font       = self._load_pil_font(self._font_config.size)
        self.char_width, self.char_height = self._measure_cell(self.font)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_to_image(
        self,
        screen: pyte.Screen,
        *,
        font_config: Optional[FontConfig] = None,
    ) -> Image.Image:
        """Transform a *pyte.Screen* state into a PIL RGBA Image.

        Args:
            screen: The pyte screen to render.
            font_config: Overrides the instance-level font config for this
                call only (useful for testing different orientations).

        Returns:
            A PIL ``"RGBA"`` image with the rendered terminal state.
        """
        cfg = font_config or self._font_config
        # Reload PIL font if the size changed.
        if cfg.size != self._font_config.size or font_config is not None:
            pil_font = self._load_pil_font(cfg.size)
            cw, ch  = self._measure_cell(pil_font)
        else:
            pil_font = self.font
            cw, ch   = self.char_width, self.char_height

        width  = screen.columns * cw
        height = screen.lines   * ch

        image  = Image.new("RGBA", (width, height), color=(0, 0, 0, 255))
        draw   = ImageDraw.Draw(image)
        buffer = screen.buffer

        for y in range(screen.lines):
            for x in range(screen.columns):
                try:
                    char = buffer[y][x]
                except (KeyError, IndexError):
                    continue

                # Background colour
                bg_key = char.bg
                if char.bold and char.bg in self.PALETTE and f"bright{char.bg}" in self.PALETTE:
                    bg_key = f"bright{char.bg}"
                bg_color = self.BG_PALETTE.get(bg_key, self.BG_PALETTE["default"])
                if bg_color != self.BG_PALETTE["default"]:
                    draw.rectangle(
                        [x * cw, y * ch, (x + 1) * cw, (y + 1) * ch],
                        fill=bg_color,
                    )

                # Foreground glyph
                if char.data and char.data != " ":
                    fg_key = char.fg
                    if char.bold and char.fg in self.PALETTE and f"bright{char.fg}" in self.PALETTE:
                        fg_key = f"bright{char.fg}"
                    fg_color = self.PALETTE.get(fg_key, self.PALETTE["default"])
                    draw.text(
                        (x * cw, y * ch),
                        char.data,
                        font=pil_font,
                        fill=fg_color,
                        anchor="lt",
                    )

        # Apply orientation transform if requested
        image = self._apply_orientation(image, cfg.orientation)
        return image

    def render_text_overlay(
        self,
        base_image: Image.Image,
        text: str,
        position: tuple,
        font_config: Optional[FontConfig] = None,
    ) -> Image.Image:
        """Render a text string onto an existing image using the FontManager.

        Unlike :meth:`render_to_image` this method targets a specific region
        of an already-rendered screenshot and supports all six
        :class:`~binterint.font_manager.TextOrientation` modes.

        Args:
            base_image: The PIL image to composite onto.
            text: UTF-8 text to render.
            position: ``(x, y)`` pixel position for the top-left of the text.
            font_config: Font config; falls back to the instance config.

        Returns:
            A new ``"RGBA"`` image with the text composited onto *base_image*.
        """
        cfg    = font_config or self._font_config
        result = self._font_manager.render_text(text, cfg)
        if not result.pixels or result.width <= 0 or result.height <= 0:
            return base_image

        # Build PIL image from raw RGBA bytes.
        text_img = Image.frombytes("RGBA", (result.width, result.height),
                                   bytes(result.pixels))
        output = base_image.convert("RGBA").copy()
        output.paste(text_img, position, mask=text_img)
        return output

    def save_screenshot(self, screen: pyte.Screen, path: str) -> str:
        """Render *screen* and save the PNG to *path*.

        Args:
            screen: pyte screen to render.
            path: Output file path (PNG).

        Returns:
            Absolute path to the saved file.
        """
        image = self.render_to_image(screen)
        image.save(path)
        return os.path.abspath(path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_pil_font(size: int) -> ImageFont.FreeTypeFont:
        """Load the bundled Roboto Mono font at *size* pixels, with fallbacks."""
        base_path = Path(__file__).parent
        candidates = [
            base_path / "fonts" / "RobotoMono-Regular.ttf",
            Path("C:\\Windows\\Fonts\\consola.ttf"),
            Path("/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"),
            Path("/System/Library/Fonts/Supplemental/Courier New.ttf"),
        ]
        for candidate in candidates:
            if candidate.exists():
                try:
                    return ImageFont.truetype(str(candidate), size=size)
                except Exception:
                    continue
        return ImageFont.load_default()

    @staticmethod
    def _measure_cell(font: ImageFont.FreeTypeFont) -> tuple:
        """Return ``(char_width, char_height)`` for a monospace font."""
        try:
            char_width  = int(font.getlength("M"))
            ascent, descent = font.getmetrics()
            char_height = ascent + descent
            if char_height == 0:
                char_height = char_width * 2
        except Exception:
            char_width, char_height = 10, 20
        return char_width, char_height

    @staticmethod
    def _apply_orientation(
        image: Image.Image, orientation: TextOrientation
    ) -> Image.Image:
        """Rotate/flip *image* according to *orientation*.

        For the full-screen render the meaningful orientations are
        VERTICAL and DIAGONAL (e.g. rotated terminal views).
        HORIZONTAL_LTR is a no-op.
        """
        if orientation == TextOrientation.HORIZONTAL_RTL:
            return image.transpose(Image.FLIP_LEFT_RIGHT)
        if orientation == TextOrientation.VERTICAL_TTB:
            return image.rotate(-90, expand=True)
        if orientation == TextOrientation.VERTICAL_BTT:
            return image.rotate(90, expand=True)
        if orientation == TextOrientation.DIAGONAL_45:
            return image.rotate(45, expand=True)
        if orientation == TextOrientation.DIAGONAL_135:
            return image.rotate(-45, expand=True)
        return image  # HORIZONTAL_LTR — no-op
