"""
binterint.plugins.renderer_plugin
==================================
Renderer plugin — listens for :attr:`~binterint.event_bus.EventType.RENDER_FRAME`
events and renders the current screen state to a PNG file via
:class:`~binterint.renderer.TerminalRenderer`.

Subscribes to
~~~~~~~~~~~~~
* :attr:`~binterint.event_bus.EventType.RENDER_FRAME` — render the screen and
  emit :attr:`~binterint.event_bus.EventType.RENDER_COMPLETE`.
* :attr:`~binterint.event_bus.EventType.SCREEN_UPDATED` — auto-render if
  *auto_render* is enabled.
* :attr:`~binterint.event_bus.EventType.SHUTDOWN` — no-op cleanup.

Emits
~~~~~
* :attr:`~binterint.event_bus.EventType.RENDER_COMPLETE` — after a PNG is saved.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

import pyte

from ..event_bus import Event, EventBus, EventType, TerminalPlugin
from ..font_manager import FontConfig
from ..renderer import TerminalRenderer

logger = logging.getLogger("binterint.plugins.renderer")


class RendererPlugin(TerminalPlugin):
    """Event-driven renderer plugin.

    Wraps :class:`~binterint.renderer.TerminalRenderer` and renders the
    shared :class:`~pyte.Screen` to PNG on demand.

    Args:
        screen: The pyte screen shared with a :class:`PtyPlugin`.
        output_dir: Directory where rendered screenshots are saved.
        font_config: Optional font configuration for rendering.
        auto_render: If ``True``, render automatically on every
            :attr:`~binterint.event_bus.EventType.SCREEN_UPDATED` event.
    """

    def __init__(
        self,
        screen: pyte.Screen,
        output_dir: str = ".",
        font_config: Optional[FontConfig] = None,
        auto_render: bool = False,
    ) -> None:
        self._screen      = screen
        self._output_dir  = Path(output_dir)
        self._renderer    = TerminalRenderer(font_config=font_config)
        self._auto_render = auto_render
        self._bus:        Optional[EventBus] = None
        self._frame_count = 0

    # ------------------------------------------------------------------
    # TerminalPlugin interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "renderer"

    def subscribe_to(self) -> List[EventType]:
        events = [EventType.RENDER_FRAME, EventType.SHUTDOWN]
        if self._auto_render:
            events.append(EventType.SCREEN_UPDATED)
        return events

    def on_register(self, bus: EventBus) -> None:
        self._bus = bus
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def on_event(self, event: Event) -> None:
        if event.type in (EventType.RENDER_FRAME, EventType.SCREEN_UPDATED):
            path = event.data.get("path") or self._next_frame_path()
            self._render(str(path))
        elif event.type == EventType.SHUTDOWN:
            pass  # No resource cleanup needed.

    def on_unregister(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_now(self, path: Optional[str] = None) -> str:
        """Immediately render the current screen to *path* (or auto-path).

        Args:
            path: Output file path.  A sequential name is used when ``None``.

        Returns:
            Absolute path to the saved PNG.
        """
        out_path = path or self._next_frame_path()
        return self._render(out_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render(self, path: str) -> str:
        saved = self._renderer.save_screenshot(self._screen, path)
        logger.debug("RendererPlugin: saved frame to %s", saved)
        if self._bus:
            self._bus.emit(Event(EventType.RENDER_COMPLETE, self.name,
                                 {"path": saved}))
        return saved

    def _next_frame_path(self) -> str:
        self._frame_count += 1
        return str(self._output_dir / f"frame_{self._frame_count:05d}.png")
