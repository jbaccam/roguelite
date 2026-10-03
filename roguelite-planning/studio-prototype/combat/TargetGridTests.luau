-- Pure checks for TargetGrid (launch audit P4): on made-up crowds it must pick exactly what the old
-- per-slot scan picked (the nearest allowed enemy with a clear line, ties to the earlier one), with
-- far fewer line checks. Studio Edit, no Play: load TargetGrid's source with loadstring and pass it
-- in. Returns {passed, checks, scenarios, oldClears, newClears}.
return function(G)
 local checks=0;local function check(ok,message) checks+=1;assert(ok,message) end
 local rng=Random.new(11)
 -- The old scan from RogueliteCombat.server, over the same list in the same order.
 local function old(list,origin,range,can,measure,clear)
  local target,best,point=nil,range,nil
  for _,e in list do
   if can(e) then
    local position=measure(e);local distance=(position-origin).Magnitude
    if distance<best and distance>.01 and clear(position,e) then target=e;best=distance;point=position end
   end
  end
  return target,point
 end
 local oldClears,newClears,scenarios=0,0,0
 for scenario=1,400 do
  local list={}
  local count=rng:NextInteger(0,120)
  local spread=({20,60,200})[scenario%3+1]
  for i=1,count do
   local position=Vector3.new(rng:NextNumber(-spread,spread),rng:NextNumber(0,8),rng:NextNumber(-spread,spread))
   -- Some exact duplicates, for ties.
   if i>1 and rng:NextNumber()<.08 then position=list[rng:NextInteger(1,i-1)].position end
   list[i]={position=position,boss=rng:NextNumber()<.04,allowed=rng:NextNumber()<.9,blocked=rng:NextNumber()<.3,id=i}
  end
  local grid=G.new(list)
  for _=1,6 do
   local origin=Vector3.new(rng:NextNumber(-spread,spread),rng:NextNumber(0,6),rng:NextNumber(-spread,spread))
   local range=({6,12,25,45,70})[rng:NextInteger(1,5)]
   local function can(e) return e.allowed end
   -- A boss is measured to a side up to 9 studs nearer than its root (like reachPoint).
   local function measure(e)
    if not e.boss then return e.position end
    local away=e.position-origin
    return away.Magnitude>9.05 and e.position-away.Unit*9 or origin+(away.Magnitude>.01 and away.Unit or Vector3.xAxis)*.05
   end
   local used=0
   local function clear(_,e) used+=1;return not e.blocked end
   local a,ap=old(list,origin,range,can,measure,clear);oldClears+=used;used=0
   local b,bp=G.nearest(grid,origin,range,can,measure,clear);newClears+=used
   check(a==b,('scenario %d: old picked %s, grid picked %s'):format(scenario,a and a.id or 'none',b and b.id or 'none'))
   check(ap==bp,'same point')
   -- around() never misses an enemy in range.
   local got={};for _,e in G.around(grid,origin,range) do got[e]=true end
   for _,e in list do if e.boss or (e.position-origin).Magnitude<=range then check(got[e],'around covers everything in range') end end
   scenarios+=1
  end
 end
 -- Range edges: exactly at range is out, inside is in; nearer than .01 is ignored.
 local list={{position=Vector3.new(10,0,0)},{position=Vector3.new(9.99,0,0)},{position=Vector3.new(.005,0,0)}}
 local grid=G.new(list)
 local function yes() return true end
 local function at(e) return e.position end
 check(G.nearest(grid,Vector3.zero,10,yes,at,yes)==list[2],'range is exclusive; too-near ignored')
 check(G.nearest(grid,Vector3.zero,9.98,yes,at,yes)==nil,'nothing in range')
 check(oldClears>0 and newClears<oldClears,'fewer line checks than the old scan')
 return {passed=true,checks=checks,scenarios=scenarios,oldClears=oldClears,newClears=newClears}
end
