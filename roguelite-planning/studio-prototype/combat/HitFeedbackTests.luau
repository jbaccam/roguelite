-- Pure checks for HitFeedbackVisuals' pool rules (launch audit F2). Studio Edit, no Play: load its
-- source with loadstring and pass the module in (V.pick and V.pickFlash touch no Instances).
return function(V)
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
 check(V.Flashes<=12,'well under the 31 Highlight limit')
 return {passed=true,checks=checks}
end
