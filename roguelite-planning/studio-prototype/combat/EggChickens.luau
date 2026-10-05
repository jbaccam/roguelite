-- Egg chickens: a landing Egg sometimes hatches a chicken (Minecraft's 1 in 8) that runs at the
-- nearest enemy and pecks it. When its time is up it swells and pops into feathers.
-- Server-owned Humanoid like the enemies; RogueliteChickens.client animates it and draws the
-- hatch and the pop. Pecks go through CombatEffectsService as secondary hits: no crits,
-- knockback or status procs, and the owner must still be alive.
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local PhysicsService=game:GetService('PhysicsService')
local ServerStorage=game:GetService('ServerStorage')
local Ground=require(game.ReplicatedStorage.RogueliteCombat.GroundContact)
local Template=require(script.Parent.ChickenTemplate)
local C={
 Chance=1/8,Lifetime=8,PerPlayer=3,Max=24,
 PeckDamage=.4,PeckEvery=.7,PeckImpact=.12,PeckReach=2.2,
 Speed=22,Sight=45,Follow=8,PopTime=.35,MinMass=4,
}
function C.new(combat,damage,rayParams)
 local folder=workspace:FindFirstChild('RogueliteChickens') or Instance.new('Folder')
 folder.Name='RogueliteChickens';folder.Parent=workspace
 local chickens={};local fallback
 local groundProbe=Ground.new({folder})
 local function flat(v) return Vector3.new(v.X,0,v.Z) end
 local function valid(d)
  local h=d.character and d.owner.Character==d.character and d.character:FindFirstChildOfClass('Humanoid')
  local state=combat.PlayerStates:FindFirstChild(tostring(d.owner.UserId))
  return h and h.Health>0 and not d.owner:GetAttribute('RunDown') and state and state:GetAttribute('WeaponEnabled') and (combat:GetAttribute('ZombiesEnabled') or d.practiceTarget)
 end
 -- Same rule as the egg itself: a practice throw only ever hits practice targets.
 local function usable(npc,d)
  if not npc or not npc.Parent or not Tags:HasTag(npc,'RogueliteZombie') then return end
  if d.practiceTarget and npc:GetAttribute('PracticeTarget')~=true then return end
  local h=npc:FindFirstChildOfClass('Humanoid');local r=npc:FindFirstChild('HumanoidRootPart')
  if h and r and h.Health>0 then return r end
 end
 local function nearest(c)
  local best,distance=nil,C.Sight
  for _,npc in Tags:GetTagged('RogueliteZombie') do
   local r=usable(npc,c.d)
   if r then local d=flat(r.Position-c.root.Position).Magnitude;if d<distance then best,distance=npc,d end end
  end
  return best
 end
 local function pop(c)
  if c.popAt then return end
  c.popAt=workspace:GetServerTimeNow()+C.PopTime
  c.humanoid:MoveTo(c.root.Position)
  c.model:SetAttribute('PopAt',c.popAt)
 end
 local function mine(owner)
  local list={}
  for _,c in chickens do if c.d.owner==owner and not c.popAt then table.insert(list,c) end end
  table.sort(list,function(a,b) return a.born<b.born end)
  return list
 end
 local function hatch(d,position,template)
  local ground=groundProbe:floor(position)
  if not ground then return false,'No floor' end
  -- A fourth chicken makes the owner's oldest one pop early.
  local own=mine(d.owner);if #own>=C.PerPlayer then pop(own[1]) end
  local model=template:Clone();model.Name='EggChicken'
  local root=model:FindFirstChild('HumanoidRootPart');local humanoid=model:FindFirstChildOfClass('Humanoid')
  if not root or not humanoid then model:Destroy();return false,'Invalid chicken template' end
  local now=workspace:GetServerTimeNow()
  model:SetAttribute('OwnerUserId',d.owner.UserId);model:SetAttribute('HatchedAt',now)
  local yaw=math.random()*math.pi*2
  -- HipHeight is privileged in sandboxed code. The fallback supplies its authored foot offset;
  -- imported rigs derive it from their real bounds instead of reading avatar appearance.
  local groundOffset=model:GetAttribute('GroundOffset')
  if type(groundOffset)~='number' then local cf,size=model:GetBoundingBox();groundOffset=root.Position.Y-cf.Position.Y+size.Y*.5 end
  model:PivotTo(CFrame.new(ground+Vector3.yAxis*(groundOffset+.05))*CFrame.Angles(0,yaw,0))
  -- Enemy collision group: walls and floors are solid, players and enemies are not. Nothing
  -- may query it, so a chicken never blocks a shot, an enemy swing or a line-of-sight check.
  local group=PhysicsService:IsCollisionGroupRegistered('RogueliteZombies') and 'RogueliteZombies' or nil
  for _,p in model:GetDescendants() do if p:IsA('BasePart') then
   p.Anchored=false;p.CanCollide=p==root;p.CanQuery=false;p.CanTouch=false;if group then p.CollisionGroup=group end
  end end
  -- A body this light can't be steered by its Humanoid (see RogueliteZombieChase MIN_MASS).
  if root.AssemblyMass<C.MinMass then
   local physical=root.CurrentPhysicalProperties
   local density=(root:GetMass()+C.MinMass-root.AssemblyMass)/(root.Size.X*root.Size.Y*root.Size.Z)
   root.CustomPhysicalProperties=PhysicalProperties.new(math.min(density,100),physical.Friction,physical.Elasticity,physical.FrictionWeight,physical.ElasticityWeight)
  end
  humanoid.WalkSpeed=C.Speed
  -- Turn to the target while pecking with an AlignOrientation: writing a Humanoid's root
  -- CFrame every tick can stop its walk (see EnemyAttacks' AttackFacing).
  local attachment=Instance.new('Attachment');attachment.Name='PeckFacing';attachment.Parent=root
  local align=Instance.new('AlignOrientation');align.Name='PeckFacing';align.Mode=Enum.OrientationAlignmentMode.OneAttachment
  align.Attachment0=attachment;align.MaxTorque=math.huge;align.Responsiveness=60;align.Enabled=false;align.Parent=root
  model.Parent=folder
  root:SetNetworkOwner(nil)
  Tags:AddTag(model,'RogueliteChicken')
  chickens[model]={model=model,root=root,humanoid=humanoid,align=align,d=d,born=now,ends=now+C.Lifetime,nextPeck=now+.25}
  return true,model
 end
 local elapsed=0
 RunService.Heartbeat:Connect(function(dt)
  elapsed+=dt;if elapsed<.1 then return end;local step=elapsed;elapsed=0
  local now=workspace:GetServerTimeNow()
  for model,c in chickens do
   if c.popAt then
    if now>=c.popAt then chickens[model]=nil;model:Destroy() end
    continue
   end
   if not model.Parent or c.humanoid.Health<=0 then chickens[model]=nil;model:Destroy();continue end
   if combat:GetAttribute('RunPaused') then
    c.ends+=step;c.nextPeck+=step;c.humanoid:MoveTo(c.root.Position);c.align.Enabled=false;continue
   end
   if now>=c.ends or not valid(c.d) then pop(c);continue end
   local root,humanoid=c.root,c.humanoid
   local targetRoot=usable(c.target,c.d)
   if not targetRoot then c.target=nearest(c);targetRoot=usable(c.target,c.d) end
   local goal,moving,pecking
   if targetRoot then
    local offset=flat(targetRoot.Position-root.Position)
    local reach=C.PeckReach+math.max(targetRoot.Size.X,targetRoot.Size.Z)*.5
    if offset.Magnitude>reach then
     goal=targetRoot.Position-offset.Unit*reach*.7;moving=true
    else
     humanoid:MoveTo(root.Position)
     pecking=true
     if offset.Magnitude>.01 then c.align.CFrame=CFrame.lookAt(Vector3.zero,offset) end
     if now>=c.nextPeck then
      c.nextPeck=now+C.PeckEvery;model:SetAttribute('PeckStart',now)
      local target,d=c.target,c.d
      task.delay(C.PeckImpact,function()
       local r=chickens[model] and not c.popAt and valid(d) and not combat:GetAttribute('RunPaused') and usable(target,d)
       if r and flat(r.Position-root.Position).Magnitude<=reach*1.3 and not workspace:Raycast(root.Position,r.Position-root.Position,rayParams(d.character,true)) then damage(target,d.damage*C.PeckDamage,d,true) end
      end)
     end
    end
   else
    -- Nothing to peck: trot back to the owner.
    local ownerRoot=c.d.character:FindFirstChild('HumanoidRootPart')
    local offset=ownerRoot and flat(ownerRoot.Position-root.Position)
    if offset and offset.Magnitude>C.Follow then goal=ownerRoot.Position-offset.Unit*C.Follow*.5;moving=true
    else humanoid:MoveTo(root.Position) end
   end
   if goal then humanoid:MoveTo(Vector3.new(goal.X,root.Position.Y,goal.Z)) end
   c.align.Enabled=pecking==true;humanoid.AutoRotate=not pecking
   -- Hop anything taller than its little legs, like the enemies do.
   if moving then
    if not c.stall then c.stall={at=root.Position,since=now}
    elseif now-c.stall.since>=.3 then
     if flat(root.Position-c.stall.at).Magnitude<C.Speed*.3*.15 then humanoid.Jump=true end
     c.stall=nil
    end
   else c.stall=nil end
  end
 end)
 local self={}
 -- Called once per egg flight that lands (hit or ground), never for cancelled flights.
 function self:landed(d,position)
  -- Studio tests can raise the odds with the TestChickenChance attribute (0-1).
  local override=RunService:IsStudio() and combat:GetAttribute('TestChickenChance')
  local chance=type(override)=='number' and override==override and math.clamp(override,0,1) or C.Chance
  if d.id~='15' or not valid(d) or combat:GetAttribute('RunPaused') then return false,'Invalid egg owner' end
  if math.random()>=chance then return false,'No hatch roll' end
  local total=0;for _ in chickens do total+=1 end
  if total>=C.Max then return false,'Chicken cap' end
  local allies=ServerStorage:FindFirstChild('RogueliteAllies');local template=allies and allies:FindFirstChild('EggChicken')
  if not template or not template:FindFirstChild('HumanoidRootPart') or not template:FindFirstChildOfClass('Humanoid') then
   -- Keep the cached template outside the world: only landed eggs create visible/collidable rigs.
   if not fallback then fallback=Template.build();fallback.Name='EggChickenFallback' end
   template=fallback
  end
  return hatch(d,position,template)
 end
 return self
end
return C
