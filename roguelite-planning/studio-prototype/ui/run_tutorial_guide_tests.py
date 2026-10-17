"""Run TutorialGuideTests against the real TutorialGuideUI placement maths in the Luau CLI.

Usage (from the repo root):
  python roguelite-planning/studio-prototype/ui/run_tutorial_guide_tests.py build/luau-validation/luau.exe

Only Roblox wiring is replaced: a small pure-Luau Vector2, a `game` whose services are empty
tables and a `require` that hands back a stub UITheme. G.new (which needs a real PlayerGui) is
never called; the tests drive G.toLocal, G.clip, G.placeArrow, G.scrollInto, G.spots,
G.placeBox and G.fitText. 2026-10-16: added with the phone placement fixes.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent

PRELUDE = r'''
local V2 = {}
V2.__index = function(v, k) if k == "Magnitude" then return math.sqrt(v.X * v.X + v.Y * v.Y) end return nil end
local function new(x, y) return setmetatable({ X = x or 0, Y = y or 0 }, V2) end
V2.__add = function(a, b) return new(a.X + b.X, a.Y + b.Y) end
V2.__sub = function(a, b) return new(a.X - b.X, a.Y - b.Y) end
V2.__unm = function(a) return new(-a.X, -a.Y) end
V2.__mul = function(a, b)
	if type(a) == "number" then return new(a * b.X, a * b.Y) end
	if type(b) == "number" then return new(a.X * b, a.Y * b) end
	return new(a.X * b.X, a.Y * b.Y)
end
V2.__div = function(a, b) return new(a.X / b, a.Y / b) end
V2.__eq = function(a, b) return a.X == b.X and a.Y == b.Y end
Vector2 = { new = new, zero = new(0, 0) }
local game = { GetService = function() return { WaitForChild = function() return "UITheme" end } end }
local require = function() return { Color = {} } end
'''

module = (root / "TutorialGuideUI.luau").read_text(encoding="utf-8-sig")
tests = (root / "TutorialGuideTests.luau").read_text(encoding="utf-8-sig")
source = (
    PRELUDE
    + f"local G=(function()\n{module}\nend)()\n"
    + f"local Tests=(function()\n{tests}\nend)()\n"
    + "print(('TutorialGuideTests: %d checks passed'):format(Tests(G)))\n"
)
with tempfile.TemporaryDirectory(prefix="roguelite-tutorial-guide-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
