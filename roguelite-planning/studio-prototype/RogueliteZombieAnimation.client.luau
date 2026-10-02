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
local EMPTY=table.freeze({})
-- Imported bipeds run on planted IK feet (NativeEnemyFeet.bindImported); the Move clip is sampled
-- for it at the scale the enemy is shown at.
local function bindLegs(npc,state)
 local data=state.data;if not data or state.config.legacy then return nil end
 local relativeScale=npc:GetScale()/(npc:GetAttribute('EnemyBaselineModelScale') or 1)
 local config=state.config
 return NativeFeet.bindImported(npc,state.joints,function(t) return Motion.scalePose(Motion.sample(data,'Move',t),relativeScale) end,data.clips.Move.duration,config.runStance or (config.behavior=='Heavy' and .45 or .32))
end
local function untrack(npc)
 local state=tracked[npc]
 if state then
  for _,connection in state.connections do connection:Disconnect() end
  tracked[npc]=nil
 end
 SlamVisuals.remove(npc);HeldProjectiles.remove(npc)
end
local function track(npc)
 if tracked[npc] or npc:GetAttribute('IsBoss') or npc:GetAttribute('IsHammerBoss') then return end
 local config=Catalog.fromModel(npc);if not config then return end
 local seed=((npc:GetAttribute('SpawnIndex') or 1)*2.3999632297)%(2*math.pi)
 tracked[npc]={joints=Motion.bind(npc),phase=seed,idleOffset=seed,stride=0,reach=0,moveClock=0,poses={},spare={},config=config,bindingsDirty=false,feetRetry=0,connections={},feet=config.legacy and NativeFeet.bind(npc,config.legacy)}
 -- Per-enemy pose buffers, refilled every frame instead of allocating new tables (see the frame).
 tracked[npc].buffers={idle={},move={},mix={},attack={},scaled={},display={}}
 local state=tracked[npc]
 local function changed(descendant)
  if descendant:IsA('Bone') or descendant:IsA('Motor6D') or descendant:IsA('BasePart') or descendant:IsA('Humanoid') then
   state.bindingsDirty=true
  end
 end
 table.insert(state.connections,npc.DescendantAdded:Connect(changed))
 table.insert(state.connections,npc.DescendantRemoving:Connect(changed))
end
Tags:GetInstanceAddedSignal('RogueliteZombie'):Connect(track)
Tags:GetInstanceRemovedSignal('RogueliteZombie'):Connect(untrack)
for _,npc in Tags:GetTagged('RogueliteZombie') do track(npc) end
-- A beat after join and on each roster change, build the map's enemy clips one type at a time
-- across frames, so the first wave doesn't stall a frame per new type.
local warmSerial=0
local function warmRoster()
 warmSerial+=1;local mine=warmSerial
 task.delay(2,function()
  local roster=combat:GetAttribute('EnemyRoster')
  if type(roster)~='string' then return end
  for id in roster:gmatch('[^,%s]+') do
   if mine~=warmSerial then return end
   Motion.warm(id)
  end
 end)
end
combat:GetAttributeChangedSignal('EnemyRoster'):Connect(warmRoster)
warmRoster()
local function attackTime(data,config,age)
 local clip=data.clips.Attack;local authoredImpact=data.motion.attackImpact or clip.duration*.45
 if age<=config.attackImpact then return math.clamp(age/config.attackImpact,0,1)*authoredImpact end
 return authoredImpact+math.clamp((age-config.attackImpact)/(config.attackRecovery-config.attackImpact),0,1)*(clip.duration-authoredImpact)
end
RunService.PreSimulation:Connect(function(dt)
 local now=workspace:GetServerTimeNow()
 debug.profilebegin('EnemyAnim:Update') -- MicroProfiler label (bosses/DEVICE_PROFILING.md)
 for npc,state in tracked do
  if not npc.Parent then untrack(npc);continue end
  local root=npc:FindFirstChild('HumanoidRootPart');local h=npc:FindFirstChildOfClass('Humanoid')
  if not root or not h or h.Health<=0 or npc:GetAttribute('PracticeTarget') then SlamVisuals.remove(npc);HeldProjectiles.remove(npc);continue end
  local config=state.config
  if state.bindingsDirty then
   state.joints=Motion.bind(npc)
   state.feet=config.legacy and NativeFeet.bind(npc,config.legacy)
   state.legs=bindLegs(npc,state)
   state.bindingsDirty=false;state.feetRetry=now+1
  elseif config.legacy and not state.feet and now>=state.feetRetry then
   -- A rig that can't bind yet retries on its next structural change, else once a second.
   state.feet=NativeFeet.bind(npc,config.legacy);state.feetRetry=now+1
  end
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
  local target;local buffers=state.buffers
  if config.legacy then
   if config.legacy=='Mutant' then SlamVisuals.update(npc,now) end
   if walking then state.phase=(state.phase+distance*(state.feet and 2*math.pi/state.feet.strideLength or config.cadence))%(2*math.pi) end
   -- Arms rise to the zombie reach over ~0.25 s when a chase starts.
   state.reach+=((npc:GetAttribute('Chasing') and 1 or 0)-state.reach)*(1-math.exp(-math.min(dt,.1)*8))
   target=NativeMotion.pose(config.legacy,state.phase,state.stride,state.reach,now+state.idleOffset,attacking and age or nil,config.attackImpact,config.attackRecovery,buffers.mix)
  else
   if not state.data then
    -- A type's first sighting builds its clips over the next few frames (bind pose meanwhile),
    -- not inside this frame; warmRoster usually has the map's types ready before the wave.
    local data,pending=Motion.loadAsync(config.id)
    state.data=data
    if not data and not pending and not state.warned then warn('Missing enemy clips: '..config.id);state.warned=true end
    if state.data then
     state.moveClock=state.idleOffset/(2*math.pi)*state.data.clips.Move.duration
     state.legs=bindLegs(npc,state)
     -- Leg bones on every rig: Thigh/Shin/Foot, Upper/LowerLeg, crab and spider LegNUpper/Lower.
     state.legBones={}
     for bone in state.data.bones do
      if bone:find('Leg') or bone:find('Thigh') or bone:find('Shin') or bone:find('Foot') then table.insert(state.legBones,bone) end
     end
    end
   end
   if not state.data then continue end
   local data=state.data;local clip=data.clips.Move
   local relativeScale=npc:GetScale()/(npc:GetAttribute('EnemyBaselineModelScale') or 1)
   -- gaitStride (EnemyCatalog): a gameplay stride for clips whose authored one is far too short.
   local strideLength=(config.gaitStride or data.motion.strideLength or config.strideLength)*relativeScale
   if state.legs then
    -- Feet set the pace; the clip's left foot plants when footPath's does (phase 0.25).
    if walking then state.phase=(state.phase+distance*2*math.pi/state.legs.strideLength)%(2*math.pi) end
    state.moveClock=(state.legs.plantTime+(state.phase/(2*math.pi)-.25)*clip.duration)%clip.duration
   elseif walking then
    -- Cadence follows distance, capped per mob at the loops its own stride needs at full speed
    -- (4-12/s), so short-legged mobs no longer glide. Example: a spider (2.6-stud stride, 20
    -- studs/s) may loop 7.7/s; the old flat cap of 4 left its feet covering half the ground.
    local cap=config.maxMoveCycles or math.clamp(config.speed/math.max(.1,strideLength)*1.05,MAX_MOVE_CYCLES,12)
    local advance=config.timeBasedMovement and dt*math.clamp(speed/config.speed,0,2) or math.min(distance/math.max(.1,strideLength),dt*cap)*clip.duration
    state.moveClock=(state.moveClock+advance)%clip.duration
   end
   -- Each buffer is written once and only read after that, within this frame.
   local idle=Motion.sample(data,'Idle',now+state.idleOffset,buffers.idle)
   local move=Motion.sample(data,'Move',state.moveClock,buffers.move)
   target=Motion.blend(idle,move,state.stride,buffers.mix)
   if attacking then
    -- The attack plays above the hips; the legs keep the walk cycle while the enemy moves and
    -- settle into the authored attack stance when it stands still. Legless rigs use the whole clip.
    local attack=Motion.sample(data,'Attack',attackTime(data,config,age),buffers.attack)
    for _,bone in state.legBones do
     if attack[bone] and target[bone] then attack[bone]=attack[bone]:Lerp(target[bone],state.stride) end
    end
    target=attack
   end
   target=Motion.scalePose(target,relativeScale,buffers.scaled)
  end
  local mode=attacking and 'Attack' or walking and 'Move' or 'Idle'
  -- The outgoing pose freezes as the transition source; output swaps to the other buffer so
  -- the frozen one is never overwritten while it is blended from.
  if mode~=state.mode then state.mode=mode;state.transition=0;state.transitionPose=state.poses;state.poses,state.spare=state.spare,state.poses end
  state.transition=(state.transition or 0)+dt
  -- Blend only on state changes; continuous smoothing would drag planted feet.
  state.poses=Motion.blend(state.transitionPose or EMPTY,target,math.min(1,state.transition/.12),state.poses)
  local displayPoses=state.poses
  -- Zombie feet stay planted only for a standing attack; on the move they keep stepping.
  -- The feet write into their copy, never into state.poses (next frame's transition source).
  if config.legacy or state.legs then
   local copy=buffers.display;table.clear(copy)
   for name,pose in state.poses do copy[name]=pose end
   if config.legacy then displayPoses=NativeFeet.apply(state.feet,copy,state.phase,state.stride,attacking and not walking)
   -- Imported bipeds: IK legs while moving, the clip's own legs (idle, attack stance) standing.
   else displayPoses=NativeFeet.applyImported(state.legs,copy,state.phase,state.stride) end
  end
  Motion.apply(state.joints,displayPoses)
  if state.data then HeldProjectiles.update(npc,config,state.data,state.poses,attacking and age or nil,attacking and attackTime(state.data,config,age) or 0) end
  npc:SetAttribute('ClientMotionState',mode)
  npc:SetAttribute('ClientMeasuredSpeed',speed)
 end
 debug.profileend()
end)
