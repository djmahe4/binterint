import os
from typing import List
from PIL import Image, ImageDraw, ImageFont
import pyte
from pathlib import Path

class TerminalRenderer:
    """
    Renders a pyte.Screen buffer into a high-fidelity image using monospaced fonts.
    Optimized for headless execution without system font dependencies.
    """
    
    # 16-color ANSI Palette (standard VGA)
    PALETTE = {
        "black": "#000000",
        "red": "#AA0000",
        "green": "#00AA00",
        "brown": "#AA5500",
        "blue": "#0000AA",
        "magenta": "#AA00AA",
        "cyan": "#00AAAA",
        "white": "#AAAAAA",
        "brightblack": "#555555",
        "brightred": "#FF5555",
        "brightgreen": "#55FF55",
        "brightyellow": "#FFFF55",
        "brightblue": "#5555FF",
        "brightmagenta": "#5555FF",
        "brightcyan": "#55FFFF",
        "brightwhite": "#FFFFFF",
        "default": "#FFFFFF"
    }
    
    BG_PALETTE = {**PALETTE, "default": "#000000"}

    def __init__(self, char_width: int = 10, char_height: int = 20):
        self.char_width = char_width
        self.char_height = char_height
        self.font = self._load_font()

    def _load_font(self) -> ImageFont.FreeTypeFont:
        """
        Loads the bundled monospaced font for consistent cross-platform rendering.
        """
        # Look for font bundled with the package
        base_path = Path(__file__).parent
        font_path = base_path / "fonts" / "RobotoMono-Regular.ttf"
        
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=14)
        
        # Fallback to simple loader for basic environments
        try:
            return ImageFont.load_default()
        except Exception:
            # Absolute fallback
            return None

    def render_to_image(self, screen: pyte.Screen) -> Image.Image:
        """
        Transforms a pyte.Screen state into a PIL Image.
        """
        width = screen.columns * self.char_width
        height = screen.lines * self.char_height
        
        image = Image.new("RGB", (width, height), color=self.BG_PALETTE["default"])
        draw = ImageDraw.Draw(image)
        
        for y in range(screen.lines):
            for x in range(screen.columns):
                char = screen.buffer[y][x]
                
                # Render background if not default
                bg_color = self.BG_PALETTE.get(char.bg, self.BG_PALETTE["default"])
                if bg_color != self.BG_PALETTE["default"]:
                    draw.rectangle(
                        [
                            x * self.char_width,
                            y * self.char_height,
                            (x + 1) * self.char_width,
                            (y + 1) * self.char_height
                        ],
                        fill=bg_color
                    )
                
                # Render character
                if char.data.strip():
                    fg_color = self.PALETTE.get(char.fg, self.PALETTE["default"])
                    draw.text(
                        (x * self.char_width, y * self.char_height),
                        char.data,
                        font=self.font,
                        fill=fg_color
                    )
                    
        return image

    def save_screenshot(self, screen: pyte.Screen, output_path: str) -> str:
        """
        Renders and saves a screenshot to the specified path.
        """
        img = self.render_to_image(screen)
        img.save(output_path)
        return os.path.abspath(output_path)
