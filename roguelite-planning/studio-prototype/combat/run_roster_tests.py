"""Pure roster checks (2026-10-09 Chef / weapon types) without Studio.

Usage: python run_roster_tests.py path/to/luau.exe
Runs WeaponClassTagTests, WeaponTypeTests, RosterBalanceTests, RunSetupValidationTests,
NormalBalanceTests, GearPowerTests and WeaponShowcaseTests on the real source. Only Roblox
module wiring is replaced (by exact anchors, as in run_enemy_scaling_tests.py).
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent
proto = root.parent


def module(name, path, substitutions=()):
    source = (proto / path).read_text(encoding="utf-8-sig")
    for before, after in substitutions:
        assert before in source, f"Missing test adapter in {path}: {before}"
        source = source.replace(before, after)
    return f"local {name}=(function()\n{source}\nend)()\n"


source = module("Weapons", "combat/WeaponCatalog.luau")
source += module("SpecialMotion", "combat/SpecialMotion.luau")
source += module("Stats", "combat/CharacterStats.luau", [
    ("local Motion=require(script.Parent.WeaponMotion)", "local Motion={}"),
    ("local Weapons=require(script.Parent.WeaponCatalog)", "local Weapons=Weapons"),
    ("local Thrown=require(script.Parent.SpecialMotion).profiles", "local Thrown=SpecialMotion.profiles"),
])
source += module("Playable", "combat/MapConfig.luau")
source += module("Rules", "lobby/RunSetupRules.luau", [
    ("local RS=game:GetService('ReplicatedStorage')", ""),
    ("local combat=RS:WaitForChild('RogueliteCombat')", ""),
    ("local Weapons=require(combat:WaitForChild('WeaponCatalog'))", ""),
    ("local Stats=require(combat:WaitForChild('CharacterStats'))", ""),
    ("local Playable=require(combat:WaitForChild('MapConfig'))", ""),
])
source += module("Types", "combat/ZombieTypes.luau")
source += module("Enemies", "combat/EnemyCatalog.luau", [
    ("local Types = require(script.Parent.ZombieTypes)", ""),
    ("local MotionTuning = require(script.Parent.EnemyMotionTuning)", "local MotionTuning = {}"),
])
source += module("Showcase", "ui/WeaponShowcaseCatalog.luau")
source += module("ClassTagTests", "combat/WeaponClassTagTests.luau")
source += "print('WeaponClassTagTests: '..ClassTagTests(Weapons).checks..' checks')\n"
source += module("TypeTests", "combat/WeaponTypeTests.luau")
source += "print('WeaponTypeTests: '..TypeTests(Weapons,Stats,Rules)..' checks')\n"
source += module("ValidationTests", "lobby/RunSetupValidationTests.luau")
source += "print('RunSetupValidationTests: '..ValidationTests.run(Rules).passed..' checks')\n"
source += module("ShowcaseTests", "ui/WeaponShowcaseTests.luau")
source += "print('WeaponShowcaseTests: '..ShowcaseTests.run(Weapons,Showcase).passed..' checks')\n"
source += module("GearTests", "combat/GearPowerTests.luau")
source += "print('GearPowerTests: '..GearTests(Stats,Rules)..' checks')\n"
source += module("NormalTests", "combat/NormalBalanceTests.luau")
source += "NormalTests(Enemies,Weapons,Stats,Rules)\n"
source += module("RosterTests", "combat/RosterBalanceTests.luau")
source += "print('RosterBalanceTests: '..RosterTests(Weapons,Stats)..' checks')\n"
with tempfile.TemporaryDirectory(prefix="roguelite-roster-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
