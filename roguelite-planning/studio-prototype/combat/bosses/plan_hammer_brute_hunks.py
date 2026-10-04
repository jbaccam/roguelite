"""Hammer Brute rebuild's anchored edits to shared scripts (plans/2026-10-03-hammer-brute-build-steps.md).
Other sessions edit these files too, so only these hunks are ours; R7 adds its consumer edits here.
MapBossPresentation, MapBossService, BossVfx/* and the other combat/bosses files are whole modules.
    python plan_hammer_brute_hunks.py [--check] [--stage] [--json]   (see tools/hunks.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from hunks import run  # noqa: E402

INTRO = "combat/BossIntro.client.luau"
INTRO_S = "StarterPlayer.StarterPlayerScripts.BossIntro"

HUNKS = [
    # --- R4 BossIntro: map bosses with a sky-drop entrance (MapBossService def.intro) -------------
    (INTRO, INTRO_S,
     "-- locally; it is put back on the server's spot at the landing. The camera is always handed back.", "after",
     "-- Map bosses with a def.intro (MapBossService; the Hammer Brute) set the same attributes and\n"
     "-- BossIntroName, and MapBossPresentation plays their intro clip (IntroLand) timed to the landing."),
    (INTRO, INTRO_S,
     " local ui=overlay(NAMES[npc:GetAttribute('ZombieType')] or string.upper(npc.Name))", "replace",
     " -- The card: the old Hammer's name, else the map boss's BossIntroName (MapBossDefs introName), else\n"
     " -- its BossName in capitals.\n"
     " local ui=overlay(NAMES[npc.Name] or npc:GetAttribute('BossIntroName') or string.upper(npc:GetAttribute('BossName') or npc.Name))"),
    (INTRO, INTRO_S,
     "for _,npc in Tags:GetTagged('HammerBoss') do watchBoss(npc) end", "after",
     "-- Map bosses play it only with a sky-drop entrance (BossIntroStart). The tag can land a moment\n"
     "-- before the intro attributes, so a boss without them yet is given 2 s for BossIntroStart.\n"
     "local function watchMapBoss(npc)\n"
     " if npc:GetAttribute('BossIntroStart')~=nil then watchBoss(npc);return end\n"
     " local c;c=npc:GetAttributeChangedSignal('BossIntroStart'):Connect(function() c:Disconnect();watchBoss(npc) end)\n"
     " task.delay(2,function() if c.Connected then c:Disconnect() end end)\n"
     "end\n"
     "Tags:GetInstanceAddedSignal('MapBoss'):Connect(watchMapBoss)\n"
     "for _,npc in Tags:GetTagged('MapBoss') do watchMapBoss(npc) end"),
]

if __name__ == "__main__":
    run(HUNKS)
