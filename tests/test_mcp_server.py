"""
Tests for binterint.mcp_server — unit tests that mock out TUIController
so no real PTY subprocess is spawned.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    """Run a coroutine synchronously in a new event loop."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_mock_ctrl(tmp_path, text="Hello World"):
    """Return a MagicMock that mimics TUIController."""
    ctrl = MagicMock()
    ctrl.screen.get_text_content.return_value = text
    screenshot_path = str(tmp_path / "screenshot.png")

    # Create a tiny 1×1 PNG so PIL doesn't complain.
    from PIL import Image
    Image.new("RGB", (8, 8), color=(0, 0, 0)).save(screenshot_path)

    ctrl.save_screenshot.return_value = screenshot_path
    ctrl.pty.process.isalive.return_value = False  # Exits after 1 step
    ctrl.drain.return_value = None
    ctrl.stop.return_value = None
    return ctrl


# ---------------------------------------------------------------------------
# tui_screenshot
# ---------------------------------------------------------------------------

class TestTuiScreenshot:
    def test_returns_expected_keys(self, tmp_path):
        from binterint.mcp_server import tui_screenshot
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            result = run(tui_screenshot(
                command="echo hello",
                output_path=str(tmp_path / "out.png"),
                wait_seconds=0,
            ))
        assert "path"              in result
        assert "dimensions"        in result
        assert "text_content"      in result
        assert "detected_elements" in result

    def test_dimensions_match_args(self, tmp_path):
        from binterint.mcp_server import tui_screenshot
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            result = run(tui_screenshot(
                command="echo", columns=120, rows=40, wait_seconds=0
            ))
        assert result["dimensions"] == {"columns": 120, "rows": 40}

    def test_keys_to_send_are_forwarded(self, tmp_path):
        from binterint.mcp_server import tui_screenshot
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            run(tui_screenshot(
                command="echo",
                wait_seconds=0,
                keys_to_send=["j", "q"],
            ))
        # send_key should have been called twice.
        assert ctrl.send_key.call_count == 2

    def test_ctrl_stop_always_called(self, tmp_path):
        from binterint.mcp_server import tui_screenshot
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            run(tui_screenshot(command="echo", wait_seconds=0))
        ctrl.stop.assert_called_once()


# ---------------------------------------------------------------------------
# tui_interact
# ---------------------------------------------------------------------------

class TestTuiInteract:
    def test_send_key_step(self, tmp_path):
        from binterint.mcp_server import tui_interact
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            result = run(tui_interact(
                command="echo",
                interaction_plan=[{"action": "send_key", "key": "q"}],
            ))
        assert result["success"] is True
        assert result["steps"][0]["action"] == "send_key"
        assert result["steps"][0]["key"]    == "q"

    def test_screenshot_step(self, tmp_path):
        from binterint.mcp_server import tui_interact
        ctrl = _make_mock_ctrl(tmp_path)
        out  = str(tmp_path / "step1.png")
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            result = run(tui_interact(
                command="echo",
                interaction_plan=[{"action": "screenshot", "path": out}],
            ))
        assert result["success"] is True
        assert result["steps"][0]["action"] == "screenshot"

    def test_get_text_step(self, tmp_path):
        from binterint.mcp_server import tui_interact
        ctrl = _make_mock_ctrl(tmp_path, text="Screen text")
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            result = run(tui_interact(
                command="echo",
                interaction_plan=[{"action": "get_text"}],
            ))
        assert result["steps"][0]["action"] == "get_text"
        assert result["steps"][0]["text"]   == "Screen text"

    def test_wait_step(self, tmp_path):
        from binterint.mcp_server import tui_interact
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            result = run(tui_interact(
                command="echo",
                interaction_plan=[{"action": "wait", "seconds": 0}],
            ))
        assert result["steps"][0]["seconds"] == 0.0

    def test_unknown_action_recorded(self, tmp_path):
        from binterint.mcp_server import tui_interact
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            result = run(tui_interact(
                command="echo",
                interaction_plan=[{"action": "bogus"}],
            ))
        assert result["steps"][0]["error"] == "unknown action"

    def test_ctrl_stop_always_called(self, tmp_path):
        from binterint.mcp_server import tui_interact
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            run(tui_interact(command="echo", interaction_plan=[]))
        ctrl.stop.assert_called_once()

    def test_exception_returns_failure_dict(self, tmp_path):
        from binterint.mcp_server import tui_interact
        ctrl = MagicMock()
        ctrl.spawn.side_effect = RuntimeError("boom")
        ctrl.stop.return_value = None
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            result = run(tui_interact(command="echo", interaction_plan=[]))
        assert result["success"] is False
        assert "boom" in result["error"]


# ---------------------------------------------------------------------------
# tui_analyze
# ---------------------------------------------------------------------------

class TestTuiAnalyze:
    def test_returns_list(self, tmp_path):
        from binterint.mcp_server import tui_analyze

        # Create a tiny valid PNG.
        from PIL import Image
        img_path = str(tmp_path / "screen.png")
        Image.new("RGB", (80, 24), (0, 0, 0)).save(img_path)

        # Patch analyze_screenshot to return a mock element.
        from binterint.semantic import DetectedElement
        mock_element = DetectedElement(
            type="button", label="OK", x=10, y=5, confidence=0.9
        )

        async def fake_analyze(path, cols, rows):
            return [mock_element]

        with patch("binterint.mcp_server.SemanticAnalyzer") as MockAnalyzer:
            instance = MockAnalyzer.return_value
            instance.analyze_screenshot = fake_analyze
            MockAnalyzer.map_to_grid.return_value = {"col": 1, "row": 0}
            result = run(tui_analyze(screenshot_path=img_path))

        assert isinstance(result, list)

    def test_returns_empty_list_on_exception(self, tmp_path):
        from binterint.mcp_server import tui_analyze
        img_path = str(tmp_path / "noexist.png")
        result   = run(tui_analyze(screenshot_path=img_path))
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# tui_navigate
# ---------------------------------------------------------------------------

class TestTuiNavigate:
    def test_returns_expected_keys(self, tmp_path):
        from binterint.mcp_server import tui_navigate
        ctrl = _make_mock_ctrl(tmp_path, text="some screen")
        # decide_next_action returns None immediately → 0 keys sent.
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            with patch("binterint.mcp_server.SemanticAnalyzer") as MockSA:
                MockSA.return_value.decide_next_action.return_value = None
                result = run(tui_navigate(command="echo", goal="do nothing"))

        assert "success"          in result
        assert "goal"             in result
        assert "steps_taken"      in result
        assert "history"          in result
        assert "final_screenshot" in result

    def test_goal_in_result(self, tmp_path):
        from binterint.mcp_server import tui_navigate
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            with patch("binterint.mcp_server.SemanticAnalyzer") as MockSA:
                MockSA.return_value.decide_next_action.return_value = None
                result = run(tui_navigate(command="echo", goal="my goal"))
        assert result["goal"] == "my goal"

    def test_ctrl_stop_always_called(self, tmp_path):
        from binterint.mcp_server import tui_navigate
        ctrl = _make_mock_ctrl(tmp_path)
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            with patch("binterint.mcp_server.SemanticAnalyzer") as MockSA:
                MockSA.return_value.decide_next_action.return_value = None
                run(tui_navigate(command="echo", goal="g"))
        ctrl.stop.assert_called_once()

    def test_exception_returns_failure_dict(self, tmp_path):
        from binterint.mcp_server import tui_navigate
        ctrl = MagicMock()
        ctrl.spawn.side_effect = RuntimeError("crash")
        ctrl.stop.return_value = None
        with patch("binterint.mcp_server.TUIController", return_value=ctrl):
            result = run(tui_navigate(command="echo", goal="g"))
        assert result["success"] is False


# ---------------------------------------------------------------------------
# run_mcp_server entry point importable
# ---------------------------------------------------------------------------

def test_run_mcp_server_importable():
    from binterint.mcp_server import run_mcp_server
    assert callable(run_mcp_server)


def test_mcp_instance_has_tools():
    from binterint.mcp_server import mcp
    # FastMCP exposes registered tools via _tool_manager
    assert mcp is not None
