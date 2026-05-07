#pragma once
// Context7: /pybind/pybind11 — Header-only C++ screen buffer with dirty-rect tracking
#include <vector>
#include <string>
#include <cstdint>
#include <algorithm>

/// A single terminal cell with character data, colors, and attributes.
struct Cell {
    std::string char_data = " ";
    uint32_t fg_color = 0xFFFFFFFF; ///< RGBA packed: R<<24|G<<16|B<<8|A
    uint32_t bg_color = 0x000000FF;
    bool bold      = false;
    bool italic    = false;
    bool underline = false;
    bool dirty     = true;
};

/// Axis-aligned rectangle in cell coordinates.
struct Rect {
    int x      = 0;
    int y      = 0;
    int width  = 0;
    int height = 0;
};

/// A 2-D grid of Cells with incremental dirty-region tracking.
class ScreenBuffer {
    int cols_;
    int rows_;
    std::vector<Cell> cells_;

    // Dirty-rect represented as bounding box (min/max corners).
    int dirty_min_x_;
    int dirty_min_y_;
    int dirty_max_x_; ///< exclusive
    int dirty_max_y_; ///< exclusive
    bool has_dirty_;

    void reset_dirty_bounds() {
        dirty_min_x_ = cols_;
        dirty_min_y_ = rows_;
        dirty_max_x_ = 0;
        dirty_max_y_ = 0;
        has_dirty_   = false;
    }

public:
    ScreenBuffer(int cols, int rows)
        : cols_(cols), rows_(rows),
          cells_(static_cast<std::size_t>(cols) * rows)
    {
        reset_dirty_bounds();
        // All cells start dirty so the first render is complete.
        for (auto& c : cells_) c.dirty = true;
        dirty_min_x_ = 0; dirty_min_y_ = 0;
        dirty_max_x_ = cols_; dirty_max_y_ = rows_;
        has_dirty_ = true;
    }

    int columns() const { return cols_; }
    int rows()    const { return rows_; }

    void write(int x, int y, const Cell& cell) {
        if (x < 0 || x >= cols_ || y < 0 || y >= rows_) return;
        cells_[static_cast<std::size_t>(y) * cols_ + x] = cell;
        cells_[static_cast<std::size_t>(y) * cols_ + x].dirty = true;

        dirty_min_x_ = std::min(dirty_min_x_, x);
        dirty_min_y_ = std::min(dirty_min_y_, y);
        dirty_max_x_ = std::max(dirty_max_x_, x + 1);
        dirty_max_y_ = std::max(dirty_max_y_, y + 1);
        has_dirty_   = true;
    }

    const Cell& get_cell(int x, int y) const {
        return cells_[static_cast<std::size_t>(y) * cols_ + x];
    }

    /// Returns a list of dirty rectangles (currently a single bounding box).
    std::vector<Rect> get_dirty_rects() const {
        if (!has_dirty_) return {};
        return {{ dirty_min_x_, dirty_min_y_,
                  dirty_max_x_ - dirty_min_x_,
                  dirty_max_y_ - dirty_min_y_ }};
    }

    /// Clears dirty flags and resets the tracking bounding box.
    void clear_dirty() {
        for (auto& c : cells_) c.dirty = false;
        reset_dirty_bounds();
    }

    void resize(int cols, int rows) {
        cols_ = cols;
        rows_ = rows;
        cells_.assign(static_cast<std::size_t>(cols) * rows, Cell{});
        // Mark everything dirty after resize.
        for (auto& c : cells_) c.dirty = true;
        dirty_min_x_ = 0; dirty_min_y_ = 0;
        dirty_max_x_ = cols_; dirty_max_y_ = rows_;
        has_dirty_ = true;
    }
};
