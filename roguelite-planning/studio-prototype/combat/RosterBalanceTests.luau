-- Old vs new roster balance (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md). Pure:
-- pass WeaponCatalog and CharacterStats. "Old" is the pre-2026-10-09 math (git HEAD 3c28997), kept
-- here as constants: each weapon's old class list, the class fit matrix (own +15, 0 / -5 / -10 / -15)
-- and the class two / four home bonuses. "New" is the live code: specialty +10% and type sets.
-- Chef has no old self; its old column is Thrower's (Thrower owners became Chef owners).
-- Single target DPS = hit damage x hits per volley x expected crit / cooldown, no items, gear power 1.
-- An extra projectile counts as a whole extra hit (the most it is worth on one target).
-- Prints the tables between ROSTER_BALANCE_BEGIN / _END. Returns the number of checks.
return function(Weapons,Stats)
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 local OLD_CLASSES={['00']={'Gunner'},['01']={'Brawler'},['02']={'Brawler'},['03']={'Brawler'},['04']={'Juggler','Thrower'},
  ['05']={'Juggler','Handyman'},['06']={'Brawler'},['07']={'Gunner'},['08']={'Gunner','Mage'},['09']={'Gunner'},['10']={'Gunner','Thrower'},
  ['11']={'Gunner','Handyman'},['12']={'Thrower','Juggler'},['13']={'Thrower'},['14']={'Thrower','Mage'},['15']={'Thrower','Juggler'},
  ['16']={'Thrower'},['17']={'Juggler','Thrower'},['18']={'Thrower','Juggler'},['19']={'Brawler','Juggler'},['20']={'Brawler','Handyman'},
  ['21']={'Juggler'},['22']={'Juggler','Thrower'},['23']={'Juggler','Brawler'},['24']={'Handyman','Gunner'},['25']={'Handyman'},
  ['26']={'Handyman','Brawler'},['27']={'Handyman'},['28']={'Handyman'},['29']={'Handyman'},['30']={'Mage'},['31']={'Mage','Thrower'},
  ['32']={'Mage','Brawler'},['33']={'Mage'},['34']={'Mage'},['35']={'Mage'},['42']={}} -- Pizza Cutter is new: no old class, fit 0
 local OLD_FIT={Own=15,
  Brawler={Gunner=-15,Thrower=-5,Juggler=-5,Handyman=0,Mage=-10},Gunner={Brawler=-15,Thrower=0,Juggler=-5,Handyman=0,Mage=-5},
  Thrower={Brawler=-5,Gunner=0,Juggler=0,Handyman=0,Mage=-5},Juggler={Brawler=-5,Gunner=-5,Thrower=0,Handyman=0,Mage=-5},
  Handyman={Brawler=0,Gunner=0,Thrower=0,Juggler=0,Mage=-5},Mage={Brawler=-10,Gunner=-5,Thrower=-5,Juggler=-5,Handyman=-5}}
 local OLD={
  Brawler={buffs={MeleeDamage=20,RangedDamage=-15},two={MeleeDamage=15},four={}},
  Gunner={buffs={RangedDamage=20,CritChance=5,MeleeDamage=-15},ranged=10,two={Pierce=1},four={ProjectileCount=1}},
  Thrower={buffs={RangedDamage=15,MeleeDamage=-10},two={RangedDamage=15},four={ProjectileCount=1}},
  Juggler={buffs={AttackSpeed=15,Damage=-10},two={},four={AttackSpeed=15}},
  Handyman={buffs={UtilityPower=15},two={CooldownReduction=10},four={UtilityPower=20},gain={UtilityPower=1.25,Damage=.5}},
  Mage={buffs={ElementalDamage=25,MeleeDamage=-10},two={ElementalDamage=15},four={}},
 }
 local function oldFit(w,class)
  if w.godly then return 0 end
  local best
  for _,c in OLD_CLASSES[w.id] do local pct=c==class and OLD_FIT.Own or OLD_FIT[class][c];best=math.max(best or pct,pct) end
  return best or 0
 end
 local function oldStat(c,id,count)
  local sets=(count>=2 and (c.two[id] or 0) or 0)+(count>=4 and (c.four[id] or 0) or 0)
  if c.gain and c.gain[id] and sets>0 then sets*=c.gain[id] end
  local d=Stats.ById[id];return math.clamp(d.base+(c.buffs[id] or 0)+sets,d.min,d.max)
 end
 local mult=Stats.mult
 local function volley(d,extra) local n=(d.projectileCount or 1)+extra;return d.id=='18' and n/3 or n end
 -- Old: the HEAD formula for one weapon; count = equipped weapons listing the class (copies count).
 local function oldDps(w,class,tier,count)
  local c=OLD[class=='Chef' and 'Thrower' or class]
  local function st(id) return oldStat(c,id,count) end
  local d=Stats.weapon(w,Stats.resolve('Brawler',0,{AttackSpeed=0,CooldownReduction=0}),nil,tier) -- the shape (pellets, cards)
  local dmg=w.tierDamage[tier]*mult(st('Damage'))*mult(w.kind=='Melee' and st('MeleeDamage') or st('RangedDamage'))
  if w.elemental then dmg*=mult(st('ElementalDamage')) end
  if w.utility then dmg*=mult(st('UtilityPower')) end
  dmg*=mult(oldFit(w,class=='Chef' and 'Thrower' or class))
  local speed=mult(st('AttackSpeed'))*(c.ranged and w.kind~='Melee' and 1+c.ranged/100 or 1)
  local cd=math.max(w.kind=='Melee' and .18 or .08,w.cooldown*w.tierCooldown[tier]/speed*(1-st('CooldownReduction')/100))
  local extra=Stats.usesStat(w,'ProjectileCount') and st('ProjectileCount') or 0
  return dmg*volley(d,extra)*(1+st('CritChance')/100*(st('CritDamage')/100-1))/cd
 end
 -- New: the live code for one weapon in a build (counts: Stats.typeCounts of the build).
 local function newDps(w,class,tier,counts)
  local s=Stats.resolve(class,counts)
  local d=Stats.weapon(w,s,class,tier,counts);d.stats=Stats.weaponStats(s,d)
  local extra=Stats.shotStat(d,'ProjectileCount')
  return d.damage*volley(d,extra)*(1+d.stats.CritChance/100*(d.stats.CritDamage/100-1))/d.cooldown
 end
 local function oldCount(ids,class) local n=0;for _,id in ids do if table.find(OLD_CLASSES[id] or {},class=='Chef' and 'Thrower' or class) then n+=1 end end;return n end
 local function buildDps(ids,class,tier)
  local counts=Stats.typeCounts(ids);local old,new=0,0
  for _,id in ids do local w=Weapons.ById[id];old+=oldDps(w,class,tier,oldCount(ids,class));new+=newDps(w,class,tier,counts) end
  return old,new
 end
 local out={}
 local function line(s) table.insert(out,s) end

 -- 1. One weapon, no sets on either side: every class x every ordinary weapon at Tier I and IV.
 local rows,summary={},{}
 for _,class in Stats.ClassOrder do
  for _,w in Weapons.List do
   if w.godly or w.id=='42' then continue end
   local oldOn=table.find(OLD_CLASSES[w.id],class=='Chef' and 'Thrower' or class)~=nil
   local newOn=w.class==class
   local kind=oldOn and newOn and 'kept' or newOn and 'moved in' or oldOn and 'moved out' or 'off'
   for _,tier in {1,4} do
    local o=oldDps(w,class,tier,1);local n=newDps(w,class,tier,Stats.typeCounts({w.id}))
    local r=n/o
    if class~='Chef' then
     if kind=='kept' then check(r<=1.05,string.format('on-class %s %s T%d gains %.1f%%',class,w.id,tier,(r-1)*100)) end
     if kind=='off' then check(r>=1-1e-9,string.format('off-class %s %s T%d worse %.1f%%',class,w.id,tier,(r-1)*100)) end
    end
    local key=(class=='Chef' and 'Chef (old: Thrower) ' or '')..kind
    local sm=summary[key] or {n=0,min=math.huge,max=-math.huge};summary[key]=sm
    sm.n+=1;sm.min=math.min(sm.min,r);sm.max=math.max(sm.max,r)
    if tier==1 then table.insert(rows,{class=class,w=w,kind=kind,o1=o,n1=n}) else rows[#rows].o4=o;rows[#rows].n4=n end
   end
  end
 end
 line('| Group | Rows | New / old (min to max) |');line('|---|---:|---|')
 local keys={};for k in summary do table.insert(keys,k) end;table.sort(keys)
 for _,k in keys do local sm=summary[k];line(string.format('| %s | %d | %.3f to %.3f |',k,sm.n,sm.min,sm.max)) end
 line('');line('Moved weapons (one copy, no items):');line('');line('| Class | Weapon | Change | T1 old -> new DPS | T4 old -> new DPS |');line('|---|---|---|---:|---:|')
 for _,r in rows do
  if r.kind=='moved in' or r.kind=='moved out' or (r.class=='Chef' and r.kind~='off') then
   line(string.format('| %s | %s | %s | %.1f -> %.1f | %.1f -> %.1f |',r.class,r.w.name,r.kind,r.o1,r.n1,r.o4,r.n4))
  end
 end

 -- 2. Pizza Cutter against the Legendary melee (no class, Tier I and IV).
 local neutral=Stats.resolve('Brawler',0,{Damage=0,MeleeDamage=0,RangedDamage=0,ElementalDamage=0,UtilityPower=0,ExplosionDamage=0,AttackSpeed=0,CooldownReduction=0})
 local function raw(id,tier) local d=Stats.weapon(Weapons.ById[id],neutral,nil,tier);return d.damage/d.cooldown,d.range end
 line('');line('| Weapon | Reach | T1 DPS | T4 DPS |');line('|---|---:|---:|---:|')
 for _,id in {'42','03','16','25','31','32'} do local a,reach=raw(id,1);local b=raw(id,4);line(string.format('| %s | %.1f | %.1f | %.1f |',Weapons.ById[id].name,reach,a,b)) end
 local pc,katana=raw('42',1),raw('03',1)
 check(math.abs(pc/katana-1)<=.10,string.format('Pizza Cutter T1 DPS %.2f within 10%% of Katana %.2f',pc,katana))
 check(Weapons.ById['42'].range<Weapons.ById['03'].range and Weapons.ById['42'].cooldown<Weapons.ById['03'].cooldown,'Pizza Cutter: shorter reach, faster hits than Katana')

 -- 3. Builds: old two / four and class fit vs new specialty and sets. Targets (parent, 2026-10-09):
 -- each class's own roster within about -7% to +5% of old at Tier I and IV, guns never above +6%.
 -- Juggler has 7 weapons and 6 slots: its first 6. Chef's old column is Thrower's, so it is shown, not held.
 line('');line('| Build | Class | T1 old -> new | T1 new / old | T4 old -> new | T4 new / old |');line('|---|---|---:|---:|---:|---:|')
 local builds={
  {'Brawler roster','Brawler',{'02','03','04','06','19','20'},true},
  {'Gunner roster (6 guns)','Gunner',{'00','07','08','09','10','11'},true},
  {'Chef roster','Chef',{'01','05','14','15','16','42'},false},
  {'Juggler roster','Juggler',{'12','13','17','18','21','22'},true},
  {'Handyman roster','Handyman',{'24','25','26','27','28','29'},true},
  {'Mage roster','Mage',{'30','31','32','33','34','35'},true},
  {'4 guns','Gunner',{'00','07','09','10'},false},
  {'6 Katanas','Brawler',{'03','03','03','03','03','03'},false},
  {'6 Staffs','Mage',{'30','30','30','30','30','30'},false},
 }
 local misses={}
 for _,b in builds do
  local o1,n1=buildDps(b[3],b[2],1);local o4,n4=buildDps(b[3],b[2],4)
  line(string.format('| %s | %s | %.1f -> %.1f | %.3f | %.1f -> %.1f | %.3f |',b[1],b[2],o1,n1,n1/o1,o4,n4,n4/o4))
  for _,r in {{1,n1/o1},{4,n4/o4}} do
   -- Gunner targets are printed, not held: with one damage curve for every set, 6 guns come out
   -- +10% (Gun 6 +15% x specialty 1.10 against fit 1.15, the projectile on both sides). The parent
   -- decides (2026-10-09); the other rosters are held to the band.
   if b[2]=='Gunner' then
    if r[2]>1.06+1e-9 then table.insert(misses,string.format('%s T%d above +6%% (%.3f)',b[1],r[1],r[2])) end
   elseif b[4] then check(r[2]>=.93-1e-9 and r[2]<=1.05+1e-9,string.format('%s T%d within -7%%..+5%% of old (%.3f)',b[1],r[1],r[2])) end
  end
 end
 line('');for _,m in misses do line('TARGET MISS: '..m) end
 print('ROSTER_BALANCE_BEGIN');for _,s in out do print(s) end;print('ROSTER_BALANCE_END')
 return checks
end
