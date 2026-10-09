-- Local presentation of server heart pickups; never requests pickups or healing.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('ShardMotion'))
local Visual=require(combat:WaitForChild('HeartPickupVisual'))
local drops=workspace:WaitForChild('RogueliteHeartDrops')
local player=Players.LocalPlayer
local folder=Instance.new('Folder');folder.Name='LocalHeartVisuals';folder.Parent=workspace
local template=Visual.create(nil,'HeartPickup',1.8)
-- The HUD icon's dark border, drawn around the faceted body.
local outline=Instance.new('Highlight');outline.Name='HeartOutline'
outline.FillTransparency=1;outline.OutlineColor=Color3.fromRGB(8,9,10);outline.OutlineTransparency=0
outline.DepthMode=Enum.HighlightDepthMode.Occluded;outline.Parent=template
local glow=Instance.new('PointLight');glow.Name='HeartGlow'
glow.Color=Color3.fromRGB(255,95,90);glow.Brightness=.6;glow.Range=6;glow.Shadows=false
glow.Parent=template.PrimaryPart
local visuals={}
local function healPop(amount)
 local root=player.Character and player.Character:FindFirstChild('HumanoidRootPart');if not root then return end
 local gui=Instance.new('BillboardGui');gui.Name='HeartHealPop';gui.Size=UDim2.fromOffset(120,40)
 gui.StudsOffset=Vector3.new(0,3.2,0);gui.AlwaysOnTop=true;gui.Adornee=root
 local label=Instance.new('TextLabel');label.Size=UDim2.fromScale(1,1);label.BackgroundTransparency=1
 label.Font=Enum.Font.FredokaOne;label.TextScaled=true;label.Text='+'..math.max(1,math.round(amount))..' HP'
 label.TextColor3=Color3.fromRGB(255,120,115);label.TextStrokeColor3=Color3.fromRGB(8,9,10);label.TextStrokeTransparency=0
 label.Parent=gui;gui.Parent=root
 TweenService:Create(gui,TweenInfo.new(.8,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{StudsOffset=Vector3.new(0,5,0)}):Play()
 TweenService:Create(label,TweenInfo.new(.8,Enum.EasingStyle.Quad,Enum.EasingDirection.In),{TextTransparency=1,TextStrokeTransparency=1}):Play()
 task.delay(.85,function() gui:Destroy() end)
end
local function track(m)
 if visuals[m] or not m:IsA('Model') or m:GetAttribute('Kind')=='Pizza' then return end -- ChefPizzaVisuals draws those
 local v=template:Clone();v.Parent=folder;visuals[m]=v
end
drops.ChildAdded:Connect(track)
drops.ChildRemoved:Connect(function(m)
 local v=visuals[m];visuals[m]=nil;if v then v:Destroy() end
 if m:GetAttribute('MagnetUserId')==player.UserId and (m:GetAttribute('Healed') or 0)>0 then healPop(m:GetAttribute('Healed')) end
end)
for _,m in drops:GetChildren() do track(m) end
RunService.RenderStepped:Connect(function()
 local now=workspace:GetServerTimeNow()
 for m,v in visuals do
  local origin=m:GetAttribute('Origin')
  if typeof(origin)~='Vector3' then continue end
  local born=m:GetAttribute('BornAt') or now
  local pos=Motion.idle(origin,born,now)
  local id=m:GetAttribute('MagnetUserId');local start=m:GetAttribute('MagnetStart')
  local p=id and Players:GetPlayerByUserId(id)
  local r=p and p.Character and p.Character:FindFirstChild('HumanoidRootPart')
  if r and start then pos=Motion.pull(m:GetAttribute('MagnetOrigin') or pos,r.Position,now-start) end
  -- Upright, turning slowly about its vertical axis so both faces read.
  v:PivotTo(CFrame.new(pos)*CFrame.Angles(0,(now-born)*1.6+born%6.28,0))
  -- Blink through its last 3 seconds before it expires (not while flying to a player).
  local left=(m:GetAttribute('ExpiresAt') or math.huge)-now
  local hidden=not start and left<3 and (now*(left<1.2 and 8 or 4))%1<.35
  if v:GetAttribute('Hidden')~=hidden then
   v:SetAttribute('Hidden',hidden)
   for _,d in v:GetDescendants() do
    if d:IsA('BasePart') then d.LocalTransparencyModifier=hidden and 1 or 0
    elseif d:IsA('Highlight') then d.Enabled=not hidden
    elseif d:IsA('Light') then d.Enabled=not hidden end
   end
  end
 end
end)
