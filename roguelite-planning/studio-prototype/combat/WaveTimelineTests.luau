return function(T,Catalog,Maps)
 local checks=0
 local function check(ok,label) checks+=1;assert(ok,label) end
 local function simulate(wave,players,boss,step)
  local s=T.new(wave);local total,pulses=0,0
  for _=1,math.floor(40/step) do local e=T.step(s,step,false,boss,players);if e then total+=#e.roles;pulses+=1 end end
  return total,pulses
 end
 for _,case in {{1,42},{5,72},{10,120},{20,180},{25,180}} do
  for _,dt in {.05,.025} do local total=simulate(case[1],1,false,dt);check(total==case[2],'authored total '..case[1]..' dt '..dt..': '..total) end
 end
 check(simulate(20,1,true,.05)==84,'boss wave has eighty-four scheduled adds over forty seconds')
 check(simulate(1,4,false,.05)==168,'four players receive exactly four solo arrival budgets')
 for players=1,4 do
  check(simulate(20,players,false,.025)==180*players,'linear ordinary arrival budget '..players)
  check(simulate(20,players,true,.025)==84*players,'linear boss arrival budget '..players)
  check(math.abs(T.dispatchInterval(players)*players-.25)<1e-9,'linear dispatch throughput '..players)
  check(math.abs(T.groupInterval(.65,players)*players-.65)<1e-9,'linear boss group throughput '..players)
  check(math.abs(T.groupInterval(.22,players)*players-.22)<1e-9,'linear normal group throughput '..players)
  local cursor,counts=0,table.create(players,0)
  for _=1,players*12 do cursor=T.nextRoot(cursor,players);counts[cursor]+=1 end
  for _,count in counts do check(count==12,'per-mark living-member round robin') end
 end
 local changing=T.new(20)
 check(#T.step(changing,0,false,true,4).roles==24,'four living members boss pulse')
 check(T.step(changing,3,false,true,0)==nil and changing.elapsed==0,'all down freezes arrivals and clock')
 check(#T.step(changing,3,false,true,1).roles==6,'one survivor uses solo next pulse')
 check(#T.step(changing,3,false,true,3).roles==18,'revived members join next pulse without catch-up')
 check(T.participating(true,false,false,10,true,false),'living run member included')
 check(not T.participating(false,false,false,10,true,false),'lobby/spectator excluded')
 check(not T.participating(true,true,false,10,true,false),'downed member excluded')
 check(not T.participating(true,false,true,10,true,false),'returning member excluded')
 check(not T.participating(true,false,false,0,true,false),'dead member excluded')
 check(not T.participating(true,false,false,10,false,false),'missing character root excluded')
 local backlog={}
 for pulse=1,200 do
  T.enqueue(backlog,table.create(72,'enemy'),0,T.queueLimit(4,false))
  check(#backlog<=100,'protected cap blockage cannot accumulate unbounded orders')
 end
 T.enqueue(backlog,{},30,T.queueLimit(1,false));check(#backlog==6,'downed-party queue shrinks around existing reservations')
 T.enqueue(backlog,{},0,T.queueLimit(0,false));check(#backlog==0,'no pressure backlog while every member down')
 local s=T.new(20);local first=T.step(s,0,false,false,1)
 check(first and first.at==0 and #first.roles==18,'opening pulse at time zero')
 local elapsed=s.elapsed;check(T.step(s,30,true,false,1)==nil and s.elapsed==elapsed,'pause does not consume clock')
 check(T.step(s,3,false,false,1)==nil,'no replacement pulse just because enemies died')
 check(T.step(s,1,false,false,1)~=nil,'next pulse at authored interval')
 local boss=T.step(s,0,false,true,1);check(boss and #boss.roles==6,'boss transition immediately selects add schedule')
 check(T.step(s,1,false,false,1)==nil,'boss death does not dump overdue regular arrivals')
 s=T.new(20);T.step(s,0,false,true,1)
 local n=0;for _=1,20 do if T.step(s,8,false,true,1) then n+=1 end end
 check(n==20 and s.elapsed>40,'small scheduled boss adds continue while wave held')
 s=T.new(1);T.step(s,0,false,false,1)
 local hitched=T.step(s,20,false,false,1)
 check(hitched and T.step(s,0,false,false,1)==nil,'hitch emits one pulse, not all overdue pulses')
 for wave=1,20 do
  s=T.new(wave)
  for _=1,40 do local e=T.step(s,1,false,false,1);if e then for _,role in e.roles do check(role~='Heavy' or wave>=8,'heavy wave gate') end end end
 end
 local legacy={Regular='normal',Baby='fast',Mutant='tank'}
 local catalog={normal={speed=16,behavior='Melee'},fast={speed=20,legacy='Baby',behavior='Melee'},tank={speed=12,behavior='Heavy'},archer={speed=13,behavior='Ranged'}}
 check(T.pickId('Heavy',1,nil,catalog,legacy,8)=='tank','native heavy role resolves map enemy')
 check(T.pickId('Heavy',1,nil,catalog,legacy,1)=='normal','early roster excludes tank even if role requested')
 check(T.pickId('Fast',1,'archer normal',catalog,legacy,20)=='archer','missing map role falls back within roster')
 check(T.pickId('Basic',1,'unknown-map-enemy',catalog,legacy,20)==nil,'invalid explicit roster does not import Pine Valley mobs')
 for n=1,20 do check(T.pickId('Basic',n,'archer normal',catalog,legacy,20)~='tank','no enemy from another map') end
 check(T.capacity(99,19,0,20) and not T.capacity(100,19,0,20),'global cap includes protected rigs')
 check(not T.capacity(99,20,0,20) and not T.capacity(95,15,5,20),'boss cap counts alive and pending')
 local protected={born=0,index=1,protected=true};local ordinary={born=2,index=3};local oldest={born=1,index=2}
 check(T.retireCandidate({protected,ordinary,oldest})==oldest,'oldest ordinary retired before protected boss/elite/admin')
 check(T.retireCandidate({protected})==nil,'all protected capacity defers arrivals')
 local warned=0
 for _=1,5 do warned=T.advanceWarning(warned,.1,false) end
 check(warned<1 and T.advanceWarning(warned,10,true)==warned,'paused warning never completes')
 for _=1,6 do warned=T.advanceWarning(warned,.1,false) end
 check(warned>=1,'full active warning time required')
 local distance=function(a,b) return math.abs(a-b) end
 check(T.safeSpots({10,20},{0},5,distance),'spaced marked locations safe')
 check(not T.safeSpots({10,20},{18},5,distance),'player entering any marker forces relocation')
 check(T.advanceWarning(0,.1,false)<1,'relocation starts fresh full warning')
 if Catalog and Maps then
  for name,map in Maps.Maps do
   local expected,seen={},{}
   if map.roster then for id in map.roster:gmatch('[^,%s]+') do expected[id]=true end
   else for _,id in Catalog.ByLegacy do expected[id]=true end end
   for wave=1,20 do
    local state=T.new(wave)
    for _=1,800 do
     local e=T.step(state,.05,false,false,1)
     if e then for i,role in e.roles do
      local id=T.pickId(role,e.serial*100+i,map.roster,Catalog.ById,Catalog.ByLegacy,wave)
      check(expected[id]==true,'foreign map enemy '..name..' '..id);seen[id]=true
     end end
    end
   end
   for id in expected do check(seen[id],'authored map enemy starved: '..name..' '..id) end
  end
 end
 return {passed=true,checks=checks}
end
