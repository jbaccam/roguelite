"""Run TurretTests against the real HandymanTurret rules in the Luau CLI.

Usage: python run_turret_tests.py path/to/luau.exe
Only Roblox datatypes are replaced, by small pure-Luau Vector3/Vector2/CFrame/Random/typeof
shims (the ring jitter uses its own Random, so seeded spots differ from Studio's but every check
is about spacing, bands and order, not exact numbers). HandymanTurret, CharacterStats,
WeaponCatalog, EconomyConfig, ShopCatalog and TargetGrid run unchanged except for their
script.Parent requires. 2026-10-10: added with turret follow (HANDYMAN_TURRET.md).
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
local methods = {
	Dot = function(a, b) return a.X * b.X + a.Y * b.Y + a.Z * b.Z end,
	Cross = function(a, b) return Vector3.new(a.Y * b.Z - a.Z * b.Y, a.Z * b.X - a.X * b.Z, a.X * b.Y - a.Y * b.X) end,
	Lerp = function(a, b, t) return a + (b - a) * t end,
}
mt.__index = function(a, k)
	if k == "Magnitude" then return math.sqrt(a.X * a.X + a.Y * a.Y + a.Z * a.Z) end
	if k == "Unit" then local m = math.sqrt(a.X * a.X + a.Y * a.Y + a.Z * a.Z) return Vector3.new(a.X / m, a.Y / m, a.Z / m) end
	return methods[k]
end
Vector3.zero, Vector3.one = Vector3.new(0, 0, 0), Vector3.new(1, 1, 1)
Vector3.xAxis, Vector3.yAxis, Vector3.zAxis = Vector3.new(1, 0, 0), Vector3.new(0, 1, 0), Vector3.new(0, 0, 1)
Vector2 = { new = function(x, y) return { X = x, Y = y, Magnitude = math.sqrt(x * x + y * y) } end }
-- Yaw-only CFrames: TurretTests reads CFrame.Angles(0, yaw, 0).LookVector.
CFrame = {}
function CFrame.Angles(x, y, z)
	assert(x == 0 and z == 0, "CFrame shim: yaw only")
	return { LookVector = Vector3.new(-math.sin(y), 0, -math.cos(y)) }
end
-- A seeded LCG standing in for Random (jitter only).
Random = {}
function Random.new(seed)
	local state = (math.floor(tonumber(seed) or os.clock() * 1e6) % 2147483647) + 1
	local r = {}
	function r:NextNumber(lo, hi)
		state = (state * 48271) % 2147483647
		local u = state / 2147483647
		if lo then return lo + (hi - lo) * u end
		return u
	end
	return r
end
typeof = function(v)
	if type(v) == "table" and getmetatable(v) == mt then return "Vector3" end
	return type(v)
end
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
source += module("Economy", "EconomyConfig.luau")
source += module("H", "HandymanTurret.luau", [
    ("local Stats=require(script.Parent.CharacterStats)", "local Stats=Stats"),
    ("local Weapons=require(script.Parent.WeaponCatalog)", "local Weapons=Weapons"),
])
source += module("Catalog", "ShopCatalog.luau", [
    ("local Weapons=require(script.Parent.WeaponCatalog)", "local Weapons=Weapons"),
    ("local Economy=require(script.Parent.EconomyConfig)", "local Economy=Economy"),
    ("local Stats=require(script.Parent.CharacterStats)", "local Stats=Stats"),
    ("local turretOk,Turret=pcall(require,script.Parent:FindFirstChild('HandymanTurret'))", "local turretOk,Turret=true,H"),
])
source += module("Grid", "TargetGrid.luau")
source += module("Tests", "TurretTests.luau")
source += "print('TurretTests: '..Tests(H,Grid,Weapons,Stats,Economy,Catalog)..' checks passed')\n"
with tempfile.TemporaryDirectory(prefix="roguelite-turrets-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
