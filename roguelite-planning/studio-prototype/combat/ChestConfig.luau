-- Chest tiers, weapon rarities and odds, shared by the server (rolls) and the UI (odds shown
-- before opening). Design: roguelite-planning/STORE_AND_CHESTS.md, Part 2.
-- A chest holds a fixed number of weapon copies: a guaranteed number of Rare and Epic copies,
-- a chance of one Legendary copy, and Commons for the rest. Copies of one rarity are grouped
-- into 1-3 weapons (e.g. ×5 Frying Pan, ×3 Glock). Rarity only says how often a weapon drops.
local C={Order={},ById={}}

C.Rarities={'Common','Rare','Epic','Legendary'}
C.RarityColor={
 Common=Color3.fromRGB(214,222,226),Rare=Color3.fromRGB(79,183,245),
 Epic=Color3.fromRGB(192,116,249),Legendary=Color3.fromRGB(255,196,60),
}
-- Fixed rarity per weapon id (WeaponCatalog). Every class signature weapon is Common.
local RARITY={
 Common={'01','05','00','08','12','15','19','17','24','26','30','35'},
 Rare={'02','06','09','07','13','16','23','21','27','29','34','33'},
 Epic={'04','10','14','20','28','31'},
 Legendary={'03','11','18','22','25','32'},
}
C.Pool={};C.RarityOf={}
for _,r in C.Rarities do
 C.Pool[r]=table.clone(RARITY[r])
 for _,id in RARITY[r] do C.RarityOf[id]=r end
end

-- Copies spent to raise a weapon's starting tier (I->II, II->III, III->IV). Rarer weapons need
-- fewer copies because they drop less.
C.UpgradeByRarity={Common={4,10,20},Rare={2,5,10},Epic={1,2,4},Legendary={1,1,2}}
C.UpgradeCost=C.UpgradeByRarity.Common -- fallback for unknown ids
function C.upgradeCost(id,tier)
 local costs=C.UpgradeByRarity[C.RarityOf[id] or 'Common']
 return costs[tier]
end
-- Copies past Tier IV turn into this many emeralds each.
C.OverflowByRarity={Common=2,Rare=5,Epic=20,Legendary=60}
function C.overflow(id) return C.OverflowByRarity[C.RarityOf[id] or 'Common'] end

-- A Legendary copy is guaranteed after this many chests in a row without one (Silver or better).
C.LegendaryPity=50
-- Chests bought or opened at once.
C.Amounts={1,10,100}
function C.validAmount(n) return table.find(C.Amounts,n)~=nil end

-- epic: guaranteed copies plus a chance of one more (1.35 = 1 copy + 35% of a second).
-- legendary: chance of one Legendary copy. aura: the chest's glow and opening colour.
-- emeralds=nil: not sold for emeralds (Legendary comes from Robux packs and rewards).
local function add(d) C.ById[d.id]=d;table.insert(C.Order,d.id) end
add({id='Wooden',icon='rbxassetid://107136053285951',name='Wooden Chest',emeralds=60,copies=7,rare=1,epic=.1,legendary=.01,pity=false,
 aura=Color3.fromRGB(120,235,70),glow=Color3.fromRGB(255,190,80)})
add({id='Silver',icon='rbxassetid://103320236733137',name='Silver Chest',emeralds=160,copies=16,rare=2,epic=.35,legendary=.04,pity=true,
 aura=Color3.fromRGB(70,170,255),glow=Color3.fromRGB(110,195,255)})
add({id='Gold',icon='rbxassetid://88627612681717',name='Gold Chest',emeralds=300,copies=30,rare=5,epic=1,legendary=.15,pity=true,
 aura=Color3.fromRGB(255,200,50),glow=Color3.fromRGB(255,206,90)})
add({id='Magical',icon='rbxassetid://92681366357642',name='Magical Chest',emeralds=700,copies=40,rare=10,epic=3,legendary=.5,pity=true,
 aura=Color3.fromRGB(176,90,255),glow=Color3.fromRGB(110,180,255)})
add({id='Legendary',icon='rbxassetid://81753880209961',name='Legendary Chest',emeralds=nil,copies=14,rare=4,epic=2,legendary=1,pity=true,
 aura=Color3.fromRGB(255,110,40),glow=Color3.fromRGB(255,176,60),accent=Color3.fromRGB(120,255,232)})
-- Old saves: class chests become Wooden, the Royal Chest becomes Legendary (same Robux packs).
C.Legacy={Brawler='Wooden',Gunner='Wooden',Thrower='Wooden',Juggler='Wooden',Handyman='Wooden',Mage='Wooden',Royal='Legendary'}

-- How many stacks a rarity's copies are grouped into.
local function stacks(copies) return copies<=0 and 0 or copies==1 and 1 or copies<=3 and 2 or 3 end

-- Copies per rarity for one chest (epic/legendary rolled with rng; forceLegendary = pity).
function C.rollCounts(kind,rng,forceLegendary)
 local d=C.ById[kind]
 local epic=math.floor(d.epic)+(rng:NextNumber()<d.epic%1 and 1 or 0)
 local legendary=(forceLegendary or rng:NextNumber()<d.legendary) and 1 or 0
 local rare=d.rare
 return {Common=math.max(0,d.copies-rare-epic-legendary),Rare=rare,Epic=epic,Legendary=legendary}
end

-- Split `copies` of one rarity over 1-3 different weapons. Returns {id=count}.
function C.group(rarity,copies,rng,into)
 into=into or {}
 local pool=table.clone(C.Pool[rarity]);local n=math.min(stacks(copies),#pool)
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

-- Rarity summary for the chest screen: amounts are fixed copies ("×8") or chances ("15%").
function C.summary(kind)
 local d=C.ById[kind];local out={}
 local epicWhole=math.floor(d.epic);local epicChance=d.epic%1
 local commonLow=d.copies-d.rare-epicWhole-(epicChance>0 and 1 or 0)-(d.legendary>0 and 1 or 0)
 local commonHigh=d.copies-d.rare-epicWhole-(d.legendary>=1 and 1 or 0)
 table.insert(out,{rarity='Common',text=commonLow==commonHigh and ('×'..commonHigh) or ('×'..commonLow..'–'..commonHigh)})
 table.insert(out,{rarity='Rare',text='×'..d.rare})
 local epicText=epicWhole>0 and ('×'..epicWhole) or ''
 if epicChance>0 then epicText=epicText..(epicWhole>0 and ' + ' or '')..math.floor(epicChance*100+.5)..'%' end
 table.insert(out,{rarity='Epic',text=epicText})
 table.insert(out,{rarity='Legendary',text=d.legendary>=1 and '×1' or (math.floor(d.legendary*1000+.5)/10)..'%'})
 return out
end

-- Chance (percent) that one chest includes at least one copy of each weapon, grouped by
-- rarity. Exact for the rules above (stacks are distinct weapons picked uniformly).
function C.odds(kind)
 local d=C.ById[kind];if not d then return {} end
 local epicWhole=math.floor(d.epic);local epicChance=d.epic%1
 local function includeChance(rarity)
  local pool=#C.Pool[rarity];local p=0
  local cases={}
  if rarity=='Rare' then cases={{d.rare,1}}
  elseif rarity=='Epic' then cases={{epicWhole,1-epicChance},{epicWhole+1,epicChance}}
  elseif rarity=='Legendary' then cases={{1,d.legendary},{0,1-d.legendary}}
  else
   -- Common count depends on the epic and legendary rolls.
   for _,e in {{epicWhole,1-epicChance},{epicWhole+1,epicChance}} do
    for _,l in {{1,d.legendary},{0,1-d.legendary}} do
     table.insert(cases,{d.copies-d.rare-e[1]-l[1],e[2]*l[2]})
    end
   end
  end
  for _,c in cases do p+=c[2]*math.min(stacks(c[1]),pool)/pool end
  return p*100
 end
 local out={}
 for _,r in C.Rarities do
  local chance=includeChance(r)
  for _,id in C.Pool[r] do table.insert(out,{id=id,rarity=r,chance=chance}) end
 end
 return out
end
return C
