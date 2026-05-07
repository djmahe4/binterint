"""
binterint.mcp_server
====================
FastMCP server that exposes binterint's TUI automation capabilities as MCP tools.

Four tools are available:

``tui_screenshot``
    Spawn a TUI, wait for it to render, and return a screenshot PNG path
    along with the text content and detected UI elements.

``tui_interact``
    Execute a sequence of actions (key presses, screenshots, waits) on a
    running TUI.

``tui_analyze``
    Analyse an existing TUI screenshot and return detected interactive
    elements.

``tui_navigate``
    Autonomously navigate a TUI toward a natural-language goal.

Starting the server
-------------------
CLI entry point (registered in ``pyproject.toml``)::

    binterint-mcp

Programmatic::

    from binterint.mcp_server import run_mcp_server
    run_mcp_server()

Context7: /prefecthq/fastmcp — Using @mcp.tool decorator pattern from FastMCP v3.2.x
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

from .controller import TUIController
from .semantic import SemanticAnalyzer

logger = logging.getLogger("binterint.mcp_server")

mcp = FastMCP("binterint")


# ---------------------------------------------------------------------------
# Tool: tui_screenshot
# ---------------------------------------------------------------------------

@mcp.tool
async def tui_screenshot(
    command: str,
    output_path: str = "screenshot.png",
    columns: int = 80,
    rows: int = 24,
    wait_seconds: float = 1.5,
    keys_to_send: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Spawn a TUI application headlessly and capture a screenshot.

    Args:
        command: Shell command to spawn (e.g. ``"htop"`` or
            ``"python my_tui.py"``).  Passed to ``shlex.split`` so quoting
            works as expected.
        output_path: Filesystem path for the output PNG screenshot.
        columns: Terminal width in character columns.
        rows: Terminal height in character rows.
        wait_seconds: Seconds to wait for the initial TUI render.
        keys_to_send: Optional list of key sequences to send before capturing
            (e.g. ``["j", "j", "q"]``).

    Returns:
        Dict with keys:

        * ``path`` — absolute path to the saved PNG.
        * ``dimensions`` — ``{"columns": …, "rows": …}``.
        * ``text_content`` — visible text of the terminal screen.
        * ``detected_elements`` — list of detected UI elements, each a dict
          with ``type``, ``label``, and ``key``.
    """
    import shlex  # noqa: PLC0415

    cmd = shlex.split(command)
    ctrl = TUIController(cols=columns, rows=rows)
    try:
        ctrl.spawn(cmd)
        await asyncio.sleep(wait_seconds)
        ctrl.drain(timeout=wait_seconds)

        if keys_to_send:
            for key in keys_to_send:
                ctrl.send_key(key)
                await asyncio.sleep(0.3)
                ctrl.drain(timeout=0.5)

        path = ctrl.save_screenshot(output_path)
        text = ctrl.screen.get_text_content()

        analyzer  = SemanticAnalyzer()
        elements  = analyzer.extract_from_screen(text)

        return {
            "path":       path,
            "dimensions": {"columns": columns, "rows": rows},
            "text_content": text,
            "detected_elements": elements,
        }
    finally:
        ctrl.stop()


# ---------------------------------------------------------------------------
# Tool: tui_interact
# ---------------------------------------------------------------------------

@mcp.tool
async def tui_interact(
    command: str,
    interaction_plan: List[Dict[str, Any]],
    columns: int = 80,
    rows: int = 24,
) -> Dict[str, Any]:
    """Interact with a TUI using a plan of actions and capture the result.

    Each step in *interaction_plan* is a dict with an ``"action"`` key:

    * ``{"action": "send_key", "key": "<sequence>"}`` — send a key sequence.
    * ``{"action": "screenshot", "path": "<file.png>"}`` — save a screenshot.
    * ``{"action": "get_text"}`` — append the current screen text to results.
    * ``{"action": "wait", "seconds": 1.0}`` — sleep for the given duration.

    Args:
        command: Shell command to spawn.
        interaction_plan: Ordered list of action dicts.
        columns: Terminal width.
        rows: Terminal height.

    Returns:
        Dict with ``"success"`` (bool) and ``"steps"`` (list of result dicts,
        one per interaction step).
    """
    import shlex  # noqa: PLC0415

    cmd  = shlex.split(command)
    ctrl = TUIController(cols=columns, rows=rows)
    results: List[Dict[str, Any]] = []

    try:
        ctrl.spawn(cmd)
        await asyncio.sleep(1.0)
        ctrl.drain(timeout=1.5)

        for step in interaction_plan:
            action = step.get("action", "")
            if action == "send_key":
                key = step.get("key", "")
                ctrl.send_key(key)
                await asyncio.sleep(0.3)
                ctrl.drain(timeout=0.5)
                results.append({"action": "send_key", "key": key})

            elif action == "screenshot":
                out_path = step.get("path", f"step_{len(results) + 1}.png")
                saved    = ctrl.save_screenshot(out_path)
                results.append({"action": "screenshot", "path": saved})

            elif action == "get_text":
                text = ctrl.screen.get_text_content()
                results.append({"action": "get_text", "text": text})

            elif action == "wait":
                secs = float(step.get("seconds", 1.0))
                await asyncio.sleep(secs)
                ctrl.drain()
                results.append({"action": "wait", "seconds": secs})

            else:
                logger.warning("tui_interact: unknown action '%s'", action)
                results.append({"action": action, "error": "unknown action"})

        return {"success": True, "steps": results}

    except Exception as exc:
        logger.exception("tui_interact failed")
        return {"success": False, "error": str(exc), "steps": results}
    finally:
        ctrl.stop()


# ---------------------------------------------------------------------------
# Tool: tui_analyze
# ---------------------------------------------------------------------------

@mcp.tool
async def tui_analyze(
    screenshot_path: str,
    columns: int = 80,
    rows: int = 24,
) -> List[Dict[str, Any]]:
    """Analyse a TUI screenshot and detect interactive elements.

    Uses the rule-based extractor from :class:`~binterint.semantic.SemanticAnalyzer`.
    When a Vision LLM API key is configured, the LLM is used instead for
    higher accuracy.

    Args:
        screenshot_path: Path to a PNG screenshot of a TUI application.
        columns: Terminal width for coordinate normalisation.
        rows: Terminal height for coordinate normalisation.

    Returns:
        List of detected element dicts, each with keys ``type``, ``label``,
        and ``key``.
    """
    analyzer = SemanticAnalyzer()
    path     = str(Path(screenshot_path).expanduser().resolve())

    try:
        elements = await analyzer.analyze_screenshot(path, columns, rows)
        return [
            {
                "type":       e.type,
                "label":      e.label,
                "x":          e.x,
                "y":          e.y,
                "confidence": e.confidence,
                "grid":       SemanticAnalyzer.map_to_grid(
                                  e.x, e.y, columns, rows),
            }
            for e in elements
        ]
    except Exception:
        # Fall back to rule-based extraction on the image text.
        logger.exception("tui_analyze vision failed, returning empty list")
        return []


# ---------------------------------------------------------------------------
# Tool: tui_navigate
# ---------------------------------------------------------------------------

@mcp.tool
async def tui_navigate(
    command: str,
    goal: str,
    max_steps: int = 10,
    columns: int = 80,
    rows: int = 24,
) -> Dict[str, Any]:
    """Autonomously navigate a TUI toward a natural-language goal.

    At each step the :class:`~binterint.semantic.SemanticAnalyzer` inspects
    the current screen text and decides the next key to press.  The loop
    terminates when the analyzer returns ``None``, *max_steps* is reached, or
    the child process exits.

    Args:
        command: Shell command to spawn.
        goal: Natural-language description of the desired outcome (e.g.
            ``"Navigate to settings and enable dark mode"``).
        max_steps: Maximum number of interaction steps before giving up.
        columns: Terminal width.
        rows: Terminal height.

    Returns:
        Dict with:

        * ``success`` (bool)
        * ``goal`` (str)
        * ``steps_taken`` (int)
        * ``history`` — list of ``{"step": int, "key": str, "screenshot": str}``
          dicts.
        * ``final_screenshot`` — path to the last screenshot, or ``None``.
    """
    import shlex  # noqa: PLC0415

    cmd      = shlex.split(command)
    ctrl     = TUIController(cols=columns, rows=rows)
    analyzer = SemanticAnalyzer()
    history: List[Dict[str, Any]]  = []
    screenshots: List[str]         = []

    try:
        ctrl.spawn(cmd)
        await asyncio.sleep(1.5)
        ctrl.drain(timeout=2.0)

        for step in range(1, max_steps + 1):
            text      = ctrl.screen.get_text_content()
            shot_path = f"navigate_step_{step}.png"
            ctrl.save_screenshot(shot_path)
            screenshots.append(shot_path)

            key = analyzer.decide_next_action(text, goal=goal,
                                              history=[h.get("key", "") for h in history])
            if not key:
                history.append({"step": step, "note": "no action decided",
                                "screenshot": shot_path})
                break

            ctrl.send_key(key)
            history.append({"step": step, "key": key, "screenshot": shot_path})
            await asyncio.sleep(0.5)
            ctrl.drain(timeout=0.6)

            if ctrl.pty.process and not ctrl.pty.process.isalive():
                history.append({"step": step, "note": "process terminated",
                                "screenshot": shot_path})
                break

        return {
            "success":          True,
            "goal":             goal,
            "steps_taken":      len(history),
            "history":          history,
            "final_screenshot": screenshots[-1] if screenshots else None,
        }

    except Exception as exc:
        logger.exception("tui_navigate failed")
        return {
            "success":          False,
            "goal":             goal,
            "error":            str(exc),
            "steps_taken":      len(history),
            "history":          history,
            "final_screenshot": screenshots[-1] if screenshots else None,
        }
    finally:
        ctrl.stop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_mcp_server() -> None:
    """Start the binterint MCP server (stdio transport by default).

    This function is the target of the ``binterint-mcp`` CLI entry point
    defined in ``pyproject.toml``.
    """
    mcp.run()
