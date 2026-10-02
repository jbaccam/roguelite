-- Chest tiers, item rarities and odds, shared by the server (rolls) and the UI (odds shown
-- before opening). Numbers: roguelite-planning/RARITY_GODLY_ARMOR.md sections 1-3.
-- Chests hold weapons AND armor pieces (user, 2026-09-30): every armor piece (ArmorCatalog,
-- e.g. 'Iron.Helmet') is its own item with its set's rarity, pooled with that rarity's weapons.
-- A chest holds a handful of item copies. Rare and Epic amounts are whole copies plus a chance
-- of one more (.25 = a 25% chance of one, 1 = exactly one); Legendary and Godly are a chance of
-- one copy (1 = always). Commons fill the rest. Copies of one rarity are grouped into 1-3 weapons
-- (e.g. ×5 Frying Pan, ×2 Egg).
local C={Order={},ById={}}
local Armor=require(script.Parent:WaitForChild('ArmorCatalog'))
local Pets=require(script.Parent:WaitForChild('PetConfig')) -- sandboxed data; fine from here

C.Rarities={'Common','Rare','Epic','Legendary','Godly'}
C.RarityColor={
 Common=Color3.fromRGB(214,222,226),Rare=Color3.fromRGB(79,183,245),
 Epic=Color3.fromRGB(192,116,249),Legendary=Color3.fromRGB(255,196,60),
 Godly=Color3.fromRGB(226,34,64),
}
-- Fixed rarity per weapon id (WeaponCatalog). Every class signature weapon is Common.
-- Godly weapons (WeaponCatalog 36-41, plans/2026-10-01-G) drop from every chest with a Godly chance.
local RARITY={
 Common={'01','05','00','08','12','15','19','17','24','26','30','35'},
 Rare={'02','06','09','07','13','16','23','21','27','29','34','33'},
 Epic={'04','10','14','20','28'},
 Legendary={'03','11','18','22','25','32','31'},
 Godly={'36','37','38','39','40','41'},
}
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

-- aura: the chest's glow and opening colour. emeralds=nil: not sold for emeralds (the Legendary
-- Chest comes from Robux packs and rewards). daily=true: free, one per day (the Wooden Chest,
-- 2026-09-30), claimed through BuyChest.
local function add(d) C.ById[d.id]=d;table.insert(C.Order,d.id) end
add({id='Wooden',icon='rbxassetid://107136053285951',name='Wooden Chest',emeralds=nil,daily=true,copies=3,rare=.25,epic=.02,legendary=.002,godly=0,pity=false,
 aura=Color3.fromRGB(120,235,70),glow=Color3.fromRGB(255,190,80)})
add({id='Silver',icon='rbxassetid://103320236733137',name='Silver Chest',emeralds=160,copies=6,rare=1,epic=.08,legendary=.008,godly=.0005,pity=true,
 aura=Color3.fromRGB(70,170,255),glow=Color3.fromRGB(110,195,255)})
add({id='Gold',icon='rbxassetid://88627612681717',name='Gold Chest',emeralds=300,copies=10,rare=2,epic=.25,legendary=.03,godly=.002,pity=true,
 aura=Color3.fromRGB(255,200,50),glow=Color3.fromRGB(255,206,90)})
add({id='Magical',icon='rbxassetid://92681366357642',name='Magical Chest',emeralds=700,copies=18,rare=4,epic=1,legendary=.1,godly=.006,pity=true,
 aura=Color3.fromRGB(176,90,255),glow=Color3.fromRGB(110,180,255)})
add({id='Legendary',icon='rbxassetid://81753880209961',name='Legendary Chest',emeralds=nil,copies=8,rare=3,epic=1,legendary=1,godly=.02,pity=true,
 aura=Color3.fromRGB(255,110,40),glow=Color3.fromRGB(255,176,60),accent=Color3.fromRGB(120,255,232)})
-- Old saves: class chests become Wooden, the Royal Chest becomes Legendary (same Robux packs).
C.Legacy={Brawler='Wooden',Gunner='Wooden',Thrower='Wooden',Juggler='Wooden',Handyman='Wooden',Mage='Wooden',Royal='Legendary'}

-- How many stacks a rarity's copies are grouped into.
local function stacks(copies) return copies<=0 and 0 or copies==1 and 1 or copies<=3 and 2 or 3 end
-- Whole copies, plus one more with the fraction's chance (.25 -> 0 or 1; 1 -> 1).
local function amount(rng,x) return math.floor(x)+(rng:NextNumber()<x%1 and 1 or 0) end

-- Copies per rarity for one chest (forceLegendary / forceGodly = pity).
function C.rollCounts(kind,rng,forceLegendary,forceGodly)
 local d=C.ById[kind]
 local rare=amount(rng,d.rare)
 local epic=amount(rng,d.epic)
 local legendary=(forceLegendary or rng:NextNumber()<d.legendary) and 1 or 0
 local godly=C.godlyEnabled(kind) and (forceGodly or rng:NextNumber()<d.godly) and 1 or 0
 return {Common=math.max(0,d.copies-rare-epic-legendary-godly),Rare=rare,Epic=epic,Legendary=legendary,Godly=godly}
end

-- One chest with pity. `pity` (the saved {Legendary=n, Godly=n}) is updated in place. Only pity
-- chests count, and Godly pity only counts once a Godly can drop.
function C.open(kind,rng,pity)
 local d=C.ById[kind]
 local godlyCounts=d.pity and C.godlyEnabled(kind)
 local counts=C.rollCounts(kind,rng,
  d.pity and (pity.Legendary or 0)>=C.LegendaryPity-1,
  godlyCounts and (pity.Godly or 0)>=C.GodlyPity-1)
 if d.pity then pity.Legendary=counts.Legendary>0 and 0 or (pity.Legendary or 0)+1 end
 if godlyCounts then pity.Godly=counts.Godly>0 and 0 or (pity.Godly or 0)+1 end
 return counts
end

-- Split `copies` of one rarity over 1-3 different items that chest `kind` can drop.
-- Returns {id=count}.
function C.group(rarity,copies,rng,into,kind)
 into=into or {}
 local pool=table.clone(C.poolFor(kind,rarity));local n=math.min(stacks(copies),#pool)
 if n==0 then return into end
 -- Distinct weapons; the first stack is the biggest (like ×5 / ×3 / ×1).
 local picked={}
 for i=1,n do table.insert(picked,table.remove(pool,rng:NextInteger(1,#pool))) end
 local shares={}
 local left=copies-n
 for i=1,n do shares[i]=1 end
 for _=1,left do local i=rng:NextNumber()<.55 and 1 or rng:NextInteger(1,n);shares[i]+=1 end
 table.sort(shares,function(a,b) return a>b end)
 for i,id in picked do into[id]=(into[id] or 0)+shares[i] end
 return into
end

-- 0.25 -> '25%', 0.002 -> '0.2%', 0.0005 -> '0.05%'.
function C.percent(x)
 local p=x*100
 local s=p>=10 and string.format('%.0f',p) or p>=1 and string.format('%.1f',p) or p>=.1 and string.format('%.2f',p) or string.format('%.3f',p)
 if s:find('%.') then s=s:gsub('0+$',''):gsub('%.$','') end
 return s..'%'
end
-- '×2', '25%' or '×1 + 25%'; nil when it can't drop.
local function amountText(x)
 local whole,frac=math.floor(x),x%1
 if whole>0 and frac>0 then return '×'..whole..' + '..C.percent(frac) end
 if whole>0 then return '×'..whole end
 if frac>0 then return C.percent(frac) end
 return nil
end

-- Rarity summary for the chest screen. Rarities this chest can't drop are left out.
function C.summary(kind)
 local d=C.ById[kind];local out={}
 local godly=C.godlyEnabled(kind) and d.godly or 0
 local most=d.copies-math.floor(d.rare)-math.floor(d.epic)-math.floor(d.legendary)-math.floor(godly)
 local least=math.max(0,d.copies-math.ceil(d.rare)-math.ceil(d.epic)-math.ceil(d.legendary)-math.ceil(godly))
 table.insert(out,{rarity='Common',text=least==most and ('×'..most) or ('×'..least..'–'..most)})
 for _,r in {{'Rare',d.rare},{'Epic',d.epic},{'Legendary',d.legendary},{'Godly',godly}} do
  local text=amountText(r[2])
  if text then table.insert(out,{rarity=r[1],text=text}) end
 end
 return out
end

-- Chance (percent) that one chest includes at least one copy of each item, grouped by
-- rarity. Exact for the rules above (stacks are distinct items picked uniformly).
function C.odds(kind)
 local d=C.ById[kind];if not d then return {} end
 local godly=C.godlyEnabled(kind) and d.godly or 0
 -- {count, probability} cases for each rarity's roll.
 local function split(x) local w,f=math.floor(x),x%1;return f>0 and {{w,1-f},{w+1,f}} or {{w,1}} end
 local function once(p) return p>=1 and {{1,1}} or p>0 and {{1,p},{0,1-p}} or {{0,1}} end
 local dist={Rare=split(d.rare),Epic=split(d.epic),Legendary=once(d.legendary),Godly=once(godly),Common={}}
 -- Commons are whatever the other rolls leave.
 for _,r in dist.Rare do for _,e in dist.Epic do for _,l in dist.Legendary do for _,g in dist.Godly do
  table.insert(dist.Common,{d.copies-r[1]-e[1]-l[1]-g[1],r[2]*e[2]*l[2]*g[2]})
 end end end end
 local out={}
 for _,r in C.Rarities do
  local items=C.poolFor(kind,r);local pool=#items
  -- A rarity this chest can't roll (Wooden: no Godly) lists nothing, not 0% rows.
  if pool>0 and not (r=='Godly' and godly<=0) then
   local p=0
   for _,c in dist[r] do p+=c[2]*math.min(stacks(math.max(0,c[1])),pool)/pool end
   for _,id in items do table.insert(out,{id=id,rarity=r,chance=p*100}) end
  end
 end
 return out
end

-- Daily deals (the "item shop sale"): each paid slot picks a rarity, then a weapon of it
-- (weapons only). Never Godly. Every price per copy is well above that rarity's spare-copy value, so buying a deal to
-- cash the copies in never pays.
C.DealOdds={{'Common',55},{'Rare',35},{'Epic',8},{'Legendary',2}}
C.DealPrice={Common=15,Rare=40,Epic=150,Legendary=500} -- emeralds per copy
C.DealAmount={Common={2,5},Rare={1,3},Epic={1,1},Legendary={1,1}}
function C.rollDeal(rng)
 local roll=rng:NextNumber()*100;local rarity=C.DealOdds[#C.DealOdds][1]
 for _,o in C.DealOdds do if roll<o[2] then rarity=o[1];break end;roll-=o[2] end
 local pool=C.WeaponPool[rarity];local id=pool[rng:NextInteger(1,#pool)]
 local a=C.DealAmount[rarity];local n=rng:NextInteger(a[1],a[2])
 return {kind='Weapon',id=id,rarity=rarity,amount=n,each=C.DealPrice[rarity],currency='Emeralds',price=n*C.DealPrice[rarity]}
end
return C
