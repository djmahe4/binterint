import os
import sys
from pathlib import Path
import pyte
from PIL import Image, ImageDraw, ImageFont

class TerminalRenderer:
    """
    Renders the state of a pyte Screen into a PIL Image for analysis.
    """
    
    # Extended ANSI colors based on standard console themes
    PALETTE = {
        "black": "#000000",
        "red": "#AA0000",
        "green": "#00AA00",
        "yellow": "#AA5500", # Common ANSI yellow/brown
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
        "default": "#FFFFFF",
    }
    
    BG_PALETTE = {**PALETTE, "default": "#000000"}

    def __init__(self):
        self.font = self._load_font()
        # Dynamically calculate character dimensions based on font metrics
        if self.font:
            try:
                bbox = self.font.getbbox("M")
                self.char_width = bbox[2] - bbox[0]
                self.char_height = bbox[3] - bbox[1]
                if self.char_height == 0:
                    self.char_height = 20
            except Exception:
                self.char_width = 10
                self.char_height = 20
        else:
            self.char_width = 10
            self.char_height = 20

    def _load_font(self) -> ImageFont.FreeTypeFont:
        """
        Loads the bundled monospaced font for consistent cross-platform rendering.
        """
        base_path = Path(__file__).parent
        font_path = base_path / "fonts" / "RobotoMono-Regular.ttf"
        font_size = 18
        
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size=font_size)
            except Exception:
                pass
        
        fallbacks = [
            "C:\\Windows\\Fonts\\consola.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/System/Library/Fonts/Supplemental/Courier New.ttf"
        ]
        
        for path in fallbacks:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size=font_size)
                except Exception:
                    continue
                    
        return ImageFont.load_default()

    def render_to_image(self, screen: pyte.Screen) -> Image.Image:
        """
        Transforms a pyte.Screen state into a PIL Image.
        """
        width = screen.columns * self.char_width
        height = screen.lines * self.char_height
        
        image = Image.new("RGB", (width, height), color=self.BG_PALETTE["default"])
        draw = ImageDraw.Draw(image)
        
        # Screen buffer can be a dictionary or a list of lines depending on pyte version
        buffer = screen.buffer
        is_dict = isinstance(buffer, dict)

        for y in range(screen.lines):
            for x in range(screen.columns):
                try:
                    if is_dict:
                        char = buffer[y][x]
                    else:
                        char = buffer[y][x]
                except (KeyError, IndexError):
                    continue

                bg_key = char.bg
                if char.bold and char.bg in self.PALETTE and f"bright{char.bg}" in self.PALETTE:
                    bg_key = f"bright{char.bg}"
                
                bg_color = self.BG_PALETTE.get(bg_key, self.BG_PALETTE["default"])
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
                
                if char.data and char.data != ' ':
                    fg_key = char.fg
                    if char.bold and char.fg in self.PALETTE and f"bright{char.fg}" in self.PALETTE:
                        fg_key = f"bright{char.fg}"
                        
                    fg_color = self.PALETTE.get(fg_key, self.PALETTE["default"])
                    draw.text(
                        (x * self.char_width, y * self.char_height),
                        char.data,
                        font=self.font,
                        fill=fg_color
                    )
                    
        return image

    def save_screenshot(self, screen: pyte.Screen, path: str) -> str:
        """
        Renders the screen and saves it to a file.
        """
        image = self.render_to_image(screen)
        image.save(path)
        return os.path.abspath(path)
