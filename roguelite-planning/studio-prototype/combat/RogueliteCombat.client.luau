local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local Debris=game:GetService('Debris')
local Input=game:GetService('UserInputService')
local combat=game:GetService('ReplicatedStorage'):WaitForChild('RogueliteCombat')
local Catalog=require(combat:WaitForChild('WeaponCatalog'))
local Motion=require(combat:WaitForChild('WeaponMotion'))
local Chains=require(combat:WaitForChild('ChainWeaponMotion'))
local Cards=require(combat:WaitForChild('CardPresentation'))
local templates=combat:WaitForChild('WeaponTemplates')
local states=combat:WaitForChild('PlayerStates')
local player=Players.LocalPlayer
local visuals=Instance.new('Folder');visuals.Name='RogueliteCombatVisuals';visuals.Parent=workspace
require(combat:WaitForChild('RocketVisuals')).mount(combat,visuals)
local bulletImpact=require(combat:WaitForChild('BulletImpactVisuals')).mount(visuals)
local muzzleFlash=require(combat:WaitForChild('MuzzleFlashVisuals')).mount(visuals)
local mobImpact=require(combat:WaitForChild('MobImpactVisuals')).mount(visuals)
-- Damage numbers and hit flashes, pooled and capped.
local hitFeedback=require(combat:WaitForChild('HitFeedbackVisuals')).mount(visuals)
local shirtShot=require(combat:WaitForChild('ShirtVisuals')).mount(visuals)
local Swing=require(combat:WaitForChild('SwingVisuals')).mount(visuals)
local Spacing=require(combat:WaitForChild('WeaponSpacing'))
local Pandora=require(combat:WaitForChild('PandoraVisuals'))
local tracked={}
local projectileStyles=require(combat:WaitForChild('ProjectileStyleVisuals')).mount(visuals,function(ownerId,index)
 local state=states:FindFirstChild(tostring(ownerId))
 local slot=state and state:FindFirstChild('Slot'..tostring(index))
 return slot and tracked[slot]
end)
local ArcMotion=require(combat:WaitForChild('ArcMotion'))
require(combat:WaitForChild('ArcVisuals')).mount(combat,visuals,function(ownerId,index)
 local state=states:FindFirstChild(tostring(ownerId))
 local slot=state and state:FindFirstChild('Slot'..index)
 return slot and tracked[slot]
end)
require(combat:WaitForChild('SpecialWeaponVisuals')).mount(combat,visuals,function(owner,index)
 local state=states:FindFirstChild(tostring(owner));return state and tracked[state:FindFirstChild('Slot'..index)]
end)
-- Godly auras, trails and specials (GodlyFX: wraiths, waves, storm arrows, dagger chain, wisps, bursts).
local godlyFX=require(combat:WaitForChild('GodlyVisuals')).mount(combat,visuals,function(owner,index)
 local state=states:FindFirstChild(tostring(owner));return state and tracked[state:FindFirstChild('Slot'..tostring(index))]
end)
-- Legendary gold aura and Tier IV moves (LegendaryFX). A do-nothing stand-in if the module is missing.
local legendaryFX=(function()
 local m=combat:FindFirstChild('LegendaryVisuals')
 local ok,api=pcall(function() return require(m).mount(combat,visuals) end)
 if m and ok then return api end
 if m then warn('LegendaryVisuals failed to start:',api) end
 return {attach=function() end,step=function() end,hide=function() end}
end)()
local floats={}
-- Each attack arrives packed in the slot's 'Attack' attribute (ShotBatch.attackOf), and AimPosition
-- now changes only every 1.5 studs or so (RogueliteCombat.server), so a gun glides toward it
-- instead of stepping; a jump of 4+ studs (a new target) still snaps.
local Wire=require(combat:WaitForChild('ShotBatch'))
local function glide(v,aim,dt)
 if aim==nil or v.aim==nil or (aim-v.aim).Magnitude>4 then v.aim=aim
 else v.aim=v.aim:Lerp(aim,1-math.exp(-20*dt)) end
 return v.aim
end
RunService:BindToRenderStep('RogueliteWeapons',Enum.RenderPriority.Character.Value+1,function(dt)
 local now=workspace:GetServerTimeNow()
 local seen={}
 for _,state in states:GetChildren() do
  local owner=Players:GetPlayerByUserId(tonumber(state.Name));local character=owner and owner.Character
  local root=character and character:FindFirstChild('HumanoidRootPart');local hum=character and character:FindFirstChildOfClass('Humanoid')
  local float=floats[state]
  if root and hum and hum.Health>0 then
   if not float or float.root~=root then float=Motion.newFloat();float.root=root;floats[state]=float end
   Motion.stepFloat(float,root.CFrame,root.AssemblyLinearVelocity,dt)
  else floats[state]=nil;float=nil end
  local frameList={}
  for _,slot in state:GetChildren() do
   local id=slot:GetAttribute('WeaponId');local d=Catalog.ById[id]
   local v=tracked[slot];seen[slot]=true
   if v and v.id~=id then
    v.model:Destroy();tracked[slot]=nil;v=nil
    if float then float.slots[slot:GetAttribute('Index')]=nil end
   end
   local template=d and templates:FindFirstChild(id)
   if template and not v then
    local model=template:Clone();model.Name='Weapon_'..state.Name..'_'..slot.Name;model.Parent=visuals
    v={model=model,id=id,parts={},chain=Chains.bind(model,id),cards=Cards.bind(model,id)};tracked[slot]=v
    if id=='19' then
     v.gloves={}
     for _,part in model:GetDescendants() do if part:IsA('BasePart') then
      local localCF=model:GetPivot():ToObjectSpace(part.CFrame);table.insert(v.gloves,{part=part,localCF=localCF,side=localCF.X<0 and -1 or 1})
     end end
    end
    if id=='15' or id=='23' then
     v.reserves={}
     for i=2,3 do local copy=template:Clone();copy.Name='Reserve'..i;copy.Parent=model;v.reserves[i]=copy end
    end
    if id=='33' then v.lid=model:FindFirstChild('W33_Lid_Hinge',true) end
    for _,part in model:GetDescendants() do if part:IsA('BasePart') then
     part.Anchored=true;part.CanCollide=false;part.CanTouch=false;part.CanQuery=false
     table.insert(v.parts,part)
    end end
    -- Cosmetic extras: swing ribbons, Pandora glow and a contact capsule.
    Swing.attach(v,id,template);godlyFX.attach(v,id,template);legendaryFX.attach(v,id,template,slot)
    if id=='33' then v.pandora=Pandora.idle(model) end
    local bounds=template:GetAttribute('BoundsSize')
    if typeof(bounds)=='Vector3' then v.capsule=Spacing.capsule(bounds,template:GetAttribute('BoundsCenter')) end
    -- Egg/pin reserves sit 1.5 studs to each side; widen the capsule to cover them.
    if v.capsule and v.reserves then v.capsule={a=Vector3.new(-1.5,.2,.1),b=Vector3.new(1.5,.2,.1),r=v.capsule.r} end
   end
   if v then
    local visible=root and hum and hum.Health>0 and state:GetAttribute('WeaponEnabled')
    local aimed=glide(v,slot:GetAttribute('AimPosition'),dt)
    if visible then
     local a=Wire.attackOf(slot)
     local start=a.start or -1e6
     local rate=a.rate or 1
     local animationNow=start+(now-start)*rate
     local age=animationNow-start
     local kind=a.kind or d.kind
     local style=a.style
     local side=a.side or 1
     local attackRoot=a.root or root.CFrame
     local _,activeEnd,duration=Motion.attackTiming(id,kind,style)
     local aim=aimed
     if kind=='Melee' and age>=0 and age<duration then aim=a.aim end
     local radius=state:GetAttribute('RingRadius') or Motion.radius(root.Size,state:GetAttribute('EquippedCount'))
     local index=slot:GetAttribute('Index')
     local pose,idlePose
     if kind=='Melee' then
      -- Keep the follower running while the sword attacks. Recovery blends to
      -- its current moving position, so the cut snaps in but never snaps back.
      -- Rest/return facing belongs to the avatar, never the changing enemy.
      local idle=Motion.pose(root.CFrame,radius,index,nil,0,1e6,kind,id)
      if float then idle=Motion.floatPose(idle,root.CFrame,float,index,false,radius,false) end
      if v.gloves then idle*=CFrame.Angles(-math.pi/2,0,0) end
      pose=idle;idlePose=idle
      if age>=0 and age<duration then
       if not v.attackReturn or v.attackReturn.start~=start then
        v.attackReturn={start=start,entry=v.lastPose or idle,gloves={}}
        if v.gloves then for _,g in v.gloves do v.attackReturn.gloves[g.part]=g.part.CFrame end end
       end
       if v.chain then
        local cut=Chains.pose(v.chain,attackRoot,a.direction,aim,math.min(age,activeEnd),a.range or d.range,style,side,true)
        pose=age<=activeEnd and cut or Chains.swingReturn(v.chain,cut,idle,age,v.attackReturn)
       else
        local cut=Motion.pose(attackRoot,radius,index,aim,start,start+math.min(age,activeEnd),kind,id,
         a.direction,a.range or d.range,
         template:GetAttribute('BoundsSize'),template:GetAttribute('BoundsCenter'),style,side,true)
        pose=age<=activeEnd and cut or Motion.swingReturn(cut,idle,age,v.attackReturn,id,style)
       end
       if age<Motion.SwingHitStart then pose=v.attackReturn.entry:Lerp(pose,Motion.entryAlpha(age)) end
      else
       v.attackReturn=nil
      end
     else
      pose=Motion.pose(root.CFrame,radius,index,aim,start,animationNow,kind,id)
      if float then pose=Motion.floatPose(pose,root.CFrame,float,index,age>=0 and age<duration,radius,aim~=nil) end
     end
     if v.gloves then pose=idlePose or pose end
     v.lastPose=pose
     v.model:PivotTo(pose)
     if v.gloves then for _,g in v.gloves do g.part.CFrame=pose*g.localCF end end
     if v.gloves and age>=0 and age<duration then
      for _,g in v.gloves do
       local target=g.side==a.hand and aim or a.second
       if target then
        local cut=Motion.glovePose(attackRoot,target,math.min(age,activeEnd),g.side,a.range or d.range)
        local rest=pose*g.localCF
        local handPose=cut:Lerp(rest,Motion.swingRecovery(age))
        if age<Motion.SwingHitStart then handPose=(v.attackReturn.gloves[g.part] or rest):Lerp(handPose,Motion.entryAlpha(age))
        elseif age>activeEnd then handPose=CFrame.new(Motion.returnPosition(cut.Position,rest.Position,age))*handPose.Rotation end
        g.part.CFrame=handPose
       end
      end
     end
     if v.reserves then
      for i,copy in v.reserves do copy:PivotTo(pose*CFrame.new((i==2 and -1 or 1)*1.5,.35, .25)*CFrame.Angles(0,0,math.sin(now*3+i)*.12)) end
     end
     if id=='16' then
      local hitAge=now-(slot:GetAttribute('LastContact') or -1e6)
      if hitAge>=0 and hitAge<.3 then v.model:PivotTo(pose*CFrame.Angles(0,0,math.sin(hitAge*80)*.24*(1-hitAge/.3))) end
     end
     Chains.apply(v.chain,age)
     Cards.step(v.cards,now)
     if v.lid then v.lid.Transform=CFrame.Angles(0,-math.pi/2*ArcMotion.lid(now-start),0) end
     if v.pandora then
      local opening=now-start
      if opening>=0 and opening<.3 and v.openedAt~=start then
       v.openedAt=start;Pandora.open(visuals,pose,template:GetAttribute('BoundsSize'))
      end
      Pandora.stepIdle(v.pandora,pose,true,ArcMotion.lid(opening))
     end
     v.frame={visible=true,active=age>=0 and age<duration,age=age,start=start,kind=kind,style=style,side=side,
      attackRoot=attackRoot,rate=rate,direction=a.direction,range=a.range or d.range,
      hand=a.hand,secondAim=a.second}
     table.insert(frameList,v)
    else
     v.frame=nil;v.spacing=nil;Swing.hide(v);godlyFX.hide(v);legendaryFX.hide(v)
     if v.pandora then Pandora.stepIdle(v.pandora,v.model:GetPivot(),false,0) end
     if float then float.slots[slot:GetAttribute('Index')]=nil end
    end
    for _,part in v.parts do
     local reserve=part:FindFirstAncestor('Reserve2') and 2 or part:FindFirstAncestor('Reserve3') and 3 or 1
     local flying=v.flying and v.flying[reserve] and v.flying[reserve]>0
     local hidden=v.hide and (v.hide[part] or 0)>0
     part.LocalTransparencyModifier=visible and not flying and not hidden and 0 or 1
    end
    if v.cards then
     for _,entry in v.cards.cards do
      for _,gui in entry.model:GetDescendants() do if gui:IsA('SurfaceGui') then gui.Enabled=visible and now>=(entry.flyingUntil or 0) end end
      if now<(entry.flyingUntil or 0) then
       for _,part in entry.model:GetDescendants() do if part:IsA('BasePart') then part.LocalTransparencyModifier=1 end end
      end
     end
    end
   end
  end
  -- Weapons are solid to each other: push overlapping capsules apart after
  -- posing. A swinging melee weapon is heavier, so idle neighbours make room.
  local bodies,owners={},{}
  for _,v in frameList do
   local flying=v.flying and v.flying[1] and v.flying[1]>0
   if v.capsule and not flying then
    local pivot=v.model:GetPivot()
    table.insert(bodies,{a=pivot:PointToWorldSpace(v.capsule.a),b=pivot:PointToWorldSpace(v.capsule.b),r=v.capsule.r,
     mass=(v.frame.active and v.frame.kind=='Melee') and Spacing.AttackMass or 1})
    table.insert(owners,v)
   else v.spacing=nil end
  end
  local offsets=#bodies>1 and Spacing.solve(bodies) or {}
  for i,v in owners do
   v.spacing=Spacing.smooth(v.spacing,offsets[i] or Vector3.zero,dt)
   if v.spacing.Magnitude>1e-3 then v.model:PivotTo(v.model:GetPivot()+v.spacing) end
  end
  for _,v in frameList do local pivot=v.model:GetPivot();Swing.step(v,pivot,v.frame);godlyFX.step(v,pivot,v.frame);legendaryFX.step(v,pivot,v.frame) end
 end
 for slot,v in tracked do if not seen[slot] then v.model:Destroy();tracked[slot]=nil end end
 for state in floats do if state.Parent~=states then floats[state]=nil end end
end)
local function showShot(origin,finish,kind,id,thickness,blastRadius,contact,normal,ownerId,slotIndex,first,mobContact,shotId,projectileId,projectileSpeed,terminal)
 if id~='10' and contact and kind=='Ranged' and not mobContact then bulletImpact(finish,normal) end
 if godlyFX.shot(origin,finish,kind,id,thickness,blastRadius,contact,normal,ownerId,slotIndex,first,mobContact,shotId,projectileId,projectileSpeed,terminal) then return end
 if first and Motion.MuzzleOffsets[id] and ownerId and slotIndex then
  local state=states:FindFirstChild(tostring(ownerId))
  local slot=state and state:FindFirstChild('Slot'..slotIndex)
  local v=slot and tracked[slot]
  if v and v.id==id then
   origin=v.model:GetPivot():PointToWorldSpace(Motion.MuzzleOffsets[id])
   if shotId and id~='10' then muzzleFlash(v.model,id,Motion.MuzzleOffsets[id],shotId) end
  end
 end
 if projectileStyles.handle(origin,finish,kind,id,thickness,blastRadius,contact,normal,ownerId,slotIndex,first,mobContact,shotId,projectileId,projectileSpeed,terminal) then return end
 if id=='10' then shirtShot(origin,finish,projectileId,projectileSpeed,terminal);return end
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
end
-- Bullets (StatProjectiles) come as a 'Fly' row per straight leg, then 'Land' or 'Drop', and are
-- flown here step by step through showShot (BulletFlights).
local flights=require(combat:WaitForChild('BulletFlights')).new(showShot)
RunService.RenderStepped:Connect(function() if next(flights.bullets) then flights.step(os.clock()) end end)
local function onShot(...)
 if not flights.row(os.clock(),...) then showShot(...) end
end
combat:WaitForChild('Shot').OnClientEvent:Connect(function(origin,finish,...)
 if origin==Wire.Marker then
  for _,row in ipairs(finish) do onShot(Wire.unpack(row)) end
 else
  onShot(origin,finish,...)
 end
 flights.launched(os.clock())
end)
local function damageNumber(position,damage,color,name,mine)
 -- Settings menu (UITheme) can hide hit numbers; your own damage taken always shows.
 local taken=name=='PlayerDamageNumber'
 if not taken and player:GetAttribute('Setting_DamageNumbers')==false then return end
 hitFeedback.number(position,damage,color,taken,mine)
end
-- mine: your own hit (teammates' numbers give way first). dot: a burn, poison or zone tick, which
-- shows its number but no splat or flash.
local function onHit(position,damage,npc,impactPosition,lethal,secondary,weaponId,mine,dot)
 if typeof(position)~='Vector3' or type(damage)~='number' then return end
 if not lethal and not dot then mobImpact.hit(impactPosition or position-Vector3.yAxis*2,npc,secondary) end
 godlyFX.hit(npc,lethal,secondary,weaponId,impactPosition or position)
 damageNumber(position,damage,Color3.fromRGB(255,246,218),'DamageNumber',mine)
 if npc and npc.Parent and not dot then hitFeedback.flash(npc) end
end
-- Kills, one at a time and reliable (CombatEffectsService); they carry their owner and dot flag.
combat:WaitForChild('Hit').OnClientEvent:Connect(function(position,damage,npc,impactPosition,lethal,secondary,weaponId,ownerId,dot)
 onHit(position,damage,npc,impactPosition,lethal,secondary,weaponId,ownerId==player.UserId,dot==true)
end)
-- Every other hit, a frame's worth per message (ShotBatch.hitWriter).
task.spawn(function()
 combat:WaitForChild('HitFX').OnClientEvent:Connect(function(buf,...)
  for _,h in Wire.readHits(buf,table.pack(...)) do
   onHit(h.position+Vector3.yAxis*2,h.damage,h.npc,h.position,h.lethal,h.secondary,h.weaponId,h.mine,h.dot)
  end
 end)
end)

-- Four full-resolution gradients stay transparent in the center; no image download.
local damageGui=Instance.new('ScreenGui');damageGui.Name='DamageFeedback';damageGui.IgnoreGuiInset=true;damageGui.ResetOnSpawn=false;damageGui.DisplayOrder=45;damageGui.Parent=player:WaitForChild('PlayerGui')
local edges={};local edgeTweens={}
for i,d in {{UDim2.fromScale(0,0),UDim2.fromScale(1,.28),90},{UDim2.fromScale(0,.72),UDim2.fromScale(1,.28),270},{UDim2.fromScale(0,0),UDim2.fromScale(.22,1),0},{UDim2.fromScale(.78,0),UDim2.fromScale(.22,1),180}} do
 local edge=Instance.new('Frame');edge.Name='Edge'..i;edge.BorderSizePixel=0;edge.Position=d[1];edge.Size=d[2];edge.BackgroundColor3=Color3.fromRGB(210,12,32);edge.BackgroundTransparency=1;edge.Parent=damageGui
 local fade=Instance.new('UIGradient');fade.Rotation=d[3];fade.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.35,.4),NumberSequenceKeypoint.new(1,1)});fade.Parent=edge;edges[i]=edge
end
local shakeUntil=0;local shakeStart=0;local lastOffset=CFrame.identity;local shakenCamera
RunService:BindToRenderStep('DamageShakeRestore',Enum.RenderPriority.Camera.Value-1,function()
 if shakenCamera and shakenCamera==workspace.CurrentCamera then shakenCamera.CFrame=shakenCamera.CFrame*lastOffset:Inverse() end
 lastOffset=CFrame.identity;shakenCamera=nil
end)
RunService:BindToRenderStep('DamageShake',Enum.RenderPriority.Camera.Value+1,function()
 local now=os.clock();local camera=workspace.CurrentCamera
 if now>=shakeUntil or not camera or camera.CameraType==Enum.CameraType.Scriptable then return end
 local age=now-shakeStart;local envelope=math.clamp((shakeUntil-now)/.28,0,1)^2
 lastOffset=CFrame.new(math.sin(age*91)*.09*envelope,math.sin(age*117)*.055*envelope,0)*CFrame.Angles(0,0,math.rad(math.sin(age*83)*.45*envelope))
 camera.CFrame*=lastOffset;shakenCamera=camera
end)
local function damageFeedback()
 for i,edge in edges do
  if edgeTweens[i] then edgeTweens[i]:Cancel() end
  edge.BackgroundTransparency=.36
  edgeTweens[i]=TweenService:Create(edge,TweenInfo.new(.95,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{BackgroundTransparency=1});edgeTweens[i]:Play()
 end
 if player:GetAttribute('Setting_ScreenShake')~=false then shakeStart=os.clock();shakeUntil=shakeStart+.28 end
end
player.CharacterAdded:Connect(function() shakeUntil=0;for i,e in edges do if edgeTweens[i] then edgeTweens[i]:Cancel() end;e.BackgroundTransparency=1 end end)
combat:WaitForChild('PlayerDamaged').OnClientEvent:Connect(function(damage)
 if type(damage)~='number' or damage~=damage or damage<=0 then return end
 local character=player.Character
 local root=character and character:FindFirstChild('HumanoidRootPart')
 local humanoid=character and character:FindFirstChildOfClass('Humanoid')
 if not root or not humanoid then return end
 damageFeedback()
 damageNumber(root.Position+Vector3.new(0,2.5,0),damage,Color3.fromRGB(235,72,72),'PlayerDamageNumber')
end)

-- Detached from the destroyed NPC; the server emits this once per death.
combat:WaitForChild('ZombiePopped').OnClientEvent:Connect(function(position)
 mobImpact.death(position)
end)

-- Developers use the ADMIN panel instead (Keep N alive, Weapons, End this wave); other Studio
-- testers keep this panel and its Z/K/X keys (ADMIN_PANEL.md).
if RunService:IsStudio() and not require(combat:WaitForChild('AdminConfig')).isAdmin(player) then
 -- Studio-only test panel, drawn with the shared green theme.
 local T=require(game.ReplicatedStorage:WaitForChild('UITheme'))
 local gui=Instance.new('ScreenGui');gui.Name='RogueliteCombatTestControls';gui.ResetOnSpawn=false;gui.ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets;gui.Parent=player:WaitForChild('PlayerGui')
 local frame=T.panel(gui,'Panel',0,0,228,196,'panel');frame.AnchorPoint=Vector2.new(0,1);frame.Position=UDim2.new(0,14,1,-16)
 local plate=T.panel(frame,'TitlePlate',26,-18,176,40,'panel');T.caps(plate,30)
 local heading=T.label(plate,'Heading','COMBAT TEST',0,0,0,0,18);heading.Size=UDim2.fromScale(1,1)
 local own=states:WaitForChild(tostring(player.UserId))
 local function toggle(key)
  local value=key=='Zombies'and combat:GetAttribute('ZombiesEnabled')or own:GetAttribute('WeaponEnabled')
  if key=='Zombies'then value=combat:GetAttribute('ZombiesEnabled')end
  combat.SetTestOption:FireServer(key,not value)
 end
 local function button(key,y,hotkey)
  local b=T.button(frame,key..'Toggle','',14,y,200,42,function()toggle(key)end);b.Caption.TextSize=18
  local function refresh()local enabled;if key=='Zombies'then enabled=combat:GetAttribute('ZombiesEnabled')else enabled=own:GetAttribute('WeaponEnabled')end;b.Caption.Text=key..': '..(enabled and 'ON' or 'OFF')..'  ['..hotkey..']';T.setPrimary(b,enabled==true)end
  if key=='Zombies'then combat:GetAttributeChangedSignal('ZombiesEnabled'):Connect(refresh)else own:GetAttributeChangedSignal('WeaponEnabled'):Connect(refresh)end;refresh()
 end
 button('Zombies',34,'Z');button('Weapons',84,'K')
 local run=game.ReplicatedStorage:WaitForChild('RogueliteRunState')
 local function stopWave() if run:GetAttribute('Phase')=='Combat' then combat.SetTestOption:FireServer('StopWave',true) end end
 local stop=T.button(frame,'StopWave','',14,134,200,42,stopWave,true);stop.Caption.TextSize=18
 local function refreshStop()
  local active=run:GetAttribute('Phase')=='Combat'
  stop.Interactable=active
  stop.Caption.Text=active and 'Stop wave  [X]' or 'No wave running'
  stop.Caption.TextColor3=active and T.Color.negative or T.Color.white
 end
 run:GetAttributeChangedSignal('Phase'):Connect(refreshStop);refreshStop()
 Input.InputBegan:Connect(function(input,processed)if processed or Input:GetFocusedTextBox()then return end;if input.KeyCode==Enum.KeyCode.Z then toggle('Zombies')elseif input.KeyCode==Enum.KeyCode.K then toggle('Weapons')elseif input.KeyCode==Enum.KeyCode.X then stopWave()end end)
end
