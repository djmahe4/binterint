import os
import sys
import signal
from typing import List, Tuple, Optional

# Conditional imports based on Platform
if sys.platform != "win32":
    try:
        from ptyprocess import PtyProcessUnicode as PtyBackend
    except ImportError:
        PtyBackend = None
else:
    try:
        from pywinpty import PtyProcess as PtyBackend
        _IMPORT_ERROR = None
    except Exception as e:
        PtyBackend = None
        _IMPORT_ERROR = str(e)

class PtyEngine:
    """
    Handles spawning and interacting with a TUI process via a Pseudo-Terminal (PTY).
    Supports both Unix (ptyprocess) and Windows (pywinpty) for OS independence.
    """
    def __init__(self, cols: int = 80, rows: int = 24):
        self.cols = cols
        self.rows = rows
        self.process: Optional[PtyBackend] = None
        
    def spawn(self, cmd: List[str], env: Optional[dict] = None) -> None:
        """
        Spawns the target command in a new PTY.
        """
        if PtyBackend is None:
            backend_name = "pywinpty" if sys.platform == "win32" else "ptyprocess"
            err_msg = f"{backend_name} is required but not installed."
            if sys.platform == "win32" and _IMPORT_ERROR:
                err_msg += f" Import Error: {_IMPORT_ERROR}"
            raise RuntimeError(err_msg)
            
        spawn_env = os.environ.copy()
        if env:
            spawn_env.update(env)
            
        # Ensure TUI knows we are a color terminal
        spawn_env["TERM"] = "xterm-256color"
        if sys.platform != "win32" and "DISPLAY" in spawn_env:
            del spawn_env["DISPLAY"]
            
        if sys.platform == "win32":
            # pywinpty expects a command string, not a list, for some versions
            cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
            self.process = PtyBackend.spawn(
                cmd_str,
                dimensions=(self.rows, self.cols),
                env=spawn_env
            )
        else:
            self.process = PtyBackend.spawn(
                cmd,
                dimensions=(self.rows, self.cols),
                env=spawn_env
            )
        
    def read(self) -> str:
        """
        Reads available output from the PTY.
        """
        if not self.process:
            return ""
        
        try:
            if sys.platform == "win32":
                return self.process.read(4096)
            else:
                return self.process.read()
        except (EOFError, IOError):
            return ""
            
    def write(self, data: str) -> None:
        """
        Writes string data (keystrokes) to the PTY.
        """
        if self.process:
            self.process.write(data)
            self.process.flush()
            
    def resize(self, cols: int, rows: int) -> None:
        """
        Resizes the terminal window and notifies the child process.
        """
        self.cols = cols
        self.rows = rows
        if self.process:
            self.process.setwinsize(rows, cols)
            
    def is_alive(self) -> bool:
        """
        Checks if the child process is still running.
        """
        return self.process.isalive() if self.process else False
        
    def kill(self) -> None:
        """
        Terminates the spawned process.
        """
        if self.process:
            self.process.terminate(force=True)
            self.process = None

    def send_key(self, key_code: str) -> None:
        """
        Helper to send specialized keys.
        """
        key_map = {
            "enter": "\r",
            "tab": "\t",
            "esc": "\x1b",
            "up": "\x1b[A",
            "down": "\x1b[B",
            "right": "\x1b[C",
            "left": "\x1b[D",
            "backspace": "\x08" if sys.platform == "win32" else "\x7f",
        }
        
        code = key_map.get(key_code.lower())
        if code:
            self.write(code)
        else:
            self.write(key_code)
