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
-- Drops being pulled first, then nearest. Only the best 128 are drawn and only the first 32 need
-- their rank (glow and aura), so the rest are never sorted.
local entries,list,pass={},{},0 -- entries: drop model -> {model,origin,distance,active,seen}
local function before(a,b) if a.active~=b.active then return a.active end;return a.distance<b.distance end
-- Moves the k best of list[1..n] into list[1..k], unordered (Wirth's FIND, average O(n)).
local function select(n,k)
 local lo,hi=1,n
 while lo<hi do
  local pivot=list[(lo+hi)//2];local i,j=lo,hi
  repeat
   while before(list[i],pivot) do i+=1 end
   while before(pivot,list[j]) do j-=1 end
   if i<=j then list[i],list[j]=list[j],list[i];i+=1;j-=1 end
  until i>j
  if k<=j then hi=j elseif k>=i then lo=i else return end
 end
end
RunService.RenderStepped:Connect(function(dt)
 local now=workspace:GetServerTimeNow();refresh-=dt
 if refresh<=0 then
  refresh=.15
  local position=workspace.CurrentCamera.CFrame.Position
  local root=Players.LocalPlayer.Character and Players.LocalPlayer.Character:FindFirstChild('HumanoidRootPart')
  if root then position=root.Position end
  pass+=1
  local n=0
  for _,m in drops:GetChildren() do
   -- A drop's Origin never changes once it exists, so it is read once.
   local e=entries[m]
   if not e then
    local origin=m:GetAttribute('Origin')
    if typeof(origin)=='Vector3' then e={model=m,origin=origin};entries[m]=e end
   end
   if e then
    e.seen=pass;e.distance=(e.origin-position).Magnitude;e.active=m:GetAttribute('MagnetUserId')~=nil
    n+=1;list[n]=e
   end
  end
  for i=n+1,#list do list[i]=nil end
  for m,e in entries do if e.seen~=pass then entries[m]=nil end end
  local count=math.min(128,n);local ranked=math.min(32,count)
  if n>count then select(n,count) end
  if count>ranked then select(count,ranked) end
  for i=2,ranked do -- insertion sort of the ranked few
   local e=list[i];local j=i-1
   while j>=1 and before(e,list[j]) do list[j+1]=list[j];j-=1 end
   list[j+1]=e
  end
  local wanted={}
  for i=1,count do
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
