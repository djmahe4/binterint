// Context7: /pybind/pybind11 — pybind11 module exposing binterint C++ core
// Source: Context7 /pybind/pybind11 — Using py::class_<> for ScreenBuffer, TerminalEmulator, FontEngine bindings
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "screen_buffer.h"
#include "terminal_emulator.h"
#include "font_engine.h"

namespace py = pybind11;

PYBIND11_MODULE(_binterint_core, m) {
    m.doc() = "binterint C++ acceleration core — terminal emulation, "
              "font rendering, and screen buffer management";

    // ------------------------------------------------------------------
    // Cell
    // ------------------------------------------------------------------
    py::class_<Cell>(m, "Cell")
        .def(py::init<>())
        .def_readwrite("char_data",  &Cell::char_data)
        .def_readwrite("fg_color",   &Cell::fg_color)
        .def_readwrite("bg_color",   &Cell::bg_color)
        .def_readwrite("bold",       &Cell::bold)
        .def_readwrite("italic",     &Cell::italic)
        .def_readwrite("underline",  &Cell::underline)
        .def_readwrite("dirty",      &Cell::dirty)
        .def("__repr__", [](const Cell& c) {
            return "<Cell '" + c.char_data + "'>";
        });

    // ------------------------------------------------------------------
    // Rect
    // ------------------------------------------------------------------
    py::class_<Rect>(m, "Rect")
        .def(py::init<>())
        .def_readwrite("x",      &Rect::x)
        .def_readwrite("y",      &Rect::y)
        .def_readwrite("width",  &Rect::width)
        .def_readwrite("height", &Rect::height)
        .def("__repr__", [](const Rect& r) {
            return "<Rect x=" + std::to_string(r.x) + " y=" + std::to_string(r.y)
                 + " w=" + std::to_string(r.width) + " h=" + std::to_string(r.height) + ">";
        });

    // ------------------------------------------------------------------
    // ScreenBuffer
    // ------------------------------------------------------------------
    py::class_<ScreenBuffer>(m, "ScreenBuffer")
        .def(py::init<int, int>(), py::arg("cols"), py::arg("rows"),
             "Create a ScreenBuffer with the given dimensions.")
        .def("write",           &ScreenBuffer::write,
             py::arg("x"), py::arg("y"), py::arg("cell"))
        .def("get_cell",        &ScreenBuffer::get_cell,
             py::arg("x"), py::arg("y"))
        .def("get_dirty_rects", &ScreenBuffer::get_dirty_rects)
        .def("clear_dirty",     &ScreenBuffer::clear_dirty)
        .def("resize",          &ScreenBuffer::resize,
             py::arg("cols"), py::arg("rows"))
        .def_property_readonly("columns", &ScreenBuffer::columns)
        .def_property_readonly("rows",    &ScreenBuffer::rows);

    // ------------------------------------------------------------------
    // TerminalEmulator
    // ------------------------------------------------------------------
    py::class_<TerminalEmulator>(m, "TerminalEmulator")
        .def(py::init<int, int>(), py::arg("cols"), py::arg("rows"),
             "Create a libvterm-backed terminal emulator.")
        .def("feed",             &TerminalEmulator::feed,
             py::arg("data"),
             "Feed raw PTY bytes to the emulator.")
        .def("resize",           &TerminalEmulator::resize,
             py::arg("cols"), py::arg("rows"))
        .def("get_text_content", &TerminalEmulator::get_text_content,
             "Return visible screen as a plain UTF-8 string.")
        .def("get_screen",       &TerminalEmulator::get_screen,
             py::return_value_policy::reference_internal,
             "Access the backing ScreenBuffer.");

    // ------------------------------------------------------------------
    // GlyphMetrics
    // ------------------------------------------------------------------
    py::class_<GlyphMetrics>(m, "GlyphMetrics")
        .def(py::init<>())
        .def_readwrite("width",     &GlyphMetrics::width)
        .def_readwrite("height",    &GlyphMetrics::height)
        .def_readwrite("bearing_x", &GlyphMetrics::bearing_x)
        .def_readwrite("bearing_y", &GlyphMetrics::bearing_y)
        .def_readwrite("advance_x", &GlyphMetrics::advance_x)
        .def_readwrite("advance_y", &GlyphMetrics::advance_y);

    // ------------------------------------------------------------------
    // RenderResult
    // ------------------------------------------------------------------
    py::class_<RenderResult>(m, "RenderResult")
        .def(py::init<>())
        .def_readonly("pixels", &RenderResult::pixels,
                      "RGBA pixel data (row-major, 4 bytes per pixel).")
        .def_readonly("width",  &RenderResult::width)
        .def_readonly("height", &RenderResult::height);

    // ------------------------------------------------------------------
    // TextOrientation enum
    // ------------------------------------------------------------------
    py::enum_<TextOrientation>(m, "TextOrientation")
        .value("HORIZONTAL_LTR", TextOrientation::HORIZONTAL_LTR)
        .value("HORIZONTAL_RTL", TextOrientation::HORIZONTAL_RTL)
        .value("VERTICAL_TTB",   TextOrientation::VERTICAL_TTB)
        .value("VERTICAL_BTT",   TextOrientation::VERTICAL_BTT)
        .value("DIAGONAL_45",    TextOrientation::DIAGONAL_45)
        .value("DIAGONAL_135",   TextOrientation::DIAGONAL_135)
        .export_values();

    // ------------------------------------------------------------------
    // FontEngine
    // ------------------------------------------------------------------
    py::class_<FontEngine>(m, "FontEngine")
        .def(py::init<>(), "Initialise FreeType library.")
        .def("load_font",         &FontEngine::load_font,
             py::arg("path"), py::arg("size_px"),
             "Load a TTF font from *path* at *size_px* pixels. Returns a handle.")
        .def("get_glyph_metrics", &FontEngine::get_glyph_metrics,
             py::arg("handle"), py::arg("codepoint"))
        .def("render_text",       &FontEngine::render_text,
             py::arg("handle"), py::arg("text"),
             py::arg("orientation") = 0,
             py::arg("letter_spacing") = 0.0f,
             "Render UTF-8 text, returning a RenderResult (RGBA pixels + size).")
        .def("measure_text",      &FontEngine::measure_text,
             py::arg("handle"), py::arg("text"),
             py::arg("letter_spacing") = 0.0f,
             "Return (total_width, line_height) without rendering.")
        .def("list_loaded_fonts", &FontEngine::list_loaded_fonts,
             "Return list of (handle, path) for all loaded fonts.");
}
