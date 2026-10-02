-- The egg merchant NPC (Workspace.RogueliteLobby.EggMerchant.Merchant): idle life, looking at you,
-- waving hello, presenting the egg, a nod when you buy, a cheer for a big hatch, and a speech
-- bubble. Client-only presentation: each client poses its own copy of the anchored parts (CFrames
-- set on the client never replicate), so nothing here touches the server.
--
-- Rig (blender-egg-merchant-kit merchant, placed by lobby/InstallEggMerchant.luau): rigid MeshParts.
-- Every part except the root (Merchant_Hips) carries `Joint` (joint name), `JointParent` (parent
-- part name) and `JointPivot` (Vector3: the joint in the Merchant model's pivot space). The rest
-- pose is the installed CFrames. Model space: front -Z, the merchant's right +X, up +Y.
-- Angles (radians, about model axes at the joint): +X raises an arm or bends an elbow forward,
-- +Z swings the RIGHT arm out sideways (the left arm uses -Z), +Y turns left.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local T=require(RS:WaitForChild('UITheme'))
local M={}

local player=Players.LocalPlayer
local model,parts,rest,joints,order
local pivot0
local started=false

-- Lines (short, playful; the bubble fits about 40 characters on two lines).
M.Lines={
 greet={'Psst! Fresh eggs here!','Eggs! Hatch yourself a buddy!','Ooh, an adventurer! Need a pet?',"Every egg's a surprise, friend!"},
 open={'250 emeralds an egg. Feeling lucky?','Pick one, tap it till it cracks!','Warm, fresh, and full of pets!'},
 bought={'Pleasure doing business!','Good choice. Very good choice.','Handle with care!'},
 broke={'Come back with more emeralds!','Eggs cost emeralds, friend.'},
 bye={'Come back soon!','Take care of that pet!'},
 Common={'A fine little friend!','Aww, look at it!'},
 Rare={'Ooh, a rare one!','Now we\'re talking!'},
 Epic={'Now THAT is an Epic!','Whoa! Lucky you!'},
 Legendary={'NO WAY! A LEGENDARY!','I\'ve never seen one hatch!'},
}
function M.pick(kind) local l=M.Lines[kind];return l and l[math.random(1,#l)] or '' end

-- Pose state: target angles per joint (Vector3 of X,Y,Z), eased toward each frame.
local target,current={},{}
local rootOffset=CFrame.identity
local mode='idle' -- idle | wave | present | nod | cheer
local modeUntil=0
local lookAt -- world position the head turns to (nil = nearest player)
local tossAt=os.clock()+6
local eggHop,eggSpin=0,0

local function find()
 local lobby=workspace:FindFirstChild('RogueliteLobby')
 local root=lobby and lobby:FindFirstChild('EggMerchant')
 local m=root and root:FindFirstChild('Merchant')
 if not m or not m:FindFirstChild('Merchant_Hips') then return nil end
 for _,p in m:GetChildren() do if p:IsA('BasePart') and p.Name~='Merchant_Hips' and not p:GetAttribute('JointParent') then return nil end end
 return m
end

local function setup(m)
 model=m;parts={};rest={};joints={};order={}
 pivot0=m:GetPivot()
 for _,p in m:GetChildren() do
  if p:IsA('BasePart') then parts[p.Name]=p;rest[p.Name]=pivot0:ToObjectSpace(p.CFrame) end
 end
 -- Parents before children.
 local placed={Merchant_Hips=true};order={'Merchant_Hips'}
 for _=1,12 do
  for name,p in parts do
   local parent=p:GetAttribute('JointParent')
   if not placed[name] and parent and placed[parent] then
    placed[name]=true;table.insert(order,name)
    local j=p:GetAttribute('Joint') or name
    joints[name]={joint=j,parent=parent,pivot=p:GetAttribute('JointPivot') or Vector3.zero}
    target[j]=target[j] or Vector3.zero;current[j]=current[j] or Vector3.zero
   end
  end
 end
end

local function ang(v) return CFrame.Angles(v.X,v.Y,v.Z) end
local function set(j,x,y,z) target[j]=Vector3.new(x or 0,y or 0,z or 0) end

-- Pose for the current mode at time t (sets `target`, `rootOffset`, the hand egg's hop).
local function pose(t,dt)
 local breathe=math.sin(t*1.7)
 local sway=math.sin(t*.55)
 for j in target do target[j]=Vector3.zero end
 rootOffset=CFrame.new(0,breathe*.025,0)*CFrame.Angles(0,0,sway*.012)
 set('Waist',breathe*.02,sway*.03,0)
 set('Pack',breathe*.025+.01,0,sway*.02)
 set('Shoulder_R',.06+breathe*.03,0,.08)
 set('Elbow_R',.25)
 -- Left hand holds the little egg up in front of him, like the concept art (the rest pose already
 -- bends that elbow 22 degrees).
 set('Shoulder_L',.3+breathe*.02,0,-.06)
 set('Elbow_L',.7)
 set('Hip_L',0,0,-.02);set('Hip_R',0,0,.02)
 eggHop=0;eggSpin=0
 -- An idle egg toss now and then: the forearm flicks and the egg hops and spins.
 local toss=t-tossAt
 if mode=='idle' and toss>=0 then
  if toss>1 then tossAt=t+7+math.random()*5
  else
   local up=math.sin(math.clamp(toss/.8,0,1)*math.pi)
   eggHop=up*1.4;eggSpin=toss/.8*math.pi*2
   set('Elbow_L',.7+math.max(0,math.sin(math.clamp(toss/.18,0,1)*math.pi))*.45)
  end
 end
 local k=t-(modeUntil-(M.Duration[mode] or 0))
 if mode=='wave' then
  local w=math.sin(k*11)
  set('Shoulder_R',.15,0,2.45+w*.12)
  set('Elbow_R',.35,0,.25+w*.5)
  set('Neck',0,0,-.08)
 elseif mode=='present' then
  -- Right arm out toward the egg, palm up (the forearm twists -80 degrees about its own length
  -- before the elbow bends); the body turns a little with it.
  set('Waist',breathe*.02,-.16,0)
  set('Shoulder_R',1.05+breathe*.03,0,.75)
  set('Elbow_R',.5,-1.4,0)
 elseif mode=='nod' then
  set('Neck',-math.max(0,math.sin(k*9))*.32,0,0) -- +X looks up, so a nod is negative
  set('Shoulder_R',.2,0,.25);set('Elbow_R',.6)
 elseif mode=='cheer' then
  local hop=math.max(0,math.sin(k*8))
  rootOffset=CFrame.new(0,hop*.45,0)
  -- Both arms up in front (raising the left arm sideways would hit the bedroll on the pack).
  set('Shoulder_R',2.5+hop*.15,0,.35);set('Elbow_R',.3)
  set('Shoulder_L',2.5+hop*.15,0,-.35);set('Elbow_L',.3)
  set('Neck',.2,0,0) -- chin up
 end
end
M.Duration={wave=1.6,nod=1.1,cheer=2.2,present=1e9}

-- Head turns toward `lookAt`, else the local player when close. Yaw and pitch are clamped.
local headYaw,headPitch=0,0
local function look(dt)
 local want=lookAt
 if not want then
  local char=player and player.Character
  local hrp=char and char:FindFirstChild('HumanoidRootPart')
  if hrp and (hrp.Position-pivot0.Position).Magnitude<34 then want=hrp.Position+Vector3.new(0,1.2,0) end
 end
 local yaw,pitch=0,0
 if want then
  local head=parts.Merchant_Head
  local jp=joints.Merchant_Head and pivot0*joints.Merchant_Head.pivot or head.Position
  local rel=pivot0:VectorToObjectSpace(want-jp)
  yaw=math.clamp(math.atan2(-rel.X,-rel.Z),-.95,.95)
  pitch=math.clamp(math.atan2(rel.Y,math.sqrt(rel.X^2+rel.Z^2)),-.35,.3)
 end
 local k=1-math.exp(-dt*5)
 headYaw+=(yaw-headYaw)*k;headPitch+=(pitch-headPitch)*k
end

local function frame(dt)
 if not model or not model.Parent then started=false;return end
 local t=os.clock()
 if mode~='idle' and mode~='present' and t>=modeUntil then mode='idle' end
 pose(t,dt)
 look(dt)
 local nod=target.Neck or Vector3.zero
 target.Neck=Vector3.new(headPitch+nod.X,headYaw,nod.Z)
 local k=1-math.exp(-dt*9)
 for j,v in target do current[j]=(current[j] or Vector3.zero):Lerp(v,k) end
 -- Forward kinematics in model space: delta[part] moves the part's rest CFrame.
 local delta={}
 local hipsPivot=joints.Merchant_Torso and joints.Merchant_Torso.pivot or Vector3.new(0,3,0)
 delta.Merchant_Hips=CFrame.new(hipsPivot)*rootOffset*CFrame.new(-hipsPivot)
 for _,name in order do
  local jn=joints[name]
  if jn then
   local a=current[jn.joint] or Vector3.zero
   local d=delta[jn.parent]*CFrame.new(jn.pivot)*ang(a)*CFrame.new(-jn.pivot)
   if name=='Merchant_HandEgg' and (eggHop>0 or eggSpin>0) then
    local c=rest[name].Position
    d=d*CFrame.new(c+Vector3.new(0,eggHop,0))*CFrame.Angles(eggSpin,0,eggSpin*.5)*CFrame.new(-c)
   end
   delta[name]=d
  end
 end
 for _,name in order do
  local p=parts[name]
  if p and p.Parent and delta[name] then p.CFrame=pivot0*delta[name]*rest[name] end
 end
end

-- Speech bubble -------------------------------------------------------------------------------
local bubble,bubbleText,bubbleToken
local function makeBubble()
 local head=parts and parts.Merchant_Head;if not head then return end
 if bubble and bubble.Parent then return end
 bubble=Instance.new('BillboardGui');bubble.Name='MerchantSpeech';bubble.Adornee=head
 bubble.Size=UDim2.fromOffset(440,120);bubble.StudsOffsetWorldSpace=Vector3.new(0,3.4,0)
 bubble.LightInfluence=0;bubble.MaxDistance=80;bubble.AlwaysOnTop=true;bubble.ResetOnSpawn=false;bubble.Enabled=false
 local p=T.panel(bubble,'Panel',10,0,420,96,'panel')
 local tail=T.make('Frame',bubble,{Name='Tail',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(220,96),Size=UDim2.fromOffset(22,22),Rotation=45,BackgroundColor3=Color3.fromRGB(24,28,30),BorderSizePixel=0,ZIndex=0})
 T.make('UIStroke',tail,{Color=Color3.fromRGB(145,239,20),Thickness=2})
 local name=T.label(p,'Name','EGG MERCHANT',22,6,376,26,20,T.Color.lime);name.TextXAlignment=Enum.TextXAlignment.Left
 bubbleText=T.label(p,'Line','',22,32,376,56,28,T.Color.white);bubbleText.TextXAlignment=Enum.TextXAlignment.Left;bubbleText.TextWrapped=true
 bubble.Parent=player:WaitForChild('PlayerGui')
end
function M.Say(text,seconds)
 if not model then return end
 makeBubble();if not bubble then return end
 local token={};bubbleToken=token
 bubbleText.Text=text;bubbleText.MaxVisibleGraphemes=0
 bubble.Enabled=true
 local s=bubble.Panel:FindFirstChild('Pop') or T.make('UIScale',bubble.Panel,{Name='Pop',Scale=1})
 s.Scale=.6;TweenService:Create(s,TweenInfo.new(.25,Enum.EasingStyle.Back),{Scale=1}):Play()
 task.spawn(function()
  local n=utf8.len(text) or #text
  for i=1,n do
   if bubbleToken~=token then return end
   bubbleText.MaxVisibleGraphemes=i;task.wait(.022)
  end
  bubbleText.MaxVisibleGraphemes=-1
  task.wait(seconds or 3.2)
  if bubbleToken==token then bubble.Enabled=false end
 end)
end

-- Gestures -------------------------------------------------------------------------------------
local function play(m) mode=m;modeUntil=os.clock()+(M.Duration[m] or 1) end
function M.Wave() if mode~='present' then play('wave') end end
function M.Nod() play('nod') end
function M.Cheer() play('cheer') end
function M.Present(on) if on then mode='present';modeUntil=math.huge elseif mode=='present' then mode='idle' end end
function M.LookAt(pos) lookAt=pos end
function M.Model() return model end

-- Greets the local player once each time they walk up (re-arms after they wander off).
local greeted=false
local function greet()
 local hrp=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
 if not hrp or not model then return end
 local d=(hrp.Position-pivot0.Position).Magnitude
 if d<18 and not greeted then greeted=true;M.Wave();M.Say(M.pick('greet'))
 elseif d>30 then greeted=false end
end

-- Edit-mode checks (no Play session): pose the installed merchant in one mode and leave him there,
-- or put every part back. Example: M.DebugPose(workspace.RogueliteLobby.EggMerchant.Merchant,'present')
function M.DebugPose(m,modeName)
 if model~=m then setup(m) else M.DebugReset() end -- rest = the installed pose, never a posed one
 mode=modeName or 'idle';modeUntil=os.clock()+(M.Duration[mode] or 1)
 for _=1,40 do frame(.5) end
end
function M.DebugReset()
 if not model then return end
 for name,p in parts do p.CFrame=pivot0*rest[name] end
 mode='idle'
end

-- Starts once the merchant has streamed in (the EggMerchant model is Persistent); safe to call
-- more than once. Stops by itself if the model goes away and restarts when it comes back.
function M.Start()
 if started then return end
 started=true
 task.spawn(function()
  local m
  for _=1,600 do m=find();if m then break end;task.wait(.5) end
  if not m then started=false;return end
  setup(m)
  local conn
  conn=RunService.RenderStepped:Connect(function(dt)
   if not model or not model.Parent then conn:Disconnect();started=false;model=nil;task.delay(2,M.Start);return end
   frame(math.min(dt,.1))
  end)
  while model do greet();task.wait(.3) end
 end)
end

return M
