// Context7: /pybind/pybind11 — libvterm terminal emulator implementation
#include "terminal_emulator.h"
#include <cstring>
#include <stdexcept>

// ---------------------------------------------------------------------------
// libvterm screen callback table (C-linkage compatible struct).
// ---------------------------------------------------------------------------
static VTermScreenCallbacks make_callbacks() {
    VTermScreenCallbacks cbs;
    std::memset(&cbs, 0, sizeof(cbs));
    cbs.damage     = &TerminalEmulator::s_damage;
    cbs.movecursor = &TerminalEmulator::s_movecursor;
    return cbs;
}

// ---------------------------------------------------------------------------
// TerminalEmulator
// ---------------------------------------------------------------------------
TerminalEmulator::TerminalEmulator(int cols, int rows)
    : buffer_(cols, rows)
{
    vt_ = vterm_new(rows, cols);
    if (!vt_) throw std::runtime_error("vterm_new failed");

    vterm_set_utf8(vt_, 1);

    vtscreen_ = vterm_obtain_screen(vt_);
    vterm_screen_reset(vtscreen_, 1);

    static const VTermScreenCallbacks cbs = make_callbacks();
    vterm_screen_set_callbacks(vtscreen_, &cbs, this);

    // Enable damage merging so we get one damage rect per-flush.
    vterm_screen_set_damage_merge(vtscreen_, VTERM_DAMAGE_SCROLL);
}

TerminalEmulator::~TerminalEmulator() {
    if (vt_) {
        vterm_free(vt_);
        vt_ = nullptr;
    }
}

void TerminalEmulator::feed(const std::string& data) {
    vterm_input_write(vt_, data.c_str(), data.size());
    vterm_screen_flush_damage(vtscreen_);
}

void TerminalEmulator::resize(int cols, int rows) {
    buffer_.resize(cols, rows);
    vterm_set_size(vt_, rows, cols);
    vterm_screen_flush_damage(vtscreen_);
}

ScreenBuffer& TerminalEmulator::get_screen() {
    return buffer_;
}

std::string TerminalEmulator::get_text_content() const {
    const int rows = buffer_.rows();
    const int cols = buffer_.columns();
    std::string result;
    result.reserve(static_cast<std::size_t>(rows) * (cols + 1));
    for (int y = 0; y < rows; ++y) {
        for (int x = 0; x < cols; ++x)
            result += buffer_.get_cell(x, y).char_data;
        if (y < rows - 1) result += '\n';
    }
    return result;
}

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------
std::string TerminalEmulator::cp_to_utf8(uint32_t cp) {
    if (cp == 0)        return " ";
    if (cp < 0x80)      return std::string(1, static_cast<char>(cp));
    if (cp < 0x800)     return { static_cast<char>(0xC0 | (cp >> 6)),
                                 static_cast<char>(0x80 | (cp & 0x3F)) };
    if (cp < 0x10000)   return { static_cast<char>(0xE0 | (cp >> 12)),
                                 static_cast<char>(0x80 | ((cp >>  6) & 0x3F)),
                                 static_cast<char>(0x80 | ( cp        & 0x3F)) };
    return { static_cast<char>(0xF0 | (cp >> 18)),
             static_cast<char>(0x80 | ((cp >> 12) & 0x3F)),
             static_cast<char>(0x80 | ((cp >>  6) & 0x3F)),
             static_cast<char>(0x80 | ( cp        & 0x3F)) };
}

void TerminalEmulator::sync_cell(int row, int col) {
    VTermPos pos{row, col};
    VTermScreenCell vcell;
    if (!vterm_screen_get_cell(vtscreen_, pos, &vcell)) return;

    Cell cell;

    // Character data: scan chars[] for the first non-zero code-point.
    // A cell may contain a multi-codepoint grapheme cluster (e.g. combining
    // characters), where chars[0] == 0 but chars[1] != 0 is theoretically
    // impossible — libvterm always puts the base character at index 0 and
    // combining characters at subsequent indices.  We take chars[0] as the
    // primary glyph and fall back to a space if it is zero (empty cell).
    uint32_t primary_cp = 0;
    for (int i = 0; i < VTERM_MAX_CHARS_PER_CELL; ++i) {
        if (vcell.chars[i] != 0) { primary_cp = vcell.chars[i]; break; }
    }
    cell.char_data = (primary_cp != 0) ? cp_to_utf8(primary_cp) : " ";

    // Colours — convert indexed/default colours to RGB first.
    VTermColor fg = vcell.fg;
    VTermColor bg = vcell.bg;
    vterm_screen_convert_color_to_rgb(vtscreen_, &fg);
    vterm_screen_convert_color_to_rgb(vtscreen_, &bg);

    if (VTERM_COLOR_IS_RGB(&fg)) {
        cell.fg_color = (static_cast<uint32_t>(fg.rgb.red)   << 24)
                      | (static_cast<uint32_t>(fg.rgb.green) << 16)
                      | (static_cast<uint32_t>(fg.rgb.blue)  <<  8)
                      | 0xFF;
    }
    if (VTERM_COLOR_IS_RGB(&bg)) {
        cell.bg_color = (static_cast<uint32_t>(bg.rgb.red)   << 24)
                      | (static_cast<uint32_t>(bg.rgb.green) << 16)
                      | (static_cast<uint32_t>(bg.rgb.blue)  <<  8)
                      | 0xFF;
    }

    cell.bold      = vcell.attrs.bold      != 0;
    cell.italic    = vcell.attrs.italic    != 0;
    cell.underline = vcell.attrs.underline != 0;

    buffer_.write(col, row, cell);
}

// ---------------------------------------------------------------------------
// Static libvterm callbacks
// ---------------------------------------------------------------------------
int TerminalEmulator::s_damage(VTermRect rect, void* user) {
    auto* self = static_cast<TerminalEmulator*>(user);
    for (int row = rect.start_row; row < rect.end_row; ++row)
        for (int col = rect.start_col; col < rect.end_col; ++col)
            self->sync_cell(row, col);
    return 1;
}

int TerminalEmulator::s_movecursor(VTermPos /*pos*/, VTermPos /*oldpos*/,
                                   int /*visible*/, void* /*user*/) {
    return 1;
}
