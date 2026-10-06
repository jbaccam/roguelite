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
    v={model=model,id=id,parts={},reserveIndex={},chain=Chains.bind(model,id),cards=Cards.bind(model,id)};tracked[slot]=v
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
     v.reserveIndex[part]=part:FindFirstAncestor('Reserve2') and 2 or part:FindFirstAncestor('Reserve3') and 3 or 1
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
     local reserve=v.reserveIndex[part]
     local flying=v.flying and v.flying[reserve] and v.flying[reserve]>0
     local hidden=v.hide and (v.hide[part] or 0)>0
     part.LocalTransparencyModifier=visible and not flying and not hidden and 0 or 1
    end
    if v.cards then
     for _,entry in v.cards.cards do
      for _,gui in entry.guis do gui.Enabled=visible and now>=(entry.flyingUntil or 0) end
      if now<(entry.flyingUntil or 0) then
       for _,part in entry.parts do part.LocalTransparencyModifier=1 end
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
   -- The moving client muzzle is only a flash anchor. Replacing the first segment's
   -- server origin creates an elbow where it meets the rest of the straight flight.
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
-- shows its number and white flash without an extra splat.
local function onHit(position,damage,npc,impactPosition,lethal,secondary,weaponId,mine,dot)
 if typeof(position)~='Vector3' or type(damage)~='number' then return end
 if not lethal and not dot then mobImpact.hit(impactPosition or position-Vector3.yAxis*2,npc,secondary) end
 godlyFX.hit(npc,lethal,secondary,weaponId,impactPosition or position)
 damageNumber(position,damage,Color3.fromRGB(255,246,218),'DamageNumber',mine)
 if npc and npc.Parent then hitFeedback.flash(npc) end
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

-- Where this body is on this screen, 30 times a second while in a run (CharacterService.seen):
-- the server sees a body about 0.2 s late, so enemy hits are judged on this instead (2026-10-03).
task.spawn(function()
 local view=combat:WaitForChild('PlayerView',30);if not view then return end
 local me=Players.LocalPlayer;local since=0
 RunService.Heartbeat:Connect(function(dt)
  since+=dt;if since<1/30 then return end;since=0
  local root=me.Character and me.Character:FindFirstChild('HumanoidRootPart')
  if root and me:GetAttribute('RunMember') then view:FireServer(root.Position) end
 end)
end)

-- Air speed (2026-10-03, "jumping should be like the optimal way to move around"): this body runs at
-- the server's GroundSpeed and switches to its AirSpeed the frame it leaves the ground (CharacterService;
-- both 0 while held). A server WalkSpeed write that lands mid-jump is put back to the air speed.
local function airSpeed(character)
 local h=character:WaitForChild('Humanoid',15);if not h then return end
 local function apply()
  local ground=character:GetAttribute('GroundSpeed');if type(ground)~='number' then return end
  local state=h:GetState()
  local flying=state==Enum.HumanoidStateType.Jumping or state==Enum.HumanoidStateType.Freefall
  local want=flying and character:GetAttribute('AirSpeed') or ground
  if type(want)=='number' and math.abs(h.WalkSpeed-want)>.01 then h.WalkSpeed=want end
 end
 h.StateChanged:Connect(apply)
 h:GetPropertyChangedSignal('WalkSpeed'):Connect(apply)
 character:GetAttributeChangedSignal('GroundSpeed'):Connect(apply)
 character:GetAttributeChangedSignal('AirSpeed'):Connect(apply)
 apply()
end
player.CharacterAdded:Connect(airSpeed)
if player.Character then task.spawn(airSpeed,player.Character) end

-- Melee dash (2026-10-03; reworked 2026-10-04, user: "like a Jett dash in Valorant: smooth af and
-- clean, an actual dash, not a speed boost"). Brawlers and any class whose starting weapon is melee
-- (CharacterStats.dashes) dash the way they're moving, else where the camera looks, on the ground or
-- in the air: Q, gamepad X or the DASH button. A burst, not a sprint (CharacterStats.Dash): 280
-- studs/s at once, easing out to the run speed over 0.3 s, about 26 studs (21 in the first 0.14 s),
-- cut short by a wall; an air dash holds level through the burst. This body moves itself (its client
-- owns its physics) and tells the server (RunAction 'Dash'), which checks the class, the cooldown and
-- that the wave is on, then stamps DashAt for MovementGuard and the other screens. Every screen draws
-- the pose (lean in, arms swept back, legs tucked), afterimages, streaks, a wind ring and end wisps;
-- the dasher also gets speed lines and an FOV punch. Ready again 3 s later. No damage, no invulnerability.
task.spawn(function()
 local RS=game:GetService('ReplicatedStorage')
 local Stats=require(combat:WaitForChild('CharacterStats'));local D=Stats.Dash
 local runAction=combat:WaitForChild('RunAction',60)
 if not D or not D.Peak or not runAction then return end
 local T=require(RS:WaitForChild('UITheme'))
 local K=require(combat:WaitForChild('VfxKit'))
 local readyAt=0 -- os.clock() when this player's dash is ready again
 local WHITE,LIME,MINT=Color3.fromRGB(248,249,245),Color3.fromRGB(145,239,20),Color3.fromRGB(210,255,161)
 -- Burst speed t s in, for a run speed: Peak, easing out ((1-u)^Ease) to the run speed by Seconds.
 -- Example (run 24): 280 at once, 132 at 0.06 s, 56 at 0.15 s, 24 at 0.3 s.
 local function speedAt(t,run) local u=math.clamp(t/D.Seconds,0,1);return run+(D.Peak-run)*(1-u)^D.Ease end

 -- The pose, layered on the Animator's frame (Motor6D.Transform, every frame before physics; the
 -- R15 rig AvatarNormalizer gives everyone): radians at full weight. f/r: the dash direction's
 -- forward / right share in the body's own frame, so a side dash leans sideways.
 local JOINTS={Root='LowerTorso',Waist='UpperTorso',Neck='Head',RightShoulder='RightUpperArm',LeftShoulder='LeftUpperArm',
  RightElbow='RightLowerArm',LeftElbow='LeftLowerArm',RightHip='RightUpperLeg',LeftHip='LeftUpperLeg',RightKnee='RightLowerLeg',LeftKnee='LeftLowerLeg'}
 local function offset(name,w,f,r)
  if name=='Root' then return CFrame.Angles(-.42*f*w,0,-.32*r*w) -- the whole body leans into it (24 degrees)
  elseif name=='Waist' then return CFrame.Angles(-.22*f*w,0,-.16*r*w)
  elseif name=='Neck' then return CFrame.Angles(.4*f*w,0,.28*r*w) -- the head stays up, eyes ahead
  elseif name=='RightShoulder' then return CFrame.Angles(-1.05*w,0,.3*w) -- arms swept back and out
  elseif name=='LeftShoulder' then return CFrame.Angles(-1.05*w,0,-.3*w)
  elseif name=='RightElbow' or name=='LeftElbow' then return CFrame.Angles(.35*w,0,0)
  elseif name=='RightHip' then return CFrame.Angles(.62*w,0,0) -- legs tucked under, one more than the other
  elseif name=='LeftHip' then return CFrame.Angles(.36*w,0,0)
  elseif name=='RightKnee' then return CFrame.Angles(-.95*w,0,0)
  else return CFrame.Angles(-.6*w,0,0) end
 end
 -- In over 0.04 s, held through the burst, eased back out over 0.12 s (gone by 0.29 s).
 local function weight(t)
  if t<.04 then return 1-(1-t/.04)^2 end
  if t<.17 then return 1 end
  return 1-K.smooth((t-.17)/.12)
 end
 local function jointsOf(character)
  local list={}
  for name,partName in JOINTS do
   local part=character:FindFirstChild(partName);local j=part and part:FindFirstChild(name)
   if j and j:IsA('Motor6D') then list[name]=j end
  end
  return list
 end
 -- A joint the Animator didn't write this frame still holds last frame's pose: start from the base
 -- under it, so the lean never stacks up.
 local function pose(e,w)
  local l=e.root.CFrame:VectorToObjectSpace(e.dir);local f,r=-l.Z,l.X
  for name,j in e.joints do
   if j.Parent then
    local base=j.Transform
    if e.written[j]==base then base=e.bases[j] end
    local cf=base*offset(name,w,f,r)
    j.Transform=cf;e.written[j]=cf;e.bases[j]=base
   end
  end
 end
 local function unpose(e) for _,j in e.joints do if e.written[j]==j.Transform then j.Transform=e.bases[j] end end end

 -- Streaks: a wide camera-facing ribbon on the root and a thin one on each hand, built once per body
 -- and lit only while dashing (cleared first, so one never stretches from the last dash).
 local rigs=setmetatable({},{__mode='k'}) -- character -> its streak Trails
 local function ribbon(part,half,life,alpha)
  local a0=Instance.new('Attachment');a0.Name='DashStreakA';a0.Position=Vector3.new(0,half,0);a0.Parent=part
  local a1=Instance.new('Attachment');a1.Name='DashStreakB';a1.Position=Vector3.new(0,-half,0);a1.Parent=part
  local t=Instance.new('Trail');t.Name='DashStreak';t.Attachment0=a0;t.Attachment1=a1;t.FaceCamera=true;t.Enabled=false
  t.Lifetime=life;t.MinLength=.05;t.LightEmission=.7;t.LightInfluence=0;t.Color=ColorSequence.new(WHITE,LIME)
  t.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,alpha),NumberSequenceKeypoint.new(.5,.7),NumberSequenceKeypoint.new(1,1)})
  t.WidthScale=NumberSequence.new(1,.1);t.Parent=part
  return t
 end
 local function setTrails(character,on)
  local list=rigs[character]
  if not list then
   if not on then return end
   list={}
   local root=character:FindFirstChild('HumanoidRootPart');if root then table.insert(list,ribbon(root,1.25,.2,.3)) end
   for _,name in {'RightHand','LeftHand'} do local p=character:FindFirstChild(name);if p then table.insert(list,ribbon(p,.1,.16,.05)) end end
   rigs[character]=list
  end
  for _,t in list do if t.Parent then if on then pcall(t.Clear,t) end;t.Enabled=on end end
 end

 -- Afterimages: Neon copies of the body (blocks, the head a ball), pooled: at most 9 (three dashes'
 -- worth, the oldest reused) x 11 parts. Three a dash at 0.02 / 0.07 / 0.12 s (white, lime, mint),
 -- each fading from 0.4 to clear over 0.26 s.
 local GHOST_PARTS={'Head','UpperTorso','LowerTorso','RightUpperArm','RightLowerArm','LeftUpperArm','LeftLowerArm','RightUpperLeg','RightLowerLeg','LeftUpperLeg','LeftLowerLeg'}
 local GHOST_AT,GHOST_COLOR={.02,.07,.12},{WHITE,LIME,MINT}
 local ghosts,ghostNext={},0
 local function ghost(character,color)
  ghostNext=ghostNext%9+1
  local g=ghosts[ghostNext]
  if not g then
   g={parts={}};ghosts[ghostNext]=g
   for i,name in GHOST_PARTS do g.parts[i]=K.part(visuals,'DashGhost',Vector3.one,WHITE,1,Enum.Material.Neon,name=='Head' and Enum.PartType.Ball or nil) end
  end
  g.born=os.clock()
  for i,name in GHOST_PARTS do
   local src=character:FindFirstChild(name);local p=g.parts[i]
   if src and src:IsA('BasePart') then
    local size=src.Size*.96;if name=='Head' then size=Vector3.one*math.min(size.X,size.Y,size.Z) end
    p.Size=size;p.CFrame=src.CFrame;p.Color=color;p.Transparency=.4
   else p.Transparency=1 end
  end
 end

 -- The start: a flat wind ring on the ground (upright, facing the dash, in the air) and five flat
 -- slivers of wind kicked back along the ground, fading over 0.26 s.
 local function kick(at,dir)
  local list={}
  for i=1,5 do
   local back=CFrame.fromAxisAngle(Vector3.yAxis,(i-3)*.32+(math.random()-.5)*.15):VectorToWorldSpace(-dir)
   list[i]={part=K.part(visuals,'DashWind',Vector3.new(.14,.05,2),i%2==0 and LIME or WHITE,1,Enum.Material.Neon),dir=back,len=1.8+math.random()*1.4}
  end
  K.animate(.26,function(t)
   local e=1-(1-t)^3
   for _,s in list do
    local from=at+s.dir*(1+4.5*e)
    s.part.Size=Vector3.new(.14*(1-t*.5),.05,s.len*(1-.4*t));s.part.CFrame=CFrame.lookAt(from,from+s.dir)
    s.part.Transparency=.15+.85*K.smooth(t)
   end
  end,function() for _,s in list do s.part:Destroy() end end,'dashWind',12)
 end
 local function burst(character,root,dir)
  local p=root.Position
  local ground=K.groundBelow(p,{character,visuals,workspace:FindFirstChild('RogueliteEnemies')},nil)
  if ground and p.Y-ground<5.5 then
   local at=Vector3.new(p.X,ground+.12,p.Z)
   K.ring(visuals,CFrame.new(at),{radius0=1,radius1=5,width=.6,duration=.3,segments=14,color=WHITE,rim=LIME,bodyAlpha=.3,hold=.02})
   kick(at,dir)
  else
   K.ring(visuals,CFrame.fromMatrix(p-dir*.5,dir:Cross(Vector3.yAxis).Unit,dir),{radius0=.8,radius1=3.6,width=.45,duration=.28,segments=14,color=WHITE,rim=LIME,bodyAlpha=.3,hold=.02})
  end
 end
 -- The end: three thin wind wisps curling open around where the dash lands.
 local function wisps(at,dir)
  local yaw=math.atan2(-dir.X,-dir.Z)
  for i=1,3 do
   local frame=CFrame.new(at+Vector3.new(0,-.8+i*.55,0))*CFrame.Angles(0,yaw+(i-2)*.7,0)*CFrame.Angles((i-2)*.5,0,(math.random()-.5)*.6)
   local from=math.pi*(.6+math.random()*.8)
   K.ring(visuals,frame,{from=from,to=from+2.3,radius0=.5,radius1=1.8+i*.3,width=.16,duration=.4,reveal=.1,segments=7,color=i==2 and LIME or WHITE,bodyAlpha=.2})
  end
 end

 -- Dashes being drawn, any player's: character -> {root, start, dir, own, near, joints, ghosts, wisped}.
 -- Effects only within 180 studs of the camera; the pose always.
 local active={}
 local function begin(character,root,dir,own)
  local old=active[character];if old then unpose(old) end
  local e={root=root,start=os.clock(),dir=dir,own=own,near=own or K.near(root.Position,180),joints=jointsOf(character),bases={},written={},ghosts=0,wisped=false}
  active[character]=e
  if e.near then setTrails(character,true);burst(character,root,dir) end
 end
 -- A teammate's approved dash (their sound: RogueliteSounds): the way their body is going, else facing.
 local function watch(p)
  if p==player then return end
  p:GetAttributeChangedSignal('DashAt'):Connect(function()
   local character=p.Character;local root=character and character:FindFirstChild('HumanoidRootPart');if not root then return end
   local v=root.AssemblyLinearVelocity;local dir=Vector3.new(v.X,0,v.Z)
   if dir.Magnitude<30 then local look=root.CFrame.LookVector;dir=Vector3.new(look.X,0,look.Z) end
   if dir.Magnitude>.1 then begin(character,root,dir.Unit,false) end
  end)
 end
 for _,p in Players:GetPlayers() do watch(p) end
 Players.PlayerAdded:Connect(watch)

 -- Your own dash only: speed lines streaking in from the screen edge (a 2D flash, 0.24 s; 3 px lines
 -- the tutorial guide ignores) and an FOV punch of +7 that always returns to UITheme's constant
 -- through its camera helpers (never set directly), skipped while a camera stage holds the camera
 -- and with Screen shake off.
 local lines=Instance.new('ScreenGui');lines.Name='RogueliteDashLines';lines.IgnoreGuiInset=true;lines.ResetOnSpawn=false;lines.DisplayOrder=18;lines.Enabled=false
 lines.Parent=player:WaitForChild('PlayerGui')
 local speedLines={}
 for i=1,14 do
  local a=(i-.5)/14*math.pi*2+(i%3)*.09
  speedLines[i]={angle=a,len=90+(i*53)%110,frame=T.make('Frame',lines,{Name='SpeedLine',AnchorPoint=Vector2.new(.5,.5),BorderSizePixel=0,BackgroundColor3=WHITE,BackgroundTransparency=1,Rotation=math.deg(a)})}
 end
 local linesAt
 local function punch()
  if not T.cameraFov or not T.CAMERA_FOV or player:GetAttribute('Setting_ScreenShake')==false then return end
  T.cameraFov(T.CAMERA_FOV+7,TweenInfo.new(.07,Enum.EasingStyle.Quad,Enum.EasingDirection.Out))
  task.delay(.08,function() T.cameraFov(T.CAMERA_FOV,TweenInfo.new(.3,Enum.EasingStyle.Quad,Enum.EasingDirection.InOut)) end)
  -- If the camera was busy for the way back, put it back once it's free (never left wide).
  task.delay(.7,function()
   local c=workspace.CurrentCamera
   if c and c.FieldOfView>T.CAMERA_FOV+.5 and T.cameraOwner()==nil and c.CameraType==Enum.CameraType.Custom then
    T.cameraFov(T.CAMERA_FOV,TweenInfo.new(.2))
   end
  end)
 end

 -- This player's dash in progress: a pooled world-plane LinearVelocity on the root, set every frame
 -- before physics (a velocity set once would lose to the Humanoid's own walking).
 local drive
 local cast=RaycastParams.new();cast.FilterType=Enum.RaycastFilterType.Exclude;cast.RespectCanCollide=true
 pcall(function() cast.CollisionGroup='RoguelitePlayers' end) -- mobs and teammates never stop a dash (MobCollision)
 -- Hand back the run speed along the dash: a tiny carry, no slide, no dead stop; into a wall, none.
 local function finish(d,wall)
  drive=nil;d.push.Enabled=false
  local root,h=d.root,d.h
  if not root.Parent or h.Health<=0 then return end
  local flat=d.dir*h.WalkSpeed
  if wall and wall.Magnitude>.01 then wall=wall.Unit;flat-=wall*math.min(0,flat:Dot(wall)) end
  local v=root.AssemblyLinearVelocity;root.AssemblyLinearVelocity=Vector3.new(flat.X,v.Y,flat.Z)
 end
 local function stepDrive(dt)
  local d=drive;if not d then return end
  local root,h=d.root,d.h
  if not root.Parent or h.Health<=0 or player.Character~=d.character then drive=nil;d.push.Enabled=false;return end
  local t=os.clock()-d.start
  if t>=D.Seconds then finish(d);return end
  local speed=speedAt(t,math.max(h.WalkSpeed,0))
  -- A wall ahead (steeper than 50 degrees, within this frame's travel and a body's reach) ends it here.
  local ok,hit=pcall(workspace.Spherecast,workspace,root.Position,1,d.dir*(speed*math.max(dt,1/60)+1.4),cast)
  if ok and hit and hit.Normal.Y<.65 then finish(d,Vector3.new(hit.Normal.X,0,hit.Normal.Z));return end
  if d.air and t<D.Seconds*.55 then
   -- In the air: level through the burst (no hop, no drop), then gravity takes over again.
   d.push.VelocityConstraintMode=Enum.VelocityConstraintMode.Vector;d.push.VectorVelocity=d.dir*speed
  else
   d.push.VelocityConstraintMode=Enum.VelocityConstraintMode.Plane;d.push.PlaneVelocity=Vector2.new(d.dir.X,d.dir.Z)*speed
  end
 end
 RunService.PreSimulation:Connect(function(dt)
  stepDrive(dt)
  local now=os.clock()
  for character,e in active do
   local t=now-e.start
   if not e.root.Parent or t>=.3 then unpose(e);active[character]=nil
   else pose(e,weight(t)) end
  end
 end)
 RunService.RenderStepped:Connect(function()
  local now=os.clock()
  for character,e in active do
   local t=now-e.start
   -- A teammate's direction follows their body while it's really dashing.
   if not e.own then local v=e.root.AssemblyLinearVelocity;local flat=Vector3.new(v.X,0,v.Z);if flat.Magnitude>40 then e.dir=flat.Unit end end
   if e.near then
    while e.ghosts<3 and t>=GHOST_AT[e.ghosts+1] do e.ghosts+=1;ghost(character,GHOST_COLOR[e.ghosts]) end
    if not e.wisped and t>=.2 then e.wisped=true;setTrails(character,false);wisps(e.root.Position,e.dir) end
   end
  end
  for _,g in ghosts do
   if g.born then
    local t=(now-g.born)/.26
    if t>=1 then g.born=nil;for _,p in g.parts do p.Transparency=1 end
    else local a=.4+.6*K.smooth(t);for _,p in g.parts do if p.Transparency<1 then p.Transparency=a end end end
   end
  end
  if linesAt then
   local t=(now-linesAt)/.24
   if t>=1 then linesAt=nil;lines.Enabled=false
   else
    local e=1-(1-t)^2
    for _,s in speedLines do
     s.frame.Position=UDim2.fromScale(.5+math.cos(s.angle)*(.56-.1*e),.5+math.sin(s.angle)*(.54-.1*e))
     s.frame.Size=UDim2.fromOffset(s.len*(1-.35*e),3);s.frame.BackgroundTransparency=.15+.85*K.smooth(t)
    end
   end
  end
 end)
 -- The button shows: a run member mid-wave (or in the sandbox), standing, whose class or starter dashes.
 local function allowed()
  if player:GetAttribute('RunMember')~=true or player:GetAttribute('RunDown') or player:GetAttribute('RunResult')~=nil or player:GetAttribute('LobbyPreviewActive')==true then return false end
  local run=RS:FindFirstChild('RogueliteRunState');local phase=run and run:GetAttribute('Phase')
  if phase~='Combat' and phase~='Practice' then return false end
  local own=states:FindFirstChild(tostring(player.UserId))
  return Stats.dashes(own and own:GetAttribute('Class') or player:GetAttribute('RunClass'))
 end
 -- Usable this moment: alive, not held (a pause or a boss entrance: GroundSpeed 0), not on the pause screen.
 local function body()
  local character=player.Character;local h=character and character:FindFirstChildOfClass('Humanoid')
  local root=character and character:FindFirstChild('HumanoidRootPart')
  if not h or not root or h.Health<=0 or player:GetAttribute('Paused') then return nil end
  if (character:GetAttribute('GroundSpeed') or 1)<=0 or combat:GetAttribute('RunPaused')==true then return nil end
  if (combat:GetAttribute('CinematicUntil') or 0)>workspace:GetServerTimeNow() then return nil end
  local state=h:GetState()
  if state==Enum.HumanoidStateType.Seated or state==Enum.HumanoidStateType.PlatformStanding or state==Enum.HumanoidStateType.Dead then return nil end
  return h,root
 end
 local function dash()
  if drive or os.clock()<readyAt or not allowed() then return end
  local h,root=body();if not root then return end
  local character=root.Parent
  local attachment=root:FindFirstChild('RootAttachment') or root:FindFirstChildWhichIsA('Attachment');if not attachment then return end
  -- The way you're moving, else where the camera looks (third person and shift-lock alike).
  local move=h.MoveDirection;local dir=Vector3.new(move.X,0,move.Z)
  local camera=workspace.CurrentCamera
  if dir.Magnitude<.1 and camera then local look=camera.CFrame.LookVector;dir=Vector3.new(look.X,0,look.Z) end
  if dir.Magnitude<.1 then local look=root.CFrame.LookVector;dir=Vector3.new(look.X,0,look.Z) end
  if dir.Magnitude<.1 then return end
  dir=dir.Unit;readyAt=os.clock()+D.Cooldown
  local push=root:FindFirstChild('RogueliteDash')
  if not push then
   push=Instance.new('LinearVelocity');push.Name='RogueliteDash';push.Attachment0=attachment;push.Enabled=false
   push.RelativeTo=Enum.ActuatorRelativeTo.World;push.PrimaryTangentAxis=Vector3.xAxis;push.SecondaryTangentAxis=Vector3.zAxis
   push.MaxForce=math.huge;push.Parent=root
  end
  cast.FilterDescendantsInstances={character,visuals,workspace:FindFirstChild('RogueliteEnemies')}
  drive={character=character,root=root,h=h,push=push,dir=dir,start=os.clock(),air=h.FloorMaterial==Enum.Material.Air}
  stepDrive(0)
  if drive then push.Enabled=true end
  begin(character,root,dir,true)
  T.sound('dash');punch();linesAt=os.clock();lines.Enabled=true
  runAction:FireServer('Dash')
 end
 Input.InputBegan:Connect(function(input,processed)
  if processed or Input:GetFocusedTextBox() then return end
  if input.KeyCode==Enum.KeyCode.Q or input.KeyCode==Enum.KeyCode.ButtonX then dash() end
 end)
 -- The DASH button: the Movement Speed wing (its level-up card art) on a lime face; charcoal with a
 -- dark sweep draining down and the seconds left while it recharges; greyed while held. Bottom
 -- right with its key (Q, or the pad's X) on keyboard and gamepad screens; beside the jump button
 -- on touch screens. Below the HUD (DisplayOrder 19), so menus and the shop cover it.
 local gui=Instance.new('ScreenGui');gui.Name='RogueliteDash';gui.ResetOnSpawn=false;gui.DisplayOrder=19;gui.Enabled=false
 gui.ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets;gui.ZIndexBehavior=Enum.ZIndexBehavior.Sibling
 gui.Parent=player:WaitForChild('PlayerGui')
 local area=T.frame(gui,'SafeArea',0,0,0,0);area.Size=UDim2.fromScale(1,1)
 local SIZE=76
 local b=T.button(area,'DashButton','DASH',0,0,SIZE,SIZE,nil,false)
 b.AnchorPoint=Vector2.new(.5,.5);b.Selectable=false;b:SetAttribute('NoClickSound',true) -- the whoosh is its sound
 local scale=T.make('UIScale',b,{Scale=1})
 local caption=b.Caption;caption.Position=UDim2.new(0,4,1,-27);caption.Size=UDim2.new(1,-8,0,22);caption.TextSize=18;caption.ZIndex=2
 T.icon(b,'Icon',16,4,44,'rbxassetid://117216104224040').ZIndex=2 -- LevelUpCatalog's MoveSpeed wing
 local sweep=T.make('Frame',b,{Name='Cooldown',AnchorPoint=Vector2.new(0,1),Position=UDim2.new(0,5,1,-5),Size=UDim2.new(1,-10,0,0),BackgroundColor3=T.Color.shade,BackgroundTransparency=.3,BorderSizePixel=0,ZIndex=3,Visible=false})
 T.make('UICorner',sweep,{CornerRadius=UDim.new(0,8)})
 local seconds=T.label(b,'Seconds','',0,0,0,0,30);seconds.Size=UDim2.fromScale(1,1);seconds.ZIndex=4;seconds.Visible=false
 local key=T.make('Frame',b,{Name='Key',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.new(1,-6,0,6),Size=UDim2.fromOffset(28,28),BackgroundColor3=T.Color.well,BorderSizePixel=0,ZIndex=5})
 T.make('UICorner',key,{CornerRadius=UDim.new(0,7)});T.make('UIStroke',key,{Color=Color3.fromRGB(8,10,11),Thickness=2})
 local keyText=T.label(key,'Text','Q',0,0,0,0,17);keyText.Size=UDim2.fromScale(1,1)
 local keyPad=T.make('ImageLabel',key,{Name='Pad',BackgroundTransparency=1,Position=UDim2.fromOffset(2,2),Size=UDim2.new(1,-4,1,-4),ScaleType=Enum.ScaleType.Fit,Image='',Visible=false})
 -- A finger or a click dashes on the press itself, not the release.
 b.InputBegan:Connect(function(input)
  if input.UserInputType==Enum.UserInputType.Touch or input.UserInputType==Enum.UserInputType.MouseButton1 then dash() end
 end)
 -- Input in use: the HUD's rule (RogueliteUI touchPlay), Roblox's preferred input where it has one.
 local function prefers(kind,fallback)
  local ok,yes=pcall(function() return Input.PreferredInput==Enum.PreferredInput[kind] end)
  if ok then return yes end
  return fallback()
 end
 local function touchPlay()
  return prefers('Touch',function()
   local last=Input:GetLastInputType()
   if last==Enum.UserInputType.Touch then return true end
   return (last==Enum.UserInputType.None or last==Enum.UserInputType.Focus) and Input.TouchEnabled and not Input.KeyboardEnabled
  end)
 end
 local function padPlay() return prefers('Gamepad',function() return Input:GetLastInputType().Name:find('Gamepad')~=nil end) end
 local function rectOf(o) local p=o.AbsolutePosition-area.AbsolutePosition;return {p.X,p.Y,p.X+o.AbsoluteSize.X,p.Y+o.AbsoluteSize.Y} end
 -- Where it sits, in safe-area pixels. Touch: left of the jump button and a little higher, sized to
 -- it (a 70 px phone jump button gets a 56 px dash, a 120 px tablet one 92). Otherwise the bottom
 -- right corner at the HUD launchers' scale (.7-1.1). Then clear of the HUD's menu column and boss
 -- bar: left of what sits on the right edge, above anything else.
 local function layout()
  local w,h=area.AbsoluteSize.X,area.AbsoluteSize.Y;if w<2 or h<2 then return end
  local touch=touchPlay();local s,c
  if touch then
   local small=math.min(w,h)<=500
   local jump=small and {w-95,h-90,w-25,h-20} or {w-170,h-210,w-50,h-90}
   local touchGui=player.PlayerGui:FindFirstChild('TouchGui');local frame=touchGui and touchGui:FindFirstChild('TouchControlFrame')
   local button=frame and frame:FindFirstChild('JumpButton')
   if button and button:IsA('GuiObject') and button.Visible and button.AbsoluteSize.X>0 then jump=rectOf(button) end
   local J=jump[3]-jump[1];s=math.clamp(J*.8,52,96)/SIZE
   c=Vector2.new(jump[1]-10-SIZE*s/2,(jump[2]+jump[4])/2-J*.35)
  else
   s=math.clamp(math.min(w/1100,h/620)*T.setting('HudScale'),.7,1.1)
   c=Vector2.new(w-16-SIZE*s/2,h-16-SIZE*s/2)
  end
  local half=SIZE*s/2+8;local list={}
  local hud=player.PlayerGui:FindFirstChild('RogueliteHUD');local base=hud and hud:FindFirstChild('SafeArea');base=base and base:FindFirstChild('HUD')
  for _,name in {'Menu','BossHealth'} do
   local o=base and base:FindFirstChild(name)
   if o and o.Visible and o.AbsoluteSize.X>0 then table.insert(list,rectOf(o)) end
  end
  for _=1,3 do
   local hit
   for _,r in list do if c.X+half>r[1] and c.X-half<r[3] and c.Y+half>r[2] and c.Y-half<r[4] then hit=r;break end end
   if not hit then break end
   c=hit[3]>=w-40 and Vector2.new(hit[1]-half,c.Y) or Vector2.new(c.X,hit[2]-half)
  end
  scale.Scale=s;b.Position=UDim2.fromOffset(c.X,c.Y)
  local pad=not touch and padPlay()
  key.Visible=not touch;keyText.Visible=not pad;keyPad.Visible=pad
  if pad and keyPad.Image=='' then local ok,img=pcall(function() return Input:GetImageForKeyCode(Enum.KeyCode.ButtonX) end);keyPad.Image=ok and img or '' end
 end
 area:GetPropertyChangedSignal('AbsoluteSize'):Connect(layout)
 Input.LastInputTypeChanged:Connect(function() if gui.Enabled then layout() end end)
 player:GetAttributeChangedSignal('Setting_HudScale'):Connect(layout)
 -- Shown or hidden, ready or not, five times a second (the layout follows the HUD once a second);
 -- the sweep every frame while it recharges.
 local since,ticks=1,0
 RunService.RenderStepped:Connect(function(dt)
  since+=dt
  if since>=.2 then
   since=0;ticks+=1
   local on=allowed()
   if gui.Enabled~=on then gui.Enabled=on;if on then layout() end
   elseif on and ticks%5==0 then layout() end
   if on then local ok=body()~=nil;if b.Interactable~=ok then b.Interactable=ok end end
  end
  if not gui.Enabled then return end
  local left=readyAt-os.clock();local cooling=left>0
  if b:GetAttribute('Neutral')~=cooling then T.setPrimary(b,not cooling) end
  sweep.Visible=cooling;seconds.Visible=cooling
  if cooling then
   local f=math.clamp(left/D.Cooldown,0,1)
   sweep.Size=UDim2.new(1,-10,f,-10*f);seconds.Text=tostring(math.ceil(left))
  end
 end)
end)
