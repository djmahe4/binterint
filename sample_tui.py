import sys
import os
import time

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

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
        
        # Cross platform character reading without echoing
        if os.name == 'nt':
            import msvcrt
            def read_char():
                try:
                    c = msvcrt.getch()
                    return c.decode('utf-8', 'ignore') if isinstance(c, bytes) else c
                except Exception:
                    return ""
        else:
            import tty, termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(sys.stdin.fileno())
            def read_char():
                try:
                    return sys.stdin.read(1)
                except Exception:
                    return ""
        
        while True:
            char = read_char()
            if char.lower() == 'q':
                break
            elif char == '1':
                draw_box(5, 6, 15, 3, " [ CLICKED ] ", "33")
            elif char == '2':
                draw_box(22, 6, 15, 3, " [ CLICKED ] ", "33")
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        if os.name != 'nt':
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    main()
