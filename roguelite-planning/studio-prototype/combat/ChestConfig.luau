-- Chest tiers, item rarities and odds, shared by the server (rolls) and the UI (odds shown
-- before opening). Numbers: roguelite-planning/RARITY_GODLY_ARMOR.md sections 1-3.
-- Chests hold weapons AND armor pieces (user, 2026-09-30): every armor piece (ArmorCatalog,
-- e.g. 'Iron.Helmet') is its own item with its set's rarity, pooled with that rarity's weapons.
-- A chest holds a FEW ITEMS (below, "What a chest holds"): a Silver Chest is one item, e.g. ×4
-- Iron Legs or ×2 Ninja Legs. Until 2026-10-03 a chest was a pile of copies spread over every
-- rarity, and a Silver Chest gave 3-5 different items (user: "it should be like 1-2 max").
local C={Order={},ById={}}
local Armor=require(script.Parent:WaitForChild('ArmorCatalog'))
local Pets=require(script.Parent:WaitForChild('PetConfig')) -- sandboxed data; fine from here

C.Rarities={'Common','Rare','Epic','Legendary','Godly'}
C.RarityColor={
 Common=Color3.fromRGB(214,222,226),Rare=Color3.fromRGB(79,183,245),
 Epic=Color3.fromRGB(192,116,249),Legendary=Color3.fromRGB(255,196,60),
 Godly=Color3.fromRGB(226,34,64),
}
-- Fixed rarity per weapon id, from WeaponCatalog.RarityLists (the run shop and weapon stats read the
-- same lists; same order as before, so seeded daily deals don't change). Every class signature weapon
-- is Common. Godly weapons (WeaponCatalog 36-41, plans/2026-10-01-G) drop from every chest with a
-- Godly chance.
local RARITY=require(script.Parent:WaitForChild('WeaponCatalog')).RarityLists
-- Pool: everything a chest can drop per rarity. WeaponPool: weapons only (daily deals).
C.Pool={};C.WeaponPool={};C.RarityOf={}
for _,r in C.Rarities do
 -- Daily deals never sell a Godly, so its weapon pool stays empty.
 C.Pool[r]=table.clone(RARITY[r]);C.WeaponPool[r]=r=='Godly' and {} or table.clone(RARITY[r])
 for _,id in RARITY[r] do C.RarityOf[id]=r end
end
for _,set in Armor.Sets do
 for _,slot in Armor.Slots do
  local id=Armor.pieceId(set.id,slot)
  table.insert(C.Pool[set.rarity],id);C.RarityOf[id]=set.rarity
 end
end
function C.isArmor(id) return Armor.valid(id) end
-- Pets (PetConfig) have a rarity for upgrade costs and spare copies, but are NEVER in the weapon
-- and armor chest pools: they come from the Pet Chest only.
for _,pet in Pets.List do C.RarityOf[pet.id]=pet.rarity end
function C.isPet(id) return Pets.valid(id) end
-- Items only some chests drop (ArmorCatalog `chests`: Phoenix is Legendary Chest only).
C.OnlyIn={}
for _,set in Armor.Sets do
 if set.chests then for _,slot in Armor.Slots do C.OnlyIn[Armor.pieceId(set.id,slot)]=set.chests end end
end
-- What chest `kind` can drop of one rarity (every item when kind is nil).
function C.poolFor(kind,rarity)
 if not kind then return C.Pool[rarity] end
 local out={}
 for _,id in C.Pool[rarity] do
  local only=C.OnlyIn[id]
  if not only or table.find(only,kind) then table.insert(out,id) end
 end
 return out
end
-- Godly rolls only where the chest's Godly pool has items (the Godly weapons everywhere; Phoenix only in the Legendary Chest).
function C.godlyEnabled(kind) return #C.poolFor(kind,'Godly')>0 end

-- Copies spent to raise a weapon's starting tier (I->II, II->III, III->IV).
C.UpgradeByRarity={Common={2,6,15},Rare={2,4,8},Epic={1,2,4},Legendary={1,2,3},Godly={1,1,2}}
C.UpgradeCost=C.UpgradeByRarity.Common -- fallback for unknown ids
function C.upgradeCost(id,tier)
 local costs=C.UpgradeByRarity[C.RarityOf[id] or 'Common']
 return costs[tier]
end
-- Emeralds spent with those copies, tripling each tier (user, 2026-09-30: upgrading should take
-- a good chunk of chests and runs). Same table for weapons and armor pieces.
C.UpgradeEmeralds={Common={60,180,540},Rare={120,360,1080},Epic={250,750,2250},Legendary={500,1500,4500},Godly={1000,3000,9000}}
function C.upgradeEmeralds(id,tier)
 return C.UpgradeEmeralds[C.RarityOf[id] or 'Common'][tier]
end
-- Copies past Tier IV turn into this many emeralds each.
C.OverflowByRarity={Common=2,Rare=5,Epic=20,Legendary=60,Godly=200}
function C.overflow(id) return C.OverflowByRarity[C.RarityOf[id] or 'Common'] end

-- Pity, on chests with pity=true: a Legendary within 50 chests, a Godly within 150.
C.LegendaryPity=50
C.GodlyPity=150
-- Chests bought or opened at once.
C.Amounts={1,10,100}
function C.validAmount(n) return table.find(C.Amounts,n)~=nil end

-- What a chest holds (user, 2026-10-03: "the silver chest should be like 1-2 items max ... we gotta
-- lower the amount of items you get from chests"). Each chest is a few ITEMS, each one a roll:
--   items  how many rolls (1.5 = one, plus a 50% chance of a second)
--   odds   each roll's rarity (they add up to 1)
--   stack  copies of the item a roll gives, by rarity: commons come in bigger stacks than rares
-- One chest never holds the same item twice. The Legendary Chest instead always holds one item of
-- each rarity in `fixed` (×12 common, ×5 rare, ×2 epic, ×1 Legendary), plus `bonusGodly`: the
-- chance of a Godly item on top.
-- Example, a Silver Chest: one item; 60% it's ×4 of a common, 35% ×2 of a rare, 4% an epic.
-- aura: the chest's glow and opening colour. emeralds=nil: not sold for emeralds (the Legendary
-- Chest comes from Robux packs and rewards). daily=true: free, one per day (the Wooden Chest,
-- 2026-09-30), claimed through BuyChest.
local function add(d) C.ById[d.id]=d;table.insert(C.Order,d.id) end
add({id='Wooden',icon='rbxassetid://134997471113145',name='Wooden Chest',emeralds=nil,daily=true,pity=false,
 items=1,odds={Common=.78,Rare=.2,Epic=.018,Legendary=.002},stack={Common=3,Rare=1,Epic=1,Legendary=1},
 aura=Color3.fromRGB(120,235,70),glow=Color3.fromRGB(255,190,80)})
add({id='Silver',icon='rbxassetid://129205874070637',name='Silver Chest',emeralds=160,pity=true,
 items=1,odds={Common=.6,Rare=.35,Epic=.04,Legendary=.0095,Godly=.0005},stack={Common=4,Rare=2,Epic=1,Legendary=1,Godly=1},
 aura=Color3.fromRGB(70,170,255),glow=Color3.fromRGB(110,195,255)})
add({id='Gold',icon='rbxassetid://71517836177030',name='Gold Chest',emeralds=300,pity=true,
 items=1.5,odds={Common=.45,Rare=.42,Epic=.11,Legendary=.019,Godly=.001},stack={Common=6,Rare=3,Epic=1,Legendary=1,Godly=1},
 aura=Color3.fromRGB(255,200,50),glow=Color3.fromRGB(255,206,90)})
add({id='Magical',icon='rbxassetid://100435943394609',name='Magical Chest',emeralds=700,pity=true,
 items=2,odds={Common=.2,Rare=.4,Epic=.35,Legendary=.047,Godly=.003},stack={Common=8,Rare=4,Epic=2,Legendary=1,Godly=1},
 aura=Color3.fromRGB(176,90,255),glow=Color3.fromRGB(110,180,255)})
-- Legendary (Robux / rewards): 20 copies, was 8 (user, 2026-10-03: more commons, rares and epics).
add({id='Legendary',icon='rbxassetid://97798658508261',name='Legendary Chest',emeralds=nil,pity=true,
 fixed={'Common','Rare','Epic','Legendary'},bonusGodly=.02,stack={Common=12,Rare=5,Epic=2,Legendary=1,Godly=1},
 aura=Color3.fromRGB(255,110,40),glow=Color3.fromRGB(255,176,60),accent=Color3.fromRGB(120,255,232)})
-- Old saves: class chests become Wooden, the Royal Chest becomes Legendary (same Robux packs).
C.Legacy={Brawler='Wooden',Gunner='Wooden',Thrower='Wooden',Juggler='Wooden',Handyman='Wooden',Mage='Wooden',Royal='Legendary'}

-- A roll's rarity odds for chest `kind`. Godly only once a Godly can drop there; until then its
-- share goes to Common.
function C.oddsFor(kind)
 local odds=table.clone(C.ById[kind].odds or {})
 if (odds.Godly or 0)>0 and not C.godlyEnabled(kind) then odds.Common=(odds.Common or 0)+odds.Godly;odds.Godly=nil end
 return odds
end
local function pick(odds,rng)
 local x,last=rng:NextNumber(),nil
 for _,r in C.Rarities do
  local q=odds[r]
  if q and q>0 then last=r;if x<q then return r end;x-=q end
 end
 return last
end

-- The rarities of one chest's items, e.g. {'Common'} or {'Rare','Epic'} (forceLegendary /
-- forceGodly = pity). Pity puts the guaranteed rarity on the first item: a Godly first, then a
-- Legendary on the next item (with only one item it waits for the next chest).
function C.roll(kind,rng,forceLegendary,forceGodly)
 local d=C.ById[kind];local godly=C.godlyEnabled(kind)
 if d.fixed then
  local out=table.clone(d.fixed)
  if godly and (forceGodly or rng:NextNumber()<(d.bonusGodly or 0)) then table.insert(out,'Godly') end
  return out
 end
 local odds=C.oddsFor(kind);local out={}
 local n=math.floor(d.items)+(rng:NextNumber()<d.items%1 and 1 or 0)
 for i=1,n do out[i]=pick(odds,rng) end
 if forceGodly and godly and not table.find(out,'Godly') then out[1]='Godly' end
 if forceLegendary and not table.find(out,'Legendary') then
  for i,r in out do if r~='Godly' then out[i]='Legendary';break end end
 end
 return out
end

-- One chest with pity. `pity` (the saved {Legendary=n, Godly=n}) is updated in place. Only pity
-- chests count, and Godly pity only counts once a Godly can drop. Returns the rolled rarities.
function C.open(kind,rng,pity)
 local d=C.ById[kind]
 local godlyCounts=d.pity and C.godlyEnabled(kind)
 local rolls=C.roll(kind,rng,
  d.pity and (pity.Legendary or 0)>=C.LegendaryPity-1,
  godlyCounts and (pity.Godly or 0)>=C.GodlyPity-1)
 if d.pity then pity.Legendary=table.find(rolls,'Legendary') and 0 or (pity.Legendary or 0)+1 end
 if godlyCounts then pity.Godly=table.find(rolls,'Godly') and 0 or (pity.Godly or 0)+1 end
 return rolls
end

-- The items for one chest's rolls: a different item for each roll, with its rarity's stack of
-- copies. Adds to `into` ({id=copies}) and returns it.
function C.fill(kind,rolls,rng,into)
 into=into or {}
 local d=C.ById[kind];local used={}
 for _,r in rolls do
  local pool={}
  for _,id in C.poolFor(kind,r) do if not used[id] then table.insert(pool,id) end end
  if #pool>0 then
   local id=pool[rng:NextInteger(1,#pool)];used[id]=true
   into[id]=(into[id] or 0)+(d.stack[r] or 1)
  end
 end
 return into
end

-- Rolls of rarity r one chest holds on average (pity aside).
function C.expected(kind,r)
 local d=C.ById[kind]
 if d.fixed then
  local n=0;for _,x in d.fixed do if x==r then n+=1 end end
  if r=='Godly' and C.godlyEnabled(kind) then n+=d.bonusGodly or 0 end
  return n
 end
 return d.items*(C.oddsFor(kind)[r] or 0)
end
-- Chance that one chest holds at least one item of rarity r (1 = always; pity aside).
function C.chance(kind,r)
 local d=C.ById[kind];if not d then return 0 end
 if d.fixed then
  if table.find(d.fixed,r) then return 1 end
  return r=='Godly' and C.godlyEnabled(kind) and (d.bonusGodly or 0) or 0
 end
 local q=C.oddsFor(kind)[r] or 0
 if q<=0 then return 0 end
 return 1-(1-q)^math.floor(d.items)*(1-d.items%1*q)
end
-- How many different items one chest holds: lo, hi.
function C.itemRange(kind)
 local d=C.ById[kind]
 if d.fixed then return #d.fixed,#d.fixed+((d.bonusGodly or 0)>0 and C.godlyEnabled(kind) and 1 or 0) end
 return math.floor(d.items),math.ceil(d.items)
end
-- '1 item', '1–2 items', '4–5 items'.
function C.itemsText(kind)
 local lo,hi=C.itemRange(kind)
 return (lo==hi and tostring(lo) or (lo..'–'..hi))..(hi==1 and ' item' or ' items')
end

-- 0.25 -> '25%', 0.002 -> '0.2%', 0.0005 -> '0.05%'.
function C.percent(x)
 local p=x*100
 local s=p>=10 and string.format('%.0f',p) or p>=1 and string.format('%.1f',p) or p>=.1 and string.format('%.2f',p) or string.format('%.3f',p)
 if s:find('%.') then s=s:gsub('0+$',''):gsub('%.$','') end
 return s..'%'
end

-- The chest screen's rows, one per rarity the chest can hold: the chance it has an item of that
-- rarity and that item's copies ('60%  ·  ×4', '4%', or '×12' when it's always there).
function C.summary(kind)
 local d=C.ById[kind];local out={}
 for _,r in C.Rarities do
  local p=C.chance(kind,r)
  if p>0 then
   local n=d.stack[r] or 1
   table.insert(out,{rarity=r,text=p>=.9995 and ('×'..n) or (C.percent(p)..(n>1 and ('  ·  ×'..n) or ''))})
  end
 end
 return out
end

-- Chance (percent) that one chest includes each item, grouped by rarity: the rolls expected to
-- land on its rarity, shared over that rarity's items. Exact: one chest's rolls are different
-- items picked uniformly, and no chest rolls more items of a rarity than it has.
function C.odds(kind)
 if not C.ById[kind] then return {} end
 local out={}
 for _,r in C.Rarities do
  local items=C.poolFor(kind,r);local expected=C.expected(kind,r)
  if #items>0 and expected>0 then
   local p=math.min(1,expected/#items)
   for _,id in items do table.insert(out,{id=id,rarity=r,chance=p*100}) end
  end
 end
 return out
end
-- The chest screen and item cards read each chest's Legendary and Godly chance (1 = always).
for _,d in C.ById do d.legendary=C.chance(d.id,'Legendary');d.godly=C.chance(d.id,'Godly') end

-- Daily deals (the "item shop sale"): each paid slot picks a rarity, then a weapon of it
-- (weapons only). Never Godly. Every price per copy is well above that rarity's spare-copy value, so buying a deal to
-- cash the copies in never pays.
C.DealOdds={{'Common',55},{'Rare',35},{'Epic',8},{'Legendary',2}}
-- Emeralds per copy. The daily shop is how new weapons unlock now that the run shop sells only owned
-- ones, and rarer weapons cost more: a Legendary went 500 -> 800 (the user, 2026-10-02).
C.DealPrice={Common=15,Rare=40,Epic=150,Legendary=800}
C.DealAmount={Common={2,5},Rare={1,3},Epic={1,1},Legendary={1,1}}
function C.rollDeal(rng)
 local roll=rng:NextNumber()*100;local rarity=C.DealOdds[#C.DealOdds][1]
 for _,o in C.DealOdds do if roll<o[2] then rarity=o[1];break end;roll-=o[2] end
 local pool=C.WeaponPool[rarity];local id=pool[rng:NextInteger(1,#pool)]
 local a=C.DealAmount[rarity];local n=rng:NextInteger(a[1],a[2])
 return {kind='Weapon',id=id,rarity=rarity,amount=n,each=C.DealPrice[rarity],currency='Emeralds',price=n*C.DealPrice[rarity]}
end
return C
