-- Bounded server-simulated swept projectiles. Pierce and bounce never revisit a target.
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Motion=require(game.ReplicatedStorage.RogueliteCombat.WeaponMotion)
local Targets=require(game.ReplicatedStorage.RogueliteCombat.ProjectileTarget)
local ShotBatch=require(game.ReplicatedStorage.RogueliteCombat.ShotBatch)
local P={}
function P.new(combat,damage,rayParams)
 local active={}
 local serial=0
 local shots=ShotBatch.writer(combat.Shot)
 local batching=false
 -- Shots reach players near their origin plus the shooter (ShotBatch.fire).
 local function emitShot(owner,...)
  if batching then shots:push(owner,...) else ShotBatch.fire(combat.Shot,(...),owner,...) end
 end
 local function cast(r,delta)
  -- The projectile's own params (its hit enemies excluded), rebuilt only when it hits another.
  return workspace:Spherecast(r.position,r.d.projectileRadius,delta,Targets.sweepParams(r,rayParams(r.d.character,false)))
 end
 RunService.Heartbeat:Connect(function(dt)
  batching=#active>1
  for i=#active,1,-1 do
   local r=active[i];local d=r.d;local h=d.character:FindFirstChildOfClass('Humanoid')
   if (not combat:GetAttribute('ZombiesEnabled') and not d.practiceTarget) or d.owner.Character~=d.character or not h or h.Health<=0 or os.clock()>r.expires then table.remove(active,i);continue end
   if r.target and not Targets.alive(r.target) then
    local replacement=Targets.replacement(r.position,d,r.hit,r.remaining,r.launchOrigin,rayParams)
    if not replacement then table.remove(active,i);continue end
    r.target=replacement
    local point=Targets.predict(replacement,r.position,function(distance) return distance/d.projectileSpeed end,0,r.remaining,rayParams,d.character)
    r.direction=(point-r.position).Magnitude>.01 and (point-r.position).Unit or r.direction
   end
   local distance=math.min(d.projectileSpeed*math.min(dt,.1),r.remaining)
   local delta=r.direction*distance;local result=cast(r,delta)
   local finish=result and result.Position or r.position+delta
   local hitModel=result and result.Instance:FindFirstAncestorOfClass('Model')
   local mobContact=hitModel~=nil and Tags:HasTag(hitModel,'RogueliteZombie')
   emitShot(d.owner,r.position,finish,'Ranged',d.id,d.projectileRadius*2,nil,result~=nil and d.kind~='Blast',result and result.Normal,d.owner.UserId,d.slotIndex,r.first,mobContact,r.shotId,r.visualId,d.projectileSpeed,result~=nil and (not mobContact or (r.pierce<=0 and r.bounce<=0)) or r.remaining<=distance)
   -- Preserve Shot-before-damage ordering on contact; never wait another frame.
   if result then shots:flush() end
   r.first=false
   r.remaining-=(finish-r.position).Magnitude;r.position=finish
   if result then
    if d.kind=='Blast' then
     local wall=rayParams(d.character,true)
     local blastOrigin=finish+result.Normal*.12
     for _,candidate in Tags:GetTagged('RogueliteZombie') do
      local root=candidate:FindFirstChild('HumanoidRootPart');local hum=candidate:FindFirstChildOfClass('Humanoid')
      if root and hum and hum.Health>0 and (root.Position-finish).Magnitude<=d.blastRadius and not workspace:Raycast(blastOrigin,root.Position-blastOrigin,wall) then damage(candidate,d.damage,d) end
     end
     emitShot(d.owner,finish-r.direction*.15,finish,'Blast',d.id,d.projectileRadius*2,d.blastRadius)
     table.remove(active,i);continue
    end
    local npc=result.Instance:FindFirstAncestorOfClass('Model')
    if not npc or not Tags:HasTag(npc,'RogueliteZombie') then table.remove(active,i);continue end
    r.hit[npc]=true;damage(npc,d.damage*r.factor,d)
    if r.pierce>0 then r.pierce-=1;r.factor*=.7
    elseif r.bounce>0 then
     local best,range=nil,math.min(18,r.remaining);local wall=rayParams(d.character,true)
     for _,candidate in Tags:GetTagged('RogueliteZombie') do
      local root=candidate:FindFirstChild('HumanoidRootPart');local hum=candidate:FindFirstChildOfClass('Humanoid')
      if root and hum and hum.Health>0 and not r.hit[candidate] then
       local length=(root.Position-finish).Magnitude
       if length<range and length>.01 and not workspace:Raycast(finish,root.Position-finish,wall) then best=root;range=length end
      end
     end
     if not best then table.remove(active,i);continue end
     local point=Targets.predict(best,finish,function(distance) return distance/d.projectileSpeed end,0,r.remaining,rayParams,d.character)
     r.direction=(point-finish).Magnitude>.01 and (point-finish).Unit or r.direction;r.bounce-=1;r.factor*=.6
     r.target=best
    else table.remove(active,i);continue end
    r.position+=r.direction*.05;r.remaining-=.05
   end
   if r.remaining<=.01 then table.remove(active,i) end
  end
  shots:flush()
 end)
 local self={}
 function self:launch(d,origin,aim)
  if #active>=512 or (aim-origin).Magnitude<.01 then return end
  local first=false
  local muzzleOffset=Motion.MuzzleOffsets[d.id]
  if muzzleOffset then
   local direction=d.muzzleDirection or (aim-origin)
   local flat=Vector3.new(direction.X,0,direction.Z)
   if flat.Magnitude>.01 then
    local muzzle=CFrame.lookAt(origin,origin+flat):PointToWorldSpace(muzzleOffset)
    -- Do not move the spawn through an enemy or nearby wall.
    if not workspace:Raycast(origin,muzzle-origin,rayParams(d.character,false)) then origin=muzzle;first=true end
   end
  end
  if (aim-origin).Magnitude<.01 then return end
  serial+=1
  table.insert(active,{visualId=serial,d=d,target=d.arcTarget,launchOrigin=origin,position=origin,direction=(aim-origin).Unit,remaining=d.range,hit={},pierce=math.min(4,d.stats.Pierce+(d.nativePierce or 0)),bounce=math.min(4,d.stats.Bounce+(d.nativeBounce or 0)),factor=1,first=first,shotId=d.muzzleShotId,expires=os.clock()+10})
 end
 return self
end
return P
