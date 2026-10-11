"""Run BossArrivalTests and TeammateReviveTests (with the revive shove) in the Luau CLI.

Usage: python run_survival_tests.py path/to/luau.exe
2026-10-10: added with the boss arrival i-frames and the revive shove; later that day the easier
teammate revive (2.5 s, faster with helpers, slow drain, 20-stud reach, the reviver guard). CharacterStats is the real
source with its motion requires stubbed (as run_chef_pizza_tests.py does); TeammateRevive is the real
source with a Vector3 shim and stand-in services (its tests inject the clock, view and positions).
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent

PRELUDE = r'''
Vector3 = {}
local mt = {}
function Vector3.new(x, y, z) return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, mt) end
mt.__add = function(a, b) return Vector3.new(a.X + b.X, a.Y + b.Y, a.Z + b.Z) end
mt.__sub = function(a, b) return Vector3.new(a.X - b.X, a.Y - b.Y, a.Z - b.Z) end
mt.__unm = function(a) return Vector3.new(-a.X, -a.Y, -a.Z) end
mt.__mul = function(a, b) if type(a) == "number" then a, b = b, a end return Vector3.new(a.X * b, a.Y * b, a.Z * b) end
mt.__div = function(a, b) return Vector3.new(a.X / b, a.Y / b, a.Z / b) end
mt.__eq = function(a, b) return a.X == b.X and a.Y == b.Y and a.Z == b.Z end
local methods = { Dot = function(a, b) return a.X * b.X + a.Y * b.Y + a.Z * b.Z end }
mt.__index = function(a, k)
	if k == "Magnitude" then return math.sqrt(a.X * a.X + a.Y * a.Y + a.Z * a.Z) end
	if k == "Unit" then local m = math.sqrt(a.X * a.X + a.Y * a.Y + a.Z * a.Z) return Vector3.new(a.X / m, a.Y / m, a.Z / m) end
	return methods[k]
end
Vector3.zero, Vector3.one = Vector3.new(0, 0, 0), Vector3.new(1, 1, 1)
Vector3.xAxis, Vector3.yAxis, Vector3.zAxis = Vector3.new(1, 0, 0), Vector3.new(0, 1, 0), Vector3.new(0, 0, 1)
local service = setmetatable({}, { __index = function() return function() return {} end end })
game = { GetService = function() return service end }
task = { spawn = function(f, ...) f(...) end }
'''


def module(name, filename, substitutions=()):
    source = (root / filename).read_text(encoding="utf-8-sig")
    for before, after in substitutions:
        assert before in source, f"Missing test adapter in {filename}: {before}"
        source = source.replace(before, after)
    return f"local {name}=(function()\n{source}\nend)()\n"


source = PRELUDE
source += module("Weapons", "WeaponCatalog.luau")
source += module("Stats", "CharacterStats.luau", [
    ("local Motion=require(script.Parent.WeaponMotion)", "local Motion={}"),
    ("local Weapons=require(script.Parent.WeaponCatalog)", "local Weapons=Weapons"),
    ("local Thrown=require(script.Parent.SpecialMotion).profiles", "local Thrown={}"),
])
source += module("Revive", "TeammateRevive.luau")
source += module("BossArrivalTests", "BossArrivalTests.luau")
source += module("ReviveTests", "TeammateReviveTests.luau")
source += "print('BossArrivalTests: '..BossArrivalTests(Stats)..' checks passed')\n"
source += "print('TeammateReviveTests: '..ReviveTests(Revive)..' checks passed (with the revive shove)')\n"
with tempfile.TemporaryDirectory(prefix="roguelite-survival-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
