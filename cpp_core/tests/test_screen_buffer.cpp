// Basic unit tests for ScreenBuffer using a simple hand-rolled assert framework
// (no external test runner required — just compile and run).
#include <cassert>
#include <iostream>
#include "../src/screen_buffer.h"

void test_initial_state() {
    ScreenBuffer buf(10, 5);
    assert(buf.columns() == 10);
    assert(buf.rows()    == 5);
    // All cells start dirty.
    auto rects = buf.get_dirty_rects();
    assert(!rects.empty());
    std::cout << "  [PASS] initial state\n";
}

void test_write_and_get() {
    ScreenBuffer buf(10, 5);
    buf.clear_dirty();

    Cell c;
    c.char_data = "X";
    c.bold      = true;
    buf.write(3, 2, c);

    const Cell& got = buf.get_cell(3, 2);
    assert(got.char_data == "X");
    assert(got.bold      == true);
    std::cout << "  [PASS] write and get\n";
}

void test_dirty_rect_tracking() {
    ScreenBuffer buf(20, 10);
    buf.clear_dirty();
    assert(buf.get_dirty_rects().empty());

    Cell c; c.char_data = "A";
    buf.write(5, 3, c);
    buf.write(7, 3, c);
    buf.write(5, 5, c);

    auto rects = buf.get_dirty_rects();
    assert(rects.size() == 1);
    const Rect& r = rects[0];
    assert(r.x == 5);
    assert(r.y == 3);
    assert(r.width  == 3); // 5,6,7  → width 3
    assert(r.height == 3); // rows 3,4,5 → height 3

    buf.clear_dirty();
    assert(buf.get_dirty_rects().empty());
    std::cout << "  [PASS] dirty rect tracking\n";
}

void test_resize() {
    ScreenBuffer buf(10, 5);
    buf.resize(20, 10);
    assert(buf.columns() == 20);
    assert(buf.rows()    == 10);
    // Resize marks everything dirty.
    assert(!buf.get_dirty_rects().empty());
    std::cout << "  [PASS] resize\n";
}

int main() {
    std::cout << "ScreenBuffer tests:\n";
    test_initial_state();
    test_write_and_get();
    test_dirty_rect_tracking();
    test_resize();
    std::cout << "All ScreenBuffer tests passed.\n";
    return 0;
}
