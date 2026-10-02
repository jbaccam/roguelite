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
    # --- ArmoryUI: the plates under the dais come from StatPlates ----------------------------------
    ("ui/ArmoryUI.luau", "ReplicatedStorage.ArmoryUI",
     'local RunSetup = require(RS:WaitForChild("RunSetupUI"))', "after",
     'local StatPlates = require(RS:WaitForChild("StatPlates")) -- damage, health and Power under the dais (plan K)'),
    ("ui/ArmoryUI.luau", "ReplicatedStorage.ArmoryUI",
     ("\t\t-- Stat plate under the dais: the starter's damage at its tier, class health, and gear power",
      '\t\tcentred(T.text(g, "Bonus", string.format("+%d%% dmg  +%d%% hp", math.round((Stats.powerDamage(power) - 1) * 100), math.round((Stats.powerHealth(power) - 1) * 100)), 8, 38, 144, 22, 15, C.muted))'),
     "block",
     "\t\t-- Stat plates under the dais (ui/StatPlates.luau, plan K): the starter's damage at its tier,\n"
     "\t\t-- class health, and gear power with its ? card.\n"
     "\t\tlocal hp = Stats.resolve(class, 0).MaxHP\n"
     "\t\tlocal w = Weapons.ById[weapon]\n"
     "\t\tlocal dmg = w and weaponAt(w, rec and rec.tier or 1).damage or 0\n"
     "\t\tStatPlates.draw(mid, gw / 2, 640, math.min(StatPlates.WIDTH, gw - 16), {\n"
     "\t\t\tdamage = dmg,\n"
     "\t\t\thealth = math.floor(hp + 0.5),\n"
     "\t\t\tweaponIcon = WeaponIcons[weapon],\n"
     "\t\t\tweaponName = w and w.name or \"Starter\",\n"
     "\t\t\tparts = Rules.powerParts(player, weapon),\n"
     "\t\t\tmaps = Rules.Maps,\n"
     "\t\t})"),
    ("combat/default.project.json", None,
     '      "QuestsUI": {', "before",
     '      "StatPlates": {\n        "$path": "../ui/StatPlates.luau"\n      },'),
    # --- UITheme: a window may be very slightly see-through (Quests, plan K) ------------------------
    ("ui/UITheme.luau", "ReplicatedStorage.UITheme",
     " local frame=T.panel(holder,'Frame',0,0,w,h,'panel');frame.Size=UDim2.fromScale(1,1);frame.Active=true", "after",
     " if opts and opts.seeThrough then frame.ImageTransparency=opts.seeThrough end -- e.g. Quests (plan K): the world shows through a little"),
    # --- LobbyUI: the left-side tracker comes from QuestsUI.tracker --------------------------------
    ("ui/LobbyUI.luau", "ReplicatedStorage.LobbyUI",
     (" local goals=T.panel(left,'Goals',0,140,300,212,'panel')",
      " goalsButton.Activated:Connect(function() open('Quests','Daily') end)"),
     "block",
     """ -- Quest tracker (QuestsUI.tracker, plan K): today's quests, the streak and OPEN QUESTS. A finished
 -- quest claims right on it; anywhere else on the tracker opens the Quests window.
 local tracker=QuestsUI.tracker(left,0,140,{config=QuestConfig,open=function() open('Quests','Daily') end,
  claim=function(i)
   task.spawn(function()
    local ok,r=pcall(function() return combat:WaitForChild('ProfileAction'):InvokeServer('ClaimQuest',i) end)
    if ok and type(r)=='table' then
     if r.ok then T.sound('ui_purchase') end
     T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
    end
   end)
  end})
 local goals=tracker.Root"""),
    ("ui/LobbyUI.luau", "ReplicatedStorage.LobbyUI",
     ("  -- Tracker: today's three daily quests; badges count rewards waiting for CLAIM.",
      "  goalsTitle.Text='DAILY QUESTS'"),
     "block",
     "  -- Tracker (plan K): today's quests and the streak; badges count rewards waiting for CLAIM.\n"
     "  local quests=profile.quests;tracker.update(quests)"),
    ("ui/LobbyUI.luau", "ReplicatedStorage.LobbyUI",
     "  T.badge(awards,claim>0 and tostring(claim) or nil)", "after",
     "  T.badge(tracker.OpenButton,claim>0 and tostring(claim) or nil)"),
    ("ui/LobbyUI.luau", "ReplicatedStorage.LobbyUI",
     "  local leftRight,leftBottom=14+328*s,10+(goals.Visible and 352 or 118)*s", "replace",
     "  local leftRight,leftBottom=14+(goals.Visible and QuestsUI.TRACKER_W or 328)*s,10+(goals.Visible and 140+QuestsUI.TRACKER_H or 118)*s"),
    # --- The user's flat chest and egg icons for the store, quests and chest lists (plan K) ---------
    ('combat/ChestConfig.luau',
     'ReplicatedStorage.RogueliteCombat.ChestConfig',
     "add({id='Wooden',icon='rbxassetid://107136053285951',name='Wooden Chest',emeralds=nil,daily=true,copies=3,rare=.25,epic=.02,legendary=.002,godly=0,pity=false,",
     'replace',
     "add({id='Wooden',icon='rbxassetid://134997471113145',name='Wooden Chest',emeralds=nil,daily=true,copies=3,rare=.25,epic=.02,legendary=.002,godly=0,pity=false,"),
    ('combat/ChestConfig.luau',
     'ReplicatedStorage.RogueliteCombat.ChestConfig',
     "add({id='Silver',icon='rbxassetid://103320236733137',name='Silver Chest',emeralds=160,copies=6,rare=1,epic=.08,legendary=.008,godly=.0005,pity=true,",
     'replace',
     "add({id='Silver',icon='rbxassetid://129205874070637',name='Silver Chest',emeralds=160,copies=6,rare=1,epic=.08,legendary=.008,godly=.0005,pity=true,"),
    ('combat/ChestConfig.luau',
     'ReplicatedStorage.RogueliteCombat.ChestConfig',
     "add({id='Gold',icon='rbxassetid://88627612681717',name='Gold Chest',emeralds=300,copies=10,rare=2,epic=.25,legendary=.03,godly=.002,pity=true,",
     'replace',
     "add({id='Gold',icon='rbxassetid://71517836177030',name='Gold Chest',emeralds=300,copies=10,rare=2,epic=.25,legendary=.03,godly=.002,pity=true,"),
    ('combat/ChestConfig.luau',
     'ReplicatedStorage.RogueliteCombat.ChestConfig',
     "add({id='Magical',icon='rbxassetid://92681366357642',name='Magical Chest',emeralds=700,copies=18,rare=4,epic=1,legendary=.1,godly=.006,pity=true,",
     'replace',
     "add({id='Magical',icon='rbxassetid://100435943394609',name='Magical Chest',emeralds=700,copies=18,rare=4,epic=1,legendary=.1,godly=.006,pity=true,"),
    ('combat/ChestConfig.luau',
     'ReplicatedStorage.RogueliteCombat.ChestConfig',
     "add({id='Legendary',icon='rbxassetid://81753880209961',name='Legendary Chest',emeralds=nil,copies=8,rare=3,epic=1,legendary=1,godly=.02,pity=true,",
     'replace',
     "add({id='Legendary',icon='rbxassetid://97798658508261',name='Legendary Chest',emeralds=nil,copies=8,rare=3,epic=1,legendary=1,godly=.02,pity=true,"),
    ('combat/EggConfig.luau',
     'ReplicatedStorage.RogueliteCombat.EggConfig',
     "E.Icon='rbxassetid://117887028525234' -- UI icon: blender-egg-merchant-kit/previews/icon-egg.png",
     'replace',
     "E.Icon='rbxassetid://115158817562855' -- UI icon: ui/assets/hud/pet-egg.png (the user's art, plan K)"),
    # --- StoreFX: header rules and diamonds follow the title's drawn width (they sat on its letters) ---
    ("ui/StoreFX.luau", "ReplicatedStorage.StoreFX",
     ("-- Centred section title between lime rules and diamonds, with an optional line under it.",
      " diamond(cx-tw/2-22);diamond(cx+tw/2+22)"),
     "block",
     "-- Centred section title between lime rules and diamonds, with an optional line under it.\n-- Returns the sub label (a timer can rewrite it). Takes 46 px, or 72 with a sub line. The rules\n-- and diamonds follow the title's drawn width (TextBounds), so they never sit on its letters even\n-- when a client measures the font differently (plan K).\nfunction FX.header(parent,title,sub,y,w)\n local tw=Text:GetTextSize(title,32,T.Font,Vector2.new(2000,100)).X\n local cx=math.floor(w/2)\n local l=T.label(parent,'Header_'..title,title,cx-tw*.75-20,y,tw*1.5+40,40,32);l.TextStrokeTransparency=1\n T.make('UIStroke',l,{Color=INK,Thickness=3})\n local function rule(toRight)\n  local f=T.make('Frame',parent,{Name='Rule',Position=UDim2.fromOffset(0,y+18),Size=UDim2.fromOffset(0,4),BackgroundColor3=T.Color.lime,BorderSizePixel=0})\n  T.make('UICorner',f,{CornerRadius=UDim.new(1,0)})\n  T.make('UIGradient',f,{Transparency=NumberSequence.new(toRight and 0 or 1,toRight and 1 or 0)})\n  return f\n end\n local function diamond()\n  local d=T.make('Frame',parent,{Name='Diamond',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(0,y+20),Size=UDim2.fromOffset(12,12),Rotation=45,BackgroundColor3=T.Color.lime,BorderSizePixel=0})\n  T.make('UIStroke',d,{Color=INK,Thickness=2})\n  return d\n end\n local ruleL,ruleR,dL,dR=rule(false),rule(true),diamond(),diamond()\n -- half: half the title's width plus its 3 px outline, in this parent's units.\n local function place(half)\n  local x0,x1=cx-half-28,cx+half+28\n  dL.Position=UDim2.fromOffset(x0+6,y+20);dR.Position=UDim2.fromOffset(x1-6,y+20)\n  ruleL.Position=UDim2.fromOffset(8,y+18);ruleL.Size=UDim2.fromOffset(math.max(0,x0-14),4);ruleL.Visible=x0-14>20\n  ruleR.Position=UDim2.fromOffset(x1+6,y+18);ruleR.Size=UDim2.fromOffset(math.max(0,w-x1-14),4);ruleR.Visible=w-x1-14>20\n end\n place(tw/2+3)\n -- TextBounds is in drawn pixels: divide out any UIScale above (Size offset / AbsoluteSize).\n local function measure()\n  local abs=l.AbsoluteSize.X\n  if abs>0 and l.TextBounds.X>0 then place(l.TextBounds.X*(l.Size.X.Offset/abs)/2+3) end\n end\n l:GetPropertyChangedSignal('TextBounds'):Connect(measure);l:GetPropertyChangedSignal('AbsoluteSize'):Connect(measure)\n task.defer(measure)"),
]

MODULES = [
    {"path": "combat/QuestConfig.luau", "parent": "ReplicatedStorage.RogueliteCombat", "name": "QuestConfig"},
    {"path": "combat/QuestService.luau", "parent": "ServerScriptService", "name": "QuestService"},
    {"path": "ui/QuestsUI.luau", "parent": "ReplicatedStorage", "name": "QuestsUI"},
    {"path": "ui/StatPlates.luau", "parent": "ReplicatedStorage", "name": "StatPlates", "sandboxLike": "ReplicatedStorage.ArmoryUI"},
]
BASE = "e6ecedb"  # the commit Studio's copies of plan K's whole modules match (last synced 2026-10-02)

if __name__ == "__main__":
    run(HUNKS, MODULES, "combat/plan-k-sync.json", BASE)
