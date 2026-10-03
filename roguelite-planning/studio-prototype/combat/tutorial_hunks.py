"""The tutorial's anchored edits to shared scripts (plans/2026-10-03-tutorial-build-steps.md).
TutorialConfig, TutorialDirector, TutorialGuideUI, TutorialGuide and BossIntro are whole files.
    python tutorial_hunks.py [--check] [--stage] [--json]   (see tools/hunks.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from hunks import run  # noqa: E402

ECON = "combat/EconomyConfig.luau"
ECON_S = "ReplicatedStorage.RogueliteCombat.EconomyConfig"
SHARDS = "combat/ShardDropService.luau"
SHARDS_S = "ServerScriptService.ShardDropService"
SHOP = "combat/ShopService.luau"
SHOP_S = "ServerScriptService.ShopService"
BOSS = "combat/bosses/BossService.luau"
BOSS_S = "ServerScriptService.BossService"
EFFECTS = "combat/CombatEffectsService.luau"
EFFECTS_S = "ServerScriptService.CombatEffectsService"
CHAR = "combat/CharacterService.luau"
CHAR_S = "ServerScriptService.CharacterService"
CHASE = "RogueliteZombieChase.server.luau"
CHASE_S = "ServerScriptService.RogueliteZombieChase"

TUTOR = "combat/TutorialDirector.server.luau"
MATCH = "lobby/MatchService.luau"
MATCH_S = "ServerScriptService.MatchService"


def line_starting(path, prefix):
    """The one line of a repo file that starts with prefix (no trailing \\r)."""
    hits = [l.rstrip("\r") for l in (Path(__file__).resolve().parent.parent / path).read_text(encoding="utf-8").split("\n") if l.startswith(prefix)]
    assert len(hits) == 1, f"{path}: {len(hits)} lines start with {prefix!r}"
    return hits[0]


NEW_STATE = line_starting(SHOP, " local s={shards=")
NEW_STATE_OLD = NEW_STATE.replace("shards=S.tutorial and S.tutorial.startShards or E.STARTING_SHARDS", "shards=E.STARTING_SHARDS")

HUNKS = [
    # --- EconomyConfig: the shared-crystal split ------------------------------------------------
    (ECON, ECON_S,
     "return E", "before",
     "-- Shared drops (a boss's crystal shower): which of `count` players gets the nth one. Round-robin,\n"
     "-- so 50 across 3 players is 17 / 17 / 16 (TutorialTests).\n"
     "function E.shareIndex(n,count) return (n-1)%math.max(1,count)+1 end"),
    # --- ShardDropService: boss crystals fly to players; wave-end sweep; the tutorial's value ------
    (SHARDS, SHARDS_S,
     "    if not r or not characters.states[d.target] or (r.Position-d.origin).Magnitude>100 or (not d.fetched and not visible(d.target,d.position,r.Position)) then cancel(d)",
     "replace",
     "    -- A boss crystal (forced) flies to its player from anywhere, walls or not.\n"
     "    if not r or not characters.states[d.target] or (not d.forced and ((r.Position-d.origin).Magnitude>100 or (not d.fetched and not visible(d.target,d.position,r.Position)))) then cancel(d)"),
    (SHARDS, SHARDS_S,
     ("  local first", "  return first"), "block",
     "  -- The run's living players share them out evenly (EconomyConfig.shareIndex: 50 across 3 players\n"
     "  -- is 17 / 17 / 16). Each crystal bursts out to its spot, then flies to its player on its own,\n"
     "  -- no walking over needed (2026-10-03). With nobody alive in the run they stay public, as before.\n"
     "  local takers={}\n"
     "  for _,p in Players:GetPlayers() do if p:GetAttribute('RunMember') and living(p) and characters and characters.states[p] then table.insert(takers,p) end end\n"
     "  table.sort(takers,function(a,b) return a.UserId<b.UserId end)\n"
     "  local now=workspace:GetServerTimeNow()\n"
     "  local first\n"
     "  for n=1,D.BOSS_DROPS do\n"
     "   -- Golden-angle spiral: evenly filled disc, 3 to 14 studs from the body.\n"
     "   local angle=n*2.39996;local radius=3+math.sqrt(n/D.BOSS_DROPS)*11\n"
     "   local spot=position+Vector3.new(math.cos(angle)*radius,0,math.sin(angle)*radius)\n"
     "   local ground=workspace:Raycast(spot+Vector3.new(0,6,0),Vector3.new(0,-100,0),params)\n"
     "   local owner=#takers>0 and takers[E.shareIndex(n,#takers)] or nil\n"
     "   local d=dropAt(ground and ground.Position+Vector3.new(0,1.15,0) or spot,owner,D.BOSS_DROP_VALUE,0)\n"
     "   if owner then d.forced=true;D.start(owner,d,now+D.BOSS_FLY_DELAY+n*D.BOSS_FLY_STAGGER) end\n"
     "   first=first or d\n"
     "  end\n"
     "  return first"),
    (SHARDS, SHARDS_S,
     "-- A defeated wave boss showers public crystals (anyone may collect) over a wide disc.", "replace",
     "-- A defeated wave boss showers crystals over a wide disc, and they fly to the run's players (D.spawn)."),
    (SHARDS, SHARDS_S,
     "D.BOSS_DROPS=50;D.BOSS_DROP_VALUE=4", "after",
     "-- Boss crystals start flying this long after the shower, one every BOSS_FLY_STAGGER seconds.\n"
     "D.BOSS_FLY_DELAY=.6;D.BOSS_FLY_STAGGER=.02\n"
     "-- A kill's crystal value; nil = EconomyConfig.KILL_SHARDS. The tutorial (TutorialDirector) sets 5.\n"
     "D.killValue=nil"),
    (SHARDS, SHARDS_S,
     (" local value=E.KILL_SHARDS+(npc:GetAttribute('DesignerShirt')==true and E.DESIGNER_BONUS_SHARDS or 0)",
      " return dropAt(at,owner,value,value-E.KILL_SHARDS)"), "block",
     " local base=D.killValue or E.KILL_SHARDS\n"
     " local value=base+(npc:GetAttribute('DesignerShirt')==true and E.DESIGNER_BONUS_SHARDS or 0)\n"
     " return dropAt(at,owner,value,value-base)"),
    (SHARDS, SHARDS_S,
     "function D.clear(bank)", "before",
     "-- Wave end (ShopService.finishWave, while still in Combat): every crystal left on the ground or\n"
     "-- still flying is credited now as a normal pickup (shards and XP) to its owner, else the nearest\n"
     "-- living run member, and drawn flying to them: the model stays for the pull, then goes. One with\n"
     "-- nobody to take it stays for D.clear(true) to bag, as before (2026-10-03).\n"
     "function D.sweep()\n"
     " local now=workspace:GetServerTimeNow()\n"
     " for i=#D.drops,1,-1 do\n"
     "  local d=D.drops[i]\n"
     "  if d.collected or not d.model.Parent then continue end\n"
     "  local p=d.target or d.owner\n"
     "  if not (p and living(p) and characters.states[p]) then\n"
     "   p=nil;local nearest=math.huge\n"
     "   for _,q in Players:GetPlayers() do\n"
     "    local root=living(q)\n"
     "    if root and characters.states[q] and q:GetAttribute('RunMember') then\n"
     "     local distance=(root.Position-d.origin).Magnitude\n"
     "     if distance<nearest then nearest=distance;p=q end\n"
     "    end\n"
     "   end\n"
     "  end\n"
     "  if p and award(p,d.value,true) then\n"
     "   d.collected=true\n"
     "   if d.target~=p or (d.started or now)>now then\n"
     "    d.model:SetAttribute('MagnetOrigin',Motion.idle(d.origin,d.born,now));d.model:SetAttribute('MagnetStart',now);d.model:SetAttribute('MagnetUserId',p.UserId)\n"
     "   end\n"
     "   table.remove(D.drops,i);unindex(d)\n"
     "   local model=d.model\n"
     "   task.delay(Motion.PULL_SECONDS+.1,function() model:Destroy() end)\n"
     "  end\n"
     " end\n"
     "end"),
    # --- Boss super-jump intro (every wave boss) ------------------------------------------------
    (BOSS, BOSS_S,
     "local FLINCH_GAP=2", "after",
     "-- Super-jump entrance (2026-10-03): a wave boss (not an admin/practice one) drops in from the\n"
     "-- sky and lands hammer-first. drop: seconds of rumble and growing shadow before he falls; fall:\n"
     "-- the fall; after: the landing and the camera orbit (BossIntro.client). Until BossIntroUntil he\n"
     "-- can't be hurt (CombatEffectsService) and stands still, and CinematicUntil holds the players\n"
     "-- (CharacterService.frozen) and the enemies (RogueliteZombieChase).\n"
     "B.INTRO={drop=1.2,fall=.65,after=3.6}"),
    (BOSS, BOSS_S,
     " h.MaxHealth=math.ceil(HEALTH*hpScale);h.Health=h.MaxHealth;npc:SetAttribute('BossDamageScale',damageScale)", "replace",
     " -- The tutorial's boss (TutorialDirector sets TutorialBossHealth) has a fixed, small health.\n"
     " local fixed=not practice and combat:GetAttribute('TutorialBossHealth')\n"
     " h.MaxHealth=type(fixed)=='number' and fixed or math.ceil(HEALTH*hpScale);h.Health=h.MaxHealth;npc:SetAttribute('BossDamageScale',damageScale)"),
    (BOSS, BOSS_S,
     " local s={next=workspace:GetServerTimeNow()+2,index=0,lastHealth=h.Health};B.states[npc]=s", "after",
     " if not practice then\n"
     "  -- The entrance (B.INTRO): his Slam clip is timed so the hammer hits the ground as he lands;\n"
     "  -- it deals no damage (no s.attack). He stays anchored where he lands until it's over.\n"
     "  local now=workspace:GetServerTimeNow();local I=B.INTRO\n"
     "  local land=now+I.drop+I.fall;local done=land+I.after\n"
     "  npc:SetAttribute('BossIntroStart',now);npc:SetAttribute('BossIntroLand',land);npc:SetAttribute('BossIntroUntil',done)\n"
     "  npc:SetAttribute('BossAttack','Slam');npc:SetAttribute('BossStart',land-Motion.Attacks.Slam.active);npc:SetAttribute('BossFrame',root.CFrame)\n"
     "  npc:SetAttribute('BossGroundY',root.Position.Y-Motion.RootHeight-.1)\n"
     "  npc:SetAttribute('BossSerial',(npc:GetAttribute('BossSerial') or 0)+1);npc:SetAttribute('Attacking',true)\n"
     "  root.Anchored=true;h.AutoRotate=false\n"
     "  s.intro=done;s.next=done+.6\n"
     "  combat:SetAttribute('CinematicUntil',done)\n"
     " end"),
    (BOSS, BOSS_S,
     " if h.Health<=0 then s.attack=nil;return end", "after",
     " -- The super-jump entrance (B.INTRO): stand still until it's over, then fight.\n"
     " if s.intro then\n"
     "  if now<s.intro then h:Move(Vector3.zero);return end\n"
     "  s.intro=nil;npc:SetAttribute('Attacking',false);npc:SetAttribute('BossStart',nil)\n"
     "  root.Anchored=false;root:SetNetworkOwner(nil);h.AutoRotate=true\n"
     " end"),
    (EFFECTS, EFFECTS_S,
     " if not Tags:HasTag(npc,'RogueliteZombie') then return 0 end", "after",
     " -- A wave boss can't be hurt during its super-jump entrance (BossService BossIntroUntil).\n"
     " if (npc:GetAttribute('BossIntroUntil') or 0)>workspace:GetServerTimeNow() then return 0 end"),
    (CHAR, CHAR_S,
     "function Service.frozen(player) return combat:GetAttribute('RunPaused')==true and player:GetAttribute('LobbyPreviewActive')~=true end", "replace",
     "-- A boss entrance (CinematicUntil, BossService.INTRO) holds them the same way for its few seconds.\n"
     "function Service.frozen(player)\n"
     " local held=combat:GetAttribute('RunPaused')==true or (combat:GetAttribute('CinematicUntil') or 0)>workspace:GetServerTimeNow()\n"
     " return held and player:GetAttribute('LobbyPreviewActive')~=true\n"
     "end"),
    (CHASE, CHASE_S,
     "        frozen = combat:GetAttribute('AdminFreeze') == true or combat:GetAttribute('RunPaused') == true,", "replace",
     "        -- A boss entrance (CinematicUntil) holds them too while the camera is on the boss.\n"
     "        frozen = combat:GetAttribute('AdminFreeze') == true or combat:GetAttribute('RunPaused') == true\n"
     "            or (combat:GetAttribute('CinematicUntil') or 0) > workspace:GetServerTimeNow(),"),
    # --- ShopService: the tutorial run (S.tutorial, set by TutorialDirector) ----------------------
    (SHOP, SHOP_S,
     "local S={states={},wave=1,phase='Shop'}", "after",
     "-- The first-join tutorial (plans/2026-10-03-tutorial-design.md): TutorialDirector sets S.tutorial\n"
     "-- while a tutorial run is on, nil otherwise. Plain data from TutorialConfig: startShards, waves\n"
     "-- ([wave]={count,roster}), offers ([shop wave][slot]=ShopCatalog id), waveSeconds (the director\n"
     "-- ends each wave when its enemies are dead) and noShopTimer."),
    (SHOP, SHOP_S,
     NEW_STATE_OLD, "replace",
     " -- A tutorial run starts with no crystals (S.tutorial.startShards).\n"
     + NEW_STATE_OLD.replace("shards=E.STARTING_SHARDS", "shards=S.tutorial and S.tutorial.startShards or E.STARTING_SHARDS")),
    (SHOP, SHOP_S,
     " local wantWeapon=E.weaponSlot(S.wave,slot,rng)", "before",
     " -- The tutorial's guided offer (S.tutorial.offers), unless it's already on show (a reroll then\n"
     " -- rolls this slot normally).\n"
     " local forced=S.tutorial and S.tutorial.offers and S.tutorial.offers[S.wave] and S.tutorial.offers[S.wave][slot]\n"
     " local forcedEntry=forced and Catalog.ById[forced]\n"
     " if forcedEntry and not excluded[forcedEntry.id] then\n"
     "  excluded[forcedEntry.id]=true\n"
     "  return {id=forcedEntry.id,token=token(),price=E.price(forcedEntry.basePrice,S.wave,E.modifier(cs.stats)),locked=false,sold=false}\n"
     " end"),
    (SHOP, SHOP_S,
     " S.phase='Combat';run:SetAttribute('Phase','Combat');run:SetAttribute('WaveEndsAt',workspace:GetServerTimeNow()+E.WAVE_SECONDS)", "replace",
     " -- A tutorial wave has its own count and enemies, and no clock: TutorialDirector ends it.\n"
     " local tutorialWave=S.tutorial and S.tutorial.waves and S.tutorial.waves[S.wave]\n"
     " S.phase='Combat';run:SetAttribute('Phase','Combat');run:SetAttribute('WaveEndsAt',workspace:GetServerTimeNow()+(S.tutorial and S.tutorial.waveSeconds or E.WAVE_SECONDS))"),
    (SHOP, SHOP_S,
     " combat:SetAttribute('ZombieCount',combat:GetAttribute('TestZombieCountOverride') or S.waveEnemyCount());combat:SetAttribute('ZombiesEnabled',true)", "replace",
     " if tutorialWave then combat:SetAttribute('EnemyRoster',tutorialWave.roster) end\n"
     " combat:SetAttribute('ZombieCount',combat:GetAttribute('TestZombieCountOverride') or tutorialWave and tutorialWave.count or S.waveEnemyCount());combat:SetAttribute('ZombiesEnabled',true)"),
    (SHOP, SHOP_S,
     " run:SetAttribute('ShopEndsAt',workspace:GetServerTimeNow()+E.SHOP_SECONDS)", "replace",
     " -- The tutorial's shops wait for the player (no countdown).\n"
     " run:SetAttribute('ShopEndsAt',not (S.tutorial and S.tutorial.noShopTimer) and workspace:GetServerTimeNow()+E.SHOP_SECONDS or nil)"),
    # --- CharacterService: nobody dies in the tutorial ---------------------------------------------
    (CHAR, CHAR_S,
     " local before=h.Health;h:TakeDamage(Stats.incoming(amount,s.stats));local actual=before-h.Health", "replace",
     " local before=h.Health;local incoming=Stats.incoming(amount,s.stats)\n"
     " -- The tutorial (TutorialRun): hits still land and show, but health never goes below 1.\n"
     " if combat:GetAttribute('TutorialRun')==true then incoming=math.min(incoming,math.max(0,h.Health-1)) end\n"
     " h:TakeDamage(incoming);local actual=before-h.Health"),
    # --- RogueliteZombieChase: tutorial waves don't refill ------------------------------------------
    (CHASE, CHASE_S,
     "    if splitChild or admin or not npc:GetAttribute('DeathPopped') then return end", "replace",
     "    -- WaveNoRespawn (the tutorial): a wave is a fixed number of enemies that ends when they're dead.\n"
     "    if splitChild or admin or not npc:GetAttribute('DeathPopped') or combat:GetAttribute('WaveNoRespawn') == true then return end"),
    # --- MatchService: tutorial matches ------------------------------------------------------------
    (MATCH, MATCH_S,
     "function M.launch(players,map,difficulty,loadouts)", "replace",
     "-- extra (optional): {tutorial=true} makes it the first-join tutorial run (TutorialDirector).\n"
     "function M.launch(players,map,difficulty,loadouts,extra)"),
    (MATCH, MATCH_S,
     " if not retry(2,entries.SetAsync,entries,serverId,{map=map,difficulty=difficulty,members=members,code=code},ENTRY_SECONDS) then", "replace",
     " local tutorial=type(extra)=='table' and extra.tutorial==true or nil\n"
     " if not retry(2,entries.SetAsync,entries,serverId,{map=map,difficulty=difficulty,members=members,code=code,tutorial=tutorial},ENTRY_SECONDS) then"),
    (MATCH, MATCH_S,
     "    combat:SetAttribute('RunDifficulty',Rules.DifficultyIndex[entry.difficulty] and entry.difficulty or 'Normal')", "after",
     "    if entry.tutorial==true then combat:SetAttribute('TutorialRun',true) end -- TutorialDirector runs it"),
    (SHOP, SHOP_S,
     " Shards.clear(true)", "replace",
     " -- Leftover crystals fly to the players and count as pickups (XP and shards) while it's still\n"
     " -- Combat; any that nobody alive can take are bagged as before (2026-10-03).\n"
     " if Shards.sweep then Shards.sweep() end\n"
     " Shards.clear(true)"),
]

MODULES = []

if __name__ == "__main__":
    run(HUNKS, MODULES, manifest="combat/tutorial-sync.json", base=None)
