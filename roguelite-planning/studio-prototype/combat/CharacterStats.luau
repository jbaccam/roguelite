-- Shared schema and pure calculations. Only the server writes effective attributes.
local S={List={},ById={},Classes={},ClassOrder={'Brawler','Gunner','Chef','Juggler','Handyman','Mage'}}
local Motion=require(script.Parent.WeaponMotion)
local Weapons=require(script.Parent.WeaponCatalog) -- starter classes and weapon types (2026-10-09)
-- Air speed x1.45 (user 2026-10-03: "jumping should be like the optimal way to move around", then
-- "i need more of a speed boost when im in the air" -> 1.6, then "just a little too fast"; was
-- 1.12, then 1.3): a Brawler runs 22 and flies 31.9. MovementGuard scales its limit by this number.
S.Movement={Gravity=150,JumpHeight=9.5,AirSpeedMultiplier=1.45}
-- Dash (2026-10-03, play-test: "dash for melee based characters", so melee builds can close in;
-- 2026-10-04 "like a Jett dash ... an actual dash, not a speed boost"): a burst, Peak studs/s at
-- once, easing out ((1-u)^Ease, an ease-out quart in distance) to the run speed by Seconds, on the
-- ground or in the air, once every Cooldown s. At a run of 24: 0.3 x (24 + (280-24)/4) = 26.4 studs,
-- 21 of them in the first 0.14 s. Distance: the most it covers (an air run of 32: 28.2). No damage.
-- Allowance: the extra studs MovementGuard lets an approved dash cover.
-- IFrames (user, 2026-10-04: "very very brief invincibility"): no damage from any source for this
-- long after the server approves the dash (DashAt). 0.35 s covers the 0.3 s burst plus the request's
-- trip to the server; one dash every 3 s makes that about 12% of the time at most.
S.Dash={Peak=280,Ease=3,Seconds=.3,Cooldown=3,Distance=28,Allowance=30,IFrames=.35}
-- Dash is a class ability, never granted by selecting/equipping a melee weapon.
-- Brawler is the current melee-focused class; mixed/ranged classes do not gain it.
function S.dashes(class) return class=='Brawler' end
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
stat('Bounce','Bounces',0,0,4,1,'','Weapon','Extra unique targets for bouncing throws and magic; guns never bounce. 60% per bounce.')
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
-- non-melee weapons only (Gunner); the UI shows it with the buffs (S.classLines). build: the admin
-- panel's Build preset (Practice only), its own class's weapons, signature first. The class two /
-- four home-weapon bonuses went on 2026-10-09: per-weapon specialty and weapon type sets replace them.
S.Classes={
 Brawler={description='Hand-to-hand fighter: tough and hits hard up close. Slower, with weak ranged damage.',buffs={MaxHP=25,Armor=3,MeleeDamage=20,Knockback=8,MoveSpeed=-2,RangedDamage=-15},build={'06','03','19','02'}},
 Gunner={description='Fast, accurate gunfire. Less health and weak melee damage.',buffs={RangedDamage=20,ProjectileSpeed=35,CritChance=5,MaxHP=-15,MeleeDamage=-15},rangedAttackSpeed=10,build={'00','07','09','08'}},
 -- Chef (2026-10-09) takes Thrower's slot: Thrower owners own Chef. Recovery covers pizza, regen and
 -- life steal healing. Pizza drops are ChefPizza's (server); no dash (S.dashes stays Brawler-only).
 Chef={description='Kitchen fighter: sturdy, heals well, and kills with Chef weapons sometimes drop pizza. Thin armor.',buffs={MaxHP=15,MeleeDamage=10,Recovery=25,Armor=-3},build={'01','05','16','15'}},
 Juggler={description='Quick tricks with toys: fast attacks, big knockback, always moving. Lower damage per hit.',buffs={MoveSpeed=3,AttackSpeed=15,Knockback=12,Damage=-10},build={'17','21','22','23'}},
 -- Handyman = Brotato's Engineer (2026-10-04, HANDYMAN_TURRET.md): a free Nail Turret each run and a
 -- tighter turret ring (HandymanTurret.Engineer); gain: Utility Power gains x1.25, Damage gains x0.5
 -- (S.gained). His +5% Damage buff went.
 Handyman={description='Engineer: starts with a Nail Turret. Turrets spawn close to you. Utility Power gains +25%. Damage gains halved.',buffs={UtilityPower=15,AreaSize=20,Regeneration=1,MaxHP=-10},build={'24','25','28','29'},gain={UtilityPower=1.25,Damage=.5}},
 Mage={description='Elemental damage, burn and chains. Fragile, with weak physical attacks.',buffs={ElementalDamage=25,Duration=30,BurnChance=15,ChainCount=1,MaxHP=-20,Armor=-2,MeleeDamage=-10},build={'30','31','34','35'}},
}
-- Each class's starting weapon, also its icon on class cards and tags. RunSetupRules.Signature is
-- this table; ProfileService keeps a copy (it doesn't load this module). Juggler: Rubber Duck since
-- 2026-10-03 (was Boxing Gloves). 2026-10-09: Brawler starts with Boxing Gloves (the Frying Pan is
-- Chef's now) and Chef replaces Thrower. 2026-10-10: Brawler starts with the Baseball Bat instead
-- (user: the Gloves aren't a good starter); the Gloves stay a Brawler weapon, now Rare.
S.Signature={Brawler='06',Gunner='00',Chef='01',Juggler='17',Handyman='24',Mage='30'}
-- Specialty (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md; user: "per weapon,
-- never the whole build"). It replaces the 2026-10-03 class weapon fit and the class two / four
-- bonuses: each equipped weapon whose starter class is yours deals +Specialty% damage. Off-class
-- weapons get no class penalty of their own; only your class's own drawback touches them. Godlies
-- never get it. Example: a Brawler's Katana x1.10 on top of his +20% melee; his Glock takes only
-- his -15% ranged (it took another x0.85 from class fit before).
S.Specialty=10
-- The specialty percent `base` gets with `class`: S.Specialty or 0.
function S.specialty(base,class)
 if type(base)~='table' or base.godly or not S.Classes[class] then return 0 end
 return Weapons.inClass(base,class) and S.Specialty or 0
end
-- The class screen's line: '+10% damage with Chef weapons' ('' for an unknown class).
function S.specialtyText(class) return S.Classes[class] and '+'..S.Specialty..'% damage with '..class..' weapons' or '' end
-- The weapon card's line, only when it applies: 'Chef specialty: +10% damage' (else nil).
function S.specialtyCardText(base,class) return S.specialty(base,class)>0 and class..' specialty: +'..S.Specialty..'% damage' or nil end
-- Whether `class` is the weapon's starter class (WeaponCatalog.inClass). Godly: never.
function S.inClass(base,class) return Weapons.inClass(base,class) end
-- Weapon type sets (2026-10-09, Brotato-style; WeaponCatalog.TypesById). A set counts equipped COPIES
-- (six Katanas = Blade 6), so merging or selling changes it at once (CharacterService.refresh runs on
-- every slot change). Values are running totals at 2 / 3 / 4 / 5 / 6 copies, not add-ons per step.
-- Reworked the same day (parent, after the first balance run had melee rosters -13% and guns +10%):
-- every set gives its weapons the same damage curve, S.SetDamage, and a weapon with two types takes
-- only the higher of its two (never both). Each type adds one flavor bonus on top: scope 'weapon'
-- goes to that type's weapons only (S.weapon, S.weaponStats); 'you' goes to the player's stat
-- (S.resolve, where a class gain such as Handyman's Utility Power x1.25 applies). Gun's flavor is
-- +1 projectile on Gun weapons from 4 copies (it replaces Gunner's old four-weapon projectile).
-- Explosive adds to Area Size for those weapons (+10 = +10% blast radius when nothing else adds area).
-- Example: 3 Katanas + 1 Pizza Cutter = Blade 4: +10% damage and +6% crit chance on those four only;
-- the Pizza Cutter (Blade 4, Culinary 1) takes Blade's +10%.
S.SetDamage={4,7,10,13,15}
S.TypeSets={
 Blade={stat='CritChance',scope='weapon',values={2,4,6,8,10}},
 Blunt={stat='Armor',scope='you',values={1,1,2,2,3}},
 Gun={stat='ProjectileCount',scope='weapon',values={0,0,1,1,1}},
 Thrown={stat='ProjectileSpeed',scope='weapon',values={5,10,15,20,25}},
 Explosive={stat='AreaSize',scope='weapon',values={10,20,30,40,50}},
 Elemental={stat='BurnChance',scope='weapon',values={3,6,9,12,15}},
 Tool={stat='UtilityPower',scope='you',values={4,8,12,16,20}},
 Culinary={stat='LifeSteal',scope='weapon',values={2,3,4,5,6}},
 Trick={stat='Dodge',scope='you',values={2,4,6,8,10}},
}
-- Equipped ids (a list or slot map; '' and unknown ids add nothing) -> {Blade=n, ...} with every type
-- present. Copies count: typeCounts({'03','03','42'}).Blade == 3.
function S.typeCounts(ids)
 local counts={};for _,t in Weapons.Types do counts[t]=0 end
 for _,id in ids or {} do
  if type(id)=='table' then id=id.id end
  for _,t in Weapons.typesOf(id) do counts[t]+=1 end
 end
 return counts
end
local function step(count) count=math.floor(tonumber(count) or 0);return count>=2 and math.min(count,6)-1 or nil end
-- The damage % a set gives its weapons at `count` copies (0 under 2). setDamage(4) == 10.
function S.setDamage(count) local i=step(count);return i and S.SetDamage[i] or 0 end
-- A set's flavor total at `count` copies (0 under 2). setBonus('Blade', 3) == 4; Gun gives the
-- projectile: setBonus('Gun', 4) == 1.
function S.setBonus(t,count)
 local set=S.TypeSets[t];local i=step(count)
 return set and i and set.values[i] or 0
end
-- What the sets give one weapon, by stat: Damage (the higher of its types' curves) plus its types'
-- weapon-scope flavors: CritChance, ProjectileCount, ProjectileSpeed, AreaSize, BurnChance,
-- LifeSteal (missing = 0). counts: S.typeCounts, or nil for none.
function S.weaponSetBonus(base,counts)
 local out={}
 if type(counts)~='table' or type(base)~='table' then return out end
 for _,t in base.types or Weapons.typesOf(base.id) do
  local set=S.TypeSets[t]
  if set then
   local damage=S.setDamage(counts[t])
   if damage>(out.Damage or 0) then out.Damage=damage end
   local v=set.scope=='weapon' and S.setBonus(t,counts[t]) or 0
   if v>0 then out[set.stat]=(out[set.stat] or 0)+v end
  end
 end
 return out
end
-- What the 'you' sets give the player, by stat: {Armor=, UtilityPower=, Dodge=}.
function S.playerSetBonus(counts)
 local out={}
 if type(counts)~='table' then return out end
 for t,set in S.TypeSets do
  local v=set.scope=='you' and S.setBonus(t,counts[t]) or 0
  if v>0 then out[set.stat]=(out[set.stat] or 0)+v end
 end
 return out
end
-- Each flavor in words; %s is its value.
local FLAVOR={Blade='+%s%% crit chance',Blunt='+%s armor',Thrown='+%s%% projectile speed',Explosive='+%s%% blast radius',
 Elemental='+%s%% burn chance',Tool='+%s%% utility power',Trick='+%s%% dodge'}
-- The set at `count` copies in plain words, nil under 2. Examples:
--   setBonusText('Blade', 3) = 'Blade 3: +7% damage and +4% crit chance on Blade weapons'
--   setBonusText('Blunt', 2) = 'Blunt 2: +4% damage on Blunt weapons and +1 armor for you'
--   setBonusText('Gun', 4) = 'Gun 4: +10% damage and +1 projectile on Gun weapons'
--   setBonusText('Culinary', 2) = 'Culinary 2: +4% damage on Culinary weapons, and their hits heal 2% of their damage'
function S.setBonusText(t,count)
 local set=S.TypeSets[t];local damage=S.setDamage(count)
 if not set or damage<=0 then return nil end
 local n=math.min(math.floor(tonumber(count) or 0),6);local v=S.setBonus(t,count)
 local head=t..' '..n..': +'..damage..'% damage'
 if t=='Culinary' then return head..' on Culinary weapons, and their hits heal '..v..'% of their damage' end
 if t=='Gun' then return head..(v>0 and ' and +'..v..' projectile' or '')..' on Gun weapons' end
 local flavor=string.format(FLAVOR[t],tostring(v))
 if set.scope=='you' then return head..' on '..t..' weapons and '..flavor..' for you' end
 return head..' and '..flavor..' on '..t..' weapons'
end
-- The in-run Sets list and shop hints: one row per type with at least one equipped copy, in
-- WeaponCatalog.Types order: {type=, count=, damage= (% now, 0 under 2), current= (flavor now),
-- next= (copies for the next step, nil at 6), nextDamage=, nextValue= (flavor then), scope= 'weapon'
-- or 'you' (the flavor's), text= (now, nil under 2), nextText=}.
-- Example, {'03','03'}: Blade, count 2, damage 4, current 2, next 3, nextDamage 7, nextValue 4.
function S.typeLines(ids)
 local counts=S.typeCounts(ids);local out={}
 for _,t in Weapons.Types do
  local n=counts[t]
  if n>0 then
   local nxt=n<6 and math.max(2,n+1) or nil
   table.insert(out,{type=t,count=n,damage=S.setDamage(n),current=S.setBonus(t,n),next=nxt,nextDamage=nxt and S.setDamage(nxt) or nil,
    nextValue=nxt and S.setBonus(t,nxt) or nil,scope=S.TypeSets[t].scope,text=S.setBonusText(t,n),nextText=nxt and S.setBonusText(t,nxt) or nil})
  end
 end
 return out
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
-- '+15% Melee damage · +2 Armor' for a {stat=value} table (nil gives ''; the class two / four
-- tables it formatted are gone, 2026-10-09).
function S.bonusText(t)
 local out={};t=t or {}
 for _,d in S.List do local v=t[d.id];if v then table.insert(out,(v>0 and '+' or '')..v..S.statUnit(d)..' '..d.label) end end
 return table.concat(out,' · ')
end
function S.valid(id,value)
 local d=S.ById[id]
 local count=table.find({'ProjectileCount','Pierce','Bounce','PoisonStacks','ChainCount','ChainBonus','ChainEvery','BurnSpread','FirstHitBlock'},id)
 return d~=nil and type(value)=='number' and value==value and value>=d.min and value<=d.max and (not count or value%1==0)
end
-- Stat gains (2026-10-04, the Handyman as Brotato's Engineer): a class's `gain` multiplies what its
-- weapon type sets (the 'you' ones, 2026-10-09), items, level-up cards, skills, armour and pets add
-- to a stat, when that adds up to more than 0. The stat's base and the class's own buffs aren't gains. Examples for the
-- Handyman (gain UtilityPower 1.25, Damage 0.5): a +12 Utility Power card gives +15; an item with
-- +10% Damage gives +5%; a -3 never changes.
function S.gained(c,id,amount)
 local g=c and c.gain and c.gain[id]
 if g and amount>0 then return amount*g end
 return amount
end
-- sets: S.typeCounts of the equipped copies, for the 'you' type sets (Blunt armor, Tool utility
-- power, Trick dodge; 2026-10-09). It was the number of home-class weapons for the class two / four
-- bonuses, which are gone; a number is ignored, so older callers (resolve(class, 0)) still line up.
function S.resolve(class,sets,overrides,bonuses,percent)
 local result={};local c=S.Classes[class] or S.Classes.Brawler
 local typed=S.playerSetBonus(sets)
 for _,d in S.List do
  local value=d.base+(c.buffs[d.id] or 0)+S.gained(c,d.id,(typed[d.id] or 0)+((bonuses or {})[d.id] or 0))
  value=value*(1+((percent or {})[d.id] or 0)/100)
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
-- Weapon-only stats (2026-10-03): whether a weapon really uses one. The one answer for the
-- server's launchers (they read shot stats through S.shotStat), S.weapon (explosion damage), the
-- run shop's offers and the cards' "Works with" line, so none of them can disagree. It follows how
-- each weapon attacks: gun bullets use extra shots and pierce, never bounce; cards also bounce; thrown
-- weapons that fly back (Boomerang, Mjolnir, Trident) get pierce and bounce but no extra copies;
-- fire and gas throws (Molotov, Fart Gun) and explosives (Rocket Launcher, Pandora's Box) get extra
-- copies only; the Storm Bow rains more arrows; swings, the Rubber Duck's spray and the Vacuum /
-- Power Washer streams use none. Example: Two Straws gives a Glock 2 bullets, a Frying Pan nothing.
-- AreaSize and the lightning stats also count the player's own sources: with Battery Pack
-- (ChainCount 1) every weapon's hits chain lightning, so Tinfoil Antlers helps them all.
-- Attack families (2026-10-09, the family items): Melee damage helps swings; Ranged damage helps
-- everything else and the throwing hybrids (Mjolnir, Trident: a throw swaps the multiplier,
-- RogueliteCombat); Elemental damage helps elemental weapons, native burn / poison, and any weapon
-- once the player has burn or poison chance (status ticks use it). Turrets ignore all three.
-- AreaSize (2026-10-09) also counts the Duck's cone, the Vacuum / Washer streams and the Legendary
-- Tier IV moves that grow with it (at Tier IV, or any tier when the tier isn't known). The Bowling
-- Ball's roll never reads Pierce or Bounce.
-- Any other stat helps every weapon (true).
local Thrown=require(script.Parent.SpecialMotion).profiles -- SpecialWeapons' throws
-- A gun commits its firing line for its entire flight, including piercing contacts.
S.StraightGuns={['00']=true,['07']=true,['08']=true,['09']=true,['10']=true,['11']=true,['24']=true,['41']=true,Turret=true}
S.WeaponStats={ProjectileCount=true,Pierce=true,Bounce=true,ExplosionDamage=true,AreaSize=true,ChainBonus=true,ChainDamage=true,MeleeDamage=true,RangedDamage=true,ElementalDamage=true}
local AREA_SPECIALS={'waveRadius','spread','hop','burstRadius'} -- Godly special sizes GodlyWeapons scales by AreaSize
local AREA_MOVES={Slash=true,Beam=true,Shock=true,Split=true,Thunder=true,Strike=true,Roll=true} -- LegendaryMoves sizes (not the Royal Flush)
function S.usesStat(base,id,stats)
 if not S.WeaponStats[id] then return true end
 local w=base.id;local thrown=Thrown[w]
 if id=='MeleeDamage' or id=='RangedDamage' or id=='ElementalDamage' then
  if w=='Turret' then return false end
  if id=='MeleeDamage' then return base.kind=='Melee' end
  if id=='RangedDamage' then return base.kind~='Melee' or base.hybridRange~=nil end
  return base.elemental==true or (base.burn or 0)>0 or (base.poison or 0)>0 or (stats~=nil and ((stats.BurnChance or 0)>0 or (stats.PoisonChance or 0)>0))
 end
 if id=='Bounce' and S.StraightGuns[w] then return false end
 if id=='ExplosionDamage' then return base.kind=='Blast' end
 if id=='ChainBonus' or id=='ChainDamage' then return base.lightning==true or (stats~=nil and (stats.ChainCount or 0)>0) end
 if id=='AreaSize' then
  if base.blastRadius or (thrown and thrown.zone) or base.lightning then return true end
  if w=='17' or w=='28' or w=='29' then return true end
  local move=Weapons.Legendary[w]
  if move and AREA_MOVES[move.move] and (base.tier==nil or base.tier>=4) then return true end
  if stats and ((stats.ChainCount or 0)>0 or (stats.BurnSpread or 0)>0) then return true end
  for _,k in AREA_SPECIALS do if base.special and base.special[k] then return true end end
  return false
 end
 -- Shot stats, by launcher (RogueliteCombat shoot): Storm Bow arrows, spray and streams, the
 -- bowling roll, throws, swings, rockets and blasts, then bullets and cards.
 if w=='38' then return id=='ProjectileCount' end
 if w=='17' or w=='28' or w=='29' then return false end
 if w=='22' then return id=='ProjectileCount' end
 if thrown then if id=='ProjectileCount' then return not thrown.returns end;return not thrown.zone end
 if base.kind=='Melee' then return false end
 if w=='11' or base.kind=='Blast' then return id=='ProjectileCount' end
 return true
end
-- A shot stat as an attack uses it: 0 when the weapon doesn't (d: S.weapon's result, d.stats set).
-- Example: Two Straws on a Boomerang throw: S.shotStat(d,'ProjectileCount') is 0.
function S.shotStat(d,id) return S.usesStat(d,id) and (d.stats[id] or 0) or 0 end
-- sets (2026-10-09): S.typeCounts of the equipped copies; nil (previews, tests) means no type sets.
-- d.specialty: the specialty percent it got; d.typeBonus: S.weaponSetBonus (the server hands it to
-- S.weaponStats for d.stats).
function S.weapon(base,s,class,tier,sets)
 tier=math.clamp(math.floor(tonumber(tier) or 1),1,4)
 local d=table.clone(base)
 d.tier=tier
 local bonus=S.weaponSetBonus(base,sets);d.typeBonus=bonus
 d.damage=(base.tierDamage and base.tierDamage[tier] or base.damage)*S.mult(s.Damage)*S.mult(base.kind=='Melee' and s.MeleeDamage or s.RangedDamage)
 if base.elemental then d.damage*=S.mult(s.ElementalDamage) end
 if base.utility then d.damage*=S.mult(s.UtilityPower) end
 if S.usesStat(base,'ExplosionDamage') then d.damage*=S.mult(s.ExplosionDamage) end
 -- Specialty (2026-10-09; it replaced the class weapon fit here): +10% on a weapon of your class.
 d.specialty=S.specialty(base,class)
 d.damage*=S.mult(d.specialty)
 -- Type sets: the higher damage curve of its types.
 d.damage*=S.mult(bonus.Damage or 0)
 local cc=S.Classes[class]
 local speed=S.mult(s.AttackSpeed)*(cc and cc.rangedAttackSpeed and base.kind~='Melee' and 1+cc.rangedAttackSpeed/100 or 1)
 d.cooldown=math.max(base.kind=='Melee' and .18 or .08,base.cooldown*(base.tierCooldown and base.tierCooldown[tier] or 1)/speed*(1-s.CooldownReduction/100))
 -- Animation speed is independent of damage cadence: heavy weapons strike
 -- crisply, then wait for their longer cooldown. Nunchucks use a slower cut.
 d.motionRate=base.kind=='Melee' and (base.id=='02' and 1.35 or base.id=='19' and 2.7 or 1.8)*speed/(1-s.CooldownReduction/100) or base.cooldown/d.cooldown
 d.range=base.range*S.mult(s.AttackRange)
 d.targetRange=(base.hybridRange or base.range)*S.mult(s.AttackRange)
 d.projectileSpeed=(base.projectileSpeed or 110)*S.mult(s.ProjectileSpeed+(bonus.ProjectileSpeed or 0)) -- Thrown set: faster throws
 d.projectileCount=base.kind=='Spread' and (4+tier) or base.id=='18' and (tier>=3 and 4 or 3) or (base.trait=='shots' and tier>=2 and 2 or 1)
 d.nativePierce=base.trait=='pierce' and math.floor(tier/2) or 0
 if base.id=='22' then d.nativePierce=math.min(4,3+math.floor(tier/3)) end
 d.nativeBounce=base.id=='12' and math.min(4,tier+1) or base.trait=='bounce' and (tier-1) or 0
 d.projectileRadius=.12*S.mult(s.ProjectileSize)
 -- Explosive set: Area Size for those weapons (+10 at 2 copies = +10% blast radius with no other area).
 d.blastRadius=(base.blastRadius or 7)*S.mult(math.clamp(s.AreaSize+(bonus.AreaSize or 0),S.ById.AreaSize.min,S.ById.AreaSize.max))
 return d
end
-- The stats one weapon's hits use (2026-10-09): the player's, plus its weapon-scope sets that are
-- stats (Blade crit chance, Explosive Area Size, Gun's 4-copy projectile, Elemental burn chance,
-- Culinary life steal; Thrown's projectile speed is already in d.projectileSpeed), each
-- kept inside the stat's bounds. The server gives each slot's definition this as d.stats, so every
-- launcher, crit roll and life-steal heal reads that weapon's numbers. Returns `stats` itself when no
-- such set applies. d: S.weapon's result. Example: Blade 2 and CritChance 5 -> 8 for a Katana only.
local WEAPON_SET_STATS={'CritChance','AreaSize','ProjectileCount','BurnChance','LifeSteal'}
function S.weaponStats(stats,d)
 local bonus=d and d.typeBonus;local out=stats
 for _,id in WEAPON_SET_STATS do
  local v=bonus and bonus[id]
  if v and v~=0 then
   if out==stats then out=table.clone(stats) end
   local def=S.ById[id];out[id]=math.clamp((out[id] or def.base)+v,def.min,def.max)
  end
 end
 return out
end
-- Lightning targets for one weapon's chain (CombatEffectsService): the player's Lightning targets plus
-- 1 for a lightning weapon, then Extra lightning targets, at most 6; 0 = no chain. Battery Pack fix
-- (2026-10-09, items audit 6.4): it was the bigger of the two, so a lightning weapon's first Battery
-- Pack added nothing. Example: Crystal Ball + one Battery Pack (ChainCount 1) = 2 targets (was 1).
function S.chainTargets(s,w)
 local source=(s.ChainCount or 0)+((w and w.lightning) and 1 or 0)
 if source<=0 then return 0 end
 return math.min(6,source+(s.ChainBonus or 0))
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
