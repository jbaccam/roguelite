"""Run AdminCommandTests against the real AdminCommands, WeaponCatalog and ShopCatalog in the Luau CLI.

Usage: python run_admin_command_tests.py path/to/luau.exe
AdminCommands is pure. The catalogs run unchanged except for their script.Parent requires (the
same adapters and Roblox datatype shims as run_turret_tests.py). 2026-10-12: added with the admin
chat commands.
"""
import pathlib
import subprocess
import sys
import tempfile

root = pathlib.Path(__file__).resolve().parent
PRELUDE = (root / "run_turret_tests.py").read_text(encoding="utf-8").split("PRELUDE = r'''", 1)[1].split("'''", 1)[0]


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
source += module("Commands", "AdminCommands.luau")
source += module("Tests", "AdminCommandTests.luau")
source += "print('AdminCommandTests: '..Tests(Commands,Weapons,Catalog)..' checks passed')\n"
with tempfile.TemporaryDirectory(prefix="roguelite-admin-") as temporary:
    path = pathlib.Path(temporary) / "tests.luau"
    path.write_text(source, encoding="utf-8")
    subprocess.run([str(pathlib.Path(sys.argv[1]).resolve()), str(path)], check=True)
