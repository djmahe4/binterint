"""
binterint.font_manager
======================
Font configuration, text orientation, and unified font management.

Provides a high-level ``FontManager`` that:
* Loads fonts from bundled resources or the system font path.
* Delegates rendering to the C++ ``FontEngine`` (when available via
  ``cpp_bridge``) or falls back to the pure-Python Pillow implementation.
* Exposes all six ``TextOrientation`` modes, ``HorizontalAlign``, and
  ``VerticalAlign`` so callers never need to import ``cpp_bridge`` directly.

Example
-------
    from binterint.font_manager import FontManager, FontConfig, TextOrientation

    mgr = FontManager()
    config = FontConfig(family="roboto-mono", size=18)
    result = mgr.render_text("Hello", config)
    # result.pixels  — RGBA bytes
    # result.width, result.height — dimensions
"""
from __future__ import annotations

import logging
import platform
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .cpp_bridge import FontEngine, RenderResult, TextOrientation  # re-export

logger = logging.getLogger("binterint.font_manager")


# ---------------------------------------------------------------------------
# Orientation / alignment enums
# ---------------------------------------------------------------------------

class HorizontalAlign(Enum):
    """Horizontal text alignment."""
    LEFT   = auto()
    CENTER = auto()
    RIGHT  = auto()


class VerticalAlign(Enum):
    """Vertical text alignment."""
    TOP    = auto()
    MIDDLE = auto()
    BOTTOM = auto()


# ---------------------------------------------------------------------------
# Font configuration
# ---------------------------------------------------------------------------

@dataclass
class FontConfig:
    """All parameters needed to describe a rendered font style.

    Args:
        family: Primary font family name (case-insensitive).  Bundled fonts
            are ``"roboto-mono"``, ``"fira-code"``, ``"jetbrains-mono"``, and
            ``"hack"``.
        size: Pixel height of the rendered glyphs.
        weight: ``"regular"``, ``"bold"``, or ``"italic"``.
        orientation: One of the :class:`TextOrientation` values.
        h_align: Horizontal alignment.
        v_align: Vertical alignment.
        letter_spacing: Extra pixels between characters.
        color: RGBA tuple for the glyph foreground colour.
        fallback_families: Ordered list of family names tried when the
            primary family is not found.
    """
    family:            str              = "roboto-mono"
    size:              int              = 18
    weight:            str              = "regular"
    orientation:       TextOrientation  = TextOrientation.HORIZONTAL_LTR
    h_align:           HorizontalAlign  = HorizontalAlign.LEFT
    v_align:           VerticalAlign    = VerticalAlign.TOP
    letter_spacing:    float            = 0.0
    color:             Tuple[int, int, int, int] = (255, 255, 255, 255)
    fallback_families: List[str]        = field(default_factory=list)


@dataclass
class TextBlock:
    """Text to be rendered at a specific terminal-cell position.

    Args:
        text: The UTF-8 string to render.
        config: Font rendering configuration.
        position: ``(column, row)`` of the top-left anchor in terminal cells.
        max_width: Optional maximum width in terminal cells for word-wrap.
        max_height: Optional maximum height in cells for truncation.
    """
    text:       str
    config:     FontConfig
    position:   Tuple[int, int]
    max_width:  Optional[int] = None
    max_height: Optional[int] = None


class FontNotFoundError(FileNotFoundError):
    """Raised when a font family cannot be resolved to a file."""


# ---------------------------------------------------------------------------
# FontManager
# ---------------------------------------------------------------------------

class FontManager:
    """Unified font manager — loads fonts and renders text blocks.

    Uses the native C++ ``FontEngine`` when the compiled extension is
    available, otherwise delegates to the pure-Python Pillow fallback
    provided by ``cpp_bridge``.
    """

    #: Bundled fonts shipped inside ``binterint/fonts/``.
    BUNDLED_FONTS: Dict[str, str] = {
        "roboto-mono":          "RobotoMono-Regular.ttf",
        "roboto-mono-bold":     "RobotoMono-Bold.ttf",
        "roboto-mono-italic":   "RobotoMono-Italic.ttf",
        "fira-code":            "FiraCode-Regular.ttf",
        "jetbrains-mono":       "JetBrainsMono-Regular.ttf",
        "hack":                 "Hack-Regular.ttf",
    }

    #: Platform-specific directories to search for system fonts.
    SYSTEM_FONT_PATHS: Dict[str, List[str]] = {
        "linux":  ["/usr/share/fonts", "/usr/local/share/fonts", "~/.fonts"],
        "darwin": ["/System/Library/Fonts", "/Library/Fonts", "~/Library/Fonts"],
        "win32":  [
            "C:\\Windows\\Fonts",
            "~\\AppData\\Local\\Microsoft\\Windows\\Fonts",
        ],
    }

    def __init__(self) -> None:
        self._engine: FontEngine = FontEngine()
        # Cache: (family, size, weight) → engine handle
        self._handle_cache: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_font(self, config: FontConfig) -> int:
        """Load (or return a cached handle for) the font described by *config*.

        Args:
            config: Font configuration.

        Returns:
            Opaque integer handle for use with :meth:`render_text`.

        Raises:
            FontNotFoundError: If no matching font file can be found.
        """
        cache_key = f"{config.family}:{config.size}:{config.weight}"
        if cache_key in self._handle_cache:
            return self._handle_cache[cache_key]

        font_path = self._resolve_font_path(
            config.family, config.weight
        )
        handle = self._engine.load_font(str(font_path), config.size)
        self._handle_cache[cache_key] = handle
        logger.debug("Loaded font %s (handle=%d)", font_path, handle)
        return handle

    def render_text(
        self,
        text: str,
        config: FontConfig,
        *,
        letter_spacing: Optional[float] = None,
    ) -> RenderResult:
        """Render *text* with the given font configuration.

        Args:
            text: UTF-8 string to render.
            config: Describes the font, size, orientation, etc.
            letter_spacing: Overrides ``config.letter_spacing`` when given.

        Returns:
            A :class:`~binterint.cpp_bridge.RenderResult` containing
            raw RGBA pixel data and the rendered image dimensions.
        """
        handle  = self.load_font(config)
        spacing = letter_spacing if letter_spacing is not None else config.letter_spacing
        return self._engine.render_text(
            handle,
            text,
            int(config.orientation),
            spacing,
        )

    def render_block(self, block: TextBlock) -> RenderResult:
        """Convenience wrapper that renders a :class:`TextBlock`.

        Args:
            block: Text block containing text, config, and position metadata.

        Returns:
            Rendered RGBA result.
        """
        return self.render_text(block.text, block.config,
                                letter_spacing=block.config.letter_spacing)

    def measure_text(
        self,
        text: str,
        config: FontConfig,
        *,
        letter_spacing: Optional[float] = None,
    ) -> Tuple[int, int]:
        """Return ``(width, height)`` of *text* without rendering.

        Args:
            text: UTF-8 string.
            config: Font configuration.
            letter_spacing: Overrides ``config.letter_spacing`` when given.

        Returns:
            ``(total_width_px, line_height_px)``
        """
        handle  = self.load_font(config)
        spacing = letter_spacing if letter_spacing is not None else config.letter_spacing
        return self._engine.measure_text(handle, text, spacing)

    def list_loaded_fonts(self) -> List[Tuple[int, str]]:
        """Return ``[(handle, path), …]`` for all currently loaded fonts."""
        return self._engine.list_loaded_fonts()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_font_path(self, family: str, weight: str = "regular") -> Path:
        """Resolve a font family + weight to an absolute file path.

        Searches bundled fonts first, then system fonts.

        Args:
            family: Font family name (e.g. ``"roboto-mono"``).
            weight: ``"regular"``, ``"bold"``, or ``"italic"``.

        Returns:
            Absolute :class:`~pathlib.Path` to the font file.

        Raises:
            FontNotFoundError: If the font cannot be found.
        """
        family_key  = family.lower().replace(" ", "-")
        weight_key  = weight.lower()
        font_dir    = Path(__file__).parent / "fonts"

        # Build lookup keys in priority order.
        lookup_keys = [
            f"{family_key}-{weight_key}",
            family_key,
        ]

        for key in lookup_keys:
            if key in self.BUNDLED_FONTS:
                candidate = font_dir / self.BUNDLED_FONTS[key]
                if candidate.exists():
                    return candidate

        # Search system font directories.
        system = platform.system().lower()
        if system == "windows":
            system = "win32"
        for search_dir_str in self.SYSTEM_FONT_PATHS.get(system, []):
            search_path = Path(search_dir_str).expanduser()
            if not search_path.exists():
                continue
            for font_file in search_path.rglob("*.ttf"):
                stem = font_file.stem.lower()
                if family_key.replace("-", "") in stem.replace("-", "").replace("_", ""):
                    return font_file

        # Absolute fallback: use the first bundled font that exists.
        for rel_name in self.BUNDLED_FONTS.values():
            candidate = font_dir / rel_name
            if candidate.exists():
                logger.warning(
                    "Font '%s' not found; falling back to %s", family, rel_name
                )
                return candidate

        raise FontNotFoundError(
            f"Font '{family}' (weight='{weight}') not found bundled or on system. "
            "Please install a TrueType font or provide an absolute path via FontConfig."
        )


# ---------------------------------------------------------------------------
# Re-exports so callers only need ``from binterint.font_manager import …``
# ---------------------------------------------------------------------------
__all__ = [
    "FontManager",
    "FontConfig",
    "TextBlock",
    "TextOrientation",
    "HorizontalAlign",
    "VerticalAlign",
    "FontNotFoundError",
    "RenderResult",
]
