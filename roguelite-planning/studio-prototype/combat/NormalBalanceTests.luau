-- Roster-wide direct-damage audit. A hit unit can be a pellet/tick/volley basis;
-- this deliberately does not pretend every damage unit is one whole attack.
return function(Catalog, Weapons, Stats, Rules)
 local count=0
 local function check(ok,label) count+=1;assert(ok,label) end
 local normal=Rules.difficulty('Normal')
 check(normal.hp==.6 and normal.damage==.75 and normal.reward==1,'approachable Normal; unchanged rewards')
 check(Rules.difficulty('Hard').hp==1.6 and Rules.difficulty('Hard').damage==1.3,'Hard unchanged')
 check(Rules.difficulty('Nightmare').hp==2.5 and Rules.difficulty('Nightmare').damage==1.6,'Nightmare unchanged')
 local function hp(id,wave,map,difficulty)
  local _,scale=Rules.enemyScale(map,difficulty)
  return math.ceil(Catalog.scaled(id,wave).health*scale)
 end
 check(hp('regular-zombie',20,'PineValley','Normal')==25,'late Normal fodder HP')
 check(hp('tank-zombie',20,'PineValley','Normal')==138,'late Normal tank HP')
 local rows={}
 local oneShotT4,atMostTwoT4=0,0
 for _,w in Weapons.List do
  local classes=w.godly and Stats.ClassOrder or {w.home}
  for _,class in classes do
   local a=Stats.weapon(w,Stats.resolve(class,1),class,1)
   local b=Stats.weapon(w,Stats.resolve(class,6),class,4)
   local hit1=math.ceil(hp('regular-zombie',1,'PineValley','Normal')/a.damage)
   local hit5=math.ceil(hp('regular-zombie',5,'PineValley','Normal')/a.damage)
   local hit20=math.ceil(hp('regular-zombie',20,'PineValley','Normal')/b.damage)
   local tank20=math.ceil(hp('tank-zombie',20,'PineValley','Normal')/b.damage)
   check(a.damage>0 and b.damage>a.damage,'tier improvement '..w.id..class)
   check(hit1==1,'every home T1 damage unit clears first-wave fodder '..w.id..class)
   check(hit20<=math.ceil(41/b.damage),'Normal never worsens late damage-unit count '..w.id..class)
   for _,map in Rules.Maps do
    local scale=Stats.powerDamage(map.power)
    local oldHp=math.ceil(Catalog.scaled('regular-zombie',20).health*scale)
    check(hp('regular-zombie',20,map.id,'Normal')<=oldHp,'every map eased '..w.id..class)
    check(hp('tank-zombie',20,map.id,'Hard')>hp('tank-zombie',20,map.id,'Normal'),'optional challenge stays harder')
   end
   if not w.godly then
    if hit20==1 then oneShotT4+=1 end
    if hit20<=2 then atMostTwoT4+=1 end
   end
   table.insert(rows,string.format('| %s | %s | %.2f | %d / %d | %.2f | %d / %d |',w.name,class,a.damage,hit1,hit5,b.damage,hit20,tank20))
  end
 end
 -- No run damage boosts used: reward progression with broad improvement, not forced equality.
 check(atMostTwoT4>=34,'most class weapons clear late fodder in at most two direct damage units')
 print('NORMAL_ROSTER_BEGIN')
 print('| Weapon | Class | T1 damage | T1 regular hits W1 / W5 | T4 damage | T4 W20 regular / tank hits |')
 print('|---|---|---:|---:|---:|---:|')
 for _,row in rows do print(row) end
 print('NORMAL_ROSTER_END')
 print(string.format('NormalBalanceTests: %d assertions; class weapons T4 one-hit %d/36, at-most-two %d/36; all42 weapons audited (Godly across all6 classes).',count,oneShotT4,atMostTwoT4))
 return count
end
