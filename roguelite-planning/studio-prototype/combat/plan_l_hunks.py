"""Plan L's anchored edits to shared scripts: the run pause (plans/2026-10-02-L-pause.md).
The flag is the RunPaused attribute on ReplicatedStorage.RogueliteCombat; RunPause (RogueliteMeta)
sets it only when every living run member has paused.
    python plan_l_hunks.py [--check] [--stage] [--json]   (see tools/hunks.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from hunks import run  # noqa: E402

CHASE = "RogueliteZombieChase.server.luau"
CHAR = "combat/CharacterService.luau"

HUNKS = [
    # --- Spawner and enemies --------------------------------------------------------------------
    (CHASE, "ServerScriptService.RogueliteZombieChase",
     "    return run ~= nil and run:GetAttribute('AdminPaused') == true", "replace",
     "    -- Plan L: a paused run (RunPaused) spawns nothing either.\n"
     "    return (run ~= nil and run:GetAttribute('AdminPaused') == true) or combat:GetAttribute('RunPaused') == true"),
    (CHASE, "ServerScriptService.RogueliteZombieChase",
     "    if combat:GetAttribute('AdminFreeze') == true then", "replace",
     "    if combat:GetAttribute('AdminFreeze') == true or combat:GetAttribute('RunPaused') == true then -- plan L: a paused run freezes them too"),
    (CHASE, "ServerScriptService.RogueliteZombieChase",
     "    run:GetAttributeChangedSignal('AdminPaused'):Connect(function()", "before",
     "    -- Plan L: unpausing the run refills the wave's empty slots the same way.\n"
     "    combat:GetAttributeChangedSignal('RunPaused'):Connect(function()\n"
     "        if adminPaused() or combat:GetAttribute('ZombiesEnabled') ~= true or not Role.marker() then return end\n"
     "        for index = 1, spawnCount() do queueSpawn(index) end\n"
     "    end)"),
    ("combat/EnemyAttacks.luau", "ServerScriptService.EnemyAttacks",
     "\tfor i = #projectiles, 1, -1 do", "before",
     "\t-- Plan L: shots in flight hang while the run is paused, then carry on (lifetime counts frames).\n"
     "\tif combat:GetAttribute(\"RunPaused\") == true then\n"
     "\t\treturn\n"
     "\tend"),
    # --- Bosses: cancel what's under way and hold still -------------------------------------------
    ("combat/bosses/MapBossService.luau", "ServerScriptService.MapBossService",
     " checkEnrage(npc,s,h)", "before",
     " -- Pause (plan L): a paused run cancels the attack under way, its shots and follow-ups, and\n"
     " -- holds still. Attacks start fresh (with their wind-up) once the run unfreezes.\n"
     " if combat:GetAttribute('RunPaused')==true then\n"
     "  if s.attack then s.attack=nil;npc:SetAttribute('Attacking',false);npc:SetAttribute('BossStart',nil);root.Anchored=false;h.AutoRotate=true end\n"
     "  s.shots=nil;table.clear(s.follows);h:Move(Vector3.zero);h:MoveTo(root.Position);return\n"
     " end"),
    ("combat/bosses/BossService.luau", "ServerScriptService.BossService",
     " if s.attack and s.attack.kind=='Charge' then stepCharge(npc,s,now,root);return end", "before",
     " -- Pause (plan L): a paused run cancels the swing or charge under way and holds still.\n"
     " if combat:GetAttribute('RunPaused')==true then\n"
     "  if s.attack then s.attack=nil;npc:SetAttribute('Attacking',false);npc:SetAttribute('BossStart',nil);root.Anchored=false;root:SetNetworkOwner(nil);h.AutoRotate=true end\n"
     "  h:Move(Vector3.zero);h:MoveTo(root.Position);return\n"
     " end"),
    # --- Players: held, no damage, no bumps or regeneration --------------------------------------
    (CHAR, "ServerScriptService.CharacterService",
     "local function applyMoveSpeed(h,s)", "before",
     "-- Plan L: a paused run (RunPaused) holds players like the shop does and blocks their damage.\n"
     "function Service.frozen(player) return combat:GetAttribute('RunPaused')==true and player:GetAttribute('LobbyPreviewActive')~=true end"),
    (CHAR, "ServerScriptService.CharacterService",
     "   local held=Service.inShop(player)", "replace",
     "   local held=Service.inShop(player) or Service.frozen(player)"),
    (CHAR, "ServerScriptService.CharacterService",
     " if not s or not h or h.Health<=0 or player.Character:FindFirstChildOfClass('ForceField') or player:GetAttribute('AdminGod')==true or Service.inShop(player) then return 0 end", "replace",
     " if not s or not h or h.Health<=0 or player.Character:FindFirstChildOfClass('ForceField') or player:GetAttribute('AdminGod')==true or Service.inShop(player) or Service.frozen(player) then return 0 end"),
    (CHAR, "ServerScriptService.CharacterService",
     "   Service.heal(player,s.stats.Regeneration*step)", "replace",
     "   if not Service.frozen(player) then Service.heal(player,s.stats.Regeneration*step) end"),
    (CHAR, "ServerScriptService.CharacterService",
     "   if combat:GetAttribute('ZombiesEnabled') then", "replace",
     "   if combat:GetAttribute('ZombiesEnabled') and combat:GetAttribute('RunPaused')~=true then"),
    # --- Burn, poison and slow wait out a pause; their timers move later by it ---------------------
    ("combat/CombatEffectsService.luau", "ServerScriptService.CombatEffectsService",
     "local elapsed=0", "after",
     "local pausedAt -- plan L: os.clock() when the run paused"),
    ("combat/CombatEffectsService.luau", "ServerScriptService.CombatEffectsService",
     " for npc,entries in E.statuses do", "before",
     " -- Pause (plan L): statuses wait out a paused run, then their end and tick times move later by it.\n"
     " if combat:GetAttribute('RunPaused')==true then pausedAt=pausedAt or now;return end\n"
     " if pausedAt then\n"
     "  local by=now-pausedAt;pausedAt=nil\n"
     "  local serverBy=by\n"
     "  for npc,entries in E.statuses do\n"
     "   for _,e in entries do e.ends+=by;e.nextTick+=by end\n"
     "   for _,name in {'Burn','Poison','Slow'} do local u=npc:GetAttribute(name..'Until');if u then npc:SetAttribute(name..'Until',u+serverBy) end end\n"
     "  end\n"
     " end"),
    # --- Pets rest while paused (a resume counts like a new wave: half cooldown first) -------------
    ("combat/PetService.server.luau", "ServerScriptService.PetService",
     '\tlocal isCombat = r ~= nil and r:GetAttribute("Phase") == "Combat" and combat:GetAttribute("ZombiesEnabled") == true', "replace",
     '\tlocal isCombat = r ~= nil and r:GetAttribute("Phase") == "Combat" and combat:GetAttribute("ZombiesEnabled") == true\n'
     '\t\tand combat:GetAttribute("RunPaused") ~= true -- plan L: pets rest while the run is paused'),
    # --- Hearts on the ground wait out a pause ------------------------------------------------------
    ("combat/HeartDropService.luau", "ServerScriptService.HeartDropService",
     " elapsed+=dt;if elapsed<1/30 then return end;elapsed=0;H.step(workspace:GetServerTimeNow())", "replace",
     " elapsed+=dt;if elapsed<1/30 then return end;elapsed=0\n"
     " local now=workspace:GetServerTimeNow()\n"
     " -- Pause (plan L): hearts wait out a paused run; their age and ExpiresAt move later by it.\n"
     " if RS.RogueliteCombat:GetAttribute('RunPaused')==true then pausedAt=pausedAt or now;return end\n"
     " if pausedAt then\n"
     "  local by=now-pausedAt;pausedAt=nil\n"
     "  for _,d in H.drops do\n"
     "   d.born+=by\n"
     "   if d.model.Parent then d.model:SetAttribute('BornAt',d.born);d.model:SetAttribute('ExpiresAt',d.born+H.LIFETIME) end\n"
     "  end\n"
     " end\n"
     " H.step(now)"),
    ("combat/HeartDropService.luau", "ServerScriptService.HeartDropService",
     "Players.PlayerRemoving:Connect(function(p) for _,d in H.drops do if d.target==p then cancel(d) end end end)", "after",
     "local pausedAt -- plan L: server time when the run paused"),
    # --- Rojo project (repo only): the new RunPause module ----------------------------------------
    ("combat/default.project.json", None,
     '      "CharacterService": {', "before",
     '      "RunPause": {
        "$path": "RunPause.luau"
      },'),
]

MODULES = [
    {"path": "combat/RunPause.luau", "parent": "ServerScriptService", "name": "RunPause", "sandboxLike": "ServerScriptService.RogueliteMeta"},
]
BASE = "29aa821"

if __name__ == "__main__":
    run(HUNKS, MODULES, "combat/plan-l-sync.json", BASE)
