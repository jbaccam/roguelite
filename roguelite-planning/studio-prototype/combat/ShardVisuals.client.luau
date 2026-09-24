-- Smooth local presentation; never submits pickup or currency requests.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('ShardMotion'))
local Visual=require(combat:WaitForChild('CrystalShardVisual'))
local drops=workspace:WaitForChild('RogueliteShardDrops')
local folder=Instance.new('Folder');folder.Name='LocalCrystalVisuals';folder.Parent=workspace
local template=Visual.create(nil,'CrystalShard',1.5)
-- Keep deep-blue facets readable; only the pale cyan faces emit light.
for _,part in template:GetDescendants() do
 if part:IsA('BasePart') and part.Name=='AzureFacet' and part.Color.G>.7 then
  part.Material=Enum.Material.Neon
  part.Color=part.Color:Lerp(Color3.fromRGB(130,235,255),.3)
 end
end
local glow=Instance.new('PointLight');glow.Name='ShardGlow'
glow.Color=Color3.fromRGB(100,210,255);glow.Brightness=.45;glow.Range=5;glow.Shadows=false
glow.Parent=template.PrimaryPart
local attachment=Instance.new('Attachment');attachment.Name='AuraOrigin';attachment.Parent=template.PrimaryPart
local aura=Instance.new('ParticleEmitter');aura.Name='BlueAura'
aura.Texture='rbxasset://textures/particles/smoke_main.dds'
aura.Color=ColorSequence.new(Color3.fromRGB(115,210,255),Color3.fromRGB(55,150,245))
aura.LightEmission=1;aura.LightInfluence=0;aura.Rate=5
aura.Lifetime=NumberRange.new(.8,1.2);aura.Speed=NumberRange.new(.05,.18)
aura.SpreadAngle=Vector2.new(180,180);aura.Rotation=NumberRange.new(0,360);aura.RotSpeed=NumberRange.new(-18,18)
aura.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,1.35),NumberSequenceKeypoint.new(.5,2.15),NumberSequenceKeypoint.new(1,2.6)})
aura.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.2,.82),NumberSequenceKeypoint.new(.6,.91),NumberSequenceKeypoint.new(1,1)})
aura.LockedToPart=true;aura.Parent=attachment
local visuals={}
local refresh=0
RunService.RenderStepped:Connect(function(dt)
 local now=workspace:GetServerTimeNow();refresh-=dt
 if refresh<=0 then
  refresh=.15
  local position=workspace.CurrentCamera.CFrame.Position
  local root=Players.LocalPlayer.Character and Players.LocalPlayer.Character:FindFirstChild('HumanoidRootPart')
  if root then position=root.Position end
  local list={}
  for _,m in drops:GetChildren() do
   local origin=m:GetAttribute('Origin')
   if typeof(origin)=='Vector3' then table.insert(list,{model=m,distance=(origin-position).Magnitude,active=m:GetAttribute('MagnetUserId')~=nil}) end
  end
  table.sort(list,function(a,b) if a.active~=b.active then return a.active end;return a.distance<b.distance end)
  local wanted={}
  for i=1,math.min(128,#list) do
   local m=list[i].model;wanted[m]=true
   if not visuals[m] then local v=template:Clone();v.Parent=folder;visuals[m]=v end
   -- Bound translucent overdraw and dynamic lights in dense drop piles.
   local v=visuals[m]
   v.PrimaryPart.ShardGlow.Enabled=i<=12 and list[i].distance<45
   v.PrimaryPart.AuraOrigin.BlueAura.Enabled=i<=32 and list[i].distance<70
  end
  for m,v in visuals do if not wanted[m] then v:Destroy();visuals[m]=nil end end
 end
 for m,v in visuals do
  if not m.Parent then v:Destroy();visuals[m]=nil;continue end
  local origin=m:GetAttribute('Origin');local born=m:GetAttribute('BornAt') or now
  local pos=Motion.idle(origin,born,now)
  local id=m:GetAttribute('MagnetUserId');local start=m:GetAttribute('MagnetStart')
  local p=id and Players:GetPlayerByUserId(id)
  local r=p and p.Character and p.Character:FindFirstChild('HumanoidRootPart')
  if r and start then pos=Motion.pull(m:GetAttribute('MagnetOrigin') or pos,r.Position,now-start) end
  v:PivotTo(CFrame.new(pos)*Motion.rotation(born,now))
 end
end)
