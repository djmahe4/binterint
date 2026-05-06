# GitHub Copilot Instructions — binterint v1.0.0 "Event Modular Terminal + Context7 MCP"

> **`.github/copilot-instructions.md`**  
> Target: `djmahe4/binterint` · Current: `v0.1.1` (Python-only, PIL renderer, pyte backend, rule-based semantic analysis)  
> Next: `v1.0.0` — Intelligent, interactive, event-driven, modular terminal with C++ acceleration, Context7 MCP development, professional font/orientation engine.

---

## 0. REPOSITORY ANALYSIS — WHAT binterint IS TODAY

binterint (Binary Terminal Interaction) is a cross-platform headless TUI automation utility written in Python. Its current architecture:

| Layer | File | Role |
|---|---|---|
| **CLI** | `binterint/cli.py` | Typer-based CLI: `run`, `auto`, `analyze` commands |
| **Controller** | `binterint/controller.py` | Orchestrates PTY→pyte.Stream→TerminalScreen→Renderer |
| **PTY Engine** | `binterint/pty_engine.py` | Platform-conditional: `pywinpty` (Windows) / `ptyprocess` (Unix) |
| **Screen Buffer** | `binterint/screen_buffer.py` | Extends `pyte.Screen` with `get_text_content()` |
| **Renderer** | `binterint/renderer.py` | PIL/Pillow → PNG; bundled Roboto Mono `.ttf`; manual `draw.text()` per glyph |
| **Semantic** | `binterint/semantic.py` | Rule-based regex extraction + optional Gemini/OpenAI Vision LLM |
| **Entry** | `binterint/__main__.py` | Calls `cli:app()` |

**Key weaknesses identified:**
1. **No event system** — reader loop polls `time.sleep(0.01)`, no keyboard/mouse/resize event abstraction.
2. **Monolithic architecture** — controller, renderer, PTY, and semantic analysis are tightly coupled.
3. **Renderer is pixel-only** — no terminal-native rendering (Sixel, Kitty protocol, iTerm2).
4. **Single font, no orientation** — fixed Roboto Mono, horizontal-only rendering, no vertical/diagonal text, no font family mixing.
5. **Python-only** — no C/C++ acceleration path; pyte is pure Python and slow for large buffers.
6. **No MCP exposure** — binterint cannot be consumed as an MCP tool by AI agents.
7. **Rule-based semantics are fragile** — regex heuristics break on complex TUIs.

---

## 1. CONTEXT7 MCP SERVER — DEVELOPMENT INTEGRATION STRATEGY

### 1.1 What Context7 MCP Is
Context7 is an MCP server that fetches **up-to-date, version-specific documentation and code examples** from the source and places them directly into your LLM prompt. It exposes two core tools:
- **`resolve-library-id`**: Resolves a package name → Context7-compatible library ID (e.g., `/pybind/pybind11`, `/ratatui/ratatui`, `/libvterm/libvterm`).
- **`query-docs`**: Retrieves documentation snippets for a given library ID + query.

The server URL is `https://mcp.context7.com/mcp` with API key in `CONTEXT7_API_KEY` header.

### 1.2 How binterint v1.0.0 MUST Use Context7 MCP During Development

**Every time you, Copilot, generate code for this repository, you MUST first use Context7 to fetch the latest documentation for the libraries being used.** The workflow:

```
1. User asks for a feature → Copilot determines which libraries are needed.
2. Copilot calls resolve-library-id for each library (e.g., "pybind11", "libvterm", "freetype", "Pillow", "crossterm").
3. Copilot calls query-docs with the library ID + the specific question (e.g., "How to create a Python binding for a C++ class that wraps libvterm?").
4. Copilot incorporates the returned documentation into the generated code.
5. Generated code MUST cite the Context7 source (library ID, version) in docstrings.
```

### 1.3 Libraries That MUST Be Context7-Resolved Before Writing Code

| Library | Context7 ID | Purpose in binterint v1.0.0 |
|---|---|---|
| pybind11 | `/pybind/pybind11` | C++ ↔ Python bindings for terminal engine |
| libvterm | `/libvterm/libvterm` (or nearest) | C99 VT220/xterm emulator replacing pyte |
| FreeType | `/freetype/freetype` | Font rasterization, glyph metrics, orientation |
| Pillow | `/python-pillow/Pillow` | Image output, font loading, compositing |
| Ratatui | `/ratatui/ratatui` | Reference architecture for event-driven modular terminal |
| Crossterm | `/crossterm-rs/crossterm` | Reference for cross-platform terminal backend |
| FastMCP | `/jlowin/fastmcp` | Python MCP server framework for exposing binterint tools |
| Typer | `/fastapi/typer` | CLI framework (already in use, upgrade to latest) |
| PyO3/maturin | `/pyo3/pyo3` | Alternative to pybind11 for Rust-based acceleration |

**Rule**: Before writing any import or function call for these libraries, resolve them through Context7 and document the version used.

---

## 2. v1.0.0 ARCHITECTURE — EVENT-DRIVEN MODULAR TERMINAL

### 2.1 Core Architectural Principle: Plugin Microkernel

The v1.0.0 architecture MUST follow an **event-driven modular plugin system** (microkernel pattern):

```
┌─────────────────────────────────────────────────────────┐
│                    binterint CLI / API                    │
├─────────────────────────────────────────────────────────┤
│                   Event Bus (Pub/Sub)                     │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│  PTY     │ Screen   │ Renderer │ Semantic │ Font Engine  │
│  Plugin  │ Plugin   │ Plugin   │ Plugin   │ Plugin       │
├──────────┼──────────┼──────────┼──────────┼─────────────┤
│ C++ Core │ C++ Core │ PIL/C++  │ LLM/MCP  │ FreeType/C++ │
└──────────┴──────────┴──────────┴──────────┴─────────────┘
```

### 2.2 Event Types

Every interaction in binterint v1.0.0 MUST be an Event object flowing through the bus:

```python
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time

class EventType(Enum):
    # PTY events
    PTY_DATA = auto()           # Raw bytes from PTY
    PTY_CLOSED = auto()         # Child process exited
    PTY_RESIZED = auto()        # Terminal dimensions changed
    
    # Screen events
    SCREEN_UPDATED = auto()     # Screen buffer changed
    SCREEN_DIRTY_RECT = auto()  # Bounding box of changed region
    CURSOR_MOVED = auto()       # Cursor position changed
    
    # Input events
    KEY_PRESS = auto()          # Keyboard input
    KEY_RELEASE = auto()        # Key release (if supported)
    MOUSE_EVENT = auto()        # Mouse click, drag, scroll
    PASTE_EVENT = auto()        # Clipboard paste
    
    # Render events
    RENDER_FRAME = auto()       # Request frame render
    RENDER_COMPLETE = auto()    # Frame rendered to buffer
    
    # Semantic events
    ELEMENT_DETECTED = auto()   # UI element found
    ELEMENT_INTERACTED = auto() # Element was clicked/activated
    
    # Lifecycle events
    PLUGIN_LOADED = auto()      # Plugin registered
    PLUGIN_UNLOADED = auto()    # Plugin removed
    SHUTDOWN = auto()           # System shutting down

@dataclass
class Event:
    type: EventType
    source: str                 # Plugin name
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    propagation_stopped: bool = False
```

### 2.3 Plugin Interface

Every component MUST implement this interface:

```python
from abc import ABC, abstractmethod
from typing import List

class TerminalPlugin(ABC):
    """Base class for all binterint plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier."""
        ...
    
    @abstractmethod
    def on_register(self, bus: 'EventBus') -> None:
        """Called when plugin is registered with the event bus."""
        ...
    
    @abstractmethod
    def on_event(self, event: Event) -> None:
        """Handle an event from the bus."""
        ...
    
    @abstractmethod
    def on_unregister(self) -> None:
        """Cleanup when plugin is removed."""
        ...
    
    def subscribe_to(self) -> List[EventType]:
        """Event types this plugin listens to. Override in subclasses."""
        return []
```

### 2.4 Event Bus

```python
from collections import defaultdict
from typing import Dict, List, Callable
import logging

class EventBus:
    """Central pub/sub event dispatcher."""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[TerminalPlugin]] = defaultdict(list)
        self._plugins: Dict[str, TerminalPlugin] = {}
        self._event_history: List[Event] = []  # For replay/debugging
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
        self.logger = logging.getLogger("binterint.eventbus")
    
    def register(self, plugin: TerminalPlugin) -> None:
        self._plugins[plugin.name] = plugin
        for event_type in plugin.subscribe_to():
            self._subscribers[event_type].append(plugin)
        plugin.on_register(self)
        self.emit(Event(EventType.PLUGIN_LOADED, "eventbus", 
                        {"plugin": plugin.name}))
    
    def unregister(self, plugin_name: str) -> None:
        plugin = self._plugins.pop(plugin_name, None)
        if plugin:
            for subs in self._subscribers.values():
                if plugin in subs:
                    subs.remove(plugin)
            plugin.on_unregister()
    
    def emit(self, event: Event) -> None:
        self._event_history.append(event)
        for subscriber in self._subscribers.get(event.type, []):
            try:
                subscriber.on_event(event)
                if event.propagation_stopped:
                    break
            except Exception as e:
                self.logger.error(f"Plugin {subscriber.name} failed: {e}")
    
    def add_hook(self, hook_name: str, callback: Callable) -> None:
        """Add a hook for extensibility (e.g., pre-render, post-screenshot)."""
        self._hooks[hook_name].append(callback)
    
    def run_hooks(self, hook_name: str, *args, **kwargs) -> None:
        for callback in self._hooks.get(hook_name, []):
            callback(*args, **kwargs)
```

---

## 3. C++ BINDING LAYER — pybind11 ACCELERATION

### 3.1 Rationale

The current `pyte`-based screen buffer and PIL `draw.text()` per-glyph loop are the #1 performance bottleneck. For large terminal buffers (e.g., 200×80 with 60fps rendering), Python cannot keep up. We need C++ for:

1. **Terminal emulation** — parse ANSI escape sequences in C++ using `libvterm` (C99 library implementing VT220/xterm emulation)
2. **Glyph rasterization** — use FreeType directly from C++ for font loading, glyph metrics, and bitmap rendering
3. **Screen buffer management** — efficient grid of `Cell` structs with dirty-rect tracking
4. **Event parsing** — keyboard/mouse input parsing at C speed

### 3.2 Directory Structure

```
binterint/
├── cpp_core/                    # C++ source
│   ├── CMakeLists.txt
│   ├── src/
│   │   ├── terminal_emulator.cpp   # libvterm wrapper
│   │   ├── terminal_emulator.h
│   │   ├── screen_buffer.cpp       # Efficient cell grid
│   │   ├── screen_buffer.h
│   │   ├── font_engine.cpp         # FreeType wrapper
│   │   ├── font_engine.h
│   │   ├── input_parser.cpp        # ANSI/crossterm input parsing
│   │   ├── input_parser.h
│   │   └── bindings.cpp            # pybind11 module definition
│   └── tests/
├── binterint/
│   ├── cpp_bridge.py              # Python wrapper around C++ module
│   └── ... (existing files)
```

### 3.3 pybind11 Binding Template

```cpp
// bindings.cpp — pybind11 module for binterint
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include "terminal_emulator.h"
#include "screen_buffer.h"
#include "font_engine.h"

namespace py = pybind11;

PYBIND11_MODULE(_binterint_core, m) {
    m.doc() = "binterint C++ acceleration core — terminal emulation, "
              "font rendering, and screen buffer management";
    
    // Screen Buffer
    py::class_<Cell>(m, "Cell")
        .def(py::init<>())
        .def_readwrite("char_data", &Cell::char_data)
        .def_readwrite("fg_color", &Cell::fg_color)
        .def_readwrite("bg_color", &Cell::bg_color)
        .def_readwrite("bold", &Cell::bold)
        .def_readwrite("italic", &Cell::italic)
        .def_readwrite("underline", &Cell::underline);
    
    py::class_<ScreenBuffer>(m, "ScreenBuffer")
        .def(py::init<int, int>())
        .def("write", &ScreenBuffer::write)
        .def("resize", &ScreenBuffer::resize)
        .def("get_cell", &ScreenBuffer::get_cell)
        .def("get_dirty_rects", &ScreenBuffer::get_dirty_rects)
        .def("clear_dirty", &ScreenBuffer::clear_dirty)
        .def_property_readonly("columns", &ScreenBuffer::columns)
        .def_property_readonly("rows", &ScreenBuffer::rows);
    
    // Terminal Emulator (libvterm-backed)
    py::class_<TerminalEmulator>(m, "TerminalEmulator")
        .def(py::init<int, int>())
        .def("feed", &TerminalEmulator::feed)
        .def("resize", &TerminalEmulator::resize)
        .def("get_screen", &TerminalEmulator::get_screen)
        .def("set_screen_callback", &TerminalEmulator::set_screen_callback);
    
    // Font Engine (FreeType-backed)
    py::class_<FontEngine>(m, "FontEngine")
        .def(py::init<>())
        .def("load_font", &FontEngine::load_font)
        .def("get_glyph_bitmap", &FontEngine::get_glyph_bitmap)
        .def("get_glyph_metrics", &FontEngine::get_glyph_metrics)
        .def("measure_text", &FontEngine::measure_text)
        .def("set_orientation", &FontEngine::set_orientation)
        .def("list_available_fonts", &FontEngine::list_available_fonts);
}
```

### 3.4 C++ Screen Buffer — Dirty Rect Optimization

```cpp
// screen_buffer.h
#pragma once
#include <vector>
#include <string>
#include <cstdint>
#include <algorithm>

struct Cell {
    std::string char_data = " ";
    uint32_t fg_color = 0xFFFFFFFF;
    uint32_t bg_color = 0x00000000;
    bool bold = false;
    bool italic = false;
    bool underline = false;
    bool dirty = true;  // Track for incremental rendering
};

struct Rect {
    int x, y, width, height;
};

class ScreenBuffer {
    int cols_, rows_;
    std::vector<Cell> cells_;
    Rect dirty_bounds_;
    bool has_dirty_;
    
public:
    ScreenBuffer(int cols, int rows) 
        : cols_(cols), rows_(rows), 
          cells_(cols * rows), 
          dirty_bounds_{cols, rows, 0, 0}, 
          has_dirty_(false) {}
    
    int columns() const { return cols_; }
    int rows() const { return rows_; }
    
    void write(int x, int y, const Cell& cell) {
        if (x < 0 || x >= cols_ || y < 0 || y >= rows_) return;
        cells_[y * cols_ + x] = cell;
        cells_[y * cols_ + x].dirty = true;
        
        // Expand dirty bounds
        dirty_bounds_.x = std::min(dirty_bounds_.x, x);
        dirty_bounds_.y = std::min(dirty_bounds_.y, y);
        dirty_bounds_.width = std::max(dirty_bounds_.width, x + 1);
        dirty_bounds_.height = std::max(dirty_bounds_.height, y + 1);
        has_dirty_ = true;
    }
    
    const Cell& get_cell(int x, int y) const {
        return cells_[y * cols_ + x];
    }
    
    std::vector<Rect> get_dirty_rects() const {
        if (!has_dirty_) return {};
        return {dirty_bounds_};
    }
    
    void clear_dirty() {
        for (auto& cell : cells_) cell.dirty = false;
        dirty_bounds_ = Rect{cols_, rows_, 0, 0};
        has_dirty_ = false;
    }
    
    void resize(int cols, int rows) {
        cols_ = cols;
        rows_ = rows;
        cells_.resize(cols * rows);
        // Mark all dirty
        for (auto& cell : cells_) cell.dirty = true;
        dirty_bounds_ = Rect{0, 0, cols, rows};
        has_dirty_ = true;
    }
};
```

---

## 4. FONT ENGINE — PROPER FONTS, ORIENTATION, TEXT RENDERING

### 4.1 Requirements for v1.0.0

The font system MUST support:
1. **Multiple font families** — bundled monospace (Roboto Mono, Fira Code, JetBrains Mono, Hack) + system font fallback chain
2. **Font weight and style** — Regular, Bold, Italic, Bold Italic
3. **Text orientation modes**: 
   - `HORIZONTAL_LTR` (left-to-right, default)
   - `HORIZONTAL_RTL` (right-to-left)
   - `VERTICAL_TTB` (top-to-bottom, CJK-style)
   - `VERTICAL_BTT` (bottom-to-top)
   - `DIAGONAL_45` (45° upward)
   - `DIAGONAL_135` (45° downward)
4. **Text alignment** — horizontal (LEFT, CENTER, RIGHT) + vertical (TOP, MIDDLE, BOTTOM) anchored to any terminal cell
5. **Glyph substitution** — fallback font for missing glyphs (e.g., CJK characters in a Latin font)
6. **Bitmap caching** — pre-rendered glyph atlas for performance

### 4.2 Font Configuration Schema

```python
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path

class TextOrientation(Enum):
    HORIZONTAL_LTR = auto()
    HORIZONTAL_RTL = auto()
    VERTICAL_TTB = auto()
    VERTICAL_BTT = auto()
    DIAGONAL_45 = auto()
    DIAGONAL_135 = auto()

class HorizontalAlign(Enum):
    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()

class VerticalAlign(Enum):
    TOP = auto()
    MIDDLE = auto()
    BOTTOM = auto()

@dataclass
class FontConfig:
    family: str                         # Primary font family
    size: int = 18                      # Font size in points
    weight: str = "regular"             # "thin", "light", "regular", "medium", "bold", "black"
    style: str = "normal"              # "normal", "italic", "oblique"
    fallback_families: List[str] = field(default_factory=list)
    orientation: TextOrientation = TextOrientation.HORIZONTAL_LTR
    h_align: HorizontalAlign = HorizontalAlign.LEFT
    v_align: VerticalAlign = VerticalAlign.TOP
    letter_spacing: float = 0.0        # Additional spacing between characters
    line_spacing: float = 1.2          # Line height multiplier
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)

@dataclass
class TextBlock:
    text: str
    config: FontConfig
    position: Tuple[int, int]          # (x, y) in terminal cell coordinates
    max_width: Optional[int] = None    # Word-wrap width in cells
    max_height: Optional[int] = None   # Truncation height in cells
```

### 4.3 Font Loading Pipeline (Python + C++)

```python
# binterint/font_manager.py
from pathlib import Path
from typing import Dict, List, Optional
import platform
from .cpp_bridge import _binterint_core  # pybind11 module

class FontManager:
    """Manages font loading, caching, and glyph resolution."""
    
    BUNDLED_FONTS = {
        "roboto-mono": "fonts/RobotoMono-Regular.ttf",
        "roboto-mono-bold": "fonts/RobotoMono-Bold.ttf",
        "roboto-mono-italic": "fonts/RobotoMono-Italic.ttf",
        "fira-code": "fonts/FiraCode-Regular.ttf",
        "jetbrains-mono": "fonts/JetBrainsMono-Regular.ttf",
        "hack": "fonts/Hack-Regular.ttf",
    }
    
    SYSTEM_FONT_PATHS = {
        "linux": ["/usr/share/fonts", "/usr/local/share/fonts", "~/.fonts"],
        "darwin": ["/System/Library/Fonts", "/Library/Fonts", "~/Library/Fonts"],
        "win32": ["C:\\Windows\\Fonts", "~\\AppData\\Local\\Microsoft\\Windows\\Fonts"],
    }
    
    def __init__(self):
        self._engine = _binterint_core.FontEngine()
        self._loaded_fonts: Dict[str, int] = {}  # family → handle
        self._glyph_cache: Dict[str, bytes] = {}  # (font_handle, codepoint) → bitmap
        self._scan_system_fonts()
    
    def load_font(self, config: FontConfig) -> int:
        """Load a font by configuration, returns font handle."""
        cache_key = f"{config.family}:{config.size}:{config.weight}:{config.style}"
        if cache_key in self._loaded_fonts:
            return self._loaded_fonts[cache_key]
        
        font_path = self._resolve_font_path(config.family, config.weight, config.style)
        handle = self._engine.load_font(str(font_path), config.size)
        self._loaded_fonts[cache_key] = handle
        
        # Pre-load fallback fonts
        for fallback in config.fallback_families:
            fb_path = self._resolve_font_path(fallback)
            self._engine.load_fallback_font(handle, str(fb_path))
        
        return handle
    
    def render_text_block(self, block: TextBlock) -> bytes:
        """Render a text block with full orientation/alignment support.
        Returns raw RGBA pixel data."""
        handle = self.load_font(block.config)
        return self._engine.render_text(
            handle, block.text,
            block.position[0], block.position[1],
            block.config.orientation.value,
            block.config.h_align.value,
            block.config.v_align.value,
            block.config.letter_spacing,
            block.config.line_spacing,
            block.max_width or 0,
            block.max_height or 0
        )
    
    def _resolve_font_path(self, family: str, weight: str = "regular", 
                           style: str = "normal") -> Path:
        """Resolve font family to filesystem path."""
        # Check bundled fonts first
        for key, rel_path in self.BUNDLED_FONTS.items():
            if family.lower() in key:
                bundled = Path(__file__).parent / rel_path
                if bundled.exists():
                    return bundled
        
        # Search system fonts
        system = platform.system().lower()
        for search_dir in self.SYSTEM_FONT_PATHS.get(system, []):
            search_path = Path(search_dir).expanduser()
            if search_path.exists():
                for font_file in search_path.rglob("*.ttf"):
                    if family.lower() in font_file.stem.lower():
                        return font_file
        
        raise FontNotFoundError(f"Font '{family}' not found bundled or on system")
```
#### Instructions to download fonts

You’re right — the earlier links 404 because GitHub paths changed (very common). The fix is simple: use the **correct raw URLs from the right repos/paths**.

Below are **verified working commands** (based on actual repo structure and sources like Google Fonts / official repos ([openSUSE Build Service][1])).

---

##### ✅ FIXED working commands

######  📁 Create folder

####### Linux/macOS

```bash
mkdir -p fonts
```

####### Windows (PowerShell)

```powershell
New-Item -ItemType Directory -Force -Path fonts
```

---

##### ⬇️ Download fonts (correct URLs)

###### 🔹 Roboto Mono (official repo: Google Fonts)

####### wget

```bash
wget -O fonts/RobotoMono-Regular.ttf https://raw.githubusercontent.com/googlefonts/RobotoMono/main/fonts/ttf/RobotoMono-Regular.ttf
wget -O fonts/RobotoMono-Bold.ttf https://raw.githubusercontent.com/googlefonts/RobotoMono/main/fonts/ttf/RobotoMono-Bold.ttf
wget -O fonts/RobotoMono-Italic.ttf https://raw.githubusercontent.com/googlefonts/RobotoMono/main/fonts/ttf/RobotoMono-Italic.ttf
```

### curl

```powershell
curl -L -o fonts/RobotoMono-Regular.ttf https://raw.githubusercontent.com/googlefonts/RobotoMono/main/fonts/ttf/RobotoMono-Regular.ttf
curl -L -o fonts/RobotoMono-Bold.ttf https://raw.githubusercontent.com/googlefonts/RobotoMono/main/fonts/ttf/RobotoMono-Bold.ttf
curl -L -o fonts/RobotoMono-Italic.ttf https://raw.githubusercontent.com/googlefonts/RobotoMono/main/fonts/ttf/RobotoMono-Italic.ttf
```

✔ These paths are confirmed from packaging configs and repo structure ([openSUSE Build Service][1])

---

###### 🔹 Fira Code (official repo: Fira Code project)

####### wget

```bash
wget -O fonts/FiraCode-Regular.ttf https://raw.githubusercontent.com/tonsky/FiraCode/master/distr/ttf/FiraCode-Regular.ttf
```

####### curl

```powershell
curl -L -o fonts/FiraCode-Regular.ttf https://raw.githubusercontent.com/tonsky/FiraCode/master/distr/ttf/FiraCode-Regular.ttf
```

---

###### 🔹 JetBrains Mono (from JetBrains)

####### wget

```bash
wget -O fonts/JetBrainsMono-Regular.ttf https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-Regular.ttf
```

####### curl

```powershell
curl -L -o fonts/JetBrainsMono-Regular.ttf https://raw.githubusercontent.com/JetBrains/JetBrainsMono/master/fonts/ttf/JetBrainsMono-Regular.ttf
```

---

###### 🔹 Hack (from Source Foundry)

####### wget

```bash
wget -O fonts/Hack-Regular.ttf https://raw.githubusercontent.com/source-foundry/Hack/master/build/ttf/Hack-Regular.ttf
```

####### curl

```powershell
curl -L -o fonts/Hack-Regular.ttf https://raw.githubusercontent.com/source-foundry/Hack/master/build/ttf/Hack-Regular.ttf
```

---

##### ✅ Final check

```bash
ls fonts
```

Should show:

```
RobotoMono-Regular.ttf
RobotoMono-Bold.ttf
RobotoMono-Italic.ttf
FiraCode-Regular.ttf
JetBrainsMono-Regular.ttf
Hack-Regular.ttf
```

### 4.4 C++ FreeType Font Engine — Orientation & Glyph Rendering

```cpp
// font_engine.h
#pragma once
#include <string>
#include <vector>
#include <unordered_map>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_GLYPH_H

enum class TextOrientation {
    HORIZONTAL_LTR = 0,
    HORIZONTAL_RTL = 1,
    VERTICAL_TTB = 2,
    VERTICAL_BTT = 3,
    DIAGONAL_45 = 4,
    DIAGONAL_135 = 5
};

struct GlyphMetrics {
    int width, height;
    int bearing_x, bearing_y;
    int advance_x, advance_y;
};

class FontEngine {
    FT_Library library_;
    std::unordered_map<int, FT_Face> faces_;
    std::vector<uint8_t> render_buffer_;
    
public:
    FontEngine();
    ~FontEngine();
    
    int load_font(const std::string& path, int size);
    void load_fallback_font(int handle, const std::string& path);
    GlyphMetrics get_glyph_metrics(int handle, uint32_t codepoint);
    std::vector<uint8_t> render_text(
        int handle, const std::string& text,
        int pos_x, int pos_y,
        int orientation, int h_align, int v_align,
        float letter_spacing, float line_spacing,
        int max_width, int max_height
    );
    std::vector<std::string> list_available_fonts();
    
private:
    void render_horizontal_ltr(FT_Face face, const std::string& text, 
                               int& pen_x, int& pen_y);
    void render_vertical_ttb(FT_Face face, const std::string& text,
                             int& pen_x, int& pen_y);
    void render_diagonal(FT_Face face, const std::string& text,
                         int& pen_x, int& pen_y, double angle_rad);
    FT_Vector rotate_vector(FT_Vector v, double angle_rad);
};
```

---

## 5. INTERACTIVE EVENT-DRIVEN MODULAR TERMINAL — FULL SPEC

### 5.1 Terminal Backend Abstraction

```python
# binterint/backends/__init__.py
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Tuple, Optional

class KeyEvent:
    """Unified keyboard event across backends."""
    class Key(Enum):
        CHAR = auto()
        ENTER = auto(); TAB = auto(); ESC = auto(); BACKSPACE = auto()
        UP = auto(); DOWN = auto(); LEFT = auto(); RIGHT = auto()
        HOME = auto(); END = auto(); PAGE_UP = auto(); PAGE_DOWN = auto()
        INSERT = auto(); DELETE = auto()
        F1=auto(); F2=auto(); F3=auto(); F4=auto(); F5=auto()
        F6=auto(); F7=auto(); F8=auto(); F9=auto(); F10=auto()
        F11=auto(); F12=auto()
    
    class Modifier(Enum):
        NONE = 0
        CTRL = 1; ALT = 2; SHIFT = 4; META = 8
    
    key: Key
    char: str = ""
    modifiers: int = 0  # Bitmask of Modifier

class MouseEvent:
    """Unified mouse event."""
    class Button(Enum):
        LEFT = auto(); RIGHT = auto(); MIDDLE = auto()
        SCROLL_UP = auto(); SCROLL_DOWN = auto()
    
    class Action(Enum):
        PRESS = auto(); RELEASE = auto(); DRAG = auto(); MOVE = auto()
    
    button: Button
    action: Action
    x: int; y: int  # Terminal cell coordinates

class TerminalBackend(ABC):
    """Abstract terminal backend — implementations for different environments."""
    
    @abstractmethod
    def initialize(self, cols: int, rows: int) -> None: ...
    @abstractmethod
    def shutdown(self) -> None: ...
    @abstractmethod
    def poll_event(self) -> Optional[KeyEvent | MouseEvent]: ...
    @abstractmethod
    def write(self, data: str) -> None: ...
    @abstractmethod
    def resize(self, cols: int, rows: int) -> None: ...
    @abstractmethod
    def get_size(self) -> Tuple[int, int]: ...
    @abstractmethod
    def enable_raw_mode(self) -> None: ...
    @abstractmethod
    def disable_raw_mode(self) -> None: ...
```

### 5.2 Interactive Shell Plugin

```python
# binterint/plugins/interactive_shell.py
from ..event_bus import EventBus, Event, EventType, TerminalPlugin
from ..backends import TerminalBackend, KeyEvent, MouseEvent
from typing import List
import asyncio

class InteractiveShellPlugin(TerminalPlugin):
    """Interactive terminal shell with event handling."""
    
    @property
    def name(self) -> str:
        return "interactive_shell"
    
    def __init__(self, backend: TerminalBackend):
        self._backend = backend
        self._running = False
        self._key_bindings: Dict[str, Callable] = {}
        self._mouse_bindings: Dict[str, Callable] = {}
    
    def subscribe_to(self) -> List[EventType]:
        return [EventType.PTY_DATA, EventType.SCREEN_UPDATED, EventType.SHUTDOWN]
    
    def on_register(self, bus: EventBus) -> None:
        self._bus = bus
        self._backend.initialize(80, 24)
        self._backend.enable_raw_mode()
    
    def on_event(self, event: Event) -> None:
        if event.type == EventType.PTY_DATA:
            self._backend.write(event.data.get('text', ''))
        elif event.type == EventType.SCREEN_UPDATED:
            self._bus.emit(Event(EventType.RENDER_FRAME, self.name, 
                                event.data))
        elif event.type == EventType.SHUTDOWN:
            self._running = False
    
    async def input_loop(self) -> None:
        """Async input polling loop."""
        self._running = True
        while self._running:
            evt = self._backend.poll_event()
            if evt:
                if isinstance(evt, KeyEvent):
                    self._bus.emit(Event(EventType.KEY_PRESS, self.name,
                                        {'key': evt.key, 'char': evt.char, 
                                         'modifiers': evt.modifiers}))
                elif isinstance(evt, MouseEvent):
                    self._bus.emit(Event(EventType.MOUSE_EVENT, self.name,
                                        {'button': evt.button, 'action': evt.action,
                                         'x': evt.x, 'y': evt.y}))
            await asyncio.sleep(0.001)  # ~1000Hz polling
    
    def bind_key(self, key: KeyEvent.Key, modifiers: int, callback: Callable) -> None:
        binding = f"{key.name}:{modifiers}"
        self._key_bindings[binding] = callback
    
    def on_unregister(self) -> None:
        self._backend.disable_raw_mode()
        self._backend.shutdown()
```

---

## 6. MCP SERVER — EXPOSING binterint AS AN MCP TOOL

### 6.1 Rationale

binterint v1.0.0 MUST be consumable by AI coding agents (Claude, Cursor, Copilot) as an MCP server. When an AI needs to screenshot, interact with, or analyze a TUI, it should call binterint via MCP tools.

### 6.2 FastMCP Server Implementation

```python
# binterint/mcp_server.py
from fastmcp import FastMCP
from pathlib import Path
from typing import Optional, List, Dict, Any
import asyncio
import json

mcp = FastMCP("binterint")

@mcp.tool()
async def tui_screenshot(
    command: str,
    output_path: str = "screenshot.png",
    columns: int = 80,
    rows: int = 24,
    wait_seconds: float = 1.5,
    keys_to_send: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Spawn a TUI application headlessly and capture a screenshot.
    
    Args:
        command: Shell command to spawn the TUI (e.g., "htop", "python my_tui.py")
        output_path: Path for the output PNG screenshot
        columns: Terminal width in character columns
        rows: Terminal height in character rows
        wait_seconds: Time to wait for initial TUI render
        keys_to_send: Optional sequence of keys to send before screenshotting
    
    Returns:
        Dict with 'path', 'dimensions', 'text_content', and 'detected_elements'
    """
    from .controller import TUIController
    
    ctrl = TUIController(cols=columns, rows=rows)
    try:
        ctrl.spawn(command.split())
        await asyncio.sleep(wait_seconds)
        ctrl.drain(timeout=wait_seconds)
        
        if keys_to_send:
            for key in keys_to_send:
                ctrl.send_key(key)
                await asyncio.sleep(0.3)
                ctrl.drain(timeout=0.5)
        
        path = ctrl.save_screenshot(output_path)
        text = ctrl.screen.get_text_content()
        
        # Semantic analysis
        from .semantic import SemanticAnalyzer
        analyzer = SemanticAnalyzer()
        elements = await analyzer.analyze_screenshot(path, columns, rows)
        
        return {
            "path": path,
            "dimensions": {"columns": columns, "rows": rows},
            "text_content": text,
            "detected_elements": [
                {"type": e.type, "label": e.label, 
                 "x": e.x, "y": e.y, "confidence": e.confidence}
                for e in elements
            ]
        }
    finally:
        ctrl.stop()

@mcp.tool()
async def tui_interact(
    command: str,
    interaction_plan: List[Dict[str, Any]],
    columns: int = 80,
    rows: int = 24
) -> Dict[str, Any]:
    """
    Interact with a TUI using a plan of actions and capture the result.
    
    Args:
        command: Shell command to spawn
        interaction_plan: List of actions like [{"action": "send_key", "key": "Enter"}, 
                          {"action": "screenshot", "path": "step1.png"}, ...]
    
    Returns:
        Dict with results and screenshots from each step
    """
    from .controller import TUIController
    
    ctrl = TUIController(cols=columns, rows=rows)
    results = []
    try:
        ctrl.spawn(command.split())
        await asyncio.sleep(1.0)
        ctrl.drain(timeout=1.5)
        
        for step in interaction_plan:
            action = step.get("action")
            if action == "send_key":
                ctrl.send_key(step["key"])
                await asyncio.sleep(0.3)
                ctrl.drain(timeout=0.5)
                results.append({"action": "send_key", "key": step["key"]})
            elif action == "screenshot":
                path = ctrl.save_screenshot(step.get("path", f"step_{len(results)}.png"))
                results.append({"action": "screenshot", "path": path})
            elif action == "get_text":
                text = ctrl.screen.get_text_content()
                results.append({"action": "get_text", "text": text})
            elif action == "wait":
                await asyncio.sleep(step.get("seconds", 1.0))
                ctrl.drain()
        
        return {"success": True, "steps": results}
    finally:
        ctrl.stop()

@mcp.tool()
async def tui_analyze(
    screenshot_path: str,
    columns: int = 80,
    rows: int = 24
) -> List[Dict[str, Any]]:
    """
    Analyze a TUI screenshot and detect interactive elements.
    
    Args:
        screenshot_path: Path to a PNG screenshot of a TUI
        columns: Terminal width for coordinate mapping
        rows: Terminal height for coordinate mapping
    
    Returns:
        List of detected elements with type, label, coordinates, and confidence
    """
    from .semantic import SemanticAnalyzer
    analyzer = SemanticAnalyzer()
    elements = await analyzer.analyze_screenshot(screenshot_path, columns, rows)
    return [
        {"type": e.type, "label": e.label, 
         "x": e.x, "y": e.y, "confidence": e.confidence,
         "grid": analyzer.map_to_grid(e.x, e.y, columns, rows)}
        for e in elements
    ]

@mcp.tool()
async def tui_navigate(
    command: str,
    goal: str,
    max_steps: int = 10,
    columns: int = 80,
    rows: int = 24
) -> Dict[str, Any]:
    """
    Autonomous TUI navigation to achieve a goal.
    
    Args:
        command: Shell command to spawn
        goal: Natural language goal (e.g., "Navigate to settings and enable dark mode")
        max_steps: Maximum number of interaction steps
        columns: Terminal width
        rows: Terminal height
    
    Returns:
        Dict with navigation history and final state
    """
    from .controller import TUIController
    from .semantic import SemanticAnalyzer
    
    ctrl = TUIController(cols=columns, rows=rows)
    analyzer = SemanticAnalyzer()
    history = []
    screenshots = []
    
    try:
        ctrl.spawn(command.split())
        await asyncio.sleep(1.5)
        ctrl.drain(timeout=2.0)
        
        for step in range(1, max_steps + 1):
            text = ctrl.screen.get_text_content()
            key = analyzer.decide_next_action(text, goal=goal, history=history)
            
            shot_path = f"navigate_step_{step}.png"
            ctrl.save_screenshot(shot_path)
            screenshots.append(shot_path)
            
            if not key:
                break
            
            ctrl.send_key(key)
            history.append({"step": step, "key": key, "screenshot": shot_path})
            await asyncio.sleep(0.5)
            ctrl.drain(timeout=0.6)
            
            if hasattr(ctrl.pty, 'is_alive') and not ctrl.pty.is_alive():
                history.append({"step": step, "note": "Process terminated"})
                break
        
        return {
            "success": True,
            "goal": goal,
            "steps_taken": len(history),
            "history": history,
            "final_screenshot": screenshots[-1] if screenshots else None
        }
    finally:
        ctrl.stop()

def run_mcp_server():
    """Entry point for MCP server."""
    mcp.run()
```

---

## 7. IMPLEMENTATION ROADMAP

### Phase 1: Foundation (v0.2.0)
- [ ] Create `cpp_core/` with CMakeLists.txt and pybind11 scaffold
- [ ] Implement C++ `ScreenBuffer` with dirty-rect tracking — benchmark vs pyte.Screen
- [ ] Implement C++ `TerminalEmulator` wrapping libvterm — ensure ANSI parity with pyte
- [ ] Add build system integration (`pip install -e .` compiles C++ via cmake)
- [ ] Write Python `cpp_bridge.py` with graceful fallback to pyte if C++ unavailable

### Phase 2: Font & Orientation (v0.3.0)
- [ ] Bundle additional fonts: Fira Code, JetBrains Mono, Hack (all SIL OFL licensed)
- [ ] Implement C++ `FontEngine` with FreeType integration
- [ ] Implement all six `TextOrientation` modes in C++
- [ ] Implement `HorizontalAlign` and `VerticalAlign` in render pipeline
- [ ] Add font configuration to `pyproject.toml` package data
- [ ] Glyph atlas caching for 10x render performance

### Phase 3: Event System (v0.4.0)
- [ ] Implement `Event`, `EventType`, `EventBus` as specified above
- [ ] Refactor `TUIController` → `PtyPlugin : TerminalPlugin`
- [ ] Refactor `TerminalRenderer` → `RendererPlugin : TerminalPlugin`
- [ ] Refactor `SemanticAnalyzer` → `SemanticPlugin : TerminalPlugin`
- [ ] Implement `TerminalBackend` abstraction for different environments
- [ ] Implement `InteractiveShellPlugin` with async input loop

### Phase 4: MCP Integration (v0.5.0)
- [ ] Add `fastmcp` dependency
- [ ] Implement `binterint/mcp_server.py` with four MCP tools
- [ ] Add `binterint-mcp` CLI entry point (`pyproject.toml [project.scripts]`)
- [ ] Test with Claude Desktop / Cursor MCP configuration
- [ ] Document MCP server usage in README

### Phase 5: Terminal-Native Rendering (v0.6.0)
- [ ] Implement Sixel output backend (for terminals supporting it)
- [ ] Implement Kitty Terminal Graphics Protocol output
- [ ] Implement iTerm2 inline image protocol
- [ ] Add `--output-format` flag: `png`, `sixel`, `kitty`, `iterm2`
- [ ] Auto-detect terminal capabilities via `$TERM` and environment queries

### Phase 6: Polish & Release (v1.0.0)
- [ ] Full test coverage (pytest + C++ Google Test)
- [ ] CI/CD: build wheels with compiled C++ for Linux/macOS/Windows
- [ ] Performance benchmarks: pyte vs libvterm, PIL vs FreeType+C++, before/after
- [ ] Documentation site (MkDocs or Sphinx)
- [ ] Context7 library registration for binterint itself

---

## 8. COPILOT CODE GENERATION RULES

### 8.1 When Writing Python Code:
- **Always use type hints** — the project uses Pydantic and will adopt full typing
- **Prefer `pathlib.Path` over `os.path`** — consistent with existing renderer code
- **Use `asyncio` for any I/O** — PTY reads, LLM API calls, and MCP tools must be async
- **Docstrings in Google style** — every public function/method gets Args/Returns/Raises
- **Import order**: stdlib → third-party → local, with `isort` compliance
- **No bare `except:`** — always catch specific exceptions
- **Logging over `print()`** — use `logging.getLogger("binterint." + __name__)`

### 8.2 When Writing C++ Code:
- **C++17 standard** — for `std::optional`, `std::string_view`, structured bindings
- **RAII everywhere** — no manual `new`/`delete`; use `std::unique_ptr`, `std::vector`
- **Header-only where possible** — minimize compilation units
- **`#pragma once`** not include guards
- **Google C++ Style Guide** naming: `PascalCase` classes, `snake_case` functions
- **All pybind11-exposed functions must handle exceptions** — translate C++ exceptions to Python

### 8.3 When Integrating Context7 MCP:
- **Always resolve library docs before writing integration code** — prefer `ctx7` CLI or MCP tools
- **Cite Context7 sources in code comments**: `# Source: Context7 /pybind/pybind11 v2.12.0`
- **When APIs change**, re-resolve with Context7 before updating code

### 8.4 File Naming & Project Structure:
```
.github/
  copilot-instructions.md       # THIS FILE
binterint/
  __init__.py
  __main__.py
  cli.py                        # Refactored with event-based commands
  controller.py                 # → PtyPlugin
  pty_engine.py                 # Wraps C++ TerminalEmulator
  renderer.py                   # → RendererPlugin, uses FontEngine
  screen_buffer.py              # Wraps C++ ScreenBuffer
  semantic.py                   # → SemanticPlugin
  font_manager.py               # NEW: FontConfig, FontManager
  mcp_server.py                 # NEW: FastMCP server
  event_bus.py                  # NEW: Event, EventType, EventBus, TerminalPlugin
  cpp_bridge.py                 # NEW: pybind11 module wrapper
  plugins/
    __init__.py
    pty_plugin.py
    renderer_plugin.py
    semantic_plugin.py
    interactive_shell.py
    screenshot_plugin.py
  backends/
    __init__.py
    base.py                     # TerminalBackend, KeyEvent, MouseEvent
    headless.py                 # Headless backend (current mode)
    crossterm.py                # Cross-term backend (interactive mode)
    windows_console.py          # Windows Console API backend
cpp_core/
  CMakeLists.txt
  src/
    terminal_emulator.cpp/.h
    screen_buffer.cpp/.h
    font_engine.cpp/.h
    input_parser.cpp/.h
    bindings.cpp
  tests/
    test_screen_buffer.cpp
    test_terminal_emulator.cpp
fonts/
  RobotoMono-Regular.ttf        # Existing
  RobotoMono-Bold.ttf           # NEW
  RobotoMono-Italic.ttf         # NEW
  FiraCode-Regular.ttf          # NEW
  JetBrainsMono-Regular.ttf     # NEW
  Hack-Regular.ttf              # NEW
```

---

## 9. TESTING STRATEGY

### 9.1 Python Tests (pytest)
```python
# tests/test_event_bus.py
async def test_plugin_registration():
    bus = EventBus()
    plugin = MockPlugin("test")
    bus.register(plugin)
    assert "test" in bus._plugins
    assert EventType.PLUGIN_LOADED in [e.type for e in bus._event_history]

# tests/test_font_manager.py  
def test_font_orientation_rendering():
    mgr = FontManager()
    config = FontConfig(family="roboto-mono", orientation=TextOrientation.VERTICAL_TTB)
    handle = mgr.load_font(config)
    bitmap = mgr.render_text_block(TextBlock("Hello", config, (0, 0)))
    assert len(bitmap) > 0

# tests/test_cpp_bridge.py
def test_screen_buffer_performance(benchmark):
    buf = _binterint_core.ScreenBuffer(200, 80)
    cell = _binterint_core.Cell()
    cell.char_data = "X"
    benchmark(lambda: [buf.write(x % 200, (x // 200) % 80, cell) for x in range(16000)])
```

### 9.2 C++ Tests (Google Test)
- ScreenBuffer: correct cell addressing, dirty rect bounds, resize behavior
- TerminalEmulator: ANSI escape sequence parsing parity with pyte
- FontEngine: glyph metrics accuracy, orientation transform correctness
- Performance: 60fps sustained for 200×80 buffer

---

## 10. CONTEXT7 MCP INTEGRATION FOR YOUR OWN DEVELOPMENT

When you, Copilot, are generating code for binterint v1.0.0, you MUST:

1. **Before writing any pybind11 code**: Call Context7 `resolve-library-id` with `libraryName="pybind11"` then `query-docs` with the specific binding pattern needed.
2. **Before writing libvterm integration**: Resolve `libvterm` docs and study the callback-based architecture.
3. **Before writing FreeType code**: Resolve `freetype` docs for the exact API version available.
4. **Before writing MCP server code**: Resolve `fastmcp` docs and follow the latest `@mcp.tool()` decorator patterns.
5. **Document every Context7 resolution** as a comment: `# Context7: /pybind/pybind11 — Using py::class_<> for ScreenBuffer binding`

The Context7 MCP server URL is `https://mcp.context7.com/mcp`. Configure it in your IDE's MCP settings with your API key in the `CONTEXT7_API_KEY` header.

---

**End of Copilot Instructions. This file governs all AI-assisted development of binterint v1.0.0. Version: 1.0.0-draft. Last updated: 2026-05-06.**
