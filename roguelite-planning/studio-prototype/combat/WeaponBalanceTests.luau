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
 for _,wave in {1,5,10,20} do
  check(Types.scaled('Regular',wave).health==3+2*(wave-1),'regular wave HP')
  check(Types.scaled('Baby',wave).health==wave,'baby wave HP')
  check(Types.scaled('Mutant',wave).health==math.max(50,20+11*(wave-1)),'mutant wave HP')
  check(Types.scaled('Mutant',wave).damage==0,'mutant never adds contact damage')
  check(math.abs(Types.scaled('Mutant',wave).slamDamage-(2+.85*(wave-1)))<.001,'mutant slam wave damage')
  check(math.abs(Types.scaled('Regular',wave).damage-(1+.6*(wave-1)))<.001,'contact growth')
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
   local new=w.tierDamage[4]/(w.cooldown*w.tierCooldown[4])/Weapons.RarityPower[w.rarity]
   local old=OLD_T4[w.id]/(w.authoredCooldown*.84)
   check(math.abs(new/old-1)<=.10,string.format('tier IV within 10%% %s %.1f vs %.1f',w.id,new,old))
  end
 end
 check(counts.Common==12 and counts.Rare==12 and counts.Epic==5 and counts.Legendary==7 and counts.Godly==6,'rarity pools 12/12/5/7/6')
 check(Weapons.ById['03'].damage==21 and math.abs(Weapons.ById['03'].cooldown-.924)<.001,'katana example 21 / .924')
 check(Weapons.ById['00'].tierDamage[2]==17 and Weapons.ById['00'].tierDamage[4]==33,'glock example 12/17/24/33')
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
 check(math.abs(legendaryShare(1)-.102)<.005 and math.abs(legendaryShare(20)-.164)<.005,'documented legendary offer share 10% -> 16%')
 -- Rarer weapons cost more: a Legendary's catalog price is x1.5 the same band's Common price.
 for _,entry in Catalog.List do
  if entry.kind=='Weapon' then
   check(entry.basePrice>0 and entry.basePrice%1==0,'whole weapon price '..entry.id)
   check(not Weapons.ById[entry.weaponId].godly,'no godly in the run shop '..entry.id)
  end
 end
 check(E.TIER_NAMES[4]=='Tier IV','tier words are not rarity words')
end,debug.traceback)
script:SetAttribute('Result',game.HttpService:JSONEncode({passed=ok,assertions=checked,error=ok and '' or err}))
