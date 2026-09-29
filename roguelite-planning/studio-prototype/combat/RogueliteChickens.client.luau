-- Client presentation for egg chickens (server: EggChickens). Waddle, flap and peck on the
-- rig's Motor6Ds, a shell burst on hatching, and at the end a swell and a feather explosion.
-- Nothing here affects combat.
local Tags=game:GetService('CollectionService')
local RunService=game:GetService('RunService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local K=require(combat:WaitForChild('VfxKit'))
local fx=Instance.new('Folder');fx.Name='RogueliteChickenFX';fx.Parent=workspace
local SHELL=Color3.fromRGB(250,244,230)
local CREAM=Color3.fromRGB(246,236,214)
local STRIDE=1.5 -- studs of travel per full two-step cycle
local FEATHERS=18
local tracked={}

local function feathers(position)
 if not K.near(position,160) then return end
 local template=combat:FindFirstChild('ChickenFeather')
 local list={}
 for i=1,FEATHERS do
  local p
  if template then p=template:Clone() else p=K.part(fx,'Feather',Vector3.new(.22,.04,.55),SHELL) end
  p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false;p.CastShadow=false;p.Parent=fx
  local angle=(i/FEATHERS)*math.pi*2+math.random()*.5
  local out=Vector3.new(math.cos(angle),.5+math.random()*1.1,math.sin(angle)).Unit
  list[i]={part=p,position=position,velocity=out*(10+math.random()*9),seed=math.random()*6.28,
   spin=CFrame.Angles(math.random()*6.28,math.random()*6.28,math.random()*6.28),size=p.Size}
 end
 -- A fast burst, then drag takes over and they flutter down, swaying.
 local last=0
 K.animate(2.1,function(t,age)
  local dt=math.min(1/30,age-last);last=age
  for _,f in list do
   f.velocity=(f.velocity+Vector3.yAxis*-16*dt)*math.exp(-4.5*dt)
   f.position+=f.velocity*dt+Vector3.new(math.sin(age*5+f.seed),0,math.cos(age*4+f.seed))*.9*dt
   local sway=math.sin(age*7+f.seed)*.7
   f.part.CFrame=CFrame.new(f.position)*f.spin*CFrame.Angles(sway,age*2,sway*.5)
   f.part.Transparency=K.smooth((t-.7)/.3)
  end
 end,function() for _,f in list do f.part:Destroy() end end,'chickenFeathers',6)
 K.cloud(fx,position,CREAM,1.6,.45,Vector3.yAxis*.6,.35)
 K.pop(fx,position,SHELL,.6,3.2,.22,.35)
end

-- Swell and jiggle a hidden-original copy, then burst it.
local function pop(state,model,popAt)
 if state.popping then return end
 state.popping=true
 local root=model:FindFirstChild('HumanoidRootPart');if not root then return end
 local center=root.Position+Vector3.yAxis*.4
 local copies={}
 for _,p in model:GetDescendants() do
  if p:IsA('BasePart') and p~=root then
   local c=p:Clone();c:ClearAllChildren();c.Anchored=true;c.CanCollide=false;c.CanQuery=false;c.CanTouch=false;c.Parent=fx
   table.insert(copies,{part=c,offset=CFrame.new(center):ToObjectSpace(p.CFrame),size=p.Size})
   p.LocalTransparencyModifier=1
  end
 end
 local duration=math.max(.12,popAt-workspace:GetServerTimeNow())
 K.animate(duration,function(t)
  local swell=1+.55*t*t+math.sin(t*38)*.07*t
  for _,c in copies do
   c.part.Size=c.size*swell
   c.part.CFrame=CFrame.new(center)*(c.offset.Rotation+c.offset.Position*swell)
  end
 end,function()
  for _,c in copies do c.part:Destroy() end
  feathers(center)
 end,'chickenPop',12)
end

local function track(model)
 if tracked[model] then return end
 local joints={}
 for _,j in model:GetDescendants() do if j:IsA('Motor6D') then joints[j.Name]=j end end
 local root=model:FindFirstChild('HumanoidRootPart')
 local state={joints=joints,phase=0,stride=0,seed=math.random()*6.28,last=root and root.Position}
 tracked[model]=state
 local hatched=model:GetAttribute('HatchedAt')
 if root and hatched and workspace:GetServerTimeNow()-hatched<.6 and K.near(root.Position,160) then
  local feet=root.Position-Vector3.yAxis*1
  K.shards(fx,feet+Vector3.yAxis*.3,SHELL,9,7,.5,.18,Enum.Material.SmoothPlastic,.9)
  K.cloud(fx,feet,CREAM,1.2,.35,Vector3.yAxis*.5,.4)
 end
 if model:GetAttribute('PopAt') then pop(state,model,model:GetAttribute('PopAt')) end
 model:GetAttributeChangedSignal('PopAt'):Connect(function()
  local at=model:GetAttribute('PopAt');if at then pop(state,model,at) end
 end)
end
Tags:GetInstanceAddedSignal('RogueliteChicken'):Connect(track)
Tags:GetInstanceRemovedSignal('RogueliteChicken'):Connect(function(model)
 local state=tracked[model];tracked[model]=nil
 -- Removed without the server's pop (owner left, map reset): still go out in feathers.
 if state and not state.popping and state.last then feathers(state.last+Vector3.yAxis*.4) end
end)
for _,model in Tags:GetTagged('RogueliteChicken') do track(model) end

RunService.PreSimulation:Connect(function(dt)
 local now=workspace:GetServerTimeNow()
 for model,state in tracked do
  local root=model:FindFirstChild('HumanoidRootPart');local j=state.joints
  if not root or state.popping then continue end
  local step=state.last and Vector3.new(root.Position.X-state.last.X,0,root.Position.Z-state.last.Z).Magnitude or 0
  state.last=root.Position
  if dt<=0 or step>6 then step=0 end
  local walking=step/math.max(dt,1/240)>.6
  state.stride+=((walking and 1 or 0)-state.stride)*(1-math.exp(-math.min(dt,.1)*10))
  state.phase=(state.phase+step*2*math.pi/STRIDE)%(2*math.pi)
  local s,phase,wobble=state.stride,state.phase,now*2+state.seed
  local peck=model:GetAttribute('PeckStart');local age=peck and now-peck
  local strike=0
  if age and age>=0 and age<.4 then strike=age<.12 and K.smooth(age/.12) or 1-K.smooth((age-.12)/.28) end
  local swing=math.sin(phase)
  if j.LeftHip then j.LeftHip.Transform=CFrame.Angles(swing*.7*s,0,0) end
  if j.RightHip then j.RightHip.Transform=CFrame.Angles(-swing*.7*s,0,0) end
  -- Waddle: a bob twice per cycle, a side-to-side roll and a small forward lean at speed.
  if j.Body then j.Body.Transform=CFrame.new(0,math.abs(math.cos(phase))*.14*s,0)*CFrame.Angles(-.12*s-.25*strike,0,math.sin(phase)*.14*s) end
  -- Wings flap hard while running or pecking and twitch now and then at rest.
  local flap=(.2+.6*s+.5*strike)*(.5+.5*math.sin(now*(s>.3 and 26 or 9)+state.seed))+math.max(0,math.sin(wobble*1.3))^12*.4
  if j.LeftWing then j.LeftWing.Transform=CFrame.Angles(0,0,-flap) end
  if j.RightWing then j.RightWing.Transform=CFrame.Angles(0,0,flap) end
  -- Head: bobs with the steps, a derpy tilt when idle, and a hard peck forward and down.
  if j.Neck then j.Neck.Transform=CFrame.new(0,0,-.35*strike)*CFrame.Angles(math.sin(phase*2)*.12*s-.9*strike,math.sin(wobble*.7)*.25*(1-s),math.sin(wobble)*.18*(1-s)) end
 end
end)
