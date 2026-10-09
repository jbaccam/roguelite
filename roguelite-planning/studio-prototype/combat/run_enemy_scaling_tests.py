"""Run actual pure Luau enemy/stat functions without Studio or persistent services.

Usage: python run_enemy_scaling_tests.py path/to/luau.exe
Only Roblox module wiring and unused motion dependencies are replaced. Source
math, catalogs, difficulty, gear power and Endless calculations execute unchanged.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent


def module(name, filename, substitutions=()):
    source = (root / filename).read_text(encoding="utf-8-sig")
    for before, after in substitutions:
        assert before in source, f"Missing test adapter: {before}"
        source = source.replace(before, after)
    return f"local {name}=(function()\n{source}\nend)()\n"


source = module("Types", "ZombieTypes.luau")
source += module("Catalog", "EnemyCatalog.luau", [
    ("local Types = require(script.Parent.ZombieTypes)", ""),
    ("local MotionTuning = require(script.Parent.EnemyMotionTuning)", "local MotionTuning = {}"),
])
source += module("Weapons", "WeaponCatalog.luau")
source += module("Stats", "CharacterStats.luau", [
    ("local Motion=require(script.Parent.WeaponMotion)", "local Motion={}"),
    ("local Weapons=require(script.Parent.WeaponCatalog)", "local Weapons=Weapons"),
    ("local Thrown=require(script.Parent.SpecialMotion).profiles", "local Thrown={}"),
])
source += module("Playable", "MapConfig.luau")
source += module("Rules", "../lobby/RunSetupRules.luau", [
    ("local RS=game:GetService('ReplicatedStorage')", ""),
    ("local combat=RS:WaitForChild('RogueliteCombat')", ""),
    ("local Weapons=require(combat:WaitForChild('WeaponCatalog'))", ""),
    ("local Stats=require(combat:WaitForChild('CharacterStats'))", ""),
    ("local Playable=require(combat:WaitForChild('MapConfig'))", ""),
])
source += module("Scheduler", "EnemyScheduler.luau")
source += module("Tests", "EnemyScalingTests.luau")
source += "Tests(Catalog,Types,Weapons,Stats,Rules,Scheduler)\n"
source += module("NormalTests", "NormalBalanceTests.luau")
source += "NormalTests(Catalog,Weapons,Stats,Rules)\n"
source += module("GearTests", "GearPowerTests.luau")
source += "print('GearPowerTests: '..GearTests(Stats,Rules)..' assertions')\n"
with tempfile.TemporaryDirectory(prefix="roguelite-enemy-scaling-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
