"""
binterint.backends.headless
===========================
Headless terminal backend — used for automated screenshot capture and TUI
interaction where there is no interactive terminal attached.

This backend has no-op implementations for raw mode and a simple queue-based
event mechanism so tests and automation pipelines can inject synthetic key
events without needing a real terminal device.
"""
from __future__ import annotations

import queue
from typing import Optional, Tuple, Union

from .base import (
    KeyEvent,
    MouseEvent,
    TerminalBackend,
)


class HeadlessBackend(TerminalBackend):
    """No-op headless backend for automated / scripted use.

    ``poll_event`` drains a FIFO queue of pre-enqueued events so that
    automation code can inject synthetic key or mouse events.

    Example
    -------
        backend = HeadlessBackend()
        backend.initialize(80, 24)
        backend.enqueue_event(KeyEvent(Key.CHAR, char="q"))
        event = backend.poll_event()  # → KeyEvent(key=Key.CHAR, char='q')
    """

    def __init__(self) -> None:
        self._cols:   int  = 80
        self._rows:   int  = 24
        self._queue:  queue.SimpleQueue = queue.SimpleQueue()
        self._output: list = []  # Records all write() calls for inspection.

    # ------------------------------------------------------------------
    # TerminalBackend implementation
    # ------------------------------------------------------------------

    def initialize(self, cols: int, rows: int) -> None:
        self._cols = cols
        self._rows = rows

    def shutdown(self) -> None:
        # Drain the event queue on shutdown.
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def poll_event(self) -> Optional[Union[KeyEvent, MouseEvent]]:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def write(self, data: str) -> None:
        self._output.append(data)

    def resize(self, cols: int, rows: int) -> None:
        self._cols = cols
        self._rows = rows

    def get_size(self) -> Tuple[int, int]:
        return self._cols, self._rows

    def enable_raw_mode(self) -> None:
        pass  # No-op in headless mode.

    def disable_raw_mode(self) -> None:
        pass  # No-op in headless mode.

    # ------------------------------------------------------------------
    # Headless-specific helpers
    # ------------------------------------------------------------------

    def enqueue_event(self, event: Union[KeyEvent, MouseEvent]) -> None:
        """Enqueue a synthetic event to be returned by the next :meth:`poll_event` call.

        Args:
            event: A :class:`~binterint.backends.base.KeyEvent` or
                :class:`~binterint.backends.base.MouseEvent` to inject.
        """
        self._queue.put(event)

    @property
    def written_output(self) -> list:
        """All strings that have been passed to :meth:`write`, in order."""
        return list(self._output)

    def clear_output(self) -> None:
        """Clear the recorded output buffer."""
        self._output.clear()


__all__ = ["HeadlessBackend"]
