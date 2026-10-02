"""Studio sync manifest for plan J (items 6-12), from this plan's own commits only.

    python roguelite-planning/studio-prototype/tools/plan_j_sync.py

Writes studio-prototype/combat/plan-j-sync.json for tools/SyncPlan.luau:
  modules  the two new modules (LegendaryMoves, LegendaryVisuals), created with their neighbours'
           Sandboxed and Capabilities
  remotes  the LegendaryFX RemoteEvent
  hunks    every hunk of every plan J commit to a script Studio runs, as 'swap' edits: the exact
           lines before (with 3 lines of context) and after. They apply in commit order, so a
           script that other sessions also changed (and synced) only gets plan J's lines.
Then in Studio (dev_server.py running), dry run first:
  local HS=game:GetService('HttpService');local base='http://127.0.0.1:8934/'
  return loadstring(HS:GetAsync(base..'studio-prototype/tools/SyncPlan.luau?t='..os.clock(),true))()(base,'studio-prototype/combat/plan-j-sync.json',true)
"""
import json
import subprocess
from pathlib import Path

PROTO = Path(__file__).resolve().parent.parent
REPO = PROTO.parent.parent
PREFIX = "roguelite-planning/studio-prototype/"
# Plan J commits, oldest first (revives, analytics, rarity, Legendary moves, flat VFX, Play Again
# and rejoin, leaderboards, review fixes).
COMMITS = ["5ee82d5", "ae2c290", "a1b842e", "3f68fe1", "8d2fbf1", "6836364", "cbe572e"]
EXTRA = PROTO / "tools" / "plan_j_commits_extra.txt"  # later fixes, one sha per line
if EXTRA.exists():
    COMMITS += [l.strip() for l in EXTRA.read_text().splitlines() if l.strip() and not l.startswith("#")]
STUDIO = {
    "combat/MonetizationConfig.luau": "ReplicatedStorage.RogueliteCombat.MonetizationConfig",
    "combat/RogueliteMeta.server.luau": "ServerScriptService.RogueliteMeta",
    "combat/RunAnalytics.luau": "ServerScriptService.RunAnalytics",
    "ui/DeathScreenUI.luau": "ReplicatedStorage.DeathScreenUI",
    "combat/ShopService.luau": "ServerScriptService.ShopService",
    "combat/CombatEffectsService.luau": "ServerScriptService.CombatEffectsService",
    "ui/RogueliteHUD.client.luau": "StarterPlayer.StarterPlayerScripts.RogueliteHUD",
    "combat/WeaponCatalog.luau": "ReplicatedStorage.RogueliteCombat.WeaponCatalog",
    "combat/ChestConfig.luau": "ReplicatedStorage.RogueliteCombat.ChestConfig",
    "combat/EconomyConfig.luau": "ReplicatedStorage.RogueliteCombat.EconomyConfig",
    "combat/ShopCatalog.luau": "ReplicatedStorage.RogueliteCombat.ShopCatalog",
    "combat/RogueliteCombat.server.luau": "ServerScriptService.RogueliteCombat",
    "combat/RogueliteCombat.client.luau": "StarterPlayer.StarterPlayerScripts.RogueliteCombat",
    "combat/SpecialWeapons.luau": "ServerScriptService.SpecialWeapons",
    "audio/RogueliteSounds.client.luau": "StarterPlayer.StarterPlayerScripts.RogueliteSounds",
    "lobby/MatchService.luau": "ServerScriptService.MatchService",
    "ui/RunResultsUI.luau": "ReplicatedStorage.RunResultsUI",
    "combat/LeaderboardService.server.luau": "ServerScriptService.LeaderboardService",
}
MODULES = [
    {"path": "combat/LegendaryMoves.luau", "parent": "ServerScriptService", "name": "LegendaryMoves",
     "sandboxLike": "ServerScriptService.GodlyWeapons"},
    {"path": "combat/LegendaryVisuals.luau", "parent": "ReplicatedStorage.RogueliteCombat", "name": "LegendaryVisuals",
     "sandboxLike": "ReplicatedStorage.RogueliteCombat.GodlyVisuals"},
]
REMOTES = [{"parent": "ReplicatedStorage.RogueliteCombat", "name": "LegendaryFX",
            "sandboxLike": "ReplicatedStorage.RogueliteCombat.GodlyFX"}]


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, check=True).stdout.decode("utf-8")


def hunks_of(sha, path):
    """(before, after) pairs for one commit's diff of one file; CRLF dropped."""
    out, before, after, inside = [], [], [], False
    diff = git("show", "-U3", "--format=", sha, "--", PREFIX + path).replace("\r", "")
    for line in diff.split("\n"):
        if line.startswith("@@"):
            if inside:
                out.append(("\n".join(before), "\n".join(after)))
            before, after, inside = [], [], True
        elif not inside or line.startswith("\\"):
            continue
        elif line.startswith("+"):
            after.append(line[1:])
        elif line.startswith("-"):
            before.append(line[1:])
        elif line.startswith(" ") or line == "":
            before.append(line[1:]); after.append(line[1:])
    if inside:
        out.append(("\n".join(before), "\n".join(after)))
    # A trailing empty line from the diff's final newline is context, not content.
    return [(b.rstrip("\n"), a.rstrip("\n")) for b, a in out]


def main():
    import sys
    head = git("rev-parse", "--short", "HEAD").strip()
    # Arguments: commit shas to take hunks from (default: all of COMMITS). --modules-only: no hunks
    # (Studio's scripts already hold them, e.g. after a Rojo sync of the repo).
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    commits = [] if "--modules-only" in sys.argv else (args or COMMITS)
    hunks = []
    for sha in commits:
        changed = git("show", "--name-only", "--format=", sha).split()
        for full in changed:
            if not full.startswith(PREFIX):
                continue
            path = full[len(PREFIX):]
            if path not in STUDIO:
                continue
            for i, (before, after) in enumerate(hunks_of(sha, path)):
                hunks.append({"repo": path, "studio": STUDIO[path], "where": "swap", "before": before, "after": after,
                              "label": f"{sha} {path} #{i + 1}"})
    manifest = {"modules": [dict(m, base=head) for m in MODULES], "remotes": REMOTES, "hunks": hunks}
    out = PROTO / "combat" / "plan-j-sync.json"
    out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)}: {len(hunks)} hunks over {len({h['studio'] for h in hunks})} scripts, "
          f"{len(MODULES)} modules, {len(REMOTES)} remote")


main()
