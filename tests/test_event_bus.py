"""
Tests for binterint.event_bus and the three core plugins.
"""
from __future__ import annotations

import threading
import time
from typing import List

import pytest

from binterint.event_bus import (
    Event,
    EventBus,
    EventType,
    TerminalPlugin,
)
from binterint.backends.base import Key, KeyEvent, MouseButton, MouseAction, MouseEvent
from binterint.backends.headless import HeadlessBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class RecordingPlugin(TerminalPlugin):
    """Test plugin that records all received events."""

    def __init__(self, name_: str, subscriptions=None):
        self._name     = name_
        self._subs     = subscriptions or []
        self._events:  List[Event] = []
        self.registered   = False
        self.unregistered = False

    @property
    def name(self) -> str:
        return self._name

    def subscribe_to(self):
        return self._subs

    def on_register(self, bus):
        self.registered = True

    def on_event(self, event: Event):
        self._events.append(event)

    def on_unregister(self):
        self.unregistered = True

    @property
    def events(self) -> List[Event]:
        return list(self._events)


# ---------------------------------------------------------------------------
# EventBus basics
# ---------------------------------------------------------------------------

class TestEventBus:
    def test_register_plugin(self):
        bus    = EventBus()
        plugin = RecordingPlugin("a")
        bus.register(plugin)
        assert "a" in bus.plugin_names
        assert plugin.registered

    def test_duplicate_name_raises(self):
        bus = EventBus()
        bus.register(RecordingPlugin("dup"))
        with pytest.raises(ValueError, match="already registered"):
            bus.register(RecordingPlugin("dup"))

    def test_unregister_plugin(self):
        bus    = EventBus()
        plugin = RecordingPlugin("b")
        bus.register(plugin)
        bus.unregister("b")
        assert "b" not in bus.plugin_names
        assert plugin.unregistered

    def test_unregister_unknown_does_not_raise(self):
        bus = EventBus()
        bus.unregister("nonexistent")  # Should log a warning, not raise.

    def test_emit_routes_to_subscriber(self):
        bus    = EventBus()
        plugin = RecordingPlugin("p", [EventType.PTY_DATA])
        bus.register(plugin)

        bus.emit(Event(EventType.PTY_DATA, "test", {"text": "hello"}))

        non_subscribed = [e for e in plugin.events
                          if e.type == EventType.PTY_DATA]
        assert len(non_subscribed) == 1
        assert non_subscribed[0].data["text"] == "hello"

    def test_emit_does_not_route_to_unsubscribed(self):
        bus    = EventBus()
        plugin = RecordingPlugin("p", [EventType.RENDER_FRAME])
        bus.register(plugin)

        bus.emit(Event(EventType.PTY_DATA, "test"))

        pty_events = [e for e in plugin.events if e.type == EventType.PTY_DATA]
        assert len(pty_events) == 0

    def test_plugin_loaded_event_emitted_on_register(self):
        bus    = EventBus()
        plugin = RecordingPlugin("watcher", [EventType.PLUGIN_LOADED])
        bus.register(plugin)

        # After registering a second plugin, watcher should get PLUGIN_LOADED
        bus.register(RecordingPlugin("newcomer"))
        loaded_events = [e for e in plugin.events
                         if e.type == EventType.PLUGIN_LOADED
                         and e.data.get("plugin") == "newcomer"]
        assert len(loaded_events) == 1

    def test_propagation_stop(self):
        bus = EventBus()

        class StopPlugin(TerminalPlugin):
            @property
            def name(self): return "stopper"
            def subscribe_to(self): return [EventType.PTY_DATA]
            def on_register(self, bus): pass
            def on_event(self, event): event.propagation_stopped = True
            def on_unregister(self): pass

        class AfterPlugin(RecordingPlugin): pass

        bus.register(StopPlugin())
        after = AfterPlugin("after", [EventType.PTY_DATA])
        bus.register(after)
        bus.emit(Event(EventType.PTY_DATA, "x"))

        assert len([e for e in after.events if e.type == EventType.PTY_DATA]) == 0

    def test_event_history(self):
        bus = EventBus()
        bus.emit(Event(EventType.PTY_DATA, "src"))
        history = bus.event_history
        assert any(e.type == EventType.PTY_DATA for e in history)

    def test_clear_history(self):
        bus = EventBus()
        bus.emit(Event(EventType.PTY_DATA, "src"))
        bus.clear_history()
        assert bus.event_history == []

    def test_max_history_trimmed(self):
        bus = EventBus(max_history=5)
        for _ in range(10):
            bus.emit(Event(EventType.PTY_DATA, "s"))
        assert len(bus.event_history) <= 5

    def test_hooks(self):
        bus    = EventBus()
        called = []
        bus.add_hook("my_hook", lambda x: called.append(x))
        bus.run_hooks("my_hook", 42)
        assert called == [42]

    def test_shutdown_unregisters_all(self):
        bus = EventBus()
        bus.register(RecordingPlugin("x"))
        bus.register(RecordingPlugin("y"))
        bus.shutdown()
        assert bus.plugin_names == []

    def test_get_plugin(self):
        bus    = EventBus()
        plugin = RecordingPlugin("lookup")
        bus.register(plugin)
        assert bus.get_plugin("lookup") is plugin
        assert bus.get_plugin("missing") is None

    def test_broken_plugin_doesnt_crash_bus(self):
        """A plugin that raises in on_event should not stop other subscribers."""
        bus = EventBus()

        class BrokenPlugin(TerminalPlugin):
            @property
            def name(self): return "broken"
            def subscribe_to(self): return [EventType.PTY_DATA]
            def on_register(self, bus): pass
            def on_event(self, event): raise RuntimeError("boom")
            def on_unregister(self): pass

        after = RecordingPlugin("after", [EventType.PTY_DATA])
        bus.register(BrokenPlugin())
        bus.register(after)
        bus.emit(Event(EventType.PTY_DATA, "x"))
        # 'after' should still receive the event (broken plugin didn't stop it)
        assert any(e.type == EventType.PTY_DATA for e in after.events)


# ---------------------------------------------------------------------------
# Event dataclass
# ---------------------------------------------------------------------------

class TestEvent:
    def test_defaults(self):
        e = Event(EventType.PTY_DATA, "src")
        assert e.type   == EventType.PTY_DATA
        assert e.source == "src"
        assert e.data   == {}
        assert not e.propagation_stopped
        assert e.timestamp > 0

    def test_custom_data(self):
        e = Event(EventType.KEY_PRESS, "kb", {"key": "a"})
        assert e.data["key"] == "a"


# ---------------------------------------------------------------------------
# HeadlessBackend
# ---------------------------------------------------------------------------

class TestHeadlessBackend:
    def test_initialize(self):
        b = HeadlessBackend()
        b.initialize(80, 24)
        assert b.get_size() == (80, 24)

    def test_poll_empty(self):
        b = HeadlessBackend()
        assert b.poll_event() is None

    def test_enqueue_key_event(self):
        b   = HeadlessBackend()
        evt = KeyEvent(Key.CHAR, char="q")
        b.enqueue_event(evt)
        got = b.poll_event()
        assert got is evt
        assert b.poll_event() is None

    def test_enqueue_mouse_event(self):
        b   = HeadlessBackend()
        evt = MouseEvent(MouseButton.LEFT, MouseAction.PRESS, 5, 3)
        b.enqueue_event(evt)
        got = b.poll_event()
        assert isinstance(got, MouseEvent)
        assert got.x == 5

    def test_write_records_output(self):
        b = HeadlessBackend()
        b.write("hello")
        b.write(" world")
        assert b.written_output == ["hello", " world"]

    def test_clear_output(self):
        b = HeadlessBackend()
        b.write("data")
        b.clear_output()
        assert b.written_output == []

    def test_resize(self):
        b = HeadlessBackend()
        b.initialize(80, 24)
        b.resize(120, 40)
        assert b.get_size() == (120, 40)

    def test_raw_mode_noop(self):
        b = HeadlessBackend()
        b.enable_raw_mode()
        b.disable_raw_mode()

    def test_shutdown_drains_queue(self):
        b = HeadlessBackend()
        b.enqueue_event(KeyEvent(Key.ESC))
        b.shutdown()
        assert b.poll_event() is None


# ---------------------------------------------------------------------------
# KeyEvent / MouseEvent helpers
# ---------------------------------------------------------------------------

class TestKeyEvent:
    def test_has_modifier(self):
        from binterint.backends.base import Modifier
        e = KeyEvent(Key.CHAR, char="c", modifiers=Modifier.CTRL.value)
        assert e.has_modifier(Modifier.CTRL)
        assert not e.has_modifier(Modifier.ALT)


# ---------------------------------------------------------------------------
# SemanticPlugin (text analysis path — no LLM required)
# ---------------------------------------------------------------------------

class TestSemanticPlugin:
    def test_analyze_text_finds_buttons(self):
        from binterint.plugins.semantic_plugin import SemanticPlugin
        plugin  = SemanticPlugin()
        plugin.on_register(EventBus())

        elements = plugin.analyze_text("Press [ OK ] to continue or [ Cancel ]")
        labels   = [e["label"] for e in elements if e.get("type") == "button"]
        assert any("OK" in lbl for lbl in labels)

    def test_emits_element_detected(self):
        from binterint.plugins.semantic_plugin import SemanticPlugin
        bus     = EventBus()
        watcher = RecordingPlugin("watcher", [EventType.ELEMENT_DETECTED])
        bus.register(watcher)

        plugin = SemanticPlugin()
        bus.register(plugin)

        bus.emit(Event(EventType.SCREEN_UPDATED, "test",
                       {"text": "[ OK ]  [ Cancel ]"}))

        detected = [e for e in watcher.events
                    if e.type == EventType.ELEMENT_DETECTED]
        assert len(detected) >= 1


# ---------------------------------------------------------------------------
# RendererPlugin (without a real screen — only smoke-tests registration)
# ---------------------------------------------------------------------------

class TestRendererPlugin:
    def test_register_creates_output_dir(self, tmp_path):
        import pyte
        from binterint.plugins.renderer_plugin import RendererPlugin
        screen = pyte.Screen(40, 10)
        plugin = RendererPlugin(screen, output_dir=str(tmp_path / "frames"))
        bus    = EventBus()
        bus.register(plugin)
        assert (tmp_path / "frames").is_dir()

    def test_render_frame_event_saves_png(self, tmp_path):
        import pyte
        from binterint.plugins.renderer_plugin import RendererPlugin
        screen = pyte.Screen(40, 10)
        plugin = RendererPlugin(screen, output_dir=str(tmp_path))
        bus    = EventBus()
        bus.register(plugin)
        bus.emit(Event(EventType.RENDER_FRAME, "test"))
        pngs = list(tmp_path.glob("*.png"))
        assert len(pngs) == 1

    def test_render_complete_event_emitted(self, tmp_path):
        import pyte
        from binterint.plugins.renderer_plugin import RendererPlugin
        screen  = pyte.Screen(40, 10)
        plugin  = RendererPlugin(screen, output_dir=str(tmp_path))
        bus     = EventBus()
        watcher = RecordingPlugin("watcher", [EventType.RENDER_COMPLETE])
        bus.register(watcher)
        bus.register(plugin)
        bus.emit(Event(EventType.RENDER_FRAME, "test"))
        done = [e for e in watcher.events if e.type == EventType.RENDER_COMPLETE]
        assert len(done) == 1
        assert "path" in done[0].data
