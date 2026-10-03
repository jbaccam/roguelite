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
