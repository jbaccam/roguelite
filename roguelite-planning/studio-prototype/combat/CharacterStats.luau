-- Shared schema and pure calculations. Only the server writes effective attributes.
local S={List={},ById={},Classes={},ClassOrder={'Brawler','Gunner','Thrower','Juggler','Handyman','Mage'}}
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
stat('MoveSpeed','Movement speed',18,6,40,2,' studs/s','Utility','Actual Humanoid WalkSpeed.')
stat('PickupRadius','Pickup radius',8,1,50,2,' studs','Utility','Collects owner-only practice health drops. XP is deferred.')
stat('Luck','Luck',0,0,100,10,'','Utility','Health-drop chance: 15% + Luck / 500, up to 35%. No weapon weighting.')
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
stat('ChainEvery','Lightning frequency',5,1,20,1,' hits','Status','One chain every N direct hits; secondary hits cannot trigger chains.')
stat('ChainDamage','Lightning damage',0,-80,300,10,'%','Status','Chain hits deal 40% of base weapon damage, then this bonus.')
stat('FirstHitBlock','First-hit blocks',0,0,1,1,'','Defense','One block per wave; practice reset restores it, stat edits do not.')
stat('ContactReduction','Contact resistance',0,0,60,5,'%','Defense','Reduces zombie contact damage before armor.')
stat('ShopDiscount','Shop discount',0,0,30,5,'%','Economy','Reduces unlocked shop offer prices; locked prices stay fixed.')
stat('ShopPricePercent','Shop price modifier',0,-80,200,5,'%','Economy','Positive values increase prices; negative values reduce them. Combined multiplier is bounded.')
S.Classes={
 Brawler={description='Durable close-range bruiser. Slower movement and weaker ranged damage.',buffs={MaxHP=25,Armor=4,MeleeDamage=20,Knockback=8,ContactReduction=15,MoveSpeed=-2,RangedDamage=-15},build={'01','03','06','02'},two={MeleeDamage=15,Armor=2},four={LifeSteal=5}},
 Gunner={description='Fast ranged attacks and piercing. Less health and weaker melee.',buffs={RangedDamage=20,ProjectileSpeed=35,CritChance=5,MaxHP=-15,MeleeDamage=-15},build={'00','07','09','08'},two={Pierce=1},four={ProjectileCount=1}},
 Thrower={description='Long-range volleys and rebounds. Lower attack speed and armor.',buffs={AttackRange=25,Bounce=1,RangedDamage=10,AttackSpeed=-10,Armor=-2},build={'12','13','14','18'},two={RangedDamage=15},four={ProjectileCount=1}},
 Juggler={description='Mobile knockback and rebound build. Lower damage per hit.',buffs={MoveSpeed=3,AttackSpeed=15,Knockback=12,Damage=-15},build={'19','17','21','22'},two={AttackRange=15,Knockback=5},four={Bounce=1,AttackSpeed=15}},
 Handyman={description='Wide utility attacks and recovery. Slower movement and fewer criticals.',buffs={UtilityPower=25,AreaSize=20,Regeneration=1,MoveSpeed=-2,CritChance=-5},build={'24','25','28','29'},two={CooldownReduction=10},four={UtilityPower=20}},
 Mage={description='Elemental damage, burn and chains. Fragile with weaker physical attacks.',buffs={ElementalDamage=25,Duration=30,BurnChance=15,ChainCount=1,MaxHP=-20,Armor=-2,MeleeDamage=-10},build={'30','31','34','35'},two={ElementalDamage=15},four={BurnSpread=1}},
}
function S.valid(id,value)
 local d=S.ById[id]
 local count=table.find({'ProjectileCount','Pierce','Bounce','PoisonStacks','ChainCount','ChainEvery','BurnSpread','FirstHitBlock'},id)
 return d~=nil and type(value)=='number' and value==value and value>=d.min and value<=d.max and (not count or value%1==0)
end
function S.resolve(class,count,overrides,bonuses,percent)
 local result={};local c=S.Classes[class] or S.Classes.Brawler
 for _,d in S.List do
  local value=d.base+(c.buffs[d.id] or 0)+(count>=2 and (c.two[d.id] or 0) or 0)+(count>=4 and (c.four[d.id] or 0) or 0)
  value=(value+((bonuses or {})[d.id] or 0))*(1+((percent or {})[d.id] or 0)/100)
  if table.find({'ProjectileCount','Pierce','Bounce','PoisonStacks','ChainCount','ChainEvery','BurnSpread','FirstHitBlock'},d.id) then value=math.round(value) end
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
 local d=table.clone(base)
 d.damage=base.damage*S.mult(s.Damage)*S.mult(base.kind=='Melee' and s.MeleeDamage or s.RangedDamage)
 if base.elemental then d.damage*=S.mult(s.ElementalDamage) end
 if base.utility then d.damage*=S.mult(s.UtilityPower) end
 if base.kind=='Blast' then d.damage*=S.mult(s.ExplosionDamage) end
 d.damage*=require(script.Parent.EconomyConfig).TIER_DAMAGE_MULTIPLIERS[tier or 1] or 1
 local speed=S.mult(s.AttackSpeed)*(class=='Gunner' and base.kind~='Melee' and 1.1 or 1)
 d.cooldown=math.max(base.kind=='Melee' and .18 or .08,base.cooldown/speed*(1-s.CooldownReduction/100))
 d.motionRate=base.cooldown/d.cooldown
 d.range=base.range*S.mult(s.AttackRange)
 d.projectileSpeed=(base.projectileSpeed or 110)*S.mult(s.ProjectileSpeed)
 d.projectileRadius=.12*S.mult(s.ProjectileSize)
 d.blastRadius=(base.blastRadius or 7)*S.mult(s.AreaSize)
 return d
end
function S.format(d,value) return string.format(value%1==0 and '%d' or '%.1f',value)..d.unit end
return S
