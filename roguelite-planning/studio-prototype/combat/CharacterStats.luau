-- Shared schema and pure calculations. Only the server writes effective attributes.
local S={List={},ById={},Classes={},ClassOrder={'Brawler','Gunner','Thrower','Juggler','Handyman','Mage'}}
local Motion=require(script.Parent.WeaponMotion)
-- Air speed x1.3 (was 1.12; user 2026-10-03: "jumping should be like the optimal way to move
-- around"): a Brawler runs 22 and flies 28.6, so hopping covers ~25% more ground than walking.
S.Movement={Gravity=150,JumpHeight=9.5,AirSpeedMultiplier=1.3}
local function stat(id,label,base,min,max,step,unit,group,help)
 local d={id=id,label=label,base=base,min=min,max=max,step=step,unit=unit or '',group=group,help=help}
 table.insert(S.List,d);S.ById[id]=d
end
stat('MaxHP','Max health',100,1,1000,10,' HP','Defense','Maximum avatar health.')
stat('Damage','Damage',0,-80,500,10,'%','Offense','General damage bonus.')
stat('AttackSpeed','Attack speed',0,-70,200,10,'%','Offense','Faster attacks; animation and hit timing scale together.')
stat('CritChance','Critical chance',5,0,100,5,'%','Offense','Independent chance per direct hit.')
stat('CritDamage','Critical damage',150,100,400,25,'%','Offense','Total critical multiplier: 150% means 1.5x.')
stat('Armor','Armor',0,-20,100,2,'','Defense','Positive armor: damage / (1 + armor / 15). Negative armor increases damage.')
stat('Dodge','Dodge',0,0,60,5,'%','Defense','Chance to evade an incoming contact attack; capped at 60%.')
stat('Regeneration','Regeneration',0,0,25,1,' HP/s','Recovery','Passive healing; stops on death.')
stat('LifeSteal','Life steal',0,0,30,2,'%','Recovery','Heals actual damage dealt, subject to the per-second cap.')
stat('LifeStealCap','Life steal cap',10,0,50,2,' HP/s','Recovery','Maximum life-steal healing each second, after Recovery.')
stat('Recovery','Recovery',0,-80,200,10,'%','Recovery','Multiplies regeneration, life steal and health-pickup healing.')
stat('MoveSpeed','Movement speed',24,6,40,2,' studs/s','Utility','Actual Humanoid WalkSpeed.')
stat('PickupRadius','Pickup radius',8,1,50,2,' studs','Utility','Distance at which crystals start pulling toward you. Collect them for shards and run XP.')
stat('Luck','Luck',0,0,100,10,'','Utility','Improves higher-tier shop odds within rarity caps, and health-drop chance. Does not weight weapons.')
stat('MeleeDamage','Melee damage',0,-80,300,10,'%','Offense','Bonus to close-range attacks.')
stat('RangedDamage','Ranged damage',0,-80,300,10,'%','Offense','Bonus to projectile attacks, including thrown weapons.')
stat('ElementalDamage','Elemental damage',0,-80,300,10,'%','Offense','Bonus to Elemental-tagged hits and status damage.')
stat('UtilityPower','Utility power',0,-80,300,10,'%','Offense','Bonus to Construction/Utility weapons; future deployables use the same stat.')
stat('AttackRange','Attack range',0,-50,150,10,'%','Weapon','Scales targeting and melee reach or projectile travel distance.')
stat('ProjectileCount','Extra projectiles',0,0,4,1,'','Weapon','Extra shots for projectile weapons only; maximum nine shotgun pellets.')
stat('Pierce','Piercing',0,0,4,1,'','Weapon','Extra enemies per non-explosive projectile; 70% damage per added hit.')
stat('Bounce','Bounces',0,0,4,1,'','Weapon','Extra unique targets for non-explosive projectiles; 60% per bounce.')
stat('ProjectileSpeed','Projectile speed',0,-50,200,10,'%','Weapon','Scales physical projectile travel speed.')
stat('ProjectileSize','Projectile size',0,0,150,10,'%','Weapon','Scales projectile collision radius and visible shot thickness.')
stat('AreaSize','Area radius',0,-50,150,10,'%','Weapon','Scales blast and chain-search radius.')
stat('Knockback','Knockback',0,0,40,5,' studs/s','Weapon','Horizontal impulse on direct hits, bounded per target.')
stat('Duration','Effect duration',0,-50,200,10,'%','Status','Scales burn, poison and slow duration.')
stat('CooldownReduction','Cooldown reduction',0,0,50,5,'%','Weapon','Combines with attack speed; final cadence has a safe floor.')
stat('ExplosionDamage','Explosion damage',0,-80,300,10,'%','Offense','Additional multiplier for explosive weapons.')
stat('BossDamage','Elite / boss damage',0,-80,300,10,'%','Offense','Applies to enemies marked IsElite or IsBoss.')
stat('BurnChance','Burn chance',0,0,100,10,'%','Status','Direct hits may ignite. Molotov has a native 100% chance.')
stat('BurnDamage','Burn damage',0,-80,300,10,'%','Status','Burn: 6 base damage/second for 3 seconds. Refreshes, does not stack.')
stat('BurnSpread','Burn spread',0,0,3,1,' targets','Status','Spreads to nearby enemies on death; one generation only.')
stat('SlowChance','Slow chance',0,0,100,10,'%','Status','Direct hits may slow. Medusa has a native 100% chance.')
stat('SlowStrength','Slow strength',25,0,70,5,'%','Status','Movement reduction; bosses receive half strength.')
stat('SlowDuration','Slow duration',2,.5,10,.5,' s','Status','Base slow duration before the duration modifier.')
stat('PoisonChance','Poison chance',0,0,100,10,'%','Status','Direct hits may poison; Fart Gun has a native 100% chance.')
stat('PoisonDamage','Poison damage',0,-80,300,10,'%','Status','Poison: 3 base damage/second per stack for 4 seconds.')
stat('PoisonStacks','Poison stack cap',3,1,10,1,'','Status','Maximum poison stacks per attacker on a target.')
stat('ChainCount','Lightning targets',0,0,6,1,'','Status','Targets after a trigger; lightning weapons have at least one.')
stat('ChainBonus','Extra lightning targets',0,0,3,1,'','Status','Added to an existing lightning chain; does not create lightning on its own.')
stat('ChainEvery','Lightning frequency',5,1,20,1,' hits','Status','One chain every N direct hits; secondary hits cannot trigger chains.')
stat('ChainDamage','Lightning damage',0,-80,300,10,'%','Status','Chain hits deal 40% of base weapon damage, then this bonus.')
stat('FirstHitBlock','First-hit blocks',0,0,1,1,'','Defense','One block per wave; practice reset restores it, stat edits do not.')
stat('ContactReduction','Contact resistance',0,0,60,5,'%','Defense','Reduces zombie contact damage before armor.')
stat('ShopDiscount','Shop discount',0,0,30,5,'%','Economy','Reduces unlocked shop offer prices; locked prices stay fixed.')
stat('ShopPricePercent','Shop price modifier',0,-80,200,5,'%','Economy','Positive values increase prices; negative values reduce them. Combined multiplier is bounded.')
stat('GearPower','Gear power',0,0,40,1,'','Gear','Tiers of the gear you brought: starting weapon, worn armor and pet. Each point above 1 adds 12% damage and 6% max health.')
-- Classes (rebalanced 2026-10-03 so none is plainly worse): each has 3-4 buffs and 1-3 drawbacks,
-- and a drawback never weakens the class's own weapons. rangedAttackSpeed: % faster attacks with
-- non-melee weapons only (Gunner); the UI shows it with the buffs (S.classLines).
S.Classes={
 Brawler={description='Hand-to-hand fighter: tough and hits hard up close. Slower, with weak ranged damage.',buffs={MaxHP=25,Armor=3,MeleeDamage=20,Knockback=8,MoveSpeed=-2,RangedDamage=-15},build={'01','03','06','19'},two={MeleeDamage=15,Armor=2},four={LifeSteal=5}},
 Gunner={description='Fast, piercing gunfire. Less health and weak melee damage.',buffs={RangedDamage=20,ProjectileSpeed=35,CritChance=5,MaxHP=-15,MeleeDamage=-15},rangedAttackSpeed=10,build={'00','07','09','08'},two={Pierce=1},four={ProjectileCount=1}},
 Thrower={description='Long-range throws that rebound. Thin armor and weak melee damage.',buffs={AttackRange=25,Bounce=1,RangedDamage=15,Armor=-2,MeleeDamage=-10},build={'12','13','14','18'},two={RangedDamage=15},four={ProjectileCount=1}},
 Juggler={description='Quick tricks with toys: fast attacks, big knockback, always moving. Lower damage per hit.',buffs={MoveSpeed=3,AttackSpeed=15,Knockback=12,Damage=-10},build={'17','21','22','23'},two={AttackRange=15,Knockback=5},four={Bounce=1,AttackSpeed=15}},
 Handyman={description='Handy with anything: no penalty with almost any weapon, bigger blasts and slow healing. A little less health.',buffs={Damage=5,UtilityPower=15,AreaSize=20,Regeneration=1,MaxHP=-10},build={'24','25','28','29'},two={CooldownReduction=10},four={UtilityPower=20}},
 Mage={description='Elemental damage, burn and chains. Fragile, with weak physical attacks.',buffs={ElementalDamage=25,Duration=30,BurnChance=15,ChainCount=1,MaxHP=-20,Armor=-2,MeleeDamage=-10},build={'30','31','34','35'},two={ElementalDamage=15},four={BurnSpread=1}},
}
-- Each class's starting weapon, also its icon on class cards and tags. RunSetupRules.Signature is
-- this table; ProfileService keeps a copy (it doesn't load this module). Juggler: Rubber Duck since
-- 2026-10-03 (was Boxing Gloves).
S.Signature={Brawler='01',Gunner='00',Thrower='12',Juggler='17',Handyman='24',Mage='30'}
-- Class weapon fit (2026-10-03, Brotato-style but gentler): each equipped weapon's damage changes by
-- how close its home class is to yours. Own class +15%. Each pair of classes has one number, the same
-- both ways: 0 = close enough, -5 a bit off, -10 different, -15 opposite (fists vs guns). Handyman is
-- handy with anything: 0 with every class but Mage. Godly weapons belong to no class: no change.
-- Stacks with the class stats above, so a Brawler's Glock takes -15% and the Brawler's -15% ranged:
-- 0.85 x 0.85 = about -28%.
S.ClassFit={Own=15,
 Brawler={Gunner=-15,Thrower=-5,Juggler=-5,Handyman=0,Mage=-10},
 Gunner={Brawler=-15,Thrower=0,Juggler=-5,Handyman=0,Mage=-5},
 Thrower={Brawler=-5,Gunner=0,Juggler=0,Handyman=0,Mage=-5},
 Juggler={Brawler=-5,Gunner=-5,Thrower=0,Handyman=0,Mage=-5},
 Handyman={Brawler=0,Gunner=0,Thrower=0,Juggler=0,Mage=-5},
 Mage={Brawler=-10,Gunner=-5,Thrower=-5,Juggler=-5,Handyman=-5},
}
-- 'home' (+15), 'similar' (0) or 'off' (negative), and the percent; nil,0 for Godly or no class.
function S.classFit(base,class)
 local row=S.ClassFit[class]
 if base.godly or not S.Classes[class] or not row then return nil,0 end
 if base.home==class then return 'home',S.ClassFit.Own end
 local pct=row[base.home] or 0
 return pct<0 and 'off' or 'similar',pct
end
-- One line for class screens: 'Brawler +15% · Juggler 0% · Handyman -5% · Thrower, Mage -10% · Gunner -15%'.
function S.classFitText(class)
 local row=S.ClassFit[class];if not row then return '' end
 local byPct={}
 for _,other in S.ClassOrder do local v=row[other];if v then byPct[v]=byPct[v] or {};table.insert(byPct[v],other) end end
 local out={class..' +'..S.ClassFit.Own..'%'}
 for _,v in {0,-5,-10,-15} do if byPct[v] then table.insert(out,table.concat(byPct[v],', ')..' '..v..'%') end end
 return table.concat(out,' · ')
end
-- A class's always-on stats for the UI: good and bad lists of {value=, unit=, label=} in stat order,
-- plus Gunner's ranged attack speed. unit is '%' or ''. Example Brawler good[1]: 25, '', 'Max health'.
function S.statUnit(d) return d.unit=='%' and '%' or d.unit==' HP/s' and ' HP/s' or '' end
function S.classLines(class)
 local c=S.Classes[class];local good,bad={},{}
 if not c then return good,bad end
 for _,d in S.List do
  local v=c.buffs[d.id]
  -- Regeneration reads '+1  HP/s Regeneration': the unit joins the label so the number stays short.
  if v then table.insert(v>0 and good or bad,{value=v,unit=d.unit=='%' and '%' or '',label=(d.unit==' HP/s' and 'HP/s ' or '')..d.label}) end
 end
 if c.rangedAttackSpeed then table.insert(good,{value=c.rangedAttackSpeed,unit='%',label='Ranged attack speed'}) end
 return good,bad
end
-- '+15% Melee damage · +2 Armor' for a home-weapon bonus table (two / four).
function S.bonusText(t)
 local out={}
 for _,d in S.List do local v=t[d.id];if v then table.insert(out,(v>0 and '+' or '')..v..S.statUnit(d)..' '..d.label) end end
 return table.concat(out,' · ')
end
function S.valid(id,value)
 local d=S.ById[id]
 local count=table.find({'ProjectileCount','Pierce','Bounce','PoisonStacks','ChainCount','ChainBonus','ChainEvery','BurnSpread','FirstHitBlock'},id)
 return d~=nil and type(value)=='number' and value==value and value>=d.min and value<=d.max and (not count or value%1==0)
end
function S.resolve(class,count,overrides,bonuses,percent)
 local result={};local c=S.Classes[class] or S.Classes.Brawler
 for _,d in S.List do
  local value=d.base+(c.buffs[d.id] or 0)+(count>=2 and (c.two[d.id] or 0) or 0)+(count>=4 and (c.four[d.id] or 0) or 0)
  value=(value+((bonuses or {})[d.id] or 0))*(1+((percent or {})[d.id] or 0)/100)
  if table.find({'ProjectileCount','Pierce','Bounce','PoisonStacks','ChainCount','ChainBonus','ChainEvery','BurnSpread','FirstHitBlock'},d.id) then value=math.round(value) end
  if overrides and overrides[d.id]~=nil then value=overrides[d.id] end
  result[d.id]=math.clamp(value,d.min,d.max)
 end
 return result
end
function S.read(instance)
 local result={};for _,d in S.List do result[d.id]=instance:GetAttribute('Stat_'..d.id) or d.base end;return result
end
function S.mult(value) return math.max(.05,1+value/100) end
function S.incoming(amount,s) return amount*S.mult(-s.ContactReduction)*(s.Armor>=0 and 1/(1+s.Armor/15) or 1-s.Armor/15) end
function S.weapon(base,s,class,tier)
 tier=math.clamp(math.floor(tonumber(tier) or 1),1,4)
 local d=table.clone(base)
 d.tier=tier
 d.damage=(base.tierDamage and base.tierDamage[tier] or base.damage)*S.mult(s.Damage)*S.mult(base.kind=='Melee' and s.MeleeDamage or s.RangedDamage)
 if base.elemental then d.damage*=S.mult(s.ElementalDamage) end
 if base.utility then d.damage*=S.mult(s.UtilityPower) end
 if base.kind=='Blast' then d.damage*=S.mult(s.ExplosionDamage) end
 d.classFit,d.classFitPercent=S.classFit(base,class)
 d.damage*=S.mult(d.classFitPercent)
 local cc=S.Classes[class]
 local speed=S.mult(s.AttackSpeed)*(cc and cc.rangedAttackSpeed and base.kind~='Melee' and 1+cc.rangedAttackSpeed/100 or 1)
 d.cooldown=math.max(base.kind=='Melee' and .18 or .08,base.cooldown*(base.tierCooldown and base.tierCooldown[tier] or 1)/speed*(1-s.CooldownReduction/100))
 -- Animation speed is independent of damage cadence: heavy weapons strike
 -- crisply, then wait for their longer cooldown. Nunchucks use a slower cut.
 d.motionRate=base.kind=='Melee' and (base.id=='02' and 1.35 or base.id=='19' and 2.7 or 1.8)*speed/(1-s.CooldownReduction/100) or base.cooldown/d.cooldown
 d.range=base.range*S.mult(s.AttackRange)
 d.targetRange=(base.hybridRange or base.range)*S.mult(s.AttackRange)
 d.projectileSpeed=(base.projectileSpeed or 110)*S.mult(s.ProjectileSpeed)
 d.projectileCount=base.kind=='Spread' and (4+tier) or base.id=='18' and (tier>=3 and 4 or 3) or (base.trait=='shots' and tier>=2 and 2 or 1)
 d.nativePierce=base.trait=='pierce' and math.floor(tier/2) or 0
 if base.id=='22' then d.nativePierce=math.min(4,3+math.floor(tier/3)) end
 d.nativeBounce=base.id=='12' and math.min(4,tier+1) or base.trait=='bounce' and (tier-1) or 0
 d.projectileRadius=.12*S.mult(s.ProjectileSize)
 d.blastRadius=(base.blastRadius or 7)*S.mult(s.AreaSize)
 return d
end
function S.format(d,value) return string.format(value%1==0 and '%d' or '%.1f',value)..d.unit end
-- Gear power (GEAR_POWER.md): one point per tier of what a player brings into a run, the starting
-- weapon, each worn armor piece and the pet. A fresh account has 1 (a Tier I starter). Each point
-- above 1 adds 12% to all damage dealt and 6% max health. Example: a Tier II Frying Pan and four
-- Tier I armor pieces = 2 + 4 = 6 power, so x1.6 damage and x1.3 health. Maps scale their enemies by
-- the same curve at their recommended power (RunSetupRules), so matching it feels like Pine Valley.
S.PowerDamagePerPoint=.12;S.PowerHealthPerPoint=.06
function S.powerDamage(power) return 1+S.PowerDamagePerPoint*math.max(0,(tonumber(power) or 1)-1) end
function S.powerHealth(power) return 1+S.PowerHealthPerPoint*math.max(0,(tonumber(power) or 1)-1) end
-- The tier of `id` in a profile list ('01:2:3,Fox:1:0' = id:tier:copies), nil when not owned.
function S.ownedTier(text,id)
 if type(text)~='string' or type(id)~='string' then return nil end
 for key,tier in string.gmatch(text,'([^,:]+):(%d+):%d+') do if key==id then return math.clamp(tonumber(tier) or 1,1,4) end end
 return nil
end
-- get(name): the server-set profile attributes (player:GetAttribute). weapon: the starter's id.
-- Only owned things count: the starter's owned tier (1 if unknown), owned worn pieces, the pet.
function S.gearPower(get,weapon)
 local power=S.ownedTier(get('ProfileWeapons'),weapon) or 1
 local tiers=S.parseArmorTiers(get('ProfileArmor') or '')
 for slot,setId in S.parseWearing(get('ProfileWearing')) do power+=tiers[setId..'.'..slot] or 0 end
 local pet=get('ProfilePet')
 if type(pet)=='string' and pet~='' then power+=S.ownedTier(get('ProfilePets'),pet) or 0 end
 return power
end
-- gearPower split for the Armory's Power card (plan K): the starter's tier, worn armor tiers and
-- the pet's tier. total equals gearPower(get, weapon).
function S.gearParts(get,weapon)
 local parts={weapon=S.ownedTier(get('ProfileWeapons'),weapon) or 1,armor=0,pet=0}
 local tiers=S.parseArmorTiers(get('ProfileArmor') or '')
 for slot,setId in S.parseWearing(get('ProfileWearing')) do parts.armor+=tiers[setId..'.'..slot] or 0 end
 local pet=get('ProfilePet')
 if type(pet)=='string' and pet~='' then parts.pet=S.ownedTier(get('ProfilePets'),pet) or 0 end
 parts.total=parts.weapon+parts.armor+parts.pet
 return parts
end
-- Armor set bonuses (RARITY_GODLY_ARMOR.md step 5, approved 2026-09-30). Only worn pieces of the
-- SAME set count: 2+ pieces give `two`, all 4 give `two` and `four`. A key that is a stat adds to
-- that stat; any other key is a perk (a number scales with tier, true is a flag). `text` is the
-- short line the Armory shows. Pure data: the server (CharacterService) and the UI both read it.
S.ArmorSlots={'Helmet','Chest','Legs','Boots'}
S.ArmorSets={
 Iron={two={Armor=2},four={ContactReduction=10},text={two='+2 Armor',four='+10% Contact resistance'}},
 Ninja={two={Dodge=8},four={DodgeCrit=true},text={two='+8% Dodge',four='After you dodge, your next hit is a critical hit'}},
 Viking={two={MeleeDamage=12},four={RageAttackSpeed=25},text={two='+12% Melee damage',four='+25% Attack speed below half health'}},
 Samurai={two={CritChance=8},four={CritDamage=40},text={two='+8% Critical chance',four='+40% Critical damage'}},
 Spartan={two={Armor=3},four={FirstHitBlock=1},text={two='+3 Armor',four='Blocks the first hit every wave'}},
 DragonScale={two={MaxHP=25},four={BurnChance=20,FireThorns=25},text={two='+25 Max health',four='+20% Burn chance; zombies that hit you may catch fire (25%)'}},
 Phoenix={two={Regeneration=2},four={PhoenixBlast=100},text={two='+2 HP/s Regeneration',four='Once per run, rise at half health and blast nearby zombies'}},
}
-- Perk constants. RageAttackSpeed: while health < RageBelow of max. FireThorns: % chance per zombie
-- hit taken. PhoenixBlast: damage to every zombie within PhoenixRadius, rising at PhoenixHealth.
S.ArmorPerks={RageBelow=.5,PhoenixRadius=12,PhoenixHealth=.5}
S.ArmorFixed={FirstHitBlock=true} -- never scaled by tier
-- 'Chest:DragonScale,Helmet:DragonScale' -> {Chest='DragonScale',Helmet='DragonScale'} (ProfileWearing)
function S.parseWearing(text)
 local t={};for slot,set in string.gmatch(type(text)=='string' and text or '','([^,:]+):([^,:]+)') do t[slot]=set end;return t
end
-- 'DragonScale.Helmet:2:0' (piece:tier:copies) -> {['DragonScale.Helmet']=2} (ProfileArmor)
function S.parseArmorTiers(text)
 local t={};for id,tier in string.gmatch(type(text)=='string' and text or '','([^,:]+):(%d+):%d+') do t[id]=math.clamp(tonumber(tier) or 1,1,4) end;return t
end
-- wearing: {slot=setId} or the ProfileWearing string. tiers: {pieceId=tier} or the ProfileArmor
-- string; when given, a worn piece must be in it (owned) to count; nil means every piece is tier I.
-- Tier scaling: x(1 + 0.1 x (tier - 1)) from the lowest tier among the pieces that count: the best
-- two for `two`, all four for `four`. Stats round to whole numbers (or a finer stat step); perk
-- numbers round to whole numbers. Returns stat deltas, perks, and per-set {count,tierTwo,tierFour}.
function S.armorBonus(wearing,tiers)
 if type(wearing)~='table' then wearing=S.parseWearing(wearing) end
 if tiers~=nil and type(tiers)~='table' then tiers=S.parseArmorTiers(tiers) end
 local bySet={}
 for _,slot in S.ArmorSlots do
  local setId=wearing[slot];local tier=S.ArmorSets[setId] and (tiers==nil and 1 or tiers[setId..'.'..slot])
  if tier then
   local list=bySet[setId] or {};bySet[setId]=list
   table.insert(list,math.clamp(math.floor(tonumber(tier) or 1),1,4))
  end
 end
 local stats,perks,sets={},{},{}
 local function add(bonus,tier)
  for id,v in bonus do
   local d=S.ById[id]
   if type(v)~='number' then perks[id]=v
   else
    local scaled=S.ArmorFixed[id] and v or v*(9+tier)/10
    if d then local step=math.min(d.step,1);stats[id]=(stats[id] or 0)+math.round(scaled/step)*step
    else perks[id]=(perks[id] or 0)+math.round(scaled) end
   end
  end
 end
 for setId,list in bySet do
  if #list>=2 then
   table.sort(list,function(a,b) return a>b end)
   local set=S.ArmorSets[setId]
   sets[setId]={count=#list,tierTwo=list[2],tierFour=#list>=4 and list[4] or nil}
   add(set.two,list[2])
   if #list>=4 then add(set.four,list[4]) end
  end
 end
 return stats,perks,sets
end
return S
