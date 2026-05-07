"""
binterint.plugins.semantic_plugin
==================================
Semantic plugin — detects UI elements in TUI screenshots and emits structured
:attr:`~binterint.event_bus.EventType.ELEMENT_DETECTED` events.

Subscribes to
~~~~~~~~~~~~~
* :attr:`~binterint.event_bus.EventType.RENDER_COMPLETE` — analyze the saved
  screenshot automatically whenever a new frame is rendered.
* :attr:`~binterint.event_bus.EventType.SCREEN_UPDATED` — run rule-based
  element extraction on the current text buffer.
* :attr:`~binterint.event_bus.EventType.SHUTDOWN` — no-op.

Emits
~~~~~
* :attr:`~binterint.event_bus.EventType.ELEMENT_DETECTED` — for each element
  found in the screen (one event per element).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

from ..event_bus import Event, EventBus, EventType, TerminalPlugin
from ..semantic import SemanticAnalyzer

logger = logging.getLogger("binterint.plugins.semantic")


class SemanticPlugin(TerminalPlugin):
    """Event-driven semantic analysis plugin.

    Wraps :class:`~binterint.semantic.SemanticAnalyzer` and emits one
    :attr:`~binterint.event_bus.EventType.ELEMENT_DETECTED` event per UI
    element found.

    Args:
        cols: Terminal width (used for coordinate normalisation).
        rows: Terminal height.
        model_id: Optional LLM model ID (passed to :class:`SemanticAnalyzer`).
        use_vision: If ``True``, use Vision LLM for screenshot analysis
            (requires ``GOOGLE_API_KEY`` or ``OPENAI_API_KEY``).  The
            rule-based extractor is always available without API keys.
    """

    def __init__(
        self,
        cols: int = 80,
        rows: int = 24,
        model_id: Optional[str] = None,
        use_vision: bool = False,
    ) -> None:
        self._cols       = cols
        self._rows       = rows
        self._analyzer   = SemanticAnalyzer(model_id=model_id)
        self._use_vision = use_vision
        self._bus:       Optional[EventBus] = None
        self._last_text: str = ""

    # ------------------------------------------------------------------
    # TerminalPlugin interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "semantic"

    def subscribe_to(self) -> List[EventType]:
        events = [EventType.SCREEN_UPDATED, EventType.SHUTDOWN]
        if self._use_vision:
            events.append(EventType.RENDER_COMPLETE)
        return events

    def on_register(self, bus: EventBus) -> None:
        self._bus = bus

    def on_event(self, event: Event) -> None:
        if event.type == EventType.SCREEN_UPDATED:
            text = event.data.get("text", self._last_text)
            if text:
                self._last_text = text
                self._analyze_text(text)

        elif event.type == EventType.RENDER_COMPLETE and self._use_vision:
            path = event.data.get("path", "")
            if path:
                asyncio.ensure_future(self._analyze_vision(path))

        elif event.type == EventType.SHUTDOWN:
            pass

    def on_unregister(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Analysis helpers
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> List[Dict]:
        """Run rule-based analysis on *text* and return the element list.

        This is also callable directly (outside the event loop) for testing.

        Args:
            text: Plain-text terminal screen content.

        Returns:
            List of element dicts as returned by
            :meth:`~binterint.semantic.SemanticAnalyzer.extract_from_screen`.
        """
        return self._analyzer.extract_from_screen(text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _analyze_text(self, text: str) -> None:
        elements = self._analyzer.extract_from_screen(text)
        if not self._bus:
            return
        for el in elements:
            self._bus.emit(Event(
                EventType.ELEMENT_DETECTED,
                self.name,
                {
                    "type":   el.get("type", "unknown"),
                    "label":  el.get("label", ""),
                    "key":    el.get("key", ""),
                    "span":   el.get("span"),
                },
            ))

    async def _analyze_vision(self, screenshot_path: str) -> None:
        try:
            elements = await self._analyzer.analyze_screenshot(
                screenshot_path, self._cols, self._rows
            )
            if not self._bus:
                return
            for el in elements:
                self._bus.emit(Event(
                    EventType.ELEMENT_DETECTED,
                    self.name,
                    {
                        "type":       el.type,
                        "label":      el.label,
                        "x":          el.x,
                        "y":          el.y,
                        "confidence": el.confidence,
                        "grid":       SemanticAnalyzer.map_to_grid(
                                          el.x, el.y, self._cols, self._rows),
                    },
                ))
        except Exception:
            logger.exception("SemanticPlugin vision analysis failed")
