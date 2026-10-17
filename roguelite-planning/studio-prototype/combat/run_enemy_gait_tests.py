"""Run EnemyGaitTests against the real NativeEnemyFeet source without Studio.

Usage: python run_enemy_gait_tests.py path/to/luau.exe
NativeEnemyFeet needs no Roblox globals to load; the tests only call its pure gait().
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent
module = (root / "NativeEnemyFeet.luau").read_text(encoding="utf-8-sig")
tests = (root / "EnemyGaitTests.luau").read_text(encoding="utf-8-sig")
source = (
    f"local Feet=(function()\n{module}\nend)()\n"
    f"local Tests=(function()\n{tests}\nend)()\n"
    "print(('EnemyGaitTests: %d checks passed'):format(Tests(Feet)))\n"
)
with tempfile.TemporaryDirectory(prefix="roguelite-enemy-gait-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
