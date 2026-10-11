"""Run FireZoneTests against the real SpecialMotion source in the Luau CLI.

Usage: python run_fire_zone_tests.py path/to/luau.exe
SpecialMotion has no requires and only touches Vector3/CFrame inside functions the tests don't
call, so it loads as is.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent


def module(name, filename):
    source = (root / filename).read_text(encoding="utf-8-sig")
    return f"local {name}=(function()\n{source}\nend)()\n"


source = module("Motion", "SpecialMotion.luau") + module("Tests", "FireZoneTests.luau")
source += "print('FireZoneTests: '..Tests(Motion)..' checks passed')\n"
with tempfile.TemporaryDirectory(prefix="roguelite-fire-zone-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
