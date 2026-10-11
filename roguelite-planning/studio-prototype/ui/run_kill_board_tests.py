"""Run the pure kill board tests (KillBoard.rank/rows/format/visible/place) without Studio (2026-10-10).

Usage (from the repo root):
  python roguelite-planning/studio-prototype/ui/run_kill_board_tests.py build/luau-validation/luau.exe

KillBoard.luau touches `game` only inside mount(), so the module loads as is.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent


def read(name):
    return (root / name).read_text(encoding="utf-8-sig").replace("\r\n", "\n")


source = "local K=(function()\n" + read("KillBoard.luau") + "\nend)()\n"
source += "local Tests=(function()\n" + read("KillBoardTests.luau") + "\nend)()\n"
source += "print('KillBoardTests: '..Tests(K)..' checks passed')\n"
with tempfile.TemporaryDirectory(prefix="roguelite-killboard-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
