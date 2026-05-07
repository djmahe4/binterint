#pragma once
// Context7: /pybind/pybind11 — FreeType-backed font engine with text orientation
#include <string>
#include <vector>
#include <unordered_map>
#include <cstdint>
#include <ft2build.h>
#include FT_FREETYPE_H

/// Text orientation modes for the FontEngine.
enum class TextOrientation : int {
    HORIZONTAL_LTR = 0, ///< Left-to-right (default)
    HORIZONTAL_RTL = 1, ///< Right-to-left (horizontal flip)
    VERTICAL_TTB   = 2, ///< Top-to-bottom (90° clockwise)
    VERTICAL_BTT   = 3, ///< Bottom-to-top (90° counter-clockwise)
    DIAGONAL_45    = 4, ///< 45° counter-clockwise
    DIAGONAL_135   = 5, ///< 45° clockwise (135° CCW)
};

/// Metrics for a single glyph.
struct GlyphMetrics {
    int width     = 0;
    int height    = 0;
    int bearing_x = 0;
    int bearing_y = 0;
    int advance_x = 0;
    int advance_y = 0;
};

/// Result of a text-render call: raw RGBA pixel data + dimensions.
struct RenderResult {
    std::vector<uint8_t> pixels; ///< row-major RGBA, 4 bytes/pixel
    int width  = 0;
    int height = 0;
};

/// FreeType-backed font engine: load fonts, measure text, render with orientation.
class FontEngine {
    FT_Library library_;
    std::unordered_map<int, FT_Face> faces_;
    int next_handle_ = 0;

public:
    FontEngine();
    ~FontEngine();

    /// Load a font from a file path at the given point size.
    /// Returns an opaque handle used by subsequent calls.
    int load_font(const std::string& path, int size_px);

    /// Return glyph metrics for a single Unicode code-point.
    GlyphMetrics get_glyph_metrics(int handle, uint32_t codepoint);

    /// Render UTF-8 text to an RGBA buffer.
    RenderResult render_text(int handle, const std::string& text,
                             int orientation, float letter_spacing);

    /// Return (total_width, line_height) for a string without rendering.
    std::pair<int,int> measure_text(int handle, const std::string& text,
                                    float letter_spacing = 0.0f);

    /// List all font faces currently loaded (handle → path).
    std::vector<std::pair<int,std::string>> list_loaded_fonts() const;

private:
    /// Decode UTF-8 string to a vector of Unicode code-points.
    static std::vector<uint32_t> decode_utf8(const std::string& s);

    /// Render text into a horizontal RGBA buffer.
    RenderResult render_horizontal(FT_Face face, const std::string& text,
                                   float letter_spacing);

    // Buffer rotation helpers — operate on RGBA data.
    static RenderResult flip_horizontal(const RenderResult& src);
    static RenderResult rotate_90cw(const RenderResult& src);
    static RenderResult rotate_90ccw(const RenderResult& src);
    static RenderResult rotate_diagonal(const RenderResult& src, double angle_deg);

    // Per-face path tracking (for list_loaded_fonts).
    std::unordered_map<int, std::string> face_paths_;
};
