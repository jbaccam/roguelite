-- Pure assertions against actual catalog/stat functions. No Instances, rewards or DataStores.
return function(Catalog, Types, Weapons, Stats, Rules, Scheduler)
 local checks=0
 local function check(ok,label) checks+=1;assert(ok,label) end
 local function near(a,b) return math.abs(a-b)<1e-6 end
 local expectedSpeeds={['regular-zombie']=14,['baby-zombie']=17,['tank-zombie']=11,
  ['spitter-zombie']=13,crab=16,snake=15,['hermit-crab']=12,['rock-throwing-crab']=13,
  skeleton=17,['bow-skeleton']=14,mummy=13,scorpion=15,['frost-ghost']=16,werewolf=21,
  ['frozen-knight']=12,['ice-elf']=14,['fire-goblin']=18,['ember-spider']=20,['lava-slime']=13,['obsidian-ogre']=12,['ash-shaman']=13}
 for _,d in Catalog.List do
  check(d.speed==expectedSpeeds[d.id],'Pine slowdown; other roster speeds preserved '..d.id)
  for _,difficulty in Rules.Difficulties do
   local move=Rules.enemyMoveScale(difficulty.id)
   check(move==(difficulty.id=='Normal' and .85 or 1),'difficulty regular movement factor')
   for wave=1,20 do
    local effective=Scheduler.endlessSpeed(Catalog.scaled(d.id,wave).speed*move,Scheduler.endless(wave))
    check(near(effective,d.speed*move),'difficulty movement remains constant through wave20 '..d.id)
    if difficulty.id=='Normal' then check(effective<18,'Normal fastest roster enemy stays below18 '..d.id) end
   end
  end
  local original=table.clone(d)
  for wave=1,20 do
   local current=Catalog.scaled(d.id,wave)
   local previous=Catalog.scaled(d.id,math.max(1,wave-1))
   check(current.health>=previous.health and current.damage>=previous.damage,'monotonic '..d.id)
   check(current.speed==d.speed,'regular waves never increase speed '..d.id)
   check(near(current.damage,d.damage+d.damagePerWave*(wave-1)),'linear damage '..d.id)
   if wave>4 then check(near(current.health-previous.health,d.healthPerWave),'linear HP '..d.id) end
  end
  for _,wave in {0,-100,0/0,-math.huge} do
   check(Catalog.scaled(d.id,wave).health==Catalog.scaled(d.id,1).health,'invalid wave fallback '..d.id)
  end
  check(Catalog.scaled(d.id,math.huge).health==Catalog.scaled(d.id,1000).health,'wave growth bound '..d.id)
  for k,v in original do check(d[k]==v,'scaling never mutates catalog '..d.id..'.'..k) end
 end
 for _,case in {{1,3,1,50},{10,21,10,119},{20,41,20,229}} do
  for i,id in {'regular-zombie','baby-zombie','tank-zombie'} do
   check(Catalog.scaled(id,case[1]).health==case[i+1],'HP benchmark '..id)
  end
 end
 check(Types.scaled('Regular',0/0).health==3,'native NaN fallback')
 check(Rules.enemyMoveScale(nil)==.85 and Rules.enemyMoveScale('Unknown')==.85,'unknown difficulty uses approachable Normal movement')
 check(Types.scaled('Mutant',20).damage==0,'tank has no extra contact damage')
 check(near(Catalog.scaled('regular-zombie',20).damage,22.1),'regular damage benchmark')
 check(near(Catalog.scaled('tank-zombie',20).damage,38.5),'tank damage benchmark')
 local boosted=Stats.resolve('Gunner',6,nil,{Damage=50,RangedDamage=30,AttackSpeed=30})
 -- 2026-10-09: the own-class bonus went from class fit x1.15 to specialty x1.10, and the old six-weapon
 -- count became type sets. glock: one Glock, no sets; glock6: six Glocks (Gun 6: +15% damage).
 local glock=Stats.weapon(Weapons.ById['00'],boosted,'Gunner',4)
 local glock6=Stats.weapon(Weapons.ById['00'],boosted,'Gunner',4,Stats.typeCounts({'00','00','00','00','00','00'}))
 local regular=Catalog.scaled('regular-zombie',20).health
 local baby=Catalog.scaled('baby-zombie',20).health
 local tank=Catalog.scaled('tank-zombie',20).health
 check(glock.damage>=regular,'strong tier IV Glock one-shots regular fodder')
 check(glock.damage>=baby,'fast fodder still clears in one upgraded hit')
 check(tank>2*glock.damage and tank<=3*glock.damage,'strong tier IV Glock takes three heavy hits')
 check(6*glock.damage/glock.cooldown>tank,'six guns can focus a tank inside one second of ideal DPS')
 check(glock6.damage>=regular and tank>2*glock6.damage and tank<=3*glock6.damage,'six Glocks: one-shot fodder, three tank hits')
 -- 2026-10-09: the Pan is Chef's; Chef + Pan joins. 2026-10-10: Brawler starts with the Baseball Bat
 -- (the Boxing Gloves' two-jab time-to-kill rule went with them), so every starter one-shots early
 -- fodder. Example: wave-5 regular (11 HP), Brawler Tier I Bat 26.4 a swing (20 x 1.2 melee x 1.1 specialty).
 local starters={{'Brawler','06'},{'Gunner','00'},{'Chef','01'},{'Mage','30'}}
 for _,starter in starters do
  local class,id=starter[1],starter[2]
  local early=Stats.weapon(Weapons.ById[id],Stats.resolve(class,1),class,1)
  for wave=1,5 do
   for _,kind in {'regular','baby'} do
    local health=Catalog.scaled(kind..'-zombie',wave).health
    check(early.damage>=health,'starter one-shots early '..kind..' '..class..' wave '..wave)
   end
  end
  local middle=Stats.weapon(Weapons.ById[id],Stats.resolve(class,4,nil,{Damage=20,AttackSpeed=15}),class,2)
  check(middle.damage>=Catalog.scaled('regular-zombie',10).health,'moderate tier II clears wave10 regular '..class)
  print(string.format('Starter %s TierI %.3f damage; moderate TierII wave10 %.3f damage',class,early.damage,middle.damage))
 end
 for _,map in Rules.Maps do
  for _,difficulty in Rules.Difficulties do
   local extra,hp,damage=Rules.enemyScale(map.id,difficulty.id)
   check(extra==0,'map scaling is not double-applied as wave offsets')
   check(near(hp,Stats.powerDamage(map.power)*difficulty.hp),'map HP matches gear power')
   check(near(damage,Stats.powerHealth(map.power)*difficulty.damage),'map damage matches gear health')
   -- Matching permanent gear power cancels the map HP factor, preserving build pacing.
   local adjustedShot=glock.damage*Stats.powerDamage(map.power)
   local regularHits=math.ceil(math.ceil(regular*hp)/adjustedShot)
   local tankHits=math.ceil(math.ceil(tank*hp)/adjustedShot)
   check(regularHits==(difficulty.id=='Nightmare' and 2 or 1),'strong build fodder hits at matching gear')
   -- 2026-10-09 (specialty x1.10, was fit x1.15): Nightmare tank 8 hits (was 7) for one Glock with no sets.
   check(tankHits==({Normal=2,Hard=5,Nightmare=8})[difficulty.id],'heavy difficulty hits at matching gear')
   local shot6=glock6.damage*Stats.powerDamage(map.power)
   check(math.ceil(math.ceil(regular*hp)/shot6)==(difficulty.id=='Nightmare' and 2 or 1),'six Glocks fodder hits at matching gear')
   check(math.ceil(math.ceil(tank*hp)/shot6)==({Normal=2,Hard=4,Nightmare=7})[difficulty.id],'six Glocks (Gun 6) heavy difficulty hits at matching gear')
   for _,wave in {1,10,20,30,40} do
    local scale=Scheduler.endless(wave)
    local d=Catalog.scaled('regular-zombie',wave)
    local final=d.health*hp*scale.health
    check(final>0 and final<1e7,'finite composed HP')
    check(wave>20 or scale.health==1 and scale.damage==1 and scale.speed==0,'no Endless in normal waves')
   end
  end
 end
 check(Scheduler.population(100,4,0)==Scheduler.MAX_POPULATION,'multiplayer count remains capped')
 print(string.format('EnemyScalingTests: %d assertions; boosted Glock %.3f damage / %.3fs, six-slot ideal DPS %.1f',checks,glock.damage,glock.cooldown,6*glock.damage/glock.cooldown))
 return checks
end
