-- Server targeting policy shared by all in-flight projectile families.
local Tags=game:GetService('CollectionService')
local T={}
-- Solve the intercept using the actual flight-duration function (including
-- curved-path timing and launch delay), rather than distance / nominal speed.
function T.intercept(origin,position,velocity,duration,delay,stop,stopVelocity)
 delay=delay or 0
 local function future(t)
  local delta=velocity*t
  if stop then
   local toward=stop+(stopVelocity or Vector3.zero)*t-position
   local along=math.max(0,toward:Dot(velocity.Magnitude>.01 and velocity.Unit or Vector3.zero))
   if delta.Magnitude>along then delta=velocity.Magnitude>.01 and velocity.Unit*along or Vector3.zero end
  end
  return position+delta
 end
 local total=math.clamp(delay+duration((position-origin).Magnitude),0,4)
 for _=1,18 do
  local nextTime=math.clamp(delay+duration((future(total)-origin).Magnitude),0,4)
  if math.abs(nextTime-total)<.0001 then total=nextTime;break end
  total=total*.25+nextTime*.75
 end
 return future(total),total
end
function T.predict(root,origin,duration,delay,range,rayParams,character,grounded)
 if not root or not root.Parent then return origin end
 local position=root.Position
 local velocity=root.AssemblyLinearVelocity
 velocity=Vector3.new(velocity.X,0,velocity.Z)
 local h=root.Parent:FindFirstChildOfClass('Humanoid')
 if velocity.Magnitude<.1 and h and not root.Anchored then velocity=h.MoveDirection*h.WalkSpeed end
 if velocity.Magnitude>45 then velocity=velocity.Unit*45 end
 local stop,stopVelocity
 local userId=root.Parent:GetAttribute('TargetUserId')
 local player=userId and game.Players:GetPlayerByUserId(userId)
 local pr=player and player.Character and player.Character:FindFirstChild('HumanoidRootPart')
 if pr and velocity.Magnitude>.1 then
  local toward=Vector3.new(pr.Position.X-position.X,0,pr.Position.Z-position.Z)
  if toward.Magnitude>.01 and toward.Unit:Dot(velocity.Unit)>.8 then
   local stopRange=root.Parent:GetAttribute('ZombieType')=='Baby' and 2.1 or 3.5
   stop=position+toward.Unit*math.max(0,toward.Magnitude-stopRange)
   stopVelocity=Vector3.new(pr.AssemblyLinearVelocity.X,0,pr.AssemblyLinearVelocity.Z)
  end
 end
 local predicted=T.intercept(origin,position,velocity,duration,delay,stop,stopVelocity)
 local params=rayParams(character,true)
 local obstruction=(predicted-position).Magnitude>.01 and workspace:Raycast(position,predicted-position,params)
 if obstruction then predicted=obstruction.Position+obstruction.Normal*.5 end
 if grounded then
  local ground=workspace:Raycast(predicted+Vector3.yAxis*3,-Vector3.yAxis*40,params)
  if ground then predicted=ground.Position+Vector3.yAxis*.1 end
 end
 local delta=predicted-origin
 if range and delta.Magnitude>range then predicted=origin+delta.Unit*range end
 return predicted
end
function T.alive(root)
 local npc=root and root.Parent
 local h=npc and npc:FindFirstChildOfClass('Humanoid')
 return npc and npc:IsDescendantOf(workspace) and Tags:HasTag(npc,'RogueliteZombie') and h and h.Health>0
end
function T.replacement(position,d,hit,remaining,launchOrigin,rayParams)
 local best,range=nil,math.min(d.range,remaining)
 for _,npc in Tags:GetTagged('RogueliteZombie') do
  local root=npc:FindFirstChild('HumanoidRootPart')
  if T.alive(root) and not (hit and hit[npc]) and (not d.practiceTarget or npc:GetAttribute('PracticeTarget')) then
   local distance=(root.Position-position).Magnitude
   if distance>.05 and distance<range and (root.Position-launchOrigin).Magnitude<=d.range
    and not workspace:Raycast(position,root.Position-position,rayParams(d.character,true)) then best=root;range=distance end
  end
 end
 return best
end
return T
