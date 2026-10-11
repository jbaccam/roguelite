"""Run ChefPizzaTests against the real ChefPizza rules in the Luau CLI.

Usage: python run_chef_pizza_tests.py path/to/luau.exe
ChefPizza needs nothing from Roblox. CharacterStats is loaded with its two motion
requires stubbed so Recovery uses the real Stats.mult; if those anchor lines have
moved, the tests fall back to CharacterService.heal's formula and say so.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent


def module(name, filename, substitutions=()):
    source = (root / filename).read_text(encoding="utf-8-sig")
    for before, after in substitutions:
        if before not in source:
            return None
        source = source.replace(before, after)
    return f"local {name}=(function()\n{source}\nend)()\n"


source = module("Pizza", "ChefPizza.luau")
# CharacterStats reads WeaponCatalog since 2026-10-09 (starter classes and weapon types).
weapons = module("Weapons", "WeaponCatalog.luau")
stats = module("Stats", "CharacterStats.luau", [
    ("local Motion=require(script.Parent.WeaponMotion)", "local Motion={}"),
    ("local Weapons=require(script.Parent.WeaponCatalog)", "local Weapons=Weapons"),
    ("local Thrown=require(script.Parent.SpecialMotion).profiles", "local Thrown={}"),
])
if stats is not None and weapons is not None:
    stats = weapons + stats
if stats is None:
    print("CharacterStats anchors moved: Recovery checked with CharacterService.heal's formula")
    source += "local Stats=nil\n"
    # The catalog alone still drives the per-weapon class-tag checks.
    source += weapons if weapons is not None else "local Weapons=nil\n"
else:
    source += stats
source += module("Tests", "ChefPizzaTests.luau")
source += "print('ChefPizzaTests: '..Tests(Pizza,Stats,Weapons)..' checks passed'..(Stats and ' (real Stats.mult)' or '')..(Weapons and ', real WeaponCatalog' or ''))\n"
with tempfile.TemporaryDirectory(prefix="roguelite-chef-pizza-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
