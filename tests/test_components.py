import sys
import os
import pyte
# Add the package to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from binterint.screen_buffer import TerminalScreen
from binterint.renderer import TerminalRenderer
from binterint.semantic import SemanticAnalyzer

def test_render_and_semantic():
    # 1. Create a fake screen
    cols, rows = 40, 10
    screen = TerminalScreen(cols, rows)
    stream = pyte.Stream(screen)
    
    # Manually feed some TUI-like text with ANSI codes
    # [ OK ] is a button
    test_data = "\x1b[1;32m[ OK ]\x1b[0m   Username: __________\n\n[===   ] 50%"
    stream.feed(test_data)
    
    # 2. Test Semantic Analysis
    semantic = SemanticAnalyzer()
    text_content = "\n".join(screen.display)
    elements = semantic.extract_from_screen(text_content)
    
    print(f"Found {len(elements)} elements:")
    for el in elements:
        print(f" - {el['type']}: '{el['label']}'")
        
    # Validation
    types = [el['type'] for el in elements]
    assert "button" in types
    
    # 3. Test Rendering
    renderer = TerminalRenderer() 
    img = renderer.render_to_image(screen)
    img.save("test_output.png")
    print("Screenshot saved to test_output.png")

if __name__ == "__main__":
    test_render_and_semantic()
