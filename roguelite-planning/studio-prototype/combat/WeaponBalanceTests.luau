-- Pure balance checks; run as a temporary server Script after syncing modules (or an Edit-mode
-- harness on copies of the repo modules). Plan J item 8 added the rarity and Brotato-tier checks.
local C=game.ReplicatedStorage.RogueliteCombat
local Weapons=require(C.WeaponCatalog)
local Stats=require(C.CharacterStats)
local Types=require(C.ZombieTypes)
local checked=0
local function check(ok,label) checked+=1;assert(ok,label) end
-- Tier IV damage of each weapon before the 2026-10-02 Brotato tiers (cooldown x.84 at Tier IV then),
-- so the new tiers can be checked to land within 10% of the old Tier IV damage per second.
local OLD_T4={['00']=40,['01']=60,['02']=21,['03']=62,['04']=53,['05']=32,['06']=70,['07']=9,['08']=14,['09']=7,
 ['10']=60,['11']=108,['12']=20,['13']=21,['14']=12,['15']=35,['16']=54,['17']=18,['18']=42,['20']=102,['21']=27,
 ['22']=81,['23']=45,['24']=12,['25']=95,['26']=64,['27']=35,['28']=14,['29']=9,['30']=32,['31']=75,['32']=89,
 ['33']=86,['34']=18,['35']=45,['36']=102,['37']=115,['38']=47,['39']=54,['40']=108,['41']=74}
-- Melee vs ranged pass (2026-10-03, WEAPON_BALANCE.md). MELEE_PASS: authored damage before -> after
-- for the five melee weapons that gained damage; their old Tier IV is scaled by the same ratio.
-- BEFORE: each weapon's range and authored cooldown before the pass.
local MELEE_PASS={['01']={16,18},['02']={6,7},['04']={15,16},['26']={18,20},['27']={10,12}}
local BEFORE={['00']={45,.72},['01']={6,1.05},['02']={6,.5},['03']={11,.95},['04']={12,1.15},['05']={6,.55},['06']={8,1.25},
 ['07']={42,.17},['08']={28,.8},['09']={24,1.1},['10']={40,1.35},['11']={70,2.4},['12']={35,.9},['13']={38,.48},['14']={38,1.7},
 ['15']={32,.85},['16']={6,.85},['17']={12,.32},['18']={42,.95},['19']={6.5,.42},['20']={7,1.35},['21']={28,.7},['22']={35,1.6},
 ['23']={28,1.25},['24']={40,.28},['25']={12,1.6},['26']={8,1.15},['27']={9,.8},['28']={20,.32},['29']={30,.24},['30']={45,1.15},
 ['31']={8,2},['32']={8.5,1.35},['33']={50,2},['34']={38,1.2},['35']={48,1.05},['36']={10,1.25},['37']={9,1.5},['38']={50,1.2},
 ['39']={10,1.3},['40']={9,1.3},['41']={48,.9}}
-- Weapons added after those passes have no old numbers (Pizza Cutter, 2026-10-09); their own checks are below.
local NEW={['42']=true}
local E=require(C.EconomyConfig)
local Catalog=require(C.ShopCatalog)
local ok,err=xpcall(function()
 local neutral=Stats.resolve('Brawler',0,{Damage=0,MeleeDamage=0,RangedDamage=0,ElementalDamage=0,UtilityPower=0,ExplosionDamage=0,AttackSpeed=0,CooldownReduction=0})
 local signatures={}
 for _,w in Weapons.List do
  local previous
  signatures[tostring(w.damage)..':'..tostring(w.cooldown)]=true
  for tier=1,4 do
   local d=Stats.weapon(w,neutral,nil,tier) -- no class: raw weapon numbers, without the class weapon fit
   check(math.abs(d.damage-w.tierDamage[tier])<.001,'actual tier damage '..w.id)
   check(d.cooldown>0 and d.range>0,'positive combat values '..w.id)
   if previous then check(d.damage>previous.damage and d.cooldown<previous.cooldown,'tier progression '..w.id) end
   check(d.nativePierce<=4 and d.nativeBounce<=4 and d.projectileCount<=8,'bounded traits '..w.id)
   previous=d
  end
 end
 local count=0;for _ in signatures do count+=1 end
 check(count>=30,'distinct damage/cadence identities')
 check(Stats.weapon(Weapons.ById['09'],neutral,'Brawler',4).projectileCount==8,'shotgun gains pellets')
 -- Boomerang: tier + 1 bounces, at most 4 (CharacterStats since 2026-09-23; this check said 3 until 2026-10-02).
 check(Stats.weapon(Weapons.ById['12'],neutral,'Brawler',4).nativeBounce==4,'boomerang gains rebounds')
 check(Stats.weapon(Weapons.ById['24'],neutral,'Brawler',4).nativePierce==2,'nails gain piercing')
 check(Stats.weapon(Weapons.ById['34'],neutral,'Brawler',2).projectileCount==2,'Medusa gains projectile')
 -- Draco late-fodder correction: actual reported loadout was Brawler (no Gunner affinity),
 -- Damage32, RangedDamage-15, GP1, with six Tier IV Dracos and +1 projectile. 2026-10-09: no class fit
 -- any more, so off-class it is 11 x 1.32 x .85 = 12.342 (was x.85 more, 10.4907); same breakpoints.
 local dracoStats=Stats.resolve('Brawler',0,{Damage=32,RangedDamage=-15,GearPower=1,ProjectileCount=1,AttackSpeed=0})
 local draco=Stats.weapon(Weapons.ById['07'],dracoStats,'Brawler',4)
 check(math.abs(draco.damage-12.342)<.0001,'Draco reported off-class damage')
 check(math.ceil(Types.scaled('Regular',20).health/draco.damage)==4,'Draco wave20 regular four-hit breakpoint')
 check(math.ceil(Types.scaled('Baby',20).health/draco.damage)==2,'Draco wave20 baby two-hit breakpoint')
 check(draco.nativePierce==0 and draco.nativeBounce==0 and draco.projectileCount==1,'Draco improves damage without adding projectile work or ricochet')
 check(math.abs(draco.cooldown-.1267)<.0001 and Weapons.ById['07'].damage==3,'Draco original cadence and Tier I unchanged')
 for _,wave in {1,5,10,20} do
  check(Types.scaled('Regular',wave).health==3+2*(wave-1),'regular wave HP')
  check(Types.scaled('Baby',wave).health==1+1*(wave-1),'baby wave HP')
  check(Types.scaled('Mutant',wave).health==math.max(50,20+11*(wave-1)),'mutant wave HP')
  check(Types.scaled('Mutant',wave).damage==0,'mutant never adds contact damage')
  check(math.abs(Types.scaled('Mutant',wave).slamDamage-(10+1.5*(wave-1)))<.001,'mutant slam wave damage')
  check(math.abs(Types.scaled('Regular',wave).damage-(5+.9*(wave-1)))<.001,'contact growth')
 end
 check(Types.forSlot(5,1)=='Regular' and Types.forSlot(5,8)=='Mutant','mutant wave gate')
 check(Types.Regular.health==3,'scaling does not mutate shared base')
 -- Rarity step 2 (RARITY_GODLY_ARMOR.md §4-6, plan J item 8).
 local counts={}
 for _,w in Weapons.List do
  check(Weapons.RarityPower[w.rarity]~=nil,'known rarity '..w.id)
  counts[w.rarity]=(counts[w.rarity] or 0)+1
  -- Rarity power is in the weapon's own numbers: damage per second x power, damage a whole number.
  local power=(w.damage/w.cooldown)/(w.authoredDamage/w.authoredCooldown)
  check(math.abs(power/Weapons.RarityPower[w.rarity]-1)<.005,'rarity power '..w.id..' '..power)
  check(w.damage%1==0 and w.damage<=w.authoredDamage*Weapons.RarityPower[w.rarity]+1e-6,'whole base damage '..w.id)
  if w.id=='19' then
   check(w.tierDamage[4]==48 and w.tierCooldown[4]==.76,'gloves keep their own tiers')
  else
   local growth=Weapons.TierGrowthById[w.id] or 1.4
   for tier=1,4 do
    check(w.tierDamage[tier]==math.floor(w.damage*growth^(tier-1)+.5),'tier damage rule '..w.id..' '..tier)
    check(w.tierCooldown[tier]==({1,.9,.8,.7})[tier],'tier cooldown rule '..w.id..' '..tier)
   end
   -- Tier IV damage per second within 10% of before, not counting rarity power.
   if NEW[w.id] then continue end
   local new=w.tierDamage[4]/(w.cooldown*w.tierCooldown[4])/Weapons.RarityPower[w.rarity]
   local pass=MELEE_PASS[w.id]
   local old=OLD_T4[w.id]*(pass and pass[2]/pass[1] or 1)/(w.authoredCooldown*.84)
   if w.id=='07' then
    check(w.tierDamage[4]==11 and math.abs(w.cooldown-.181)<.0001,'Draco explicit late-fodder tuning supersedes old DPS cap')
   else
    check(math.abs(new/old-1)<=.10,string.format('tier IV within 10%% %s %.1f vs %.1f',w.id,new,old))
   end
  end
 end
 check(counts.Common==12 and counts.Rare==12 and counts.Epic==5 and counts.Legendary==8 and counts.Godly==6,'rarity pools 12/12/5/8/6 (Pizza Cutter is Legendary)')
 check(Weapons.ById['03'].damage==21 and math.abs(Weapons.ById['03'].cooldown-.924)<.001,'katana example 21 / .924')
 check(Weapons.ById['00'].tierDamage[2]==17 and Weapons.ById['00'].tierDamage[4]==33,'glock example 12/17/24/33')
 -- Melee vs ranged pass (2026-10-03): ranged ~22% shorter and ~12% slower, melee ~20% longer.
 for _,w in Weapons.List do
  if NEW[w.id] then continue end
  local was=BEFORE[w.id];check(was~=nil,'before numbers '..w.id)
  local reach,rate=w.range/was[1],w.authoredCooldown/was[2]
  if w.kind=='Melee' then
   check(reach>=1.15 and reach<=1.26,string.format('melee reach +15-25%% %s %.2f',w.id,reach))
   check(w.id=='04' and math.abs(w.authoredCooldown-1.22)<1e-9 or math.abs(rate-1)<1e-9,'melee cadence (Kusarigama crowd nerf) '..w.id)
  elseif w.id=='17' then check(reach==1 and rate==1,'Rubber Duck unchanged (12 studs is melee distance)')
  elseif w.id=='11' then
   check(w.range==34 and w.projectileSpeed==46 and w.blastRadius==6,'rocket local crowd tuning')
  elseif w.id=='22' then
   check(w.range==36 and w.projectileSpeed==28,'bowling deliberate lane speed and distance')
  else
   check(reach>=.74 and reach<=.8+1e-9,string.format('ranged range -20-26%% %s %.2f',w.id,reach))
   if w.godly or w.id=='34' then check(math.abs(rate-1)<1e-9,'cadence kept '..w.id)
   else check(rate>=1.05 and rate<=1.15,string.format('ranged rate -5-13%% %s %.3f',w.id,rate)) end
  end
 end
 check(Weapons.ById['24'].authoredCooldown<.3,'Nail Gun keeps its fast-weapon price band (ShopCatalog < .3 s)')
 check(Weapons.ById['00'].range==35 and Weapons.ById['00'].authoredCooldown==.82,'glock example 35 studs / .82 s')
 check(Weapons.ById['01'].range==7.5 and Weapons.ById['01'].damage==18,'frying pan example 7.5 studs / 18 dmg')
 -- The slowing weapon: Medusa's Head slows 35% for 2 s on every hit, and its card says so.
 local medusa=Weapons.ById['34']
 check(medusa.slow==100 and medusa.slowStrength==35 and medusa.slowFor==2,'Medusa native slow 35% / 2 s')
 check(Weapons.slowText(medusa)=='Slows enemies 35% for 2 s.' and string.find(Weapons.describe(medusa),'Slows enemies 35% for 2 s.',1,true)~=nil,'Medusa card text has the numbers')
 check(Weapons.slowText(Weapons.ById['00'])==nil,'no slow text on a weapon that does not slow')
 check(table.find(Weapons.RarityLists.Rare,'34')~=nil,'Medusa drops from chests (Rare pool)')
 local medusaShop=false;for _,entry in Catalog.List do if entry.weaponId=='34' then medusaShop=true end end
 check(medusaShop,'Medusa is in the run shop catalog')
 -- Run-shop rarity weights: rarer is rarer, grows with wave and Luck, never above a Common.
 check(E.rarityWeight('Common',1,0)==1 and E.rarityWeight('Common',20,100)==1,'common weight 1')
 check(math.abs(E.rarityWeight('Legendary',1,0)-.4)<1e-9 and math.abs(E.rarityWeight('Legendary',20,0)-.8)<1e-9,'legendary .4 -> .8')
 check(math.abs(E.rarityWeight('Legendary',40,0)-.8)<1e-9,'weights stop growing after wave 20')
 check(E.rarityWeight('Legendary',20,100)==1 and E.rarityWeight('Epic',10,100)<=1,'luck capped at a common')
 check(E.rarityWeight('Legendary',10,0)<E.rarityWeight('Epic',10,0) and E.rarityWeight('Epic',10,0)<E.rarityWeight('Rare',10,0),'rarer is rarer')
 check(E.rarityWeight('Rare',10,50)>E.rarityWeight('Rare',10,0),'luck helps')
 check(E.rarityWeight('Godly',10,0)==0,'godly never offered')
 local legendaryShare=function(wave)
  local total,leg=0,0
  for _,w in Weapons.List do if not w.godly then local x=E.rarityWeight(w.rarity,wave,0);total+=x;if w.rarity=='Legendary' then leg+=x end end end
  return leg/total
 end
 -- 2026-10-09: the Pizza Cutter is an eighth Legendary, so the share went from 10% -> 16% to 11.5% -> 18.3%.
 check(math.abs(legendaryShare(1)-.115)<.005 and math.abs(legendaryShare(20)-.183)<.005,'documented legendary offer share 11.5% -> 18.3%')
 -- Rarer weapons cost more: a Legendary's catalog price is x1.5 the same band's Common price.
 for _,entry in Catalog.List do
  if entry.kind=='Weapon' then
   check(entry.basePrice>0 and entry.basePrice%1==0,'whole weapon price '..entry.id)
   check(not Weapons.ById[entry.weaponId].godly,'no godly in the run shop '..entry.id)
  end
 end
 check(E.TIER_NAMES[4]=='Tier IV','tier words are not rarity words')
 -- One starter class per ordinary weapon (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md):
 -- the class is in CharacterStats, Godly weapons have none, and the Elemental / Utility flags are the
 -- authored lists (the values they had when they came from Mage / Handyman membership).
 local ELEMENTAL={['08']=true,['14']=true,['17']=true,['30']=true,['31']=true,['32']=true,['33']=true,['34']=true,['35']=true,['38']=true,['41']=true}
 local UTILITY={['05']=true,['11']=true,['20']=true,['24']=true,['25']=true,['26']=true,['27']=true,['28']=true,['29']=true}
 for _,w in Weapons.List do
  if w.godly then check(#w.classes==0 and w.home=='Godly' and w.class==nil and not Weapons.inClass(w,'Brawler'),'godly has no class '..w.id)
  else check(Stats.Classes[w.class]~=nil and #w.classes==1 and w.home==w.class and Weapons.inClass(w,w.class),'one known class '..w.id) end
  check(w.elemental==(ELEMENTAL[w.id]==true) and w.utility==(UTILITY[w.id]==true),'authored elemental / utility '..w.id)
 end
 check(Weapons.ById['05'].utility and Weapons.ById['11'].utility and Weapons.ById['20'].utility,'Spatula, Rocket Launcher and Cinder Block keep Utility Power')
 check(Weapons.classNames(Weapons.ById['13'])=='Juggler' and Weapons.classNames(Weapons.ById['36'])=='','class names')
 check(string.find(Weapons.describe(Weapons.ById['12']),'Juggler starter weapon. Thrown, Trick.',1,true)==1,'card text: starter class and types')
 -- Pizza Cutter (2026-10-09): Legendary melee about Katana's and Steak's damage per second, shorter reach
 -- than Katana and faster hits; its Tier IV move is data until LegendaryMoves runs the Rolling Slice.
 local function dps(id,tier) local d=Stats.weapon(Weapons.ById[id],neutral,nil,tier);return d.damage/d.cooldown end
 local pc,katana,steak=Weapons.ById['42'],Weapons.ById['03'],Weapons.ById['16']
 check(pc.kind=='Melee' and pc.rarity=='Legendary' and pc.class=='Chef' and pc.damage==15 and math.abs(pc.cooldown-.673)<.001,'Pizza Cutter 15 / .673 (13 / .70 authored)')
 for tier=1,4 do
  check(math.abs(dps('42',tier)/dps('03',tier)-1)<=.10,string.format('Pizza Cutter T%d DPS within 10%% of Katana (%.1f vs %.1f)',tier,dps('42',tier),dps('03',tier)))
  check(dps('42',tier)>dps('16',tier),'Pizza Cutter above Steak (Rare) at T'..tier)
 end
 check(pc.range<katana.range and pc.range>steak.range and pc.cooldown<katana.cooldown,'Pizza Cutter reach between Steak and Katana, faster than Katana')
 check(Weapons.Legendary['42'] and Weapons.Legendary['42'].move=='Roll' and Weapons.legendaryText('42')~=nil,'Rolling Slice data and card line')
end,debug.traceback)
script:SetAttribute('Result',game.HttpService:JSONEncode({passed=ok,assertions=checked,error=ok and '' or err}))
