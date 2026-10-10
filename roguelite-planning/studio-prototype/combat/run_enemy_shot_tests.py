"""Run EnemyShotTests (real EnemyAttacks/ZombieAttacks sources) without Studio.

Usage: python run_enemy_shot_tests.py path/to/luau.exe
Only Roblox datatypes are replaced, by small pure-Luau Vector3/CFrame/Color3/Enum
shims; the attack modules, shot flight, aim lock and client flight math run unchanged.
2026-10-10: added with the enemy aim lines (EnemyAttacks "Aim"), so they can be checked
without a Play session.
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
local methods = {
	Dot = function(a, b) return a.X * b.X + a.Y * b.Y + a.Z * b.Z end,
	Cross = function(a, b) return Vector3.new(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X) end,
}
mt.__index = function(a, k)
	if k == "Magnitude" then return math.sqrt(a.X * a.X + a.Y * a.Y + a.Z * a.Z) end
	if k == "Unit" then local m = math.sqrt(a.X * a.X + a.Y * a.Y + a.Z * a.Z) return Vector3.new(a.X / m, a.Y / m, a.Z / m) end
	return methods[k]
end
Vector3.zero, Vector3.one = Vector3.new(0, 0, 0), Vector3.new(1, 1, 1)
Vector3.xAxis, Vector3.yAxis, Vector3.zAxis = Vector3.new(1, 0, 0), Vector3.new(0, 1, 0), Vector3.new(0, 0, 1)
-- CFrames: only what the attack modules and tests use (lookAt, yaw Angles, LookVector).
CFrame = {}
local cmt = {}
cmt.__index = {
	VectorToWorldSpace = function(c, v) return Vector3.new(v.X * c.cos + v.Z * c.sin, v.Y, -v.X * c.sin + v.Z * c.cos) end,
}
function CFrame.Angles(x, y, z)
	assert(x == 0 and z == 0, "CFrame shim: yaw only")
	return setmetatable({ cos = math.cos(y), sin = math.sin(y), Position = Vector3.zero }, cmt)
end
function CFrame.lookAt(at, target)
	local look = (target - at).Unit
	return setmetatable({ Position = at, LookVector = look, cos = 1, sin = 0 }, cmt)
end
Vector2 = { new = function(x, y) return { X = x, Y = y, Magnitude = math.sqrt(x * x + y * y) } end }
Color3 = { fromRGB = function(r, g, b) return { R = r / 255, G = g / 255, B = b / 255 } end }
Enum = setmetatable({}, { __index = function(_, a) return setmetatable({}, { __index = function(_, b) return a .. "." .. b end }) end })
'''


def module(name, filename, substitutions=()):
    source = (root / filename).read_text(encoding="utf-8-sig")
    for before, after in substitutions:
        assert before in source, f"Missing test adapter: {before}"
        source = source.replace(before, after)
    return f"local {name}=(function()\n{source}\nend)()\n"


def text(filename):
    source = (root / filename).read_text(encoding="utf-8-sig")
    level = "=" * 4
    while f"]{level}]" in source:
        level += "="
    return f"[{level}[\n{source}]{level}]"


source = PRELUDE
source += module("Types", "ZombieTypes.luau")
source += module("Catalog", "EnemyCatalog.luau", [
    ("local Types = require(script.Parent.ZombieTypes)", ""),
    ("local MotionTuning = require(script.Parent.EnemyMotionTuning)", "local MotionTuning = {}"),
])
source += module("Visuals", "EnemyProjectileVisuals.luau")
source += module("Tests", "EnemyShotTests.luau")
source += f"local result=Tests({{EnemyAttacks={text('EnemyAttacks.luau')},ZombieAttacks={text('ZombieAttacks.luau')}}},Visuals,Catalog,Types)\n"
source += "print(('EnemyShotTests: %d checks, %d frames compared, worst %.5f studs'):format(result.checks,result.comparedFrames,result.worstStuds))\n"
with tempfile.TemporaryDirectory(prefix="roguelite-enemy-shots-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
