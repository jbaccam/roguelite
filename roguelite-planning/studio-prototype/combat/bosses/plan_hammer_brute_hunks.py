"""Hammer Brute rebuild's anchored edits to shared scripts (plans/2026-10-03-hammer-brute-build-steps.md).
Other sessions edit these files too, so only these hunks are ours; R7 adds its consumer edits here.
MapBossPresentation, MapBossService, BossVfx/* and the other combat/bosses files are whole modules,
except MapBossServiceTests, which another session had open when R6-R7 landed (2026-10-03).
    python plan_hammer_brute_hunks.py [--check] [--stage] [--json]   (see tools/hunks.py)
R7: the rebuilt Hammer is a map boss (IsMapBoss, tag MapBoss, MapBossId 'Hammer', skinned sections
HammerBrute_*). Every 'Hammer' spawn checks MapBossDefs.ready('Hammer') and keeps the old BossService
Hammer until his def, timing, clips and template are all in the place.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from hunks import run  # noqa: E402

INTRO = "combat/BossIntro.client.luau"
INTRO_S = "StarterPlayer.StarterPlayerScripts.BossIntro"
CHASE = "RogueliteZombieChase.server.luau"
CHASE_S = "ServerScriptService.RogueliteZombieChase"
COMBAT = "combat/RogueliteCombat.server.luau"
COMBAT_S = "ServerScriptService.RogueliteCombat"
TURRET = "combat/HandymanTurretService.server.luau"
TURRET_S = "ServerScriptService.HandymanTurretService"
PETS = "combat/PetService.server.luau"
PETS_S = "ServerScriptService.PetService"
GUIDE = "ui/TutorialGuide.client.luau"
GUIDE_S = "StarterPlayer.StarterPlayerScripts.TutorialGuide"
TESTS = "combat/bosses/MapBossServiceTests.luau"  # run from the repo (tools/RepoRequire), not synced

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

    # --- R7 RogueliteZombieChase: the admin and Endless 'Hammer' spawns -------------------------------
    (CHASE, CHASE_S,
     ("-- The Hammer stays on BossService until MapBossDefs has his def (as BossEncounter does).",
      "local function oldHammer(id, defs) return id == 'Hammer' and not (defs and defs.get('Hammer')) end"), "block",
     "-- A map boss this place can run: MapBossDefs.ready (its def, timing, client clips and template).\n"
     "-- A MapBossDefs from before ready() (Studio behind the repo) is read the old way, Hammer excluded.\n"
     "local function mapReady(id, defs)\n"
     "    if not defs then return false end\n"
     "    if defs.ready then return defs.ready(id) end\n"
     "    local def, anims = defs.get(id), combat:FindFirstChild('BossAnimations')\n"
     "    return id ~= 'Hammer' and def ~= nil and templates:FindFirstChild(id .. '_NPC') ~= nil and anims ~= nil and anims:FindFirstChild(def.anim) ~= nil and defs.timing(id) ~= nil\n"
     "end\n"
     "-- The Hammer stays on BossService until the rebuilt Hammer Brute is ready here (as BossEncounter does).\n"
     "local function oldHammer(id, defs) return id == 'Hammer' and not mapReady(id, defs) end"),
    (CHASE, CHASE_S,
     "    local defs, anims, list = bossDefs(), combat:FindFirstChild('BossAnimations'), {}", "replace",
     "    local defs, list = bossDefs(), {}"),
    (CHASE, CHASE_S,
     ("        if oldHammer(id, defs) then ok = templates:FindFirstChild('HammerBoss_NPC') ~= nil",
      "            ok = def ~= nil and templates:FindFirstChild(id .. '_NPC') ~= nil and anims ~= nil and anims:FindFirstChild(def.anim) ~= nil and defs.timing(id) ~= nil"), "block",
     "        if oldHammer(id, defs) then ok = templates:FindFirstChild('HammerBoss_NPC') ~= nil\n"
     "        else\n"
     "            ok = mapReady(id, defs)"),
    (CHASE, CHASE_S,
     "            if id == 'Hammer' then", "replace",
     "            -- The old BossService Hammer until the rebuilt one is ready (oldHammer); then the map-boss path below.\n"
     "            if oldHammer(id, bossDefs()) then"),

    # --- R7 RogueliteCombat: the shell weapons measure to, and the melee aim at it ------------------
    (COMBAT, COMBAT_S,
     "local HELD={Hammer=true,LeftHand=true,RightHand=true}", "after",
     "-- The rebuilt Hammer Brute (a map boss, MapBossId 'Hammer') is skinned: his hands are part of his\n"
     "-- body mesh, and only the hammer is its own section.\n"
     "local HELD_BRUTE={HammerBrute_Hammer=true}\n"
     "-- The sections left out of a boss's shell: the old Hammer's hammer and hands, the new one's hammer.\n"
     "-- Non-nil only for a Hammer Brute, old or rebuilt.\n"
     "local function heldBy(npc) if npc:GetAttribute('IsHammerBoss')==true then return HELD end;return npc:GetAttribute('MapBossId')=='Hammer' and HELD_BRUTE or nil end"),
    (COMBAT, COMBAT_S,
     " local hammer=npc:GetAttribute('IsHammerBoss')==true", "replace",
     " local skip=heldBy(npc)"),
    (COMBAT, COMBAT_S,
     "  if p.Parent==npc and not (hammer and HELD[p.Name]) then", "replace",
     "  if p.Parent==npc and not (skip and skip[p.Name]) then"),
    (COMBAT, COMBAT_S,
     ("    -- A melee swing at the Hammer Brute lands on his shell (that point), not inside him at his root;",
      "    local aim=d.kind=='Melee' and target.Parent:GetAttribute('IsHammerBoss') and (reach-origin).Magnitude>.1 and reach or target.Position"), "block",
     "    -- A melee swing at the Hammer Brute (old or rebuilt) lands on his shell (that point), not inside\n"
     "    -- him at his root; standing inside a body section, it still swings at his root.\n"
     "    local aim=d.kind=='Melee' and heldBy(target.Parent)~=nil and (reach-origin).Magnitude>.1 and reach or target.Position"),

    # --- R7 turrets and pets measure to the same shell ------------------------------------------------
    (TURRET, TURRET_S,
     "  if p:IsA('MeshPart') and not (e.hammer and (p.Name=='Hammer' or p.Name=='LeftHand' or p.Name=='RightHand')) then", "replace",
     "  -- Not the Hammer Brute's hammer (nor the old one's hands): RogueliteCombat.server reachPoint.\n"
     "  if p:IsA('MeshPart') and p.Name~='HammerBrute_Hammer' and not (e.hammer and (p.Name=='Hammer' or p.Name=='LeftHand' or p.Name=='RightHand')) then"),
    (PETS, PETS_S,
     "\t\tif p:IsA(\"MeshPart\") or p == root then", "replace",
     "\t\t-- Not the rebuilt Hammer Brute's hammer: it isn't his body (RogueliteCombat.server reachPoint).\n"
     "\t\tif (p:IsA(\"MeshPart\") or p == root) and p.Name ~= \"HammerBrute_Hammer\" then"),

    # --- R7 TutorialGuide: the tutorial's boss is a map boss once the rebuilt Hammer is in --------------
    (GUIDE, GUIDE_S,
     "local function fightContext() return {edges=true,avoid=Tags:GetTagged('HammerBoss')} end", "replace",
     "-- The boss: the old Hammer (tag HammerBoss) or a map boss, the rebuilt Hammer Brute included (MapBoss).\n"
     "local function bosses() local list=Tags:GetTagged('HammerBoss');for _,npc in Tags:GetTagged('MapBoss') do table.insert(list,npc) end;return list end\n"
     "local function fightContext() return {edges=true,avoid=bosses()} end"),
    (GUIDE, GUIDE_S,
     "for _,npc in Tags:GetTagged('HammerBoss') do watchBoss(npc) end", "after",
     "Tags:GetInstanceAddedSignal('MapBoss'):Connect(watchBoss)\n"
     "for _,npc in Tags:GetTagged('MapBoss') do watchBoss(npc) end"),

    # --- R6 MapBossServiceTests: the real defs now include the Hammer --------------------------------
    (TESTS, None,
     " for _,id in Defs.Order do", "after",
     "  -- The Hammer Brute's def comes before his generated timing (rebuild R6): an id without one is skipped.\n"
     "  if not Defs.timing(id) then continue end"),
    (TESTS, None,
     " local function segd(a,b,p) local ab=b-a;local t=math.clamp((p-a):Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1);return (a+ab*t-p).Magnitude end", "before",
     " -- Every clip an attack, intro or roar plays is one the build generates (ATTACK_CLIPS, which\n"
     " -- build_boss_modules.py ATTACKS mirrors, and the client's aliased() reads).\n"
     " local unlisted={}\n"
     " for id in Defs do\n"
     "  local def=Defs.get(id)\n"
     "  if def then\n"
     "   local listed,used=Defs.ATTACK_CLIPS[def.anim] or {},{}\n"
     "   for _,a in def.attacks do for _,c in a.clips or {a.clip} do table.insert(used,c) end end\n"
     "   if def.intro then table.insert(used,def.intro.clip) end;if def.roar then table.insert(used,def.roar) end\n"
     "   for _,c in used do if not table.find(listed,c) then table.insert(unlisted,id..'.'..tostring(c)) end end\n"
     "  end\n"
     " end\n"
     " add(#unlisted==0,('every attack, intro and roar clip is in ATTACK_CLIPS (missing: %s)'):format(#unlisted>0 and table.concat(unlisted,', ') or 'none'))\n"
     " -- MapBossDefs.ready (rebuild R6): true exactly when the def, timing, client clips and template are\n"
     " -- all here, so 'Hammer' keeps the BossService Hammer until his template and animations are installed.\n"
     " local okReady,readyNow=pcall(function()\n"
     "  local anims=game.ReplicatedStorage.RogueliteCombat:FindFirstChild('BossAnimations');local npcs=game:GetService('ServerStorage'):FindFirstChild('RogueliteNPCs');local list={}\n"
     "  for _,id in Defs.Order do\n"
     "   local def=Defs.get(id);local want=def~=nil and Defs.timing(id)~=nil and anims~=nil and anims:FindFirstChild(def.anim)~=nil and npcs~=nil and npcs:FindFirstChild(id..'_NPC')~=nil\n"
     "   if Defs.ready(id)~=want then error(id..' ready '..tostring(Defs.ready(id))..', expected '..tostring(want)) end\n"
     "   if want then table.insert(list,id) end\n"
     "  end\n"
     "  assert(Defs.ready('Nope')==false,'an unknown id is ready')\n"
     "  assert(Defs.timing('Hammer')~=nil or Defs.ready('Hammer')==false,'the Hammer is ready without his timing')\n"
     "  return #list>0 and table.concat(list,', ') or 'none'\n"
     " end)\n"
     " add(okReady,('ready: only with def, timing, client clips and template all present (ready now: %s)'):format(tostring(readyNow)))"),
]

if __name__ == "__main__":
    run(HUNKS)
