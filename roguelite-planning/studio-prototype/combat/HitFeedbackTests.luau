-- Pure checks for HitFeedbackVisuals' pool rules (launch audit F2). Studio Edit, no Play: load its
-- source with loadstring and pass the module in (V.pick and V.pickFlash touch no Instances).
-- B (optional): ShotBatch, for the crit/element style's trip over the wire (run_hit_feedback_tests.py).
return function(V,B)
 local checks=0;local function check(ok,message) checks+=1;assert(ok,message) end
 local pick,pickFlash=V.pick,V.pickFlash
 -- Numbers: new ones until the cap, then free ones first.
 local pool={}
 for i=1,V.HitNumbers do
  local e=pick(pool,V.HitNumbers,i%2==0);check(e=='new','new number '..i..' under the cap')
  table.insert(pool,{born=i,mine=i%2==0})
 end
 check(pick(pool,V.HitNumbers,true)==pool[1],'full: your hit takes the oldest teammate number')
 check(pick(pool,V.HitNumbers,false)==pool[1],'full: a teammate hit takes the oldest teammate number')
 pool[5].born=nil
 check(pick(pool,V.HitNumbers,false)==pool[5],'a finished number is reused before any showing one')
 pool[5].born=100
 -- Only your numbers showing: yours replaces your oldest, a teammate's is dropped.
 for i,e in pool do e.mine=true;e.born=i end
 check(pick(pool,V.HitNumbers,true)==pool[1],'only yours: your new hit takes your oldest')
 check(pick(pool,V.HitNumbers,false)==nil,'only yours: a teammate number is dropped')
 -- Oldest means smallest born, wherever it sits.
 pool[9].mine=false;pool[9].born=50;pool[12].mine=false;pool[12].born=40
 check(pick(pool,V.HitNumbers,true)==pool[12],'oldest teammate number by time, not position')
 -- Damage taken: its own small pool, always shown (the caller passes mine=true).
 local taken={};for i=1,V.TakenNumbers do table.insert(taken,{born=i,mine=true}) end
 check(pick(taken,V.TakenNumbers,true)==taken[1],'damage taken always shows, replacing its oldest')
 check(V.TakenNumbers<V.HitNumbers and V.HitNumbers>=25 and V.HitNumbers<=30,'pool sizes as planned')
 -- Merging (2026-10-10): a burst's hits on one enemy add into one number; others stay separate.
 local function at(x,y,z) return {X=x,Y=y,Z=z} end
 local nums={{born=10,mine=true,at=at(0,0,0)},{born=10,mine=nil,at=at(0,0,0)},{born=10,mine=true,at=at(5,0,0)}}
 check(V.merge(nums,at(.5,3,.5),10.1,true)==nums[1],'your hit beside your fresh number adds into it (height ignored)')
 check(V.merge(nums,at(0,0,0),10.1,false)==nums[2],'a teammate hit merges only with teammate numbers')
 check(V.merge(nums,at(2.5,0,0),10.1,true)==nil,'a hit between two enemies starts its own number')
 check(V.merge(nums,at(0,0,0),10+V.Merge+.01,true)==nil,'an older number is left to rise; a new one shows')
 nums[1].born=nil;check(V.merge(nums,at(0,0,0),10.1,true)==nil,'a finished number never merges')
 check(V.Life<=.75 and V.Merge<V.Life,'numbers are short-lived and merge only while fresh')
 -- Colours (2026-10-10): the fill says who/how (plain, crit, turret); an element adds its outline.
 check(V.style(false,nil,false)==nil,'a plain hit keeps the caller colour and text stroke')
 local crit=V.style(true,nil)
 check(crit and crit.color==V.CritColor and crit.scale>1 and crit.suffix=='!' and crit.stroke==1 and crit.outline==V.CritOutline,'a crit is hot red, bigger, outlined white, with !')
 -- Impact streaks (MobImpactVisuals): the element's hue wins, then turret steel, then crit red.
 check(V.sparkColor(false,nil,false)==nil,'a plain hit keeps white streaks')
 check(V.sparkColor(true,nil,false)==V.CritColor and V.sparkColor(false,nil,true)==V.TurretColor,'crit streaks are red, turret streaks steel')
 for _,name in {'Burn','Frost','Poison','Lightning'} do
  check(V.sparkColor(true,name,false)==V.Sparks[name] and V.sparkColor(false,name,true)==V.Sparks[name],name..' streaks take the element colour')
 end
 check(V.sparkColor(false,'Ice',false)==nil,'an unknown element keeps white streaks')
 local turret=V.style(false,nil,true)
 check(turret and turret.color==V.TurretColor and turret.scale<1 and turret.suffix=='' and turret.outline==nil,'a turret hit is steel and smaller')
 check(turret.color~=V.CritColor and turret.kind~=crit.kind,'turret and crit numbers look and merge apart')
 check(V.style(true,nil,true)==turret,'a turret never shows as a crit')
 local seen={}
 for _,name in {'Burn','Frost','Poison','Lightning'} do
  local s=V.style(false,name)
  check(s and s.outline==V.Colors[name] and s.color==V.Fills[name] and s.scale==1 and s.suffix=='','element '..name..': coloured outline on a tinted fill, normal size')
  check(s.stroke==1,'element '..name..': its outline replaces the dark text stroke')
  check(not seen[s.outline],'element '..name..' outline differs from the others');seen[s.outline]=true
  local both=V.style(true,name)
  check(both and both.color==V.CritColor and both.outline==V.Colors[name] and both.scale==crit.scale and both.suffix=='!','crit '..name..': red fill, element outline, crit size and !')
  local t=V.style(false,name,true)
  check(t and t.color==V.TurretColor and t.outline==V.Colors[name] and t.scale==turret.scale,'turret '..name..': steel fill, element outline, turret size')
  check(both.kind~=s.kind and t.kind~=s.kind and both.kind~=t.kind and both.kind~=crit.kind,name..' styles are separate merge kinds')
 end
 check(V.style(false,'Ice')==nil and V.style(true,'Slow')==crit,'unknown elements show without an outline')
 check(V.style(true,'Burn')==V.style(true,'Burn'),'styles are shared, not built per hit')
 -- Merging keeps styles apart: a crit, burn or turret number never folds into a plain one.
 local mixed={{born=10,mine=true,at=at(0,0,0)},{born=10,mine=true,at=at(0,0,0),kind='Crit'},{born=10,mine=true,at=at(0,0,0),kind='Burn'},{born=10,mine=true,at=at(0,0,0),kind='Turret'}}
 check(V.merge(mixed,at(0,0,0),10.1,true)==mixed[1],'a plain hit merges only into the plain number')
 check(V.merge(mixed,at(0,0,0),10.1,true,'Crit')==mixed[2],'a crit merges only into a crit number')
 check(V.merge(mixed,at(0,0,0),10.1,true,'Burn')==mixed[3],'a burn tick merges only into a burn number')
 check(V.merge(mixed,at(0,0,0),10.1,true,'Turret')==mixed[4],'a turret hit merges only into a turret number')
 check(V.merge(mixed,at(0,0,0),10.1,true,'Lightning')==nil,'a lightning hit beside other styles starts its own number')
 -- The wire: ShotBatch packs crit/element/turret into the hit flags' high nibble and the Hit style.
 if B then
  local codes={}
  for _,name in {false,'Burn','Frost','Poison','Lightning'} do
   for _,src in {'plain','crit','turret'} do
    local c,tu=src=='crit',src=='turret'
    local n=B.style(c,name or nil,tu)
    check(n>=0 and n<=255 and n%16==0,'style fits the spare high nibble')
    check(not codes[n],'every style has its own code');codes[n]=true
    local c2,e2,t2=B.unstyle(n)
    check(c2==c and e2==(name or nil) and t2==tu,'style round-trips: '..tostring(name)..' '..src)
    local c3,e3,t3=B.unstyle(n+1+2+4+8) -- lethal, secondary, dot and mine set too
    check(c3==c and e3==(name or nil) and t3==tu,'style reads back from a full flags byte')
   end
  end
  check(B.style(false,nil,false)==0,'a plain hit adds nothing to the flags')
  check(B.style(true,'Ice')==B.style(true,nil),'an unknown element is not sent')
  check(B.style(true,nil,true)==B.style(false,nil,true),'a turret hit is sent as a turret, not a crit')
  local c4,e4,t4=B.unstyle(nil);check(c4==false and e4==nil and t4==false,'an old server (no style) reads as plain')
  c4,e4,t4=B.unstyle('x');check(c4==false and e4==nil and t4==false,'a malformed style reads as plain')
  c4,e4,t4=B.unstyle(15*16);check(c4==false and e4==nil and t4==false,'the unused code reads as plain')
  for name in V.Colors do check(table.find(B.Elements,name),'every coloured element can be sent: '..name) end
  for _,name in B.Elements do check(V.Colors[name],'every sent element has a colour: '..name) end
 end
 -- Flashes: an enemy already flashing restarts its own; free before new; new under the cap; else oldest.
 local a,b,c={},{},{}
 local flashes={}
 check(pickFlash(flashes,V.Flashes,a)=='new','first flash is new')
 flashes[1]={born=1,npc=a}
 check(pickFlash(flashes,V.Flashes,a)==flashes[1],'same enemy restarts its own flash')
 check(pickFlash(flashes,V.Flashes,b)=='new','another enemy gets a new one under the cap')
 for i=2,V.Flashes do flashes[i]={born=i,npc={}} end
 check(pickFlash(flashes,V.Flashes,c)==flashes[1],'full: the oldest flash moves')
 flashes[4].born=nil
 check(pickFlash(flashes,V.Flashes,c)==flashes[4],'a finished flash is reused first')
 check(V.Flashes>=100 and V.Flashes+V.FrostTints<200,'100-mob swarm with headroom under 255 Highlights')
 -- A same-frame area hit must not steal any of the first hundred silhouettes before rendering.
 local swarm={};local targets={}
 for i=1,100 do
  targets[i]={};local f=pickFlash(swarm,V.Flashes,targets[i])
  check(f=='new','swarm hit retains independent flash '..i)
  swarm[i]={born=1,npc=targets[i]}
 end
 for i=1,100 do check(pickFlash(swarm,V.Flashes,targets[i])==swarm[i],'repeat hit retains target '..i) end
 check(V.flashAlpha(0)==0 and V.flashAlpha(V.FlashHold)==0,'solid white hold includes first render frames')
 check(V.flashAlpha((V.FlashHold+V.FlashDuration)/2)>.49,'fade restores underlying status tint')
 check(V.flashAlpha(V.FlashDuration)==1,'pulse finishes cleanly')
 check(V.flashAlpha(.12)>0 and V.flashAlpha(0)==0,'repeat hit resets partially faded pulse to white')
 return {passed=true,checks=checks}
end
