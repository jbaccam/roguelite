-- Client presentation only. Position deltas set stride; server timestamps own attacks.
local Tags=game:GetService('CollectionService')
local RunService=game:GetService('RunService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('EnemyCatalog'))
local NativeMotion=require(combat:WaitForChild('ZombieMotion'))
local NativeFeet=require(combat:WaitForChild('NativeEnemyFeet'))
local Motion=require(combat:WaitForChild('EnemyMotion'))
local SlamVisuals=require(combat:WaitForChild('ZombieSlamVisuals'))
local HeldProjectiles=require(combat:WaitForChild('EnemyHeldProjectiles'))
local tracked={}
local MAX_MOVE_CYCLES=4 -- imported Move clip loops per second
local function track(npc)
 if tracked[npc] or npc:GetAttribute('IsBoss') or npc:GetAttribute('IsHammerBoss') then return end
 local config=Catalog.fromModel(npc);if not config then return end
 local seed=((npc:GetAttribute('SpawnIndex') or 1)*2.3999632297)%(2*math.pi)
 tracked[npc]={joints=Motion.bind(npc),phase=seed,idleOffset=seed,stride=0,moveClock=0,poses={},config=config,refresh=0,feet=config.legacy and NativeFeet.bind(npc,config.legacy)}
end
Tags:GetInstanceAddedSignal('RogueliteZombie'):Connect(track)
Tags:GetInstanceRemovedSignal('RogueliteZombie'):Connect(function(npc) tracked[npc]=nil;SlamVisuals.remove(npc);HeldProjectiles.remove(npc) end)
for _,npc in Tags:GetTagged('RogueliteZombie') do track(npc) end
local function attackTime(data,config,age)
 local clip=data.clips.Attack;local authoredImpact=data.motion.attackImpact or clip.duration*.45
 if age<=config.attackImpact then return math.clamp(age/config.attackImpact,0,1)*authoredImpact end
 return authoredImpact+math.clamp((age-config.attackImpact)/(config.attackRecovery-config.attackImpact),0,1)*(clip.duration-authoredImpact)
end
RunService.PreSimulation:Connect(function(dt)
 local now=workspace:GetServerTimeNow()
 for npc,state in tracked do
  if not npc.Parent then tracked[npc]=nil;SlamVisuals.remove(npc);HeldProjectiles.remove(npc);continue end
  local root=npc:FindFirstChild('HumanoidRootPart');local h=npc:FindFirstChildOfClass('Humanoid')
  if not root or not h or h.Health<=0 or npc:GetAttribute('PracticeTarget') then SlamVisuals.remove(npc);HeldProjectiles.remove(npc);continue end
  local config=state.config
  if config.legacy and not state.feet then state.feet=NativeFeet.bind(npc,config.legacy) end
  local displacement=state.lastPosition and root.Position-state.lastPosition or Vector3.zero;state.lastPosition=root.Position
  local distance=Vector2.new(displacement.X,displacement.Z).Magnitude
  -- Teleports and long hitches reset the estimator instead of spinning a gait.
  if dt<=0 or dt>.25 or distance>math.max(4,config.speed*dt*3) then distance=0 end
  local speed=distance/math.max(dt,1/240)
  local blend=1-math.exp(-math.min(dt,.1)*12)
  local attackStart=npc:GetAttribute(config.legacy=='Mutant' and 'SlamStart' or 'EnemyAttackStart')
  local age=attackStart and now-attackStart
  local attacking=age~=nil and age>=0 and age<=config.attackRecovery
  local grounded=h.FloorMaterial~=Enum.Material.Air
  -- Enemies attack on the move (EnemyAttacks), so the legs keep walking through a swing.
  local walking=grounded and speed>.2
  state.stride+=((walking and 1 or 0)-state.stride)*blend
  state.refresh+=dt
  if state.refresh>=1 then state.refresh=0;state.joints=Motion.bind(npc) end
  local target
  if config.legacy then
   if config.legacy=='Mutant' then SlamVisuals.update(npc,now) end
   if walking then state.phase=(state.phase+distance*(state.feet and 2*math.pi/state.feet.strideLength or config.cadence))%(2*math.pi) end
   target=NativeMotion.pose(config.legacy,state.phase,state.stride,npc:GetAttribute('Chasing') and 1 or 0,now+state.idleOffset,attacking and age or nil,config.attackImpact,config.attackRecovery)
  else
   if not state.data then
    state.data=Motion.load(config.id)
    if state.data then
     state.moveClock=state.idleOffset/(2*math.pi)*state.data.clips.Move.duration
     -- Leg bones on every rig: Thigh/Shin/Foot, Upper/LowerLeg, crab and spider LegNUpper/Lower.
     state.legBones={}
     for bone in state.data.bones do
      if bone:find('Leg') or bone:find('Thigh') or bone:find('Shin') or bone:find('Foot') then table.insert(state.legBones,bone) end
     end
    end
   end
   if not state.data then
    if not state.warned then warn('Missing enemy clips: '..config.id);state.warned=true end
    continue
   end
   local data=state.data;local clip=data.clips.Move
   local relativeScale=npc:GetScale()/(npc:GetAttribute('EnemyBaselineModelScale') or 1)
   local strideLength=(data.motion.strideLength or config.strideLength)*relativeScale
   if walking then
    -- Short authored strides would blur at wave speeds; cap cadence and let feet glide.
    local advance=config.timeBasedMovement and dt*math.clamp(speed/config.speed,0,2) or math.min(distance/math.max(.1,strideLength),dt*MAX_MOVE_CYCLES)*clip.duration
    state.moveClock=(state.moveClock+advance)%clip.duration
   end
   local idle=Motion.sample(data,'Idle',now+state.idleOffset)
   local move=Motion.sample(data,'Move',state.moveClock)
   target=Motion.blend(idle,move,state.stride)
   if attacking then
    -- The attack plays above the hips; the legs keep the walk cycle while the enemy moves and
    -- settle into the authored attack stance when it stands still. Legless rigs use the whole clip.
    local attack=Motion.sample(data,'Attack',attackTime(data,config,age))
    for _,bone in state.legBones do
     if attack[bone] and target[bone] then attack[bone]=attack[bone]:Lerp(target[bone],state.stride) end
    end
    target=attack
   end
   target=Motion.scalePose(target,relativeScale)
  end
  local mode=attacking and 'Attack' or walking and 'Move' or 'Idle'
  if mode~=state.mode then state.mode=mode;state.transition=0;state.transitionPose=state.poses end
  state.transition=(state.transition or 0)+dt
  -- Blend only on state changes; continuous smoothing would drag planted feet.
  state.poses=Motion.blend(state.transitionPose or {},target,math.min(1,state.transition/.12))
  local displayPoses=state.poses
  -- Zombie feet stay planted only for a standing attack; on the move they keep stepping.
  if config.legacy then displayPoses=NativeFeet.apply(state.feet,table.clone(state.poses),state.phase,state.stride,attacking and not walking) end
  Motion.apply(state.joints,displayPoses)
  if state.data then HeldProjectiles.update(npc,config,state.data,state.poses,attacking and age or nil,attacking and attackTime(state.data,config,age) or 0) end
  npc:SetAttribute('ClientMotionState',mode)
  npc:SetAttribute('ClientMeasuredSpeed',speed)
 end
end)
