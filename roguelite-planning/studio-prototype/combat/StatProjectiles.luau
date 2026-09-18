-- Bounded server-simulated swept projectiles. Pierce and bounce never revisit a target.
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Motion=require(game.ReplicatedStorage.RogueliteCombat.WeaponMotion)
local P={}
function P.new(combat,damage,rayParams)
 local active={}
 local function cast(r,delta)
  local params=rayParams(r.d.character,false);local filter=params.FilterDescendantsInstances
  for npc in r.hit do table.insert(filter,npc) end;params.FilterDescendantsInstances=filter
  return workspace:Spherecast(r.position,r.d.projectileRadius,delta,params)
 end
 RunService.Heartbeat:Connect(function(dt)
  for i=#active,1,-1 do
   local r=active[i];local d=r.d;local h=d.character:FindFirstChildOfClass('Humanoid')
   if not combat:GetAttribute('ZombiesEnabled') or d.owner.Character~=d.character or not h or h.Health<=0 or os.clock()>r.expires then table.remove(active,i);continue end
   local distance=math.min(d.projectileSpeed*math.min(dt,.1),r.remaining)
   local delta=r.direction*distance;local result=cast(r,delta)
   local finish=result and result.Position or r.position+delta
   combat.Shot:FireAllClients(r.position,finish,'Ranged',d.id,d.projectileRadius*2,nil,result~=nil and d.kind~='Blast',result and result.Normal,d.owner.UserId,d.slotIndex,r.first)
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
     combat.Shot:FireAllClients(finish-r.direction*.15,finish,'Blast',d.id,d.projectileRadius*2,d.blastRadius)
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
     r.direction=(best.Position-finish).Unit;r.bounce-=1;r.factor*=.6
    else table.remove(active,i);continue end
    r.position+=r.direction*.05;r.remaining-=.05
   end
   if r.remaining<=.01 then table.remove(active,i) end
  end
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
  table.insert(active,{d=d,position=origin,direction=(aim-origin).Unit,remaining=d.range,hit={},pierce=d.stats.Pierce,bounce=d.stats.Bounce,factor=1,first=first,expires=os.clock()+10})
 end
 return self
end
return P
