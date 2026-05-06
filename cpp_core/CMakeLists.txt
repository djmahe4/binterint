cmake_minimum_required(VERSION 3.15)
project(_binterint_core CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# ---- pybind11 ----------------------------------------------------------------
find_package(pybind11 CONFIG REQUIRED)

# ---- FreeType ----------------------------------------------------------------
find_package(Freetype REQUIRED)

# ---- libvterm ----------------------------------------------------------------
find_library(VTERM_LIBRARY NAMES vterm REQUIRED)
find_path(VTERM_INCLUDE_DIR NAMES vterm.h REQUIRED)

message(STATUS "FreeType: ${FREETYPE_LIBRARIES} (include: ${FREETYPE_INCLUDE_DIRS})")
message(STATUS "libvterm: ${VTERM_LIBRARY} (include: ${VTERM_INCLUDE_DIR})")

# ---- Module ------------------------------------------------------------------
pybind11_add_module(_binterint_core
    src/bindings.cpp
    src/terminal_emulator.cpp
    src/font_engine.cpp
)

target_include_directories(_binterint_core PRIVATE
    src
    ${FREETYPE_INCLUDE_DIRS}
    ${VTERM_INCLUDE_DIR}
)

target_link_libraries(_binterint_core PRIVATE
    ${FREETYPE_LIBRARIES}
    ${VTERM_LIBRARY}
)

# Let the caller specify where to install the .so
if(DEFINED BINTERINT_OUTPUT_DIR)
    set_target_properties(_binterint_core PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${BINTERINT_OUTPUT_DIR}"
    )
endif()
