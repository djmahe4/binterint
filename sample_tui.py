import sys
import os
import time

def clear_screen():
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()

def draw_box(x, y, w, h, title, color="37"):
    # ANSI for moving cursor and drawing
    # top
    sys.stdout.write(f"\x1b[{y};{x}H\x1b[{color}m┌{'─' * (w-2)}┐\x1b[0m")
    # middle
    for i in range(1, h-1):
        sys.stdout.write(f"\x1b[{y+i};{x}H\x1b[{color}m│{' ' * (w-2)}│\x1b[0m")
    # bottom
    sys.stdout.write(f"\x1b[{y+h-1};{x}H\x1b[{color}m└{'─' * (w-2)}┘\x1b[0m")
    # title
    sys.stdout.write(f"\x1b[{y};{x+2}H {title} ")
    sys.stdout.flush()

def main():
    clear_screen()
    draw_box(5, 2, 20, 3, "Binterint Test", "32")
    draw_box(5, 6, 15, 3, " [ Button 1 ] ", "34")
    draw_box(22, 6, 15, 3, " [ Button 2 ] ", "31")
    
    sys.stdout.write("\x1b[10;5HPress 'q' to exit, '1' or '2' to click buttons...")
    sys.stdout.flush()

    # Simple input loop
    # Note: in a real PTY this would be raw mode, but for a sample it's fine
    try:
        while True:
            char = sys.stdin.read(1)
            if char.lower() == 'q':
                break
            elif char == '1':
                draw_box(5, 6, 15, 3, " [ CLICKED ] ", "33")
            elif char == '2':
                draw_box(22, 6, 15, 3, " [ CLICKED ] ", "33")
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
