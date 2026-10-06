-- Bounded server-simulated swept projectiles. Pierce and bounce never revisit a target.
-- Clients hear about a bullet only where its path changes: a 'Fly' row for each straight leg
-- (the launch or a leg after a contact pierce/bounce), a 'Land' row where a leg stops
-- (wall, enemy, range end; terminal once the bullet is done) and 'Drop' when it is cancelled.
-- RogueliteCombat.client flies each leg itself and draws it step by step as before. It used to
-- be a row every Heartbeat: a 40-stud shot at 110 studs/s was ~22 rows, now 2. The server's
-- sweep, hits and damage are unchanged.
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local Motion=require(game.ReplicatedStorage.RogueliteCombat.WeaponMotion)
local Targets=require(game.ReplicatedStorage.RogueliteCombat.ProjectileTarget)
local ShotBatch=require(game.ReplicatedStorage.RogueliteCombat.ShotBatch)
local Stats=require(game.ReplicatedStorage.RogueliteCombat.CharacterStats)
local RayImpact=require(game.ReplicatedStorage.RogueliteCombat.RayImpact)
local P={}
-- firstKey (2026-10-03): where this instance's projectile keys start. Clients key flights by them
-- (BulletFlights), so a second instance (HandymanTurretService, 2^30) never reuses RogueliteCombat's 1, 2, 3...
function P.new(combat,damage,rayParams,firstKey)
 local active={}
 local serial=firstKey or 0
 -- Rows reach players near them plus the shooter, batched per frame (ShotBatch.writer).
 local shots=ShotBatch.writer(combat.Shot)
 -- A leg from `from` to the end of the bullet's range along its heading. Rows use the Shot
 -- argument order: origin, finish, kind, id, thickness, blastRadius, contact, normal, ownerId,
 -- slotIndex, first, mobContact, shotId, projectileId, projectileSpeed, terminal.
 local function fly(r,from)
  local d=r.d;r.open=true
  shots:push(d.owner,from,r.position+r.direction*r.remaining,'Fly',d.id,d.projectileRadius*2,nil,nil,nil,d.owner.UserId,d.slotIndex,r.first,nil,r.shotId,r.visualId,d.projectileSpeed)
  r.first=false
 end
 -- The leg stops at `at`. Not terminal (a pierce or bounce) leaves the client waiting for the
 -- next leg or a Drop.
 local function land(r,at,contact,normal,mobContact,terminal)
  shots:push(r.d.owner,at,nil,'Land',nil,nil,nil,contact,normal,nil,nil,nil,mobContact,nil,r.visualId,nil,terminal)
  if terminal then r.open=false end
 end
 local function stop(i)
  local r=table.remove(active,i)
  if r.open then shots:push(r.d.owner,r.position,nil,'Drop',nil,nil,nil,nil,nil,nil,nil,nil,nil,nil,r.visualId) end
 end
 local function cast(r,delta)
  -- The projectile's own params (its hit enemies excluded), rebuilt only when it hits another.
  return workspace:Spherecast(r.position,r.d.projectileRadius,delta,Targets.sweepParams(r,rayParams(r.d.character,false)))
 end
 local function raySplash(r,point,normal,direct)
  if r.d.id~='41' then return end
  local wall=rayParams(r.d.character,true)
  local origin=point+(normal or -r.direction)*.12
  local radius=RayImpact.radius(r.d)
  -- The impact is a server-confirmed contact, including world walls; a range-end miss
  -- never explodes. Send once per contact, independently of whether the victim dies.
  ShotBatch.fire(combat:WaitForChild('GodlyFX'),point,r.d.owner,'RayImpact',r.d.owner.UserId,point,radius)
  RayImpact.apply(r.d,point,direct,r.hit,Tags:GetTagged('RogueliteZombie'),function(_,target)
   local delta=target-origin
   return delta.Magnitude<.001 or workspace:Raycast(origin,delta,wall)==nil
  end,damage,r.factor)
 end
 RunService.Heartbeat:Connect(function(dt)
  for i=#active,1,-1 do
   local r=active[i];local d=r.d;local h=d.character:FindFirstChildOfClass('Humanoid')
   if (not combat:GetAttribute('ZombiesEnabled') and not d.practiceTarget) or d.owner.Character~=d.character or not h or h.Health<=0 or os.clock()>r.expires then stop(i);continue end
   -- A straight projectile commits its launch heading. A moving/dead target never redirects
   -- or deletes it mid-air; only an actual contact bounce below chooses another heading.
   if not r.open then fly(r,r.position) end
   local distance=math.min(d.projectileSpeed*math.min(dt,.1),r.remaining)
   local delta=r.direction*distance;local result=cast(r,delta)
   -- Spherecast.Position is the surface contact, not the swept sphere's center. Advancing
   -- to it bent grazing/piercing bullets sideways. Distance keeps every leg on its firing line.
   local finish=result and r.position+r.direction*result.Distance or r.position+delta
   local hitModel=result and result.Instance:FindFirstAncestorOfClass('Model')
   local mobContact=hitModel~=nil and Tags:HasTag(hitModel,'RogueliteZombie')
   local terminal=result~=nil and (not mobContact or (r.pierce<=0 and r.bounce<=0)) or r.remaining<=distance
   if result or terminal then land(r,finish,result~=nil and d.kind~='Blast',result and result.Normal,mobContact,terminal) end
   -- Preserve Shot-before-damage ordering on contact; never wait another frame.
   if result then shots:flush() end
   r.remaining-=(finish-r.position).Magnitude;r.position=finish
   if result then
    if d.kind=='Blast' then
     local wall=rayParams(d.character,true)
     local blastOrigin=finish+result.Normal*.12
     for _,candidate in Tags:GetTagged('RogueliteZombie') do
      local root=candidate:FindFirstChild('HumanoidRootPart');local hum=candidate:FindFirstChildOfClass('Humanoid')
      if root and hum and hum.Health>0 and (root.Position-finish).Magnitude<=d.blastRadius and not workspace:Raycast(blastOrigin,root.Position-blastOrigin,wall) then damage(candidate,d.damage,d) end
     end
     shots:push(d.owner,finish-r.direction*.15,finish,'Blast',d.id,d.projectileRadius*2,d.blastRadius)
     stop(i);continue
    end
    local npc=result.Instance:FindFirstAncestorOfClass('Model')
    if not npc or not Tags:HasTag(npc,'RogueliteZombie') then raySplash(r,finish,result.Normal,nil);stop(i);continue end
    r.hit[npc]=true
    if d.id~='41' or RayImpact.allowed(npc,d) then damage(npc,d.damage*r.factor,d) end
    raySplash(r,finish,result.Normal,npc)
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
     if not best then stop(i);continue end
     local point=Targets.predict(best,finish,function(distance) return distance/d.projectileSpeed end,0,r.remaining,rayParams,d.character)
     r.direction=(point-finish).Magnitude>.01 and (point-finish).Unit or r.direction;r.bounce-=1;r.factor*=.6
    else stop(i);continue end
    r.position+=r.direction*.05;r.remaining-=.05
    if r.remaining>.01 then fly(r,r.position) end -- on through the enemy, or off to the next
   end
   if r.remaining<=.01 then stop(i) end
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
  -- Item pierce and bounce only where the weapon uses them (CharacterStats.usesStat, 2026-10-03).
  local bounce=Stats.StraightGuns[d.id] and 0 or math.min(4,Stats.shotStat(d,'Bounce')+(d.nativeBounce or 0))
  table.insert(active,{visualId=serial,d=d,launchOrigin=origin,position=origin,direction=(aim-origin).Unit,remaining=d.range,hit={},pierce=math.min(4,Stats.shotStat(d,'Pierce')+(d.nativePierce or 0)),bounce=bounce,factor=1,first=first,shotId=d.muzzleShotId,expires=os.clock()+10})
 end
 return self
end
return P
