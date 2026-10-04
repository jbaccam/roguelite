"""Hammer Brute rebuild's anchored edits to shared scripts (plans/2026-10-03-hammer-brute-build-steps.md).
Other sessions edit these files too, so only these hunks are ours; R7 adds its consumer edits here.
MapBossPresentation, MapBossService, BossVfx/* and the other combat/bosses files are whole modules,
except MapBossServiceTests, which another session had open when R6-R7 landed (2026-10-03).
    python plan_hammer_brute_hunks.py [--check] [--stage] [--json]   (see tools/hunks.py)
R7: the rebuilt Hammer is a map boss (IsMapBoss, tag MapBoss, MapBossId 'Hammer', skinned sections
HammerBrute_*). Every 'Hammer' spawn asks MapBossDefs.legacy('Hammer') and keeps the old BossService
Hammer until his def, timing, clips, template and runtime are all in the place.
HUNKS go from the scripts before R7 (what Studio has until R8) straight to the final text.
FROM_20BFF04 moves the repo's 20bff04 text (the first R7 commit) to the same final text:
    python plan_hammer_brute_hunks.py --from-20bff04 --stage   (once, for the R6-R7 review fixes)
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

# --- Final texts (R7 and the 2026-10-03 review fixes), shared by HUNKS and FROM_20BFF04 -----------
CHASE_GATE = (
    "-- MapBossService, or nil when this place lacks it or it fails to load. It never waits, so the old\n"
    "-- Hammer and the regular enemies never depend on the map-boss modules.\n"
    "local function mapBossService()\n"
    "    local module = script.Parent:FindFirstChild('MapBossService')\n"
    "    local ok, service = pcall(function() return module and require(module) end)\n"
    "    return ok and service or nil\n"
    "end\n"
    "-- A map boss this place can run: MapBossDefs.ready (its def, timing, client clips, template and\n"
    "-- runtime). A MapBossDefs from before ready() (Studio behind the repo) is read the old way.\n"
    "local function mapReady(id, defs)\n"
    "    if not defs then return false end\n"
    "    if defs.ready then return defs.ready(id) end\n"
    "    local def, anims = defs.get(id), combat:FindFirstChild('BossAnimations')\n"
    "    return id ~= 'Hammer' and def ~= nil and templates:FindFirstChild(id .. '_NPC') ~= nil and anims ~= nil and anims:FindFirstChild(def.anim) ~= nil and defs.timing(id) ~= nil\n"
    "end\n"
    "-- The Hammer stays on BossService until the rebuilt Hammer Brute is ready here: MapBossDefs.legacy,\n"
    "-- the gate BossEncounter asks too. A MapBossDefs without legacy() (older, or none) keeps the old one.\n"
    "local function oldHammer(id, defs)\n"
    "    if id ~= 'Hammer' then return false end\n"
    "    if defs and defs.legacy then local ok, old = pcall(defs.legacy, id); return not ok or old end\n"
    "    return true\n"
    "end")
CHASE_ADMIN = (
    "            -- The old BossService Hammer until the rebuilt one is ready (oldHammer); then the map-boss path below.\n"
    "            if id == 'Hammer' and oldHammer(id, bossDefs()) then")
GUIDE_LIST = (
    "-- The bosses: the old Hammer (tag HammerBoss) and map bosses, the rebuilt Hammer Brute included\n"
    "-- (MapBoss). Kept up to date by the tag signals below, not looked up every frame.\n"
    "local bossList={}\n"
    "local function fightContext() return {edges=true,avoid=bossList} end")
GUIDE_WATCH = (
    "local function listBosses() bossList=Tags:GetTagged('HammerBoss');for _,npc in Tags:GetTagged('MapBoss') do table.insert(bossList,npc) end end\n"
    "for _,tag in {'HammerBoss','MapBoss'} do Tags:GetInstanceAddedSignal(tag):Connect(listBosses);Tags:GetInstanceRemovedSignal(tag):Connect(listBosses) end\n"
    "listBosses()\n"
    "Tags:GetInstanceAddedSignal('MapBoss'):Connect(watchBoss)\n"
    "for _,npc in Tags:GetTagged('MapBoss') do watchBoss(npc) end")
TESTS_CLIPS = (
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
    " add(#unlisted==0,('every attack, intro and roar clip is in ATTACK_CLIPS (missing: %s)'):format(#unlisted>0 and table.concat(unlisted,', ') or 'none'))")
TESTS_LEGACY = (
    " -- MapBossDefs.legacy / ready (rebuild R6): the one gate every 'Hammer' spawn asks. A stubbed\n"
    " -- has(kind,name) stands in for the place, so each missing piece is tried on its own.\n"
    " check('legacy: the Hammer is the old one unless def, timing, clips, template, MapBossService and MapBossShapes are all here; never another boss',function()\n"
    "  local asked={};local function all(kind,name) asked[kind..':'..name]=true;return true end\n"
    "  if Defs.legacy('Hammer',all)~=false or Defs.ready('Hammer',all)~=true then return false end\n"
    "  for _,key in {'timing:Hammer','clips:hammer-brute','template:Hammer_NPC','server:MapBossService','shared:MapBossShapes'} do if not asked[key] then return false end end\n"
    "  for _,missing in {'timing','clips','template','server','shared'} do\n"
    "   local function has(kind) return kind~=missing end\n"
    "   if Defs.legacy('Hammer',has)~=true or Defs.ready('Hammer',has) then return false end\n"
    "  end\n"
    "  local function none() return false end\n"
    "  return Defs.legacy('KingCrab',none)==false and Defs.legacy('KingCrab',all)==false and not Defs.ready('KingCrab',none)\n"
    "   and Defs.legacy('Nope',all)==false and Defs.ready('Nope',all)==false\n"
    " end)\n"
    " -- In this place: the Hammer stays the old one while MapBossTiming has no 'hammer-brute'.\n"
    " local okNow,readyNow=pcall(function()\n"
    "  local list={};for _,id in Defs.Order do if Defs.ready(id) then table.insert(list,id) end end\n"
    "  assert(Defs.timing('Hammer')~=nil or Defs.legacy('Hammer')==true,'the Hammer is not legacy without his timing')\n"
    "  return #list>0 and table.concat(list,', ') or 'none'\n"
    " end)\n"
    " add(okNow,('legacy here: Hammer=%s (ready now: %s)'):format(tostring(okNow and Defs.legacy('Hammer')),tostring(readyNow)))")

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
     CHASE_GATE),
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
     "    else boss = require(script.Parent:WaitForChild('MapBossService')).spawn(p.id, cf, false, {intro = true}) end", "replace",
     "    else\n"
     "        local service = mapBossService()\n"
     "        local ok, made = pcall(function() return service and service.spawn(p.id, cf, false, {intro = true}) end)\n"
     "        if not ok then warn('Endless boss ' .. p.id .. ' failed to spawn: ' .. tostring(made)) end\n"
     "        boss = ok and made or nil\n"
     "        -- The rebuilt Hammer failing to spawn brings the old one instead (as BossEncounter does).\n"
     "        if not boss and p.id == 'Hammer' then boss = Bosses.spawn(cf + Vector3.yAxis * (BossMotion.RootHeight - T.rootHeight), false); old = boss ~= nil end\n"
     "    end"),
    (CHASE, CHASE_S,
     "            if id == 'Hammer' then", "replace",
     CHASE_ADMIN),
    (CHASE, CHASE_S,
     ("                local timing = require(combat:WaitForChild('MapBossDefs')).timing(id)",
      "                local boss = at and require(script.Parent:WaitForChild('MapBossService')).spawn(id, CFrame.lookAt(at, Vector3.new(position.X, at.Y, position.Z)), true)"), "block",
     "                local defs, service = bossDefs(), mapBossService()\n"
     "                local timing = defs and service and defs.timing(id)\n"
     "                local at = timing and point + Vector3.yAxis * (timing.rootHeight + 0.1)\n"
     "                local boss = at and service.spawn(id, CFrame.lookAt(at, Vector3.new(position.X, at.Y, position.Z)), true)"),

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
     GUIDE_LIST),
    (GUIDE, GUIDE_S,
     "for _,npc in Tags:GetTagged('HammerBoss') do watchBoss(npc) end", "after",
     GUIDE_WATCH),

    # --- R6 MapBossServiceTests: the real defs now include the Hammer --------------------------------
    (TESTS, None,
     " for _,id in Defs.Order do", "after",
     "  -- The Hammer Brute's def comes before his generated timing (rebuild R6): an id without one is skipped.\n"
     "  if not Defs.timing(id) then continue end"),
    (TESTS, None,
     " local function segd(a,b,p) local ab=b-a;local t=math.clamp((p-a):Dot(ab)/math.max(ab:Dot(ab),1e-6),0,1);return (a+ab*t-p).Magnitude end", "before",
     TESTS_CLIPS + "\n" + TESTS_LEGACY),
]

# 20bff04 -> final (the 2026-10-03 review of R6-R7): run before HUNKS on files that have 20bff04's text.
FROM_20BFF04 = [
    (CHASE, CHASE_S,
     ("-- A map boss this place can run: MapBossDefs.ready (its def, timing, client clips and template).",
      "local function oldHammer(id, defs) return id == 'Hammer' and not mapReady(id, defs) end"), "block",
     CHASE_GATE),
    (CHASE, CHASE_S,
     ("            -- The old BossService Hammer until the rebuilt one is ready (oldHammer); then the map-boss path below.",
      "            if oldHammer(id, bossDefs()) then"), "block",
     CHASE_ADMIN),
    (GUIDE, GUIDE_S,
     ("-- The boss: the old Hammer (tag HammerBoss) or a map boss, the rebuilt Hammer Brute included (MapBoss).",
      "local function fightContext() return {edges=true,avoid=bosses()} end"), "block",
     GUIDE_LIST),
    (GUIDE, GUIDE_S,
     ("Tags:GetInstanceAddedSignal('MapBoss'):Connect(watchBoss)",
      "for _,npc in Tags:GetTagged('MapBoss') do watchBoss(npc) end"), "block",
     GUIDE_WATCH),
    (TESTS, None,
     (" -- MapBossDefs.ready (rebuild R6): true exactly when the def, timing, client clips and template are",
      " add(okReady,('ready: only with def, timing, client clips and template all present (ready now: %s)'):format(tostring(readyNow)))"), "block",
     TESTS_LEGACY),
]

if __name__ == "__main__":
    run(FROM_20BFF04 + HUNKS if "--from-20bff04" in sys.argv else HUNKS)
