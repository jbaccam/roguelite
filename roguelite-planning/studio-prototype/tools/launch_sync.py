"""Builds tools/_launchsync/manifest.json for tools/LaunchSync.luau from a Studio dump.

    python tools/launch_sync.py <dump.json> <map.json> [--rev REV]

dump.json: {studio dot path: {class, sandboxed, source}} posted by a read-only execute_luau to the
dev server (POST /dump/<name>). map.json: {studio dot path: repo path under studio-prototype}.
Each existing script's guard is its dumped Source, saved under tools/_launchsync/guards/ so the
dev server serves it; LaunchSync writes the script only if Studio still holds exactly that.
NEW lists scripts the commit adds (no guard: they must not exist yet) and REMOTES the remotes.
The _launchsync folder is scratch: delete it after the sync.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # studio-prototype
OUT = ROOT / "tools" / "_launchsync"

NEW = [
    # studio path, repo path, class, copy Sandboxed + Capabilities from
    ("ServerScriptService.Contribution", "combat/Contribution.luau", "ModuleScript", "ServerScriptService.RunPause"),
    ("ServerScriptService.MovementCheck", "combat/MovementCheck.luau", "ModuleScript", "ServerScriptService.RunPause"),
    ("ServerScriptService.MovementGuard", "combat/MovementGuard.server.luau", "Script", "ServerScriptService.RogueliteMeta"),
    ("ServerScriptService.TeammateRevive", "combat/TeammateRevive.luau", "ModuleScript", "ServerScriptService.RunPause"),
    ("ServerScriptService.TargetGrid", "combat/TargetGrid.luau", "ModuleScript", "ServerScriptService.StatProjectiles"),
    ("ReplicatedStorage.RogueliteCombat.BulletFlights", "combat/BulletFlights.luau", "ModuleScript", "ReplicatedStorage.RogueliteCombat.MobImpactVisuals"),
    ("ReplicatedStorage.RogueliteCombat.HitFeedbackVisuals", "combat/HitFeedbackVisuals.luau", "ModuleScript", "ReplicatedStorage.RogueliteCombat.MobImpactVisuals"),
    ("StarterPlayer.StarterPlayerScripts.EnemyVisuals", "combat/EnemyVisuals.client.luau", "LocalScript", "StarterPlayer.StarterPlayerScripts.RogueliteZombieAnimation"),
    ("StarterPlayer.StarterPlayerScripts.TeammateReviveVisuals", "combat/TeammateReviveVisuals.client.luau", "LocalScript", "StarterPlayer.StarterPlayerScripts.RogueliteZombieAnimation"),
    ("StarterPlayer.StarterPlayerScripts.SaveStatus", "ui/SaveStatus.client.luau", "LocalScript", "StarterPlayer.StarterPlayerScripts.RogueliteHUD"),
    ("StarterPlayer.StarterPlayerScripts.SettingsSync", "ui/SettingsSync.client.luau", "LocalScript", "StarterPlayer.StarterPlayerScripts.RogueliteHUD"),
]
REMOTES = [
    {"parent": "ReplicatedStorage.RogueliteCombat", "name": "HitFX", "class": "UnreliableRemoteEvent", "sandboxLike": "ReplicatedStorage.RogueliteCombat.Hit"},
]


def main():
    dump = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    mapping = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    rev = sys.argv[sys.argv.index("--rev") + 1] if "--rev" in sys.argv else subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    (OUT / "guards").mkdir(parents=True, exist_ok=True)
    scripts = []
    for studio, repo in mapping.items():
        entry = dump[studio]
        guard = OUT / "guards" / (re.sub(r"[^\w.-]", "_", studio) + ".luau")
        guard.write_text(entry["source"].replace("\r\n", "\n"), encoding="utf-8", newline="\n")
        scripts.append({"studio": studio, "repo": repo, "class": entry["class"],
                        "guard": "studio-prototype/tools/_launchsync/guards/" + guard.name})
    for studio, repo, cls, like in NEW:
        scripts.append({"studio": studio, "repo": repo, "class": cls, "sandboxLike": like})
    manifest = {"rev": rev, "scripts": scripts, "remotes": REMOTES}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"{len(scripts)} scripts ({len(NEW)} new), {len(REMOTES)} remotes, rev {rev}")


if __name__ == "__main__":
    main()
