import pyte

class TerminalScreen(pyte.Screen):
    """
    Extended pyte.Screen with helper methods for semantic extraction.
    """
    def __init__(self, cols: int, rows: int):
        super().__init__(cols, rows)
        
    def get_text_content(self) -> str:
        """
        Returns a plain text representation of the screen.
        """
        return "\n".join(self.display)
        
    def get_dirty_rect(self):
        """
        Returns bounding box of modified content (for future optimizations).
        """
        pass
