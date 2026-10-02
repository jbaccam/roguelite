"""Plan K's anchored edits to shared scripts (plans/2026-10-02-K-quests-power-ui.md).
Other sessions edit these files at the same time, so plan K never pushes them whole.
    python plan_k_hunks.py [--check] [--stage] [--json]   (see tools/hunks.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from hunks import run  # noqa: E402

META = "combat/RogueliteMeta.server.luau"
PROFILE = "combat/ProfileService.luau"

HUNKS = [
    # --- RogueliteMeta: the run's new quest stats --------------------------------------------
    (META, "ServerScriptService.RogueliteMeta",
     "local function questRun(p,stint) if Profiles.questRun then Profiles.questRun(p,stint) end end", "after",
     """-- Plan K quest stats from the run: level-ups, shards picked up and shop buys (ShopService hooks),
-- damage dealt (CombatEffectsService.listenDamage) and each minute in a run. The hooks run inside
-- the sandboxed ShopService / CombatEffectsService, so they only add to these tallies; this loop
-- sends them to quests once a second. Members of the run only; questEvent skips test runs.
local questTally={levels={},shards={},buys={},damage={}}
local function tally(stat,p,n) if Shop.members[p] then local t=questTally[stat];t[p]=(t[p] or 0)+n end end
Shop.onLevelUp=function(p,n) tally('levels',p,n) end
Shop.onShards=function(p,n) tally('shards',p,n) end
Shop.onBuy=function(p) tally('buys',p,1) end
if Effects.listenDamage then Effects.listenDamage(function(owner,_,actual) tally('damage',owner,actual) end) end -- plan J's hook; absent in older copies
task.spawn(function()
 local minuteAt=os.clock()+60
 while true do
  task.wait(1)
  for stat,t in questTally do
   for p,n in t do t[p]=nil;if Shop.members[p] then questEvent(p,stat,math.floor(n)) end end
  end
  if os.clock()>=minuteAt then minuteAt+=60;for p in Shop.members do questEvent(p,'minutes',1) end end
 end
end)"""),
    (META, "ServerScriptService.RogueliteMeta",
     "  if wavesPassed==RunSetupRules.WinWave then questEvent(p,'wins',1) end", "after",
     "  if wavesPassed==10 then questEvent(p,'deepRuns',1) end -- Reach Wave 10 in One Run"),
    (META, "ServerScriptService.RogueliteMeta",
     " if weapon and weapon.utility then questEvent(p,'utilityKills',1) end", "after",
     " if weapon then questEvent(p,weapon.kind=='Melee' and 'meleeKills' or 'rangedKills',1) end -- Ranged, Blast and Spread count as ranged"),
    # --- ProfileService: eggs hatched ----------------------------------------------------------
    (PROFILE, "ServerScriptService.ProfileService",
     " d.eggs-=n", "after",
     " quest('event',d,Money.day(),player.UserId,'eggs',n) -- Hatch an Egg, Hatcher (plan K)"),
    # --- Gear power split into its parts (the Armory's Power card) --------------------------------
    ("combat/CharacterStats.luau", "ReplicatedStorage.RogueliteCombat.CharacterStats",
     "-- Armor set bonuses (RARITY_GODLY_ARMOR.md step 5, approved 2026-09-30). Only worn pieces of the", "before",
     """-- gearPower split for the Armory's Power card (plan K): the starter's tier, worn armor tiers and
-- the pet's tier. total equals gearPower(get, weapon).
function S.gearParts(get,weapon)
 local parts={weapon=S.ownedTier(get('ProfileWeapons'),weapon) or 1,armor=0,pet=0}
 local tiers=S.parseArmorTiers(get('ProfileArmor') or '')
 for slot,setId in S.parseWearing(get('ProfileWearing')) do parts.armor+=tiers[setId..'.'..slot] or 0 end
 local pet=get('ProfilePet')
 if type(pet)=='string' and pet~='' then parts.pet=S.ownedTier(get('ProfilePets'),pet) or 0 end
 parts.total=parts.weapon+parts.armor+parts.pet
 return parts
end"""),
    ("lobby/RunSetupRules.luau", "ReplicatedStorage.RunSetupRules",
     "-- Saved win / best-wave key: Normal keeps the plain map id (older saves stay valid).", "before",
     """-- The same power split into weapon, armor and pet tiers (the Armory's Power card, plan K).
function R.powerParts(player,weapon)
 return Stats.gearParts(function(name) return player:GetAttribute(name) end,weapon or player:GetAttribute('RunWeapon') or R.Signature.Brawler)
end"""),
]

MODULES = []  # whole modules for the Studio sync: filled in Task 11
BASE = "7fd7cea"  # the commit Studio's copies of plan K's whole modules are expected to match

if __name__ == "__main__":
    run(HUNKS, MODULES, "combat/plan-k-sync.json", BASE)
