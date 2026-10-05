-- Temporary Studio SERVER Play fixture, not mapped into the shipping project.
-- Uses real SpecialWeapons -> EggChickens/UtilityWeapons and the existing client FX listeners.
-- Isolated synthetic owner/state, real templates and physics; damage only reaches fixture dummies.
-- No inventory/profile edits, rewards, DataStores, runtime source patches, or real player's movement.
-- Geometry and fixture connections clean themselves up. STOP PLAY afterwards to release the three
-- production factories' ordinary session-long Heartbeat subscriptions (their APIs have no destroy).
-- In server MCP Play context:
-- local H=game:GetService('HttpService')
-- local fn=assert(loadstring(H:GetAsync('http://127.0.0.1:8934/studio-prototype/combat/CombatFeedbackPlayQA.luau')))()
-- return fn({duration=30})
-- Inspect workspace.CombatFeedbackQA attributes during Play. Client camera fixture below is separate.
return function(options)
 options=options or {}
 local Run=game:GetService('RunService');assert(Run:IsStudio() and Run:IsRunning() and Run:IsServer(),'Studio SERVER Play only')
 local Players=game:GetService('Players');local Tags=game:GetService('CollectionService');local H=game:GetService('HttpService')
 local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
 local player=assert(Players:GetPlayers()[1],'Need one loaded player')
 local playerRoot=assert(player.Character and player.Character:FindFirstChild('HumanoidRootPart'),'Need player character')
 assert(not workspace:FindFirstChild('CombatFeedbackQA'),'Stop the previous fixture/Play before rerunning')
 local duration=math.clamp(tonumber(options.duration) or 30,16,60)
 local center=options.center or (playerRoot.Position+Vector3.new(0,35,-45))
 local prefix='CombatQA_'..H:GenerateGUID(false)..'_';local userId=-math.random(100000,900000)
 local stage=Instance.new('Folder');stage.Name='CombatFeedbackQA';stage.Parent=workspace
 stage:SetAttribute('Center',center);stage:SetAttribute('OwnerUserId',userId);stage:SetAttribute('Duration',duration)
 stage:SetAttribute('HatchCount',0);stage:SetAttribute('PeckHits',0);stage:SetAttribute('BallHits',0)
 stage:SetAttribute('VacuumHits',0);stage:SetAttribute('MaxChickenTravel',0);stage:SetAttribute('MaxActiveChickens',0)
 local function part(name,size,position,color,parent)
  local p=Instance.new('Part');p.Name=name;p.Size=size;p.Position=position;p.Color=color
  p.Anchored=true;p.TopSurface=Enum.SurfaceType.Smooth;p.BottomSurface=Enum.SurfaceType.Smooth
  p.Parent=parent or stage;return p
 end
 part('Floor',Vector3.new(84,1,60),center-Vector3.yAxis*.5,Color3.fromRGB(50,57,58))
 local function label(text,x)
  local p=part(text,Vector3.new(23,.03,56),center+Vector3.new(x,.025,0),Color3.fromRGB(68,76,75));p.CanCollide=false;p.CanQuery=false
  local gui=Instance.new('BillboardGui');gui.Size=UDim2.fromOffset(260,38);gui.StudsOffset=Vector3.new(0,9,0);gui.AlwaysOnTop=true;gui.Parent=p
  local t=Instance.new('TextLabel');t.Size=UDim2.fromScale(1,1);t.BackgroundTransparency=1;t.Text=text;t.TextSize=22
  t.Font=Enum.Font.GothamBold;t.TextColor3=Color3.new(1,1,1);t.TextStrokeTransparency=.3;t.Parent=gui
 end
 label('BOWLING · 28 STUDS/S',-26);label('EGG · FORCED QA HATCH',0);label('VACUUM · INWARD FUNNEL',26)
 local function dummy(name,offset,tagged)
  local m=Instance.new('Model');m.Name=name;m:SetAttribute('PracticeTarget',true);m:SetAttribute('LobbyDummy',true);m.Parent=stage
  local p=part('HumanoidRootPart',Vector3.new(1.8,3.2,1.5),center+offset+Vector3.yAxis*1.6,Color3.fromRGB(198,137,80),m)
  local head=part('Head',Vector3.one*1.5,center+offset+Vector3.yAxis*4,Color3.fromRGB(233,191,127),m);head.Shape=Enum.PartType.Ball
  local h=Instance.new('Humanoid');h.RequiresNeck=false;h.MaxHealth=1000000;h.Health=h.MaxHealth;h.WalkSpeed=0;h.DisplayDistanceType=Enum.HumanoidDisplayDistanceType.None;h.Parent=m
  m.PrimaryPart=p;if tagged then Tags:AddTag(m,'RogueliteZombie') end
  return m,p
 end
 -- This untagged dummy stands DIRECTLY under the ball's elevated release point. Old client floor
 -- probes accepted its head; the actual new shared probe must start the ball down at floor level.
 dummy('UntaggedLaunchDummy',Vector3.new(-26,0,18),false)
 local ballDummy,ballTarget=dummy('BallContactDummy',Vector3.new(-26,0,1),true)
 local eggDummy,eggTarget=dummy('EggPeckDummy',Vector3.new(0,0,-5),true)
 local vacuumDummy,vacuumTarget=dummy('VacuumDummy',Vector3.new(26,0,-1),true)
 local actor=Instance.new('Model');actor.Name='IsolatedOwner';actor.Parent=stage
 local ar=part('HumanoidRootPart',Vector3.new(2,2,1),center+Vector3.new(29,3,17),Color3.new(),actor)
 ar.Transparency=1;ar.CanCollide=false;ar.CanQuery=false;local ah=Instance.new('Humanoid');ah.RequiresNeck=false;ah.Parent=actor
 local owner={UserId=userId,Character=actor,GetAttribute=function() return nil end}
 local alive=true;local ids={'22','15','28'};local slots={}
 for i,id in ids do
  local attrs={WeaponId=id,CopyId=prefix..i}
  slots[i]={GetAttribute=function(_,k) return attrs[k] end,SetAttribute=function(_,k,v) attrs[k]=v end}
 end
 local state={GetAttribute=function(_,k) if k=='WeaponEnabled' then return alive elseif k=='RingRadius' then return 6.2 end end,
  FindFirstChild=function(_,n) return slots[tonumber(n:match('Slot(%d+)'))] end}
 local event={}
 function event:FireAllClients(action,key,...)
  local row=table.pack(...)
  if action=='Launch' and row[1]=='22' and stage.Parent then
   stage:SetAttribute('BallLaunchClearance',row[5].Y-center.Y)
   stage:SetAttribute('BallCollisionRadius',row[10]);stage:SetAttribute('BallDuration',row[8])
  end
  combat.SpecialFX:FireAllClients(action,prefix..tostring(key),...)
 end
 function event:FireClient(recipient,action,key,...)
  combat.SpecialFX:FireClient(recipient,action,prefix..tostring(key),...)
 end
 local context={SpecialFX=event,WeaponTemplates=combat.WeaponTemplates,
  PlayerStates={FindFirstChild=function(_,id) return id==tostring(userId) and state or nil end},
  GetAttribute=function(_,k) if k=='TestChickenChance' then return 1 elseif k=='ZombiesEnabled' then return true elseif k=='RunPaused' then return false end end}
 function context:WaitForChild(name) return self[name] end
 local function rayParams(character,ignoreEnemies)
  local filter={character}
  for _,p in Players:GetPlayers() do if p.Character then table.insert(filter,p.Character) end end
  local allies=workspace:FindFirstChild('RogueliteChickens');if allies then table.insert(filter,allies) end
  if ignoreEnemies then for _,npc in Tags:GetTagged('RogueliteZombie') do table.insert(filter,npc) end end
  local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=filter;return params
 end
 local function damage(npc,amount,d,secondary)
  if not alive or not npc:IsDescendantOf(stage) then return end
  local h=npc:FindFirstChildOfClass('Humanoid');if h then h:TakeDamage(amount) end
  local field=d.id=='22' and 'BallHits' or d.id=='28' and 'VacuumHits' or d.id=='15' and secondary and 'PeckHits'
  if field then stage:SetAttribute(field,(stage:GetAttribute(field) or 0)+1) end
 end
 local server=require(game.ServerScriptService:WaitForChild('SpecialWeapons')).new(context,damage,rayParams)
 local Stats=require(combat.CharacterStats);local Catalog=require(combat.WeaponCatalog)
 local stats=Stats.resolve('Brawler',0,{Damage=0,MeleeDamage=0,RangedDamage=0,AttackSpeed=0,CooldownReduction=0,AttackRange=0,ProjectileSpeed=0})
 local defs={}
 for slot,id in ids do
  local d=Stats.weapon(Catalog.ById[id],stats,nil,1);d.stats=stats;d.owner=owner;d.character=actor;d.slotIndex=slot;d.practiceTarget=true
  defs[id]=d
 end
 local chickens={};local added=Tags:GetInstanceAddedSignal('RogueliteChicken'):Connect(function(model)
  if model:GetAttribute('OwnerUserId')~=userId then return end
  local root=model:FindFirstChild('HumanoidRootPart');chickens[model]=root and root.Position
  stage:SetAttribute('HatchCount',stage:GetAttribute('HatchCount')+1)
  stage:SetAttribute('UsesFallback',model:GetAttribute('ProceduralChickenFallback')==true)
 end)
 local start=workspace:GetServerTimeNow();stage:SetAttribute('StartedAt',start)
 local nextBall,nextEgg,nextVacuum=0,0,0;local stopped=false
 local function cleanup()
  if stopped then return end;stopped=true;alive=false;added:Disconnect()
  for model in chickens do if model.Parent then model:Destroy() end end
  stage:Destroy()
 end
 task.spawn(function()
  while not stopped and stage.Parent do
   local now=workspace:GetServerTimeNow();local age=now-start
   if age>=duration then cleanup();break end
   -- Last ten seconds demonstrate that chickens expire after throws stop.
   if age<duration-10 then
    if age>=nextBall then nextBall=age+1.65;server:launch(defs['22'],center+Vector3.new(-26,10,18),ballTarget.Position) end
    if age>=nextEgg then nextEgg=age+1.3;server:launch(defs['15'],center+Vector3.new(0,4,15),center+Vector3.new(5,1,0)) end
    if age>=nextVacuum then nextVacuum=age+.22;server:launch(defs['28'],ar.Position,vacuumTarget.Position) end
   end
   local active,total=0,0
   for model,born in chickens do
    local root=model.Parent and model:FindFirstChild('HumanoidRootPart')
    if root then
     total+=1;if not model:GetAttribute('PopAt') then active+=1 end
     local drift=Vector3.new(root.Position.X-born.X,0,root.Position.Z-born.Z).Magnitude
     stage:SetAttribute('MaxChickenTravel',math.max(stage:GetAttribute('MaxChickenTravel'),drift))
    end
   end
   stage:SetAttribute('ActiveChickens',active);stage:SetAttribute('RemainingChickens',total)
   stage:SetAttribute('MaxActiveChickens',math.max(stage:GetAttribute('MaxActiveChickens'),active))
   stage:SetAttribute('ThrowsStopped',age>=duration-10)
   task.wait(.1)
  end
  if not stopped then cleanup() end
 end)
 return {fixture=stage:GetFullName(),duration=duration,center=tostring(center),camera=tostring(center+Vector3.new(0,43,48)),
  checks='BallLaunchClearance=BallCollisionRadius+.06; BallHits>0; HatchCount>0; UsesFallback=true; PeckHits>0; MaxActiveChickens<=3; last second RemainingChickens=0',
  cleanup='Models auto-remove; STOP PLAY after QA to release fixture factory subscriptions'}
end
