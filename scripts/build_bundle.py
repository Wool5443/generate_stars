from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import platform
import shutil
import sys

import PyInstaller.__main__


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = PROJECT_ROOT / "packaging" / "generate-stars.spec"
DIST_DIR = PROJECT_ROOT / "dist"
BUNDLE_DIR = DIST_DIR / "generate-stars"


def detect_target() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform in {"win32", "cygwin", "msys"}:
        return "windows"
    raise RuntimeError(f"Unsupported build platform: {sys.platform}")


def normalized_arch() -> str:
    machine = platform.machine().lower()
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
    }
    return aliases.get(machine, machine)


def build_bundle(*, clean: bool) -> None:
    args = [
        "--noconfirm",
        str(SPEC_PATH),
    ]
    if clean:
        args.insert(1, "--clean")
    PyInstaller.__main__.run(
        args
    )


def create_archive(target: str) -> Path:
    if not BUNDLE_DIR.exists():
        raise RuntimeError(f"Expected bundle output at {BUNDLE_DIR}")

    archive_stem = DIST_DIR / f"generate-stars-{target}-{normalized_arch()}"
    if target == "windows":
        archive_path = Path(shutil.make_archive(str(archive_stem), "zip", root_dir=DIST_DIR, base_dir=BUNDLE_DIR.name))
    else:
        archive_path = Path(
            shutil.make_archive(str(archive_stem), "xztar", root_dir=DIST_DIR, base_dir=BUNDLE_DIR.name)
        )
    return archive_path


def main() -> int:
    parser = ArgumentParser(description="Build a self-contained Generate Stars bundle.")
    parser.add_argument("--target", choices=["linux", "windows"], default=detect_target())
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Run PyInstaller with --clean (slower, but ignores build cache).",
    )
    args = parser.parse_args()

    build_bundle(clean=args.clean)
    archive_path = create_archive(args.target)
    print(archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
