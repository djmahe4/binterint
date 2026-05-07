#pragma once
// Context7: /pybind/pybind11 — libvterm-backed terminal emulator C++ class
#include <string>
#include <functional>
#include <vterm.h>
#include "screen_buffer.h"

/// Wraps a libvterm VTerm instance and syncs its screen into a ScreenBuffer.
class TerminalEmulator {
    VTerm*        vt_;
    VTermScreen*  vtscreen_;
    ScreenBuffer  buffer_;

public:
    TerminalEmulator(int cols, int rows);
    ~TerminalEmulator();

    /// Feed raw bytes (e.g. PTY output) to the terminal emulator.
    void feed(const std::string& data);

    /// Resize the virtual terminal and the backing buffer.
    void resize(int cols, int rows);

    /// Access the backing screen buffer (read/write).
    ScreenBuffer& get_screen();

    /// Return the visible screen content as a plain UTF-8 string.
    std::string get_text_content() const;

    // libvterm callbacks — must be public static so we can take their address
    // in terminal_emulator.cpp's make_callbacks() helper.
    static int s_damage(VTermRect rect, void* user);
    static int s_movecursor(VTermPos pos, VTermPos oldpos, int visible, void* user);

private:

    /// Copy a single cell from libvterm's screen model into buffer_.
    void sync_cell(int row, int col);

    /// Convert a UTF-32 code-point to a UTF-8 std::string.
    static std::string cp_to_utf8(uint32_t cp);
};
