"""Run ProfileMigrationTests without Studio (2026-10-16).

Usage (from the repo root):
  python roguelite-planning/studio-prototype/combat/run_profile_migration_tests.py build/luau-validation/luau.exe

Inlines the real WeaponCatalog (with SpecialMotion and CharacterStats, which it needs), MonetizationConfig,
ArmorCatalog, PetConfig and ChestConfig, then hands ProfileService.luau's text to ProfileMigrationTests, which
loads it with its own stand-ins for Roblox services (no DataStores, nothing saved). Only Roblox module wiring
is replaced, like run_shop_tests.py.
"""
import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent


def text(filename):
    return (root / filename).read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def module(name, filename):
    source = text(filename)
    source = re.sub(r"require\(script\.Parent:WaitForChild\('(\w+)'\)\)", r"MODULES.\1", source)
    source = re.sub(r"require\(script\.Parent\.(\w+)\)", r"MODULES.\1", source)
    source = re.sub(r"require\(game\.ReplicatedStorage\.RogueliteCombat\.(\w+)\)", r"(MODULES.\1 or {})", source)
    return f"MODULES.{name}=(function()\n{source}\nend)()\n"


source = "local MODULES={WeaponMotion={}}\n"
source += "local game={GetService=function() return {} end,ReplicatedStorage={RogueliteCombat={}}}\n"
# Data modules build colours and vectors at load; plain tables stand in.
source += "local function value(...) return {...} end\n"
source += "local Color3={fromRGB=value,new=value,fromHex=value} local Vector3={new=value} local Vector2={new=value}\n"
source += "local CFrame={new=value,Angles=value} local NumberSequence={new=value} local ColorSequence={new=value}\n"
for name in ["WeaponCatalog", "SpecialMotion", "CharacterStats", "MonetizationConfig", "ArmorCatalog", "PetConfig", "ChestConfig"]:
    source += module(name, name + ".luau")
source += "local Tests=(function()\n" + text("ProfileMigrationTests.luau") + "\nend)()\n"
source += "local M=MODULES\n"
service = text("ProfileService.luau")
level = next(n for n in range(1, 20) if "]" + "=" * n + "]" not in service)
source += "print('ProfileMigrationTests: '..Tests([" + "=" * level + "[\n" + service + "]" + "=" * level + "],{WeaponCatalog=M.WeaponCatalog,MonetizationConfig=M.MonetizationConfig,ChestConfig=M.ChestConfig,PetConfig=M.PetConfig,ArmorCatalog=M.ArmorCatalog})..' checks passed')\n"
with tempfile.TemporaryDirectory(prefix="roguelite-profile-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
