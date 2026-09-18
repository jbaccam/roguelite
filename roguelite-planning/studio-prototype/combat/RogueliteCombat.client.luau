local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local Debris=game:GetService('Debris')
local Input=game:GetService('UserInputService')
local combat=game:GetService('ReplicatedStorage'):WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local Motion=require(combat:WaitForChild('WeaponMotion'))
local templates=combat:WaitForChild('WeaponTemplates')
local states=combat:WaitForChild('PlayerStates')
local player=Players.LocalPlayer
local visuals=Instance.new('Folder');visuals.Name='RogueliteCombatVisuals';visuals.Parent=workspace
require(combat:WaitForChild('RocketVisuals')).mount(combat,visuals)
local bulletImpact=require(combat:WaitForChild('BulletImpactVisuals')).mount(visuals)
local tracked={}
local floats={}
RunService:BindToRenderStep('RogueliteWeapons',Enum.RenderPriority.Character.Value+1,function(dt)
 local now=workspace:GetServerTimeNow()
 local seen={}
 for _,state in states:GetChildren() do
  local owner=Players:GetPlayerByUserId(tonumber(state.Name));local character=owner and owner.Character
  local root=character and character:FindFirstChild('HumanoidRootPart');local hum=character and character:FindFirstChildOfClass('Humanoid')
  local float=floats[state]
  if root and hum and hum.Health>0 then
   if not float or float.root~=root then float=Motion.newFloat();float.root=root;floats[state]=float end
   Motion.stepFloat(float,root.AssemblyLinearVelocity,dt)
  else floats[state]=nil;float=nil end
  for _,slot in state:GetChildren() do
   local id=slot:GetAttribute('WeaponId');local d=Catalog.ById[id]
   local v=tracked[slot];seen[slot]=true
   if v and v.id~=id then v.model:Destroy();tracked[slot]=nil;v=nil end
   local template=d and templates:FindFirstChild(id)
   if template and not v then
    local model=template:Clone();model.Name='Weapon_'..state.Name..'_'..slot.Name;model.Parent=visuals
    v={model=model,id=id,parts={}};tracked[slot]=v
    for _,part in model:GetDescendants() do if part:IsA('BasePart') then table.insert(v.parts,part) end end
   end
   if v then
    local visible=root and hum and hum.Health>0 and state:GetAttribute('WeaponEnabled')
    if visible then
     local start=slot:GetAttribute('StartTime') or -1e6
     local rate=slot:GetAttribute('MotionRate') or 1
     local animationNow=start+(now-start)*rate
     local aim=slot:GetAttribute('AimPosition')
     if d.kind=='Melee' and animationNow-start<.34 then aim=slot:GetAttribute('AttackAim') end
     local pose=Motion.pose(root.CFrame,state:GetAttribute('RingRadius') or 6,slot:GetAttribute('Index'),aim,start,animationNow,d.kind)
     if d.kind=='Melee' then local origin=Motion.origin(root.CFrame,state:GetAttribute('RingRadius') or 6,slot:GetAttribute('Index'));local reach=slot:GetAttribute('ReachScale') or 1;pose=CFrame.new(origin+(pose.Position-origin)*reach)*pose.Rotation end
     if float then pose=Motion.floatPose(pose,root.CFrame,float,slot:GetAttribute('Index'),animationNow-start<(d.kind=='Melee' and .34 or .16)) end
     v.model:PivotTo(pose)
    end
    for _,part in v.parts do part.LocalTransparencyModifier=visible and 0 or 1 end
   end
  end
 end
 for slot,v in tracked do if not seen[slot] then v.model:Destroy();tracked[slot]=nil end end
 for state in floats do if state.Parent~=states then floats[state]=nil end end
end)
combat:WaitForChild('Shot').OnClientEvent:Connect(function(origin,finish,kind,id,thickness,blastRadius,contact,normal,ownerId,slotIndex,first)
 if contact and kind=='Ranged' then bulletImpact(finish,normal) end
 if first and Motion.MuzzleOffsets[id] and ownerId and slotIndex then
  local state=states:FindFirstChild(tostring(ownerId))
  local slot=state and state:FindFirstChild('Slot'..slotIndex)
  local v=slot and tracked[slot]
  if v and v.id==id then origin=v.model:GetPivot():PointToWorldSpace(Motion.MuzzleOffsets[id]) end
 end
 local distance=(finish-origin).Magnitude;if distance<.01 then return end
 local p=Instance.new('Part');p.Name='WeaponShot';p.Anchored=true;p.CanCollide=false;p.CanTouch=false;p.CanQuery=false
 p.Material=Enum.Material.Neon;p.Color=kind=='Blast' and Color3.fromRGB(242,164,71) or Color3.fromRGB(255,231,179)
 p.Size=Vector3.new(thickness or .07,thickness or .07,distance);p.CFrame=CFrame.lookAt((origin+finish)/2,finish);p.Parent=visuals
 TweenService:Create(p,TweenInfo.new(.12),{Transparency=1}):Play();Debris:AddItem(p,.14)
 if kind=='Blast' then
  local burst=Instance.new('Part');burst.Name='WeaponBlast';burst.Shape=Enum.PartType.Ball;burst.Size=Vector3.one
  burst.Anchored=true;burst.CanCollide=false;burst.CanTouch=false;burst.CanQuery=false;burst.Material=Enum.Material.Neon
  burst.Color=p.Color;burst.Transparency=.6;burst.Position=finish;burst.Parent=visuals
  TweenService:Create(burst,TweenInfo.new(.25),{Size=Vector3.one*(blastRadius or 7)*2,Transparency=1}):Play();Debris:AddItem(burst,.3)
 end
end)
combat:WaitForChild('Hit').OnClientEvent:Connect(function(position,damage,npc)
 local anchor=Instance.new('Part');anchor.Name='DamageNumber';anchor.Size=Vector3.one*.1;anchor.Transparency=1;anchor.Anchored=true;anchor.CanCollide=false;anchor.CanTouch=false;anchor.CanQuery=false;anchor.Position=position+Vector3.new((math.random()-.5)*.8,0,0);anchor.Parent=visuals
 local gui=Instance.new('BillboardGui');gui.Size=UDim2.fromOffset(100,60);gui.AlwaysOnTop=true;gui.MaxDistance=100;gui.Parent=anchor
 local text=Instance.new('TextLabel');text.Size=UDim2.fromScale(1,1);text.BackgroundTransparency=1;text.Text=tostring(math.round(damage));text.Font=Enum.Font.GothamBold;text.TextSize=30;text.TextColor3=Color3.fromRGB(255,246,218);text.TextStrokeColor3=Color3.fromRGB(28,22,20);text.TextStrokeTransparency=.12;text.Parent=gui
 local scale=Instance.new('UIScale');scale.Scale=.65;scale.Parent=text
 TweenService:Create(scale,TweenInfo.new(.13,Enum.EasingStyle.Back,Enum.EasingDirection.Out),{Scale=1}):Play()
 TweenService:Create(anchor,TweenInfo.new(.8,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Position=anchor.Position+Vector3.new(0,2,0)}):Play()
 task.delay(.42,function()if text.Parent then TweenService:Create(text,TweenInfo.new(.3),{TextTransparency=1,TextStrokeTransparency=1}):Play()end end)
 Debris:AddItem(anchor,.85)
 if npc and npc.Parent then
  local previous=npc:FindFirstChild('WeaponHitFlash');if previous then previous:Destroy() end
  local flash=Instance.new('Highlight');flash.Name='WeaponHitFlash';flash.FillColor=Color3.new(1,1,1)
  flash.FillTransparency=0;flash.OutlineTransparency=1;flash.DepthMode=Enum.HighlightDepthMode.Occluded;flash.Parent=npc
  task.delay(.045,function()
   if flash.Parent then TweenService:Create(flash,TweenInfo.new(.09),{FillTransparency=1}):Play() end
  end)
  Debris:AddItem(flash,.15)
 end
end)

-- Five little clustered clouds pop outward from the last server-confirmed position.
-- They are detached from the NPC: its model is destroyed immediately on death.
combat:WaitForChild('ZombiePopped').OnClientEvent:Connect(function(position)
 local camera=workspace.CurrentCamera
 if camera and (camera.CFrame.Position-position).Magnitude>150 then return end
 local puff=Instance.new('Folder');puff.Name='ZombieDeathPuff';puff.Parent=visuals
 for i=1,5 do
  local angle=(i-1)*math.pi*2/5+.25
  local direction=Vector3.new(math.cos(angle),.15+(i%2)*.18,math.sin(angle))
  local center=position+direction*.4
  local width=.48+(i%3)*.12
  for lobe=1,3 do
   local cloud=Instance.new('Part');cloud.Name='CloudLobe';cloud.Shape=Enum.PartType.Ball
   cloud.Anchored=true;cloud.CanCollide=false;cloud.CanTouch=false;cloud.CanQuery=false;cloud.CastShadow=false
   cloud.Material=Enum.Material.SmoothPlastic
   cloud.Color=lobe==2 and Color3.fromRGB(250,253,255) or Color3.fromRGB(204,225,247)
   local offset=Vector3.new((lobe-2)*width*.55,lobe==2 and width*.22 or 0,0)
   local size=Vector3.new(width,width*(lobe==2 and .95 or .7),width*.8)
   cloud.Size=size*.5;cloud.Position=center+offset*.5;cloud.Parent=puff
   TweenService:Create(cloud,TweenInfo.new(.10,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Size=size,Position=center+offset+direction*.65}):Play()
   task.delay(.10,function()
    if cloud.Parent then TweenService:Create(cloud,TweenInfo.new(.25,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Size=size*.35,Transparency=1,Position=center+offset*.35+direction*1.65+Vector3.yAxis*.35}):Play() end
   end)
  end
 end
 Debris:AddItem(puff,.38)
end)

if RunService:IsStudio()then
 local gui=Instance.new('ScreenGui');gui.Name='RogueliteCombatTestControls';gui.ResetOnSpawn=false;gui.Parent=player:WaitForChild('PlayerGui')
 local frame=Instance.new('Frame');frame.Position=UDim2.fromOffset(14,72);frame.Size=UDim2.fromOffset(210,113);frame.BackgroundColor3=Color3.fromRGB(29,34,43);frame.BackgroundTransparency=.08;frame.Parent=gui;Instance.new('UICorner',frame).CornerRadius=UDim.new(0,8)
 local heading=Instance.new('TextLabel');heading.Position=UDim2.fromOffset(10,5);heading.Size=UDim2.new(1,-20,0,23);heading.Text='COMBAT TEST';heading.TextSize=13;heading.Font=Enum.Font.GothamBold;heading.TextXAlignment=Enum.TextXAlignment.Left;heading.BackgroundTransparency=1;heading.TextColor3=Color3.fromRGB(210,215,225);heading.Parent=frame
 local own=states:WaitForChild(tostring(player.UserId))
 local function toggle(key)
  local value=key=='Zombies'and combat:GetAttribute('ZombiesEnabled')or own:GetAttribute('WeaponEnabled')
  if key=='Zombies'then value=combat:GetAttribute('ZombiesEnabled')end
  combat.SetTestOption:FireServer(key,not value)
 end
 local function button(key,y,hotkey)
  local b=Instance.new('TextButton');b.Position=UDim2.fromOffset(8,y);b.Size=UDim2.new(1,-16,0,32);b.BackgroundColor3=Color3.fromRGB(51,62,76);b.TextColor3=Color3.new(1,1,1);b.Font=Enum.Font.GothamMedium;b.TextSize=15;b.Parent=frame;Instance.new('UICorner',b).CornerRadius=UDim.new(0,5)
  b.Activated:Connect(function()toggle(key)end)
  local function refresh()local enabled;if key=='Zombies'then enabled=combat:GetAttribute('ZombiesEnabled')else enabled=own:GetAttribute('WeaponEnabled')end;b.Text=key..': '..(enabled and 'ON' or 'OFF')..'  ['..hotkey..']';b.BackgroundColor3=enabled and Color3.fromRGB(51,75,83)or Color3.fromRGB(64,56,59)end
  if key=='Zombies'then combat:GetAttributeChangedSignal('ZombiesEnabled'):Connect(refresh)else own:GetAttributeChangedSignal('WeaponEnabled'):Connect(refresh)end;refresh()
 end
 button('Zombies',33,'Z');button('Weapons',72,'K')
 Input.InputBegan:Connect(function(input,processed)if processed or Input:GetFocusedTextBox()then return end;if input.KeyCode==Enum.KeyCode.Z then toggle('Zombies')elseif input.KeyCode==Enum.KeyCode.K then toggle('Weapons')end end)
end
