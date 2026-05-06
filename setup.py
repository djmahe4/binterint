"""
setup.py — optional C++ extension build for binterint.

Running ``pip install -e .`` or ``python setup.py build_ext --inplace``
will attempt to compile the pybind11 C++ extension ``_binterint_core``.
If the build fails for any reason (missing cmake, missing system libraries,
etc.) a warning is printed and the package continues to work in pure-Python
fallback mode via ``binterint.cpp_bridge``.
"""
import glob
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from setuptools import setup
from setuptools.command.build_ext import build_ext as _build_ext


class CMakeBuildExt(_build_ext):
    """Build extension by delegating to CMake."""

    def run(self) -> None:
        # Only run for our cmake pseudo-extension — skip real ext objects.
        self._cmake_build()

    def _cmake_build(self) -> None:
        source_dir  = Path(__file__).parent / "cpp_core"
        pkg_dir     = Path(__file__).parent / "binterint"
        build_dir   = (Path(__file__).parent / self.build_temp / "binterint_cmake").resolve()
        build_dir.mkdir(parents=True, exist_ok=True)

        try:
            import pybind11  # noqa: PLC0415
        except ImportError:
            print(
                "[binterint] pybind11 not installed — skipping C++ build. "
                "Run `pip install pybind11` to enable native acceleration.",
                file=sys.stderr,
            )
            return

        # cmake configure
        cmake_args = [
            f"-Dpybind11_DIR={pybind11.get_cmake_dir()}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            f"-DBINTERINT_OUTPUT_DIR={build_dir}",
            "-DCMAKE_BUILD_TYPE=Release",
        ]
        try:
            subprocess.check_call(
                ["cmake", str(source_dir)] + cmake_args,
                cwd=str(build_dir),
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(
                f"[binterint] cmake configure failed: {exc}. "
                "Install cmake>=3.15 and the required system libraries "
                "(libvterm-dev, libfreetype-dev) to enable native acceleration.",
                file=sys.stderr,
            )
            return

        # cmake build
        try:
            subprocess.check_call(
                ["cmake", "--build", ".", "--config", "Release",
                 "--parallel", str(os.cpu_count() or 2)],
                cwd=str(build_dir),
            )
        except subprocess.CalledProcessError as exc:
            print(
                f"[binterint] cmake build failed: {exc}. "
                "Pure-Python fallback will be used.",
                file=sys.stderr,
            )
            return

        # Copy compiled .so into the package directory.
        ext_suffix  = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
        so_pattern  = str(build_dir / f"_binterint_core*{ext_suffix}")
        # Also try .so directly for builds that don't add the ABI tag.
        fallback_pattern = str(build_dir / "_binterint_core*.so")

        copied = False
        for pattern in (so_pattern, fallback_pattern):
            for src in glob.glob(pattern):
                dest = pkg_dir / Path(src).name
                shutil.copy2(src, dest)
                print(f"[binterint] Installed native extension: {dest}", file=sys.stderr)
                copied = True
                break
            if copied:
                break

        if not copied:
            print(
                "[binterint] Warning: cmake succeeded but could not find the "
                f"output .so file (looked for '{so_pattern}'). "
                "Pure-Python fallback will be used.",
                file=sys.stderr,
            )


# The ext_modules list is intentionally empty; we just need CMakeBuildExt
# to be registered so that ``pip install`` triggers our cmake run.
setup(cmdclass={"build_ext": CMakeBuildExt})
