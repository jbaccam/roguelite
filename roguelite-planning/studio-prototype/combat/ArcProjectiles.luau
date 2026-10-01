local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Motion=require(game.ReplicatedStorage.RogueliteCombat.ArcMotion)
local Targets=require(game.ReplicatedStorage.RogueliteCombat.ProjectileTarget)
local A={}
function A.new(combat,damage,rayParams)
 local event=combat:WaitForChild('ArcShot');local active={};local serial=0;local random=Random.new()
 local function finish(r,result,impact)
  active[r.serial]=nil
  event:FireAllClients('End',r.serial,impact and (result and result.Position or r.finish) or nil,r.d.id,r.d.blastRadius)
  if not impact then return end
  if r.d.id=='33' then
   local point=result and result.Position or r.finish
   local wall=rayParams(r.d.character,true)
   local origin=point+(result and result.Normal or Vector3.yAxis)*.2
   for _,npc in Tags:GetTagged('RogueliteZombie') do
    local h=npc:FindFirstChildOfClass('Humanoid');local root=npc:FindFirstChild('HumanoidRootPart')
    if h and h.Health>0 and root and (root.Position-point).Magnitude<=r.d.blastRadius and not workspace:Raycast(origin,root.Position-origin,wall) then damage(npc,r.d.damage,r.d) end
   end
  end
 end
 RunService.Heartbeat:Connect(function()
  local now=workspace:GetServerTimeNow()
  for _,r in active do
   local d=r.d;local h=d.character:FindFirstChildOfClass('Humanoid')
   if d.owner.Character~=d.character or not h or h.Health<=0 or (not combat:GetAttribute('ZombiesEnabled') and not d.practiceTarget) then finish(r,nil,false);continue end
   local state=combat.PlayerStates:FindFirstChild(tostring(d.owner.UserId));local slot=state and state:FindFirstChild('Slot'..d.slotIndex)
   if not slot or slot:GetAttribute('WeaponId')~=d.id or not state:GetAttribute('WeaponEnabled') then finish(r,nil,false);continue end
   if now>r.expires or r.remaining<=.05 then finish(r,nil,false);continue end
   if r.target and not Targets.alive(r.target) then
    local replacement=Targets.replacement(r.position,d,r.hit,r.remaining,r.launchOrigin,rayParams)
    if not replacement or r.redirects>=8 then finish(r,nil,false);continue end
    r.target=replacement;r.redirects+=1;r.origin=r.position;r.finish=Targets.predict(replacement,r.origin,function(distance) return Motion.duration(d.id,distance,d.projectileSpeed) end,math.max(0,r.started-now),r.remaining,rayParams,d.character,d.id=='33')
    if d.id=='33' then
     local ground=workspace:Raycast(r.finish+Vector3.yAxis*2,-Vector3.yAxis*30,rayParams(d.character,true))
     if ground then r.finish=ground.Position+Vector3.yAxis*.1 end
    end
    r.started=math.max(now,r.started);r.t=0
    local distance=(r.finish-r.origin).Magnitude
    r.duration=Motion.duration(d.id,distance,d.projectileSpeed)
    r.side,r.height,r.bend=Motion.shape(d.id,distance,r.index,random)
    event:FireAllClients('Redirect',r.serial,r.origin,r.finish,r.started,r.duration,r.side,r.height,replacement,r.bend)
   end
   local untilT=math.clamp((now-r.started)/r.duration,0,1)
   if d.id=='18' and r.target and r.target.Parent then r.finish=r.target.Position end
   while active[r.serial] and r.t<untilT do
    local t=math.min(untilT,r.t+.015)
    local pos=Motion.position(r.origin,r.finish,t,r.side,r.height,r.bend)
    local delta=pos-r.position
    if delta.Magnitude>r.remaining then finish(r,nil,false);break end
    local hit=delta.Magnitude>.0001 and workspace:Spherecast(r.position,math.max(d.projectileRadius,d.id=='18' and .28 or .4),delta,Targets.sweepParams(r,rayParams(d.character,false)))
    r.t=t;r.position=pos
    r.remaining-=delta.Magnitude
    if hit then
     local npc=hit.Instance:FindFirstAncestorOfClass('Model')
     if d.id=='18' and npc and Tags:HasTag(npc,'RogueliteZombie') then
      r.hit[npc]=true;damage(npc,d.damage*r.factor,d)
      if r.pierce>0 then r.pierce-=1;r.factor*=.7
      elseif r.bounce>0 then
       local closest,range=nil,math.min(18,r.remaining);local wall=rayParams(d.character,true)
       for _,candidate in Tags:GetTagged('RogueliteZombie') do
        local root=candidate:FindFirstChild('HumanoidRootPart');local hum=candidate:FindFirstChildOfClass('Humanoid')
        if root and hum and hum.Health>0 and not r.hit[candidate] then
         local distance=(root.Position-hit.Position).Magnitude
         if distance<range and distance>.1 and not workspace:Raycast(hit.Position,root.Position-hit.Position,wall) then closest=root;range=distance end
        end
       end
       if closest then
        r.origin=hit.Position;r.finish=closest.Position;r.started=now;r.duration=Motion.duration('18',range,d.projectileSpeed);r.t=0;r.position=r.origin;r.bounce-=1;r.factor*=.6
        r.side,r.height,r.bend=Motion.shape('18',range,r.index,random)
        r.target=closest
        event:FireAllClients('Redirect',r.serial,r.origin,r.finish,r.started,r.duration,r.side,r.height,closest,r.bend)
        break
       else finish(r,hit,false) end
      else finish(r,hit,false) end
     else finish(r,hit,true) end
    end
   end
   if active[r.serial] and r.t>=1 then finish(r,nil,r.d.id=='33') end
  end
 end)
 local self={}
 function self:launch(d,origin,aim)
  local existing=0;for _ in active do existing+=1 end
  local count=(d.projectileCount or (d.id=='18' and 3 or 1))+d.stats.ProjectileCount
  if existing+count>192 then return end
  for i=1,count do
   serial+=1
   local def=table.clone(d);if d.id=='18' then def.damage=d.damage/3 end
   local delay=d.id=='18' and (i-1)*Motion.CARD_STAGGER or Motion.BOX_OPEN+(i-1)*.08
   local from=origin+Vector3.yAxis*(d.id=='33' and .65 or .35)
   local target=aim
   if d.arcTarget then target=Targets.predict(d.arcTarget,from,function(distance) return Motion.duration(d.id,distance,d.projectileSpeed) end,delay,d.range,rayParams,d.character,d.id=='33') end
   if d.id=='33' then
    local ground=workspace:Raycast(target+Vector3.yAxis*2,-Vector3.yAxis*30,rayParams(d.character,true))
    if ground then target=ground.Position+Vector3.yAxis*.1 end
   end
   local distance=(target-from).Magnitude
   local side,height,bend=Motion.shape(d.id,distance,i,random)
   local r={serial=serial,d=def,origin=from,finish=target,position=from,started=workspace:GetServerTimeNow()+delay,duration=Motion.duration(d.id,distance,d.projectileSpeed),side=side,height=height,t=0,index=i,hit={},pierce=math.min(4,d.stats.Pierce+(d.nativePierce or 0)),bounce=math.min(4,d.stats.Bounce+(d.nativeBounce or 0)),factor=1,remaining=d.range}
   active[serial]=r
   -- Arc-length allowance preserves normal curved shots at maximum target range.
   r.remaining=d.range*2;r.launchOrigin=from;r.expires=workspace:GetServerTimeNow()+10;r.redirects=0
   r.bend=bend
   r.target=d.arcTarget
   event:FireAllClients('Launch',serial,d.id,d.owner.UserId,d.slotIndex,i,from,target,r.started,r.duration,side,height,d.arcTarget,bend)
  end
 end
 return self
end
return A
