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
     '      "RunPause": {\n        "$path": "RunPause.luau"\n      },'),
    # --- Run HUD: the PAUSE launcher (P and the Roblox menu are PauseUI's own) -----------------------
    ("ui/RogueliteUI.luau", "ReplicatedStorage.RogueliteUI",
     " launcher('OpenShop','store','SHOP',1,toggleShop)", "after",
     " -- Pause (plans/2026-10-02-L-pause.md): PAUSE, P and the Roblox menu open the pause screen. Built\n"
     " -- in its own thread: PauseUI waits for the run state, which must never hold up this HUD.\n"
     " local pauseScreen\n"
     " launcher('PauseButton','rbxassetid://109142479841413','PAUSE',2,function() if pauseScreen then pauseScreen.Toggle() end end)\n"
     " task.spawn(function()\n"
     "  local ok,PauseUI=pcall(require,RS:WaitForChild('PauseUI'))\n"
     "  if not ok then warn('RogueliteUI: PauseUI failed to load:',PauseUI) return end\n"
     "  local made,screen=pcall(PauseUI.new,player)\n"
     "  if made then pauseScreen=screen else warn('RogueliteUI: pause screen failed:',screen) end\n"
     " end)"),
    # --- Admin panel: P is pause now; developers open the panel with F2 ------------------------------
    ("ui/AdminPanel.client.luau", "StarterPlayer.StarterPlayerScripts.AdminPanel",
     " if processed or Input:GetFocusedTextBox() or input.KeyCode~=Enum.KeyCode.P then return end", "replace",
     " -- F2 (P was it until plan L made P the pause key for everyone).\n"
     " if processed or Input:GetFocusedTextBox() or input.KeyCode~=Enum.KeyCode.F2 then return end"),
    # --- Rojo project (repo only): PauseUI -----------------------------------------------------------
    ("combat/default.project.json", None,
     '      "QuestsUI": {', "before",
     '      "PauseUI": {\n        "$path": "../ui/PauseUI.luau"\n      },'),
    # --- RogueliteMeta and ShopService: the pause itself (after plan J's ab93d9a) --------------------
    ('combat/RogueliteMeta.server.luau',
     'ServerScriptService.RogueliteMeta',
     "-- Each cleared wave saves progress right away, so nothing waits on the death screen's Give Up:",
     'before',
     "local runKills,runDamage={},{} -- plan L: this stint's kills and damage for the pause screen (the run loop publishes them)\nif Effects.listenDamage then Effects.listenDamage(function(owner,_,actual) if Shop.members[owner] then runDamage[owner]=(runDamage[owner] or 0)+actual end end) end"),
    ('combat/RogueliteMeta.server.luau',
     'ServerScriptService.RogueliteMeta',
     "  if os.clock()>=minuteAt then minuteAt+=60;for p in Shop.members do questEvent(p,'minutes',1) end end",
     'replace',
     "  if os.clock()>=minuteAt then minuteAt+=60;if combat:GetAttribute('RunPaused')~=true then for p in Shop.members do questEvent(p,'minutes',1) end end end -- plan L: paused minutes don't count"),
    ('combat/RogueliteMeta.server.luau',
     'ServerScriptService.RogueliteMeta',
     " questEvent(p,'kills',1)",
     'after',
     " runKills[p]=(runKills[p] or 0)+1 -- plan L: the pause screen's kills this stint"),
    ('combat/RogueliteMeta.server.luau',
     'ServerScriptService.RogueliteMeta',
     'local lastRunAction={}',
     'before',
     "-- Pause (plans/2026-10-02-L-pause.md): RunAction SetPaused. The run freezes only when every living\n-- member has paused (RunPause). A freeze holds the wave clock or the shop countdown, switches each\n-- member's weapons off (restored after) and sets RogueliteCombat.RunPaused, which the spawner,\n-- enemies, bosses, statuses, pets, hearts and CharacterService (hold, no damage) all check.\nlocal RunPause=require(SSS:WaitForChild('RunPause'))\nlocal pause=RunPause.new()\nlocal pausedWeapons={} -- player -> WeaponEnabled before the freeze\nlocal shopLeft -- seconds the shop countdown had left when the run froze in the shop\nlocal lastPauseAction,statStint={},{}\nlocal function pauseLiving()\n local list={}\n for p in Shop.members do local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid');if h and h.Health>0 and not down[p] then table.insert(list,p) end end\n return list\nend\nlocal function memberState(p) local f=combat:FindFirstChild('PlayerStates');return f and f:FindFirstChild(tostring(p.UserId)) end\nlocal function applyPause()\n local frozen,count,living=RunPause.evaluate(pause,pauseLiving())\n if combat:GetAttribute('RunPausedCount')~=count then combat:SetAttribute('RunPausedCount',count) end\n if combat:GetAttribute('RunLivingCount')~=living then combat:SetAttribute('RunLivingCount',living) end\n local now=workspace:GetServerTimeNow()\n local change=RunPause.step(pause,frozen,now)\n if change=='freeze' then\n  combat:SetAttribute('RunPaused',true)\n  for p in Shop.members do local st=memberState(p);if st then pausedWeapons[p]=st:GetAttribute('WeaponEnabled');st:SetAttribute('WeaponEnabled',false) end end\n  if Shop.phase=='Combat' then Shop.pause() end\n  local ends=runState:GetAttribute('ShopEndsAt')\n  if Shop.phase=='Shop' and type(ends)=='number' then shopLeft=math.max(0,ends-now);runState:SetAttribute('ShopEndsAt',nil) end\n elseif change=='unfreeze' then\n  combat:SetAttribute('RunPaused',nil)\n  for p,was in pausedWeapons do local st=memberState(p);if st and p.Parent then st:SetAttribute('WeaponEnabled',was) end end\n  table.clear(pausedWeapons)\n  if shopLeft then if Shop.phase=='Shop' then runState:SetAttribute('ShopEndsAt',now+shopLeft) end;shopLeft=nil end\n  if livingInRun()>0 and not lastStandEnds then Shop.resume() end\n end\nend\nlocal function setPaused(p,on)\n if on and not Shop.members[p] then on=false end\n if RunPause.set(pause,p,on) then p:SetAttribute('Paused',on or nil) end\n applyPause()\nend"),
    ('combat/RogueliteMeta.server.luau',
     'ServerScriptService.RogueliteMeta',
     " elseif action=='UseReroll' or action=='UseBanish' then useStored(p,action,arg) end",
     'replace',
     " elseif action=='SetPaused' then -- plan L: the pause screen opening (true) or closing (false)\n  if os.clock()-(lastPauseAction[p] or 0)<.25 then return end;lastPauseAction[p]=os.clock()\n  setPaused(p,arg==true)\n elseif action=='UseReroll' or action=='UseBanish' then useStored(p,action,arg) end"),
    ('combat/RogueliteMeta.server.luau',
     'ServerScriptService.RogueliteMeta',
     ' checkAgain() -- Play Again starts when the old run is over and everyone on results has decided',
     'after',
     " -- Pause (plan L): who must pause changes with deaths, joins and leaves; check four times a second.\n for p in pause.paused do if not Shop.members[p] or down[p] or not p.Parent then RunPause.forget(pause,p);p:SetAttribute('Paused',nil) end end\n applyPause()\n -- This stint's kills and damage, for the pause screen (RunKills / RunDamage).\n for p,m in Shop.members do\n  if statStint[p]~=m.stint then statStint[p]=m.stint;runKills[p]=0;runDamage[p]=0 end\n  local k,dmg=runKills[p] or 0,math.floor(runDamage[p] or 0)\n  if p:GetAttribute('RunKills')~=k then p:SetAttribute('RunKills',k) end\n  if p:GetAttribute('RunDamage')~=dmg then p:SetAttribute('RunDamage',dmg) end\n end"),
    ('combat/RogueliteMeta.server.luau',
     'ServerScriptService.RogueliteMeta',
     ' returning[p]=nil;prompting[p]=nil;runInfo[p]=nil;returnTries[p]=nil;again[p]=nil;lastRunAction[p]=nil',
     'after',
     ' RunPause.forget(pause,p);pausedWeapons[p]=nil;lastPauseAction[p]=nil;runKills[p]=nil;runDamage[p]=nil;statStint[p]=nil -- plan L'),
    ('combat/ShopService.luau',
     'ServerScriptService.ShopService',
     " if not S.paused or run:GetAttribute('AdminPaused') then return end",
     'replace',
     " -- Plan L: a paused run (RunPaused) keeps the clock held too; RogueliteMeta resumes it on unfreeze.\n if not S.paused or run:GetAttribute('AdminPaused') or combat:GetAttribute('RunPaused')==true then return end"),
    ('combat/ShopService.luau',
     'ServerScriptService.ShopService',
     " local data={pendingLevels=s.pendingLevels,upgradeOffers=s.upgradeOffers,upgradeToken=s.upgradeToken,upgradeRerolls=s.upgradeRerolls,upgradeRerollPrice=E.reroll(S.wave,s.upgradeRerolls),freeRerolls=s.freeRerolls,freeUpgradeRerolls=s.freeUpgradeRerolls,baggedShards=s.baggedShards,level=s.level,shards=s.shards,wave=S.wave,phase=S.phase,rerolls=s.rerolls,rerollPrice=E.reroll(S.wave,s.rerolls),offers=s.offers,items=s.items,weapons=owned(p),ready=s.ready,revision=s.revision,message=message or s.message or '',modifier=E.modifier(Characters.states[p].stats),debug=RunService:IsStudio() and E.DEBUG_CURRENCY_ENABLED}",
     'after',
     " data.upgrades=s.upgradeBonuses -- plan L: the pause screen's level-up picks (id -> picks)"),
]

MODULES = [
    {"path": "combat/RunPause.luau", "parent": "ServerScriptService", "name": "RunPause", "sandboxLike": "ServerScriptService.RogueliteMeta"},
    {"path": "ui/PauseUI.luau", "parent": "ReplicatedStorage", "name": "PauseUI", "sandboxLike": "ReplicatedStorage.RogueliteUI"},
]
BASE = "29aa821"

if __name__ == "__main__":
    run(HUNKS, MODULES, "combat/plan-l-sync.json", BASE)
