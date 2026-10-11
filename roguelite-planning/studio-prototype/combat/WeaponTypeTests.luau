-- Starter classes, weapon types, type sets and specialty (2026-10-09,
-- plans/2026-10-09-chef-roster-weapon-types-design.md). Pure: pass WeaponCatalog, CharacterStats and
-- (optional) RunSetupRules. CLI: python combat/run_roster_tests.py build/luau-validation/luau.exe
-- Returns the number of checks.
return function(Weapons,Stats,Rules)
 local checks=0
 local function check(ok,message) checks+=1;assert(ok,message) end
 local function near(a,b,message) check(math.abs(a-b)<1e-6,message..' ('..tostring(a)..' vs '..tostring(b)..')') end
 local function set(list) local out={};for _,v in list do out[v]=true end;return out end

 -- Classes: Chef in Thrower's slot; every ordinary weapon has exactly one class; 6+ per class.
 check(table.concat(Stats.ClassOrder,',')=='Brawler,Gunner,Chef,Juggler,Handyman,Mage','class order')
 check(Stats.Classes.Thrower==nil and Stats.Signature.Thrower==nil,'Thrower removed')
 local perClass={}
 for _,w in Weapons.List do
  if w.godly then
   check(w.class==nil and #w.classes==0 and w.home=='Godly','Godly is classless '..w.id)
  else
   check(table.find(Stats.ClassOrder,w.class)~=nil and #w.classes==1 and w.classes[1]==w.class and w.home==w.class,'one known class '..w.id)
   perClass[w.class]=(perClass[w.class] or 0)+1
  end
 end
 for _,class in Stats.ClassOrder do
  -- Mage is 5 since Excalibur moved to Brawler (2026-10-10) until its planned spellbook lands.
  local least=class=='Mage' and 5 or 6
  check((perClass[class] or 0)>=least,class..' has '..least..'+ weapons')
  local sig=Weapons.ById[Stats.Signature[class]]
  check(sig and sig.class==class and sig.rarity=='Common','signature is a Common '..class..' weapon')
  check(Stats.Classes[class].build[1]==Stats.Signature[class],'build opens with the signature '..class)
  for _,id in Stats.Classes[class].build do check(Weapons.ById[id].class==class,'build uses own weapons '..class..' '..id) end
  check(Stats.Classes[class].two==nil and Stats.Classes[class].four==nil,'no two / four bonuses '..class)
  check(Stats.dashes(class)==(class=='Brawler'),'dash stays Brawler-only '..class)
 end
 -- 2026-10-10: Brawler starts with the Baseball Bat (Common); the Boxing Gloves are a Rare Brawler weapon.
 check(Stats.Signature.Brawler=='06' and Stats.Signature.Chef=='01','Brawler starts with the Bat, Chef with the Pan')
 check(Weapons.ById['19'].class=='Brawler' and Weapons.ById['19'].rarity=='Rare','Boxing Gloves: a Rare Brawler weapon')
 local chef=Stats.Classes.Chef.buffs
 check(chef.MaxHP==15 and chef.MeleeDamage==10 and chef.Recovery==25 and chef.Armor==-3,'Chef buffs and drawback')
 local n=0;for _ in chef do n+=1 end;check(n==4,'Chef has exactly those four stats')
 check(Stats.Classes.Chef.description=='Kitchen fighter: sturdy, heals well, and kills with Chef weapons sometimes drop pizza. Thin armor.','Chef description')
 check(Stats.ClassFit==nil and Stats.classFitText==nil,'class fit matrix removed')

 -- Pizza Cutter.
 local pc=Weapons.ById['42']
 check(pc.name=='Pizza Cutter' and pc.kind=='Melee' and pc.rarity=='Legendary' and pc.class=='Chef','Pizza Cutter: melee Legendary, Chef')
 check(pc.authoredDamage==13 and pc.authoredCooldown==.70 and pc.range==10,'Pizza Cutter authored 13 / .70 / 10')
 check(not pc.elemental and not pc.utility and table.concat(pc.types,',')=='Blade,Culinary','Pizza Cutter flags and types')

 -- Types: vocabulary, 1-2 each, the spec's member counts.
 check(table.concat(Weapons.Types,',')=='Blade,Blunt,Gun,Thrown,Explosive,Elemental,Tool,Culinary,Trick','type vocabulary')
 local vocab=set(Weapons.Types);local members={}
 for _,w in Weapons.List do
  check(#w.types>=1 and #w.types<=2,'1-2 types '..w.id)
  check(table.concat(Weapons.typesOf(w.id),',')==table.concat(w.types,','),'typesOf '..w.id)
  local seen={}
  for _,t in w.types do check(vocab[t] and not seen[t],'known, distinct type '..w.id..' '..t);seen[t]=true;members[t]=(members[t] or 0)+1 end
  if seen.Elemental then check(w.elemental,'Elemental type has the flag '..w.id) end
  if seen.Tool then check(w.utility,'Tool type has the flag '..w.id) end
 end
 for t,want in {Blade=8,Blunt=10,Gun=8,Thrown=8,Explosive=3,Elemental=10,Tool=7,Culinary=5,Trick=6} do check(members[t]==want,t..' has '..want..' members') end
 check(#Weapons.typesOf('nope')==0,'unknown id has no types')
 check(table.concat(Weapons.ById['13'].types,',')=='Thrown','Kunai is Thrown, not Blade')

 -- Elemental / Utility flags equal the authored lists (the old values).
 local E=set({'08','14','17','30','31','32','33','34','35','38','41'})
 local U=set({'05','11','20','24','25','26','27','28','29'})
 for _,w in Weapons.List do
  check(w.elemental==(E[w.id]==true),'elemental flag '..w.id)
  check(w.utility==(U[w.id]==true),'utility flag '..w.id)
 end

 -- Card text: starter class and types; the Duck and Washer don't claim bounce / pierce.
 check(Weapons.describe(Weapons.ById['01'])=='Chef starter weapon. Blunt, Culinary.','Pan card text')
 check(Weapons.describe(pc)=='Chef starter weapon. Blade, Culinary.','Pizza Cutter card text')
 local duck,washer=Weapons.describe(Weapons.ById['17']),Weapons.describe(Weapons.ById['29'])
 check(not duck:find('Bounces',1,true) and not washer:find('pierce',1,true),'Duck / Washer stop claiming bounce / pierce')
 check(string.find(Weapons.describe(Weapons.ById['36']),'Any class can start a run with it.',1,true)==1,'Godly card text')

 -- Set counts count copies; blanks and unknown ids add nothing.
 local counts=Stats.typeCounts({'03','03','03','42','','zz'})
 check(counts.Blade==4 and counts.Culinary==1 and counts.Gun==0,'set counts count copies')
 check(Stats.typeCounts({}).Trick==0 and Stats.typeCounts(nil).Blade==0,'empty set counts')
 check(Stats.typeCounts({Slot1='00',Slot2='00'}).Gun==2,'a slot map counts too')

 -- Set totals at 2..6 (running totals), 0 under 2: one damage curve for every type, plus a flavor.
 check(table.concat(Stats.SetDamage,',')=='4,7,10,13,15','one damage curve')
 for i,v in {0,0,4,7,10,13,15,15} do check(Stats.setDamage(i-1)==v,'set damage at '..(i-1)) end
 local want={Blade={2,4,6,8,10},Blunt={1,1,2,2,3},Gun={0,0,1,1,1},Thrown={5,10,15,20,25},Explosive={10,20,30,40,50},
  Elemental={3,6,9,12,15},Tool={4,8,12,16,20},Culinary={2,3,4,5,6},Trick={2,4,6,8,10}}
 for t,values in want do
  check(Stats.setBonus(t,0)==0 and Stats.setBonus(t,1)==0,t..' nothing under 2')
  for i,v in values do check(Stats.setBonus(t,i+1)==v,t..' flavor at '..(i+1)..' = '..v) end
  check(Stats.setBonus(t,7)==values[5],t..' stops at 6')
  check(Stats.setBonusText(t,1)==nil and type(Stats.setBonusText(t,2))=='string','set text '..t)
 end
 check(Stats.setBonusText('Blade',3)=='Blade 3: +7% damage and +4% crit chance on Blade weapons','Blade set text')
 check(Stats.setBonusText('Blunt',2)=='Blunt 2: +4% damage on Blunt weapons and +1 armor for you','Blunt set text')
 check(Stats.setBonusText('Gun',4)=='Gun 4: +10% damage and +1 projectile on Gun weapons' and Stats.setBonusText('Gun',3)=='Gun 3: +7% damage on Gun weapons','Gun set text')
 check(Stats.setBonusText('Culinary',3)=='Culinary 3: +7% damage on Culinary weapons, and their hits heal 3% of their damage','Culinary set text')
 check(Stats.setBonusText('Thrown',6)=='Thrown 6: +15% damage and +25% projectile speed on Thrown weapons','Thrown set text')

 -- Damage reaches that type's weapons (the higher curve of two types); flavors their scope.
 local function wb(id,ids) return Stats.weaponSetBonus(Weapons.ById[id],Stats.typeCounts(ids)) end
 local blade4=wb('03',{'03','03','42','39'})
 check(blade4.Damage==10 and blade4.CritChance==6,'Blade 4: +10% damage, +6 crit on a Katana')
 check(next(wb('00',{'03','03','42','39'}))==nil,'Blade set gives a Glock nothing')
 local gun3,gun4=wb('00',{'00','07','09'}),wb('00',{'00','07','09','10'})
 check(gun3.Damage==7 and gun3.ProjectileCount==nil and gun3.AttackSpeed==nil,'Gun 3: +7% damage, no projectile, no speed')
 check(gun4.Damage==10 and gun4.ProjectileCount==1,'Gun 4: +10% damage and +1 projectile')
 local thrown=wb('13',{'13','12','14'});check(thrown.Damage==7 and thrown.ProjectileSpeed==10,'Thrown 3: +7% damage, +10% projectile speed')
 local staff=wb('30',{'30','30'});check(staff.Damage==4 and staff.BurnChance==3,'Elemental 2: +4% damage, +3 burn chance')
 check(wb('11',{'11','14'}).AreaSize==10,'Explosive 2: +10 area on the Rocket')
 check(wb('01',{'01','05','15','16','42','01'}).LifeSteal==6,'Culinary 6: hits heal 6%')
 -- Mjolnir (Blunt, Elemental) with Blunt 4 and Elemental 2 takes Blunt's +10%, not +14%.
 check(wb('31',{'31','02','06','19','30'}).Damage==10,'two types: only the higher damage curve')
 check(wb('31',{'31','30','30'}).Damage==7 and wb('31',{'31','30','30'}).BurnChance==6,'Mjolnir with Elemental 3: +7% and the burn flavor')
 check(next(wb('24',{'24'}))==nil,'one copy: nothing')
 local you=Stats.playerSetBonus(Stats.typeCounts({'02','06','19','12','17','21','24','27','28','29'}))
 check(you.Armor==1 and you.Dodge==4 and you.UtilityPower==12,'Blunt 3 armor, Trick 3 dodge, Tool 4 utility')
 local tools=Stats.typeCounts({'24','25','26','27'})
 near(Stats.resolve('Handyman',tools).UtilityPower,15+12*1.25,'Tool set is a gain (Handyman x1.25)')
 near(Stats.resolve('Gunner',tools).UtilityPower,12,'Tool set for anyone')
 near(Stats.resolve('Brawler',Stats.typeCounts({'02','06','19','25'})).Armor,3+2,'Blunt 4 adds 2 to Brawler armor')
 near(Stats.resolve('Brawler',6).Armor,3,'a number (old home count) adds nothing')

 -- Specialty: +10% on own-class weapons only, never a Godly.
 check(Stats.Specialty==10,'specialty 10%')
 local neutral=Stats.resolve('Brawler',0,{Damage=0,MeleeDamage=0,RangedDamage=0,ElementalDamage=0,UtilityPower=0,ExplosionDamage=0,AttackSpeed=0,CooldownReduction=0,CritChance=5})
 for _,class in Stats.ClassOrder do
  for _,w in Weapons.List do
   local ratio=Stats.weapon(w,neutral,class,1).damage/Stats.weapon(w,neutral,nil,1).damage
   local on=not w.godly and w.class==class
   near(ratio,on and 1.1 or 1,'specialty '..class..' '..w.id)
   check(Stats.specialty(w,class)==(on and 10 or 0),'specialty value '..class..' '..w.id)
   check((Stats.specialtyCardText(w,class)~=nil)==on,'specialty card line '..class..' '..w.id)
  end
  check(Stats.specialtyText(class)=='+10% damage with '..class..' weapons','class screen line '..class)
 end
 check(Stats.specialty({home='Chef'},'Chef')==10 and Stats.specialty(Weapons.ById['36'],'Chef')==0 and Stats.classFit==nil,'bare {home=} works; the old classFit shape is gone')

 -- Per-weapon numbers from the sets (S.weapon and S.weaponStats).
 local glock=Weapons.ById['00']
 local c2=Stats.typeCounts({'00','07'})
 near(Stats.weapon(glock,neutral,nil,1,c2).cooldown,glock.cooldown,'Gun set leaves the cooldown alone')
 near(Stats.weapon(glock,neutral,nil,1,c2).damage,glock.damage*1.04,'Gun 2 +4% damage')
 near(Stats.weapon(Weapons.ById['13'],neutral,nil,1,Stats.typeCounts({'13','13'})).projectileSpeed,Weapons.ById['13'].projectileSpeed*1.05,'Thrown 2 throws 5% faster')
 check(Stats.weaponStats(neutral,Stats.weapon(Weapons.ById['30'],neutral,nil,1,Stats.typeCounts({'30','35'}))).BurnChance==3,'Elemental 2: +3 burn chance on the Staff')
 near(Stats.weapon(Weapons.ById['13'],neutral,nil,1,Stats.typeCounts({'13','13'})).damage,Weapons.ById['13'].damage*1.04,'Thrown 2 +4% damage')
 near(Stats.weapon(Weapons.ById['11'],neutral,nil,1,Stats.typeCounts({'11','14'})).blastRadius,6*1.1,'Explosive 2 widens the rocket blast 10%')
 local katana=Stats.weapon(Weapons.ById['03'],neutral,nil,1,Stats.typeCounts({'03','42'}))
 local ks=Stats.weaponStats(neutral,katana)
 check(ks.CritChance==neutral.CritChance+2 and neutral.CritChance==5,'Blade 2: +2 crit on the weapon only')
 local pan=Stats.weapon(Weapons.ById['01'],neutral,nil,1,Stats.typeCounts({'01','16'}))
 check(Stats.weaponStats(neutral,pan).LifeSteal==2 and Stats.weaponStats(neutral,pan).CritChance==5,'Culinary 2: hits heal 2%')
 local g4=Stats.weapon(glock,neutral,nil,1,Stats.typeCounts({'00','07','09','10'}));g4.stats=Stats.weaponStats(neutral,g4)
 check(Stats.shotStat(g4,'ProjectileCount')==1,'Gun 4: the Glock fires one more bullet')
 local full=table.clone(neutral);full.ProjectileCount=4
 check(Stats.weaponStats(full,g4).ProjectileCount==4,'projectiles stay inside the stat cap')
 local plain=Stats.weapon(glock,neutral,nil,1,nil)
 check(Stats.weaponStats(neutral,plain)==neutral and next(plain.typeBonus)==nil,'no sets: the player stats as they are')

 -- Lightning targets: a lightning weapon adds 1 to the player's (Battery Pack fix), at most 6.
 local crystal,staff=Weapons.ById['35'],Weapons.ById['30']
 check(Stats.chainTargets({ChainCount=0,ChainBonus=0},crystal)==1,'Crystal Ball alone chains 1')
 check(Stats.chainTargets({ChainCount=1,ChainBonus=0},crystal)==2,'Crystal Ball + Battery Pack chains 2 (was 1)')
 check(Stats.chainTargets({ChainCount=0,ChainBonus=2},staff)==0,'Extra targets alone start no chain')
 check(Stats.chainTargets({ChainCount=1,ChainBonus=1},staff)==2,'Battery Pack + Antlers on a Staff')
 check(Stats.chainTargets({ChainCount=6,ChainBonus=3},crystal)==6,'at most 6')

 -- usesStat: family items, Area Size and the Bowling Ball.
 local function uses(id,stat,stats) return Stats.usesStat(Weapons.ById[id],stat,stats) end
 check(uses('03','MeleeDamage') and not uses('00','MeleeDamage'),'Melee damage: swings only')
 check(uses('00','RangedDamage') and uses('31','RangedDamage') and uses('37','RangedDamage') and uses('17','RangedDamage') and not uses('03','RangedDamage'),'Ranged damage: non-melee and throwing hybrids')
 check(uses('30','ElementalDamage') and uses('14','ElementalDamage') and not uses('00','ElementalDamage'),'Elemental damage: elemental weapons')
 check(uses('00','ElementalDamage',{BurnChance=10,PoisonChance=0}) and uses('03','ElementalDamage',{BurnChance=0,PoisonChance=5}),'Elemental damage with burn / poison chance')
 local turret={id='Turret',kind='Ranged',utility=true}
 check(not Stats.usesStat(turret,'RangedDamage') and not Stats.usesStat(turret,'MeleeDamage') and not Stats.usesStat(turret,'ElementalDamage'),'turrets ignore the family stats')
 for _,id in {'17','28','29'} do check(uses(id,'AreaSize'),'Area Size widens '..id) end
 for _,id in {'03','11','22','25','31','32','42'} do check(uses(id,'AreaSize'),'Legendary move grows with Area Size '..id) end
 local k1,k4=table.clone(Weapons.ById['03']),table.clone(Weapons.ById['03']);k1.tier=1;k4.tier=4
 check(not Stats.usesStat(k1,'AreaSize') and Stats.usesStat(k4,'AreaSize'),'Katana: Area Size at Tier IV only')
 check(not uses('06','AreaSize'),'a plain swing ignores Area Size')
 check(uses('22','ProjectileCount') and not uses('22','Pierce') and not uses('22','Bounce'),'Bowling Ball: more balls, no pierce / bounce')
 check(Stats.weapon(Weapons.ById['17'],neutral,nil,4).nativeBounce==0 and Stats.weapon(Weapons.ById['29'],neutral,nil,4).nativePierce==0,'Duck / Washer native bounce / pierce were unused; now 0')

 -- In-run Sets lines.
 local lines=Stats.typeLines({'03','03','42','00'})
 check(#lines==3 and lines[1].type=='Blade' and lines[2].type=='Gun' and lines[3].type=='Culinary','lines in vocabulary order')
 check(lines[1].count==3 and lines[1].damage==7 and lines[1].current==4 and lines[1].next==4 and lines[1].nextDamage==10 and lines[1].nextValue==6 and lines[1].scope=='weapon','Blade line')
 check(lines[2].count==1 and lines[2].damage==0 and lines[2].current==0 and lines[2].next==2 and lines[2].nextDamage==4 and lines[2].text==nil,'Gun line under 2')
 local six=Stats.typeLines({'02','02','02','02','02','02'})
 check(six[1].type=='Blunt' and six[1].next==nil and six[1].damage==15 and six[1].current==3 and six[1].scope=='you','maxed Blunt line')

 -- Starter rules (RunSetupRules): own class or an owned Godly.
 if Rules then
  local function player(classes,weapons)
   local a={ProfileLoaded=true,ProfileClasses=classes,ProfileWeapons=weapons,ProfileMapWins=''}
   return {GetAttribute=function(_,key) return a[key] end}
  end
  local p=player('Brawler,Gunner,Chef,Juggler,Handyman,Mage','06:1:0,19:1:0,01:1:0,36:1:0,41:1:0')
  check(not Rules.validLoadout(p,'Brawler','01'),'Brawler + Pan rejected')
  check(Rules.validLoadout(p,'Brawler','06'),'Brawler + Bat accepted')
  check(Rules.validLoadout(p,'Brawler','19'),'Brawler + owned Gloves accepted')
  check(Rules.validLoadout(p,'Chef','01'),'Chef + Pan accepted')
  for _,class in Stats.ClassOrder do check(Rules.validLoadout(p,class,'36') and Rules.validLoadout(p,class,'41'),'owned Godly with '..class) end
  check(Rules.Signature==Stats.Signature and Rules.ClassUnlock.Chef~=nil,'run setup tables follow the classes')
 end
 return checks
end
