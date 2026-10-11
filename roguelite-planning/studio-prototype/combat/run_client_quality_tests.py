"""Run ClientQualityTests against the real ClientQuality source without Studio.

Usage: python run_client_quality_tests.py path/to/luau.exe [ClientQuality.luau]
`game` is stubbed as a non-client so the RenderStepped hookup is skipped; the tests drive
Q.sample with synthetic frame times.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent
module_path = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else root / "ClientQuality.luau"
module = module_path.read_text(encoding="utf-8-sig")
tests = (root / "ClientQualityTests.luau").read_text(encoding="utf-8-sig")
source = (
    "local game={GetService=function() return {IsClient=function() return false end} end}\n"
    f"local Q=(function()\n{module}\nend)()\n"
    f"local Tests=(function()\n{tests}\nend)()\n"
    "print(('ClientQualityTests: %d checks passed'):format(Tests(Q)))\n"
)
with tempfile.TemporaryDirectory(prefix="roguelite-client-quality-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
