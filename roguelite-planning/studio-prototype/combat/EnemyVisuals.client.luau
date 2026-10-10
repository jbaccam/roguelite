-- Local presentation of server enemy shots, their aim lines and spawn warnings; never decides a hit.
-- Shots: EnemyAttacks flies and hit-tests each one and sends a Launch (and an End when it stops
-- early). This draws it by server time, so a late Launch still shows the shot where it is now.
-- Spawn warnings: RogueliteZombieChase places static red crosses; this pulses them.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local TweenService=game:GetService('TweenService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Visuals=require(combat:WaitForChild('EnemyProjectileVisuals'))
local folder=Instance.new('Folder');folder.Name='LocalEnemyShots';folder.Parent=workspace
local CULL=400 -- no model for a shot this far from the camera (the radius ShotBatch sends arena events to)
local shots={}
local held=nil -- server time shots in flight stopped at while the run is paused (plan L)
local function remove(id)
 local s=shots[id];if s then shots[id]=nil;if s.model then s.model:Destroy() end end
end
-- 2026-10-10, user: "enemy projectiles like skeletons with bows and crabs with rocks should have a
-- red beam or projectile line showing where theyre gonna throw or shoot". Aim lines: EnemyAttacks
-- locks each shot at the start of the draw and sends ('Aim',id,kind,origin,velocity,startedAt,
-- releaseAt,lifetime,aimDistance,npc); this draws that exact path as a thin red Beam until release
-- (or the Launch/End/'Unaim' of the same id, or the shooter dying). Beams are pooled; only the
-- nearest V.AIM_CAP are drawn.
local aims={}
local pool={} -- idle {a0,a1,beam}
local function takeBeam()
 local b=table.remove(pool)
 if b then b.beam.Enabled=true;return b end
 local a0,a1=Instance.new('Attachment'),Instance.new('Attachment')
 a0.Name,a1.Name='EnemyAimStart','EnemyAimEnd';a0.Parent,a1.Parent=workspace.Terrain,workspace.Terrain
 local beam=Instance.new('Beam');beam.Name='EnemyAim';beam.Attachment0,beam.Attachment1=a0,a1
 beam.Color=ColorSequence.new(Visuals.AIM_COLOR);beam.LightEmission=1;beam.LightInfluence=0
 beam.FaceCamera=true;beam.Segments=1;beam.TextureLength=1;beam.Parent=folder
 return {a0=a0,a1=a1,beam=beam}
end
local function dropBeam(a) if a.b then a.b.beam.Enabled=false;table.insert(pool,a.b);a.b=nil end end
local function unaim(id) local a=aims[id];if a then aims[id]=nil;dropBeam(a) end end
-- Where it would hit the map, so it doesn't fly into a wall while the End is on its way. Only
-- collidable parts count: the server stops at those too (plus a few non-collidable ones, which the
-- End covers), and the client's own cosmetic parts never cut a shot short.
local function wallTime(origin,velocity,lifetime)
 local exclude={folder}
 local enemies=workspace:FindFirstChild('RogueliteEnemies');if enemies then table.insert(exclude,enemies) end
 for _,p in Players:GetPlayers() do if p.Character then table.insert(exclude,p.Character) end end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude
 params.FilterDescendantsInstances=exclude;params.RespectCanCollide=true
 local hit=workspace:Raycast(origin,velocity*lifetime,params)
 return hit and (hit.Position-origin).Magnitude/velocity.Magnitude or lifetime
end
-- ('Launch',id,kind,origin,velocity,started,lifetime), ('End',id), ('Hold',at), ('Resume',frozenSeconds),
-- ('Aim',id,kind,origin,velocity,startedAt,releaseAt,lifetime,aimDistance,npc), ('Unaim',id).
local function onShot(action,a,kind,origin,velocity,started,lifetime,...)
 if action=='Launch' then
  unaim(a)
  if typeof(origin)~='Vector3' or typeof(velocity)~='Vector3' or velocity.Magnitude<.01 then return end
  remove(a)
  shots[a]={kind=kind,origin=origin,velocity=velocity,started=started,stopAt=wallTime(origin,velocity,lifetime)}
 elseif action=='Aim' then
  local releaseAt,flight,aimDistance,npc=lifetime,...
  if typeof(origin)~='Vector3' or typeof(velocity)~='Vector3' or velocity.Magnitude<.01 or type(started)~='number' or type(releaseAt)~='number' or type(flight)~='number' then return end
  unaim(a)
  -- The line ends where the shot will: its range, or the first wall (the same test its flight uses).
  local length=velocity.Magnitude*wallTime(origin,velocity,flight)
  aims[a]={origin=origin,finish=origin+velocity.Unit*length,started=started,releaseAt=releaseAt,fade=Visuals.aimFade(aimDistance,length),npc=typeof(npc)=='Instance' and npc or nil}
 elseif action=='Unaim' then unaim(a)
 elseif action=='End' then unaim(a);remove(a)
 elseif action=='Hold' then held=a
 elseif action=='Resume' then
  -- Paused shots carry on from where they hung: they start later by the frozen time.
  for _,s in shots do s.started+=a end
  held=nil
 end
end
local function hook(child) if child.Name=='EnemyShot' and child:IsA('RemoteEvent') then child.OnClientEvent:Connect(onShot) end end
-- EnemyAttacks makes the remote on match servers only (lobbies run no waves), so no WaitForChild.
combat.ChildAdded:Connect(hook)
for _,child in combat:GetChildren() do hook(child) end
local function drawAims(now,camera)
 local paused=combat:GetAttribute('RunPaused')==true
 for id,a in aims do
  local npc=a.npc;local h=npc and npc:FindFirstChildOfClass('Humanoid')
  if now>=a.releaseAt or (npc and (not npc:IsDescendantOf(workspace) or (h and h.Health<=0))) then unaim(id) end
 end
 if not next(aims) then return end
 local character=Players.LocalPlayer.Character;local body=character and character:FindFirstChild('HumanoidRootPart')
 local from=body and body.Position or (camera and camera.Focus.Position) or Vector3.zero
 local keep=Visuals.nearest(aims,from,Visuals.AIM_CAP)
 for id,a in aims do
  if paused or not keep[id] or (a.origin-from).Magnitude>CULL then dropBeam(a);continue end
  if not a.b then a.b=takeBeam();a.b.a0.WorldPosition=a.origin;a.b.a1.WorldPosition=a.finish end
  local opacity,width=Visuals.aimLook(a.started,a.releaseAt,now)
  local t=1-opacity
  local beam=a.b.beam;beam.Width0,beam.Width1=width,width
  -- Solid to the aimed point, fading past it (still dangerous, just softer) to where the shot ends.
  beam.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,t),NumberSequenceKeypoint.new(a.fade,t),NumberSequenceKeypoint.new(1,1-opacity*.35)})
 end
end
RunService.RenderStepped:Connect(function()
 if next(aims) then drawAims(workspace:GetServerTimeNow(),workspace.CurrentCamera) end
 if not next(shots) then return end
 local now=workspace:GetServerTimeNow();local camera=workspace.CurrentCamera
 for id,s in shots do
  local flown=Visuals.flown(s.started,now,held)
  if flown>=s.stopAt then remove(id);continue end
  local frame=Visuals.shotFrame(s.origin,s.velocity,flown)
  if not s.model then
   if camera and (camera.CFrame.Position-frame.Position).Magnitude>CULL then continue end
   s.model=Visuals.shot(s.kind,combat:FindFirstChild('EnemyProjectileTemplates'));s.model.Parent=folder
   Visuals.readable(s.model,s.kind,frame) -- bigger + red-orange trail (2026-10-10), placed at its first frame
  end
  s.model:PivotTo(frame)
 end
end)
-- Spawn warnings: the same pulse the server's tweens had, 0.1 -> 0.55 transparency and back every
-- 0.25 s, started as each bar arrives. Streaming can bring bars in late or take them away.
local PULSE=TweenInfo.new(.25,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true)
local function pulse(bar)
 if bar.Name~='WarningBar' or not bar:IsA('BasePart') then return end
 local tween=TweenService:Create(bar,PULSE,{Transparency=.55});tween:Play()
 bar.AncestryChanged:Connect(function() if not bar:IsDescendantOf(workspace) then tween:Cancel() end end)
end
local function watch(child)
 if child.Name~='RogueliteSpawnWarnings' then return end
 child.DescendantAdded:Connect(pulse)
 for _,d in child:GetDescendants() do pulse(d) end
end
workspace.ChildAdded:Connect(watch)
for _,child in workspace:GetChildren() do watch(child) end
