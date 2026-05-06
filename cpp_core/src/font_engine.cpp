// Context7: /pybind/pybind11 — FreeType font engine implementation
#include "font_engine.h"
#include <cmath>
#include <cstring>
#include <stdexcept>
#include <algorithm>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// ---------------------------------------------------------------------------
// FontEngine lifecycle
// ---------------------------------------------------------------------------
FontEngine::FontEngine() {
    if (FT_Init_FreeType(&library_))
        throw std::runtime_error("FT_Init_FreeType failed");
}

FontEngine::~FontEngine() {
    for (auto& [handle, face] : faces_)
        FT_Done_Face(face);
    FT_Done_FreeType(library_);
}

// ---------------------------------------------------------------------------
// Font loading
// ---------------------------------------------------------------------------
int FontEngine::load_font(const std::string& path, int size_px) {
    FT_Face face;
    if (FT_New_Face(library_, path.c_str(), 0, &face))
        throw std::runtime_error("FT_New_Face failed for: " + path);
    if (FT_Set_Pixel_Sizes(face, 0, static_cast<FT_UInt>(size_px))) {
        FT_Done_Face(face);
        throw std::runtime_error("FT_Set_Pixel_Sizes failed");
    }
    int handle = next_handle_++;
    faces_[handle]      = face;
    face_paths_[handle] = path;
    return handle;
}

// ---------------------------------------------------------------------------
// Glyph metrics
// ---------------------------------------------------------------------------
GlyphMetrics FontEngine::get_glyph_metrics(int handle, uint32_t codepoint) {
    auto it = faces_.find(handle);
    if (it == faces_.end()) return {};
    FT_Face face = it->second;

    if (FT_Load_Char(face, codepoint, FT_LOAD_DEFAULT)) return {};
    const auto& m = face->glyph->metrics;
    return {
        static_cast<int>(m.width  >> 6),
        static_cast<int>(m.height >> 6),
        static_cast<int>(m.horiBearingX >> 6),
        static_cast<int>(m.horiBearingY >> 6),
        static_cast<int>(m.horiAdvance  >> 6),
        static_cast<int>(m.vertAdvance  >> 6),
    };
}

// ---------------------------------------------------------------------------
// Text measuring
// ---------------------------------------------------------------------------
std::pair<int,int> FontEngine::measure_text(int handle, const std::string& text,
                                            float letter_spacing) {
    auto it = faces_.find(handle);
    if (it == faces_.end()) return {0, 0};
    FT_Face face = it->second;

    int total_w = 0;
    int line_h  = static_cast<int>(face->size->metrics.height >> 6);
    for (uint32_t cp : decode_utf8(text)) {
        if (FT_Load_Char(face, cp, FT_LOAD_DEFAULT)) continue;
        total_w += static_cast<int>(face->glyph->advance.x >> 6)
                 + static_cast<int>(letter_spacing);
    }
    return {total_w, line_h};
}

// ---------------------------------------------------------------------------
// Top-level render_text dispatcher
// ---------------------------------------------------------------------------
RenderResult FontEngine::render_text(int handle, const std::string& text,
                                      int orientation, float letter_spacing) {
    auto it = faces_.find(handle);
    if (it == faces_.end()) return {};
    FT_Face face = it->second;

    RenderResult base = render_horizontal(face, text, letter_spacing);
    if (base.pixels.empty()) return base;

    switch (static_cast<TextOrientation>(orientation)) {
        case TextOrientation::HORIZONTAL_LTR: return base;
        case TextOrientation::HORIZONTAL_RTL: return flip_horizontal(base);
        case TextOrientation::VERTICAL_TTB:   return rotate_90cw(base);
        case TextOrientation::VERTICAL_BTT:   return rotate_90ccw(base);
        case TextOrientation::DIAGONAL_45:    return rotate_diagonal(base,  45.0);
        case TextOrientation::DIAGONAL_135:   return rotate_diagonal(base, 135.0);
        default:                              return base;
    }
}

// ---------------------------------------------------------------------------
// Horizontal rendering (baseline approach)
// ---------------------------------------------------------------------------
RenderResult FontEngine::render_horizontal(FT_Face face, const std::string& text,
                                            float letter_spacing) {
    auto codepoints = decode_utf8(text);
    if (codepoints.empty()) return {};

    int ascender  = static_cast<int>(face->size->metrics.ascender  >> 6);
    int descender = static_cast<int>(-(face->size->metrics.descender >> 6));
    int line_h    = ascender + descender;
    if (line_h <= 0) line_h = static_cast<int>(face->size->metrics.height >> 6);

    // Measure total width.
    int total_w = 0;
    for (uint32_t cp : codepoints) {
        if (FT_Load_Char(face, cp, FT_LOAD_DEFAULT)) continue;
        total_w += static_cast<int>(face->glyph->advance.x >> 6)
                 + static_cast<int>(letter_spacing);
    }
    if (total_w <= 0 || line_h <= 0) return {};

    RenderResult result;
    result.width  = total_w;
    result.height = line_h;
    result.pixels.assign(static_cast<std::size_t>(total_w) * line_h * 4, 0);

    int pen_x = 0;
    for (uint32_t cp : codepoints) {
        if (FT_Load_Char(face, cp, FT_LOAD_RENDER)) continue;
        FT_GlyphSlot g = face->glyph;

        for (unsigned int row = 0; row < g->bitmap.rows; ++row) {
            int y = ascender - g->bitmap_top + static_cast<int>(row);
            if (y < 0 || y >= line_h) continue;
            for (unsigned int col = 0; col < g->bitmap.width; ++col) {
                int x = pen_x + g->bitmap_left + static_cast<int>(col);
                if (x < 0 || x >= total_w) continue;
                uint8_t alpha = g->bitmap.buffer[row * static_cast<unsigned>(g->bitmap.pitch) + col];
                if (alpha == 0) continue;
                std::size_t idx = static_cast<std::size_t>(y) * total_w * 4
                                + static_cast<std::size_t>(x) * 4;
                result.pixels[idx + 0] = 255;   // R
                result.pixels[idx + 1] = 255;   // G
                result.pixels[idx + 2] = 255;   // B
                result.pixels[idx + 3] = alpha; // A
            }
        }
        pen_x += static_cast<int>(g->advance.x >> 6)
               + static_cast<int>(letter_spacing);
    }
    return result;
}

// ---------------------------------------------------------------------------
// Buffer rotation helpers
// ---------------------------------------------------------------------------
RenderResult FontEngine::flip_horizontal(const RenderResult& src) {
    RenderResult dst;
    dst.width  = src.width;
    dst.height = src.height;
    dst.pixels.resize(src.pixels.size(), 0);
    for (int y = 0; y < src.height; ++y) {
        for (int x = 0; x < src.width; ++x) {
            int src_idx = (y * src.width + x) * 4;
            int dst_x   = src.width - 1 - x;
            int dst_idx = (y * src.width + dst_x) * 4;
            std::memcpy(&dst.pixels[dst_idx], &src.pixels[src_idx], 4);
        }
    }
    return dst;
}

RenderResult FontEngine::rotate_90cw(const RenderResult& src) {
    // new(w,h) = old(h,w), new_pixel(r,c) = old_pixel(h-1-c, r)
    RenderResult dst;
    dst.width  = src.height;
    dst.height = src.width;
    dst.pixels.resize(static_cast<std::size_t>(dst.width) * dst.height * 4, 0);
    for (int r = 0; r < src.height; ++r) {
        for (int c = 0; c < src.width; ++c) {
            int src_idx  = (r * src.width + c) * 4;
            int dst_r    = c;
            int dst_c    = src.height - 1 - r;
            int dst_idx  = (dst_r * dst.width + dst_c) * 4;
            std::memcpy(&dst.pixels[dst_idx], &src.pixels[src_idx], 4);
        }
    }
    return dst;
}

RenderResult FontEngine::rotate_90ccw(const RenderResult& src) {
    // new_pixel(r,c) = old_pixel(c, w-1-r)
    RenderResult dst;
    dst.width  = src.height;
    dst.height = src.width;
    dst.pixels.resize(static_cast<std::size_t>(dst.width) * dst.height * 4, 0);
    for (int r = 0; r < src.height; ++r) {
        for (int c = 0; c < src.width; ++c) {
            int src_idx = (r * src.width + c) * 4;
            int dst_r   = src.width - 1 - c;
            int dst_c   = r;
            int dst_idx = (dst_r * dst.width + dst_c) * 4;
            std::memcpy(&dst.pixels[dst_idx], &src.pixels[src_idx], 4);
        }
    }
    return dst;
}

RenderResult FontEngine::rotate_diagonal(const RenderResult& src, double angle_deg) {
    const double rad = angle_deg * M_PI / 180.0;
    const double cos_a = std::cos(rad);
    const double sin_a = std::sin(rad);

    // Compute new canvas size (bounding box of rotated rectangle).
    double cx = src.width  / 2.0;
    double cy = src.height / 2.0;
    // Four corner vectors relative to centre.
    double corners_x[4] = { -cx, cx,  cx, -cx };
    double corners_y[4] = { -cy, -cy,  cy,  cy };

    double min_x = 1e9, max_x = -1e9, min_y = 1e9, max_y = -1e9;
    for (int i = 0; i < 4; ++i) {
        double rx = corners_x[i] * cos_a - corners_y[i] * sin_a;
        double ry = corners_x[i] * sin_a + corners_y[i] * cos_a;
        min_x = std::min(min_x, rx); max_x = std::max(max_x, rx);
        min_y = std::min(min_y, ry); max_y = std::max(max_y, ry);
    }

    int new_w = static_cast<int>(std::ceil(max_x - min_x));
    int new_h = static_cast<int>(std::ceil(max_y - min_y));
    if (new_w <= 0 || new_h <= 0) return {};

    RenderResult dst;
    dst.width  = new_w;
    dst.height = new_h;
    dst.pixels.resize(static_cast<std::size_t>(new_w) * new_h * 4, 0);

    double new_cx = new_w / 2.0;
    double new_cy = new_h / 2.0;

    // Inverse-map each destination pixel to source.
    for (int dy = 0; dy < new_h; ++dy) {
        for (int dx = 0; dx < new_w; ++dx) {
            double rx = dx - new_cx;
            double ry = dy - new_cy;
            // Inverse rotation (transpose of rotation matrix).
            double sx = rx * cos_a + ry * sin_a + cx;
            double sy = -rx * sin_a + ry * cos_a + cy;
            int src_x = static_cast<int>(std::round(sx));
            int src_y = static_cast<int>(std::round(sy));
            if (src_x < 0 || src_x >= src.width || src_y < 0 || src_y >= src.height)
                continue;
            int src_idx = (src_y * src.width + src_x) * 4;
            int dst_idx = (dy * new_w + dx) * 4;
            std::memcpy(&dst.pixels[dst_idx], &src.pixels[src_idx], 4);
        }
    }
    return dst;
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------
std::vector<uint32_t> FontEngine::decode_utf8(const std::string& s) {
    std::vector<uint32_t> codepoints;
    codepoints.reserve(s.size());
    for (std::size_t i = 0; i < s.size(); ) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        uint32_t cp = 0;
        int extra = 0;
        if      (c < 0x80)  { cp = c;          extra = 0; }
        else if (c < 0xC0)  { ++i; continue; } // continuation byte, skip
        else if (c < 0xE0)  { cp = c & 0x1F;  extra = 1; }
        else if (c < 0xF0)  { cp = c & 0x0F;  extra = 2; }
        else                { cp = c & 0x07;  extra = 3; }
        ++i;
        for (int j = 0; j < extra && i < s.size(); ++j, ++i)
            cp = (cp << 6) | (static_cast<unsigned char>(s[i]) & 0x3F);
        codepoints.push_back(cp);
    }
    return codepoints;
}

std::vector<std::pair<int,std::string>> FontEngine::list_loaded_fonts() const {
    std::vector<std::pair<int,std::string>> result;
    result.reserve(face_paths_.size());
    for (const auto& [handle, path] : face_paths_)
        result.emplace_back(handle, path);
    return result;
}
