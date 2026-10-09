"""Run the pure shop and stream-area tests without Studio or persistent services (2026-10-09).

Usage (from the repo root):
  python roguelite-planning/studio-prototype/combat/run_shop_tests.py build/luau-validation/luau.exe

Inlines the real catalogs (WeaponCatalog, SpecialMotion, CharacterStats, EconomyConfig,
HandymanTurret, ShopCatalog, LevelUpCatalog) and UtilityWeapons' pure Area Size rule, then runs
ShopPreferenceTests, DuckBurstTests.area and WasherBurstTests.area. Only Roblox module wiring is
replaced: `require(script.Parent.X)` and `require(game.ReplicatedStorage.RogueliteCombat.X)` read
the module loaded above, WeaponMotion is an empty table (CharacterStats only requires it) and
`game` is a stub (UtilityWeapons' W.new, which needs services, is never called).
"""
import pathlib
import re
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent


def module(name, filename):
    source = (root / filename).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    source = source.replace("pcall(require,script.Parent:FindFirstChild('HandymanTurret'))", "true,MODULES.HandymanTurret")
    source = re.sub(r"require\(script\.Parent\.(\w+)\)", r"MODULES.\1", source)
    source = re.sub(r"require\(game\.ReplicatedStorage\.RogueliteCombat\.(\w+)\)", r"(MODULES.\1 or {})", source)
    source = re.sub(r"require\(RS\.RogueliteCombat\.(\w+)\)", r"(MODULES.\1 or {})", source)
    return f"MODULES.{name}=(function()\n{source}\nend)()\n"


source = "local MODULES={WeaponMotion={}}\n"
source += "local game={GetService=function() return {} end,ReplicatedStorage={RogueliteCombat={}}}\n"
for name, filename in [
    ("WeaponCatalog", "WeaponCatalog.luau"),
    ("SpecialMotion", "SpecialMotion.luau"),
    ("CharacterStats", "CharacterStats.luau"),
    ("EconomyConfig", "EconomyConfig.luau"),
    ("HandymanTurret", "HandymanTurret.luau"),
    ("ShopCatalog", "ShopCatalog.luau"),
    ("LevelUpCatalog", "LevelUpCatalog.luau"),
    ("UtilityWeapons", "UtilityWeapons.luau"),
    ("ShopPreferenceTests", "ShopPreferenceTests.luau"),
    ("DuckBurstTests", "DuckBurstTests.luau"),
    ("WasherBurstTests", "WasherBurstTests.luau"),
]:
    source += module(name, filename)
source += """local M=MODULES
print('ShopPreferenceTests: '..M.ShopPreferenceTests(M.WeaponCatalog,M.CharacterStats,M.EconomyConfig,M.ShopCatalog,M.LevelUpCatalog)..' checks passed')
print('DuckBurstTests.area: '..M.DuckBurstTests.area(M.UtilityWeapons)..' checks passed')
print('WasherBurstTests.area: '..M.WasherBurstTests.area(M.UtilityWeapons)..' checks passed')
"""
with tempfile.TemporaryDirectory(prefix="roguelite-shop-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
