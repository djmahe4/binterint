"""
binterint.backends.base
=======================
Abstract terminal backend — defines the common interface for different
execution environments (headless, interactive crossterm, Windows Console, etc.).

All backends expose:
* A unified :class:`KeyEvent` for keyboard input.
* A unified :class:`MouseEvent` for mouse input.
* :class:`TerminalBackend` ABC that every concrete backend must implement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple, Union


# ---------------------------------------------------------------------------
# KeyEvent
# ---------------------------------------------------------------------------

class Key(Enum):
    """Named keys recognised across all backends."""
    CHAR      = auto()
    ENTER     = auto()
    TAB       = auto()
    ESC       = auto()
    BACKSPACE = auto()
    DELETE    = auto()
    INSERT    = auto()
    UP        = auto()
    DOWN      = auto()
    LEFT      = auto()
    RIGHT     = auto()
    HOME      = auto()
    END       = auto()
    PAGE_UP   = auto()
    PAGE_DOWN = auto()
    F1        = auto()
    F2        = auto()
    F3        = auto()
    F4        = auto()
    F5        = auto()
    F6        = auto()
    F7        = auto()
    F8        = auto()
    F9        = auto()
    F10       = auto()
    F11       = auto()
    F12       = auto()


class Modifier(Enum):
    """Keyboard modifier flags (combinable as a bitmask integer)."""
    NONE  = 0
    CTRL  = 1
    ALT   = 2
    SHIFT = 4
    META  = 8


@dataclass
class KeyEvent:
    """A unified keyboard event.

    Args:
        key: The :class:`Key` that was pressed.
        char: The printable character (non-empty only when ``key == Key.CHAR``).
        modifiers: Bitmask of :class:`Modifier` values.
    """
    key:       Key   = Key.CHAR
    char:      str   = ""
    modifiers: int   = Modifier.NONE.value

    def has_modifier(self, mod: Modifier) -> bool:
        """Return ``True`` if *mod* is active in this event."""
        return bool(self.modifiers & mod.value)


# ---------------------------------------------------------------------------
# MouseEvent
# ---------------------------------------------------------------------------

class MouseButton(Enum):
    """Mouse buttons."""
    LEFT        = auto()
    RIGHT       = auto()
    MIDDLE      = auto()
    SCROLL_UP   = auto()
    SCROLL_DOWN = auto()


class MouseAction(Enum):
    """Mouse action type."""
    PRESS   = auto()
    RELEASE = auto()
    DRAG    = auto()
    MOVE    = auto()


@dataclass
class MouseEvent:
    """A unified mouse event.

    Args:
        button: Which :class:`MouseButton` was involved.
        action: The :class:`MouseAction` that occurred.
        x: Column index of the event (0-based terminal cell).
        y: Row index of the event (0-based terminal cell).
    """
    button: MouseButton  = MouseButton.LEFT
    action: MouseAction  = MouseAction.PRESS
    x:      int          = 0
    y:      int          = 0


# ---------------------------------------------------------------------------
# TerminalBackend ABC
# ---------------------------------------------------------------------------

class TerminalBackend(ABC):
    """Abstract terminal backend.

    Implementations provide input event polling and output writing for a
    specific execution environment (headless automation, interactive terminal,
    Windows Console, etc.).
    """

    @abstractmethod
    def initialize(self, cols: int, rows: int) -> None:
        """Set up the backend for a terminal of the given dimensions.

        Args:
            cols: Number of terminal columns.
            rows: Number of terminal rows.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Tear down the backend and release all resources."""

    @abstractmethod
    def poll_event(self) -> Optional[Union[KeyEvent, MouseEvent]]:
        """Return the next pending input event, or ``None`` if none is available.

        This method must be non-blocking.
        """

    @abstractmethod
    def write(self, data: str) -> None:
        """Send *data* to the terminal (e.g. forward to a PTY).

        Args:
            data: UTF-8 text or escape sequences to write.
        """

    @abstractmethod
    def resize(self, cols: int, rows: int) -> None:
        """Notify the backend of a terminal resize.

        Args:
            cols: New column count.
            rows: New row count.
        """

    @abstractmethod
    def get_size(self) -> Tuple[int, int]:
        """Return the current ``(cols, rows)`` terminal dimensions."""

    @abstractmethod
    def enable_raw_mode(self) -> None:
        """Put the terminal into raw (character-at-a-time) input mode."""

    @abstractmethod
    def disable_raw_mode(self) -> None:
        """Restore the terminal to cooked (line-buffered) input mode."""


__all__ = [
    "Key",
    "Modifier",
    "KeyEvent",
    "MouseButton",
    "MouseAction",
    "MouseEvent",
    "TerminalBackend",
]
