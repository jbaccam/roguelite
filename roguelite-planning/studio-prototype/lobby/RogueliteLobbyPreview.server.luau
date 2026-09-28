-- Studio-only lobby / arena preview: step-on queue pads where the first player (host) picks
-- the map and presses START, a countdown that launches the group into the arena, and a
-- travel remote for testing either area directly.
-- Production first-join routing and reserved-match launch are separate integrations.
-- workspace.RogueliteLobby.StudioStartArea ('Arena' or 'Lobby') picks where Play starts.
local RunService=game:GetService('RunService')
if not RunService:IsStudio() then return end
local Players=game:GetService('Players')
local TweenService=game:GetService('TweenService')
local SSS=game:GetService('ServerScriptService')
local RS=game:GetService('ReplicatedStorage')
-- Match servers have no lobby: ServerRole parks it.
local Role=require(SSS:WaitForChild('ServerRole'))
if Role.get()=='Match' then return end
local root=workspace:WaitForChild('RogueliteLobby')
local State=require(script:WaitForChild('QueueState'))
local Rules=require(RS:WaitForChild('RunSetupRules'))
local combat=RS:WaitForChild('RogueliteCombat')
local Shop=require(SSS:WaitForChild('ShopService'))
local CAPACITY=4
local state=State.new(4,CAPACITY)
local last,stepOff={},{}
-- Lobby servers spawn players here; the combined Studio preview places them by script instead.
local lobbySpawn=root:WaitForChild('LobbySpawn');lobbySpawn.Enabled=Role.get()=='Lobby'
local origin=root:GetAttribute('Origin')
local now=function() return workspace:GetServerTimeNow() end
local function remote(name)
 local r=root:FindFirstChild(name) or Instance.new('RemoteEvent');r.Name=name;r.Parent=root;return r
end
-- Lobby HUD LEAVE button. Takes no arguments: a player can only remove themself.
local leaveRemote=remote('LeaveQueue')
-- Studio travel panel. One argument, 'Lobby' or 'Arena'; moves only the caller.
local travelRemote=remote('StudioTravel')
-- Run setup screen: ('Start', mapId, class, weapon, solo, difficulty) from a pad's host,
-- ('Play', same arguments) from PLAY away from the pads (claims a free pad and moves the caller
-- onto it), ('Ready', class, weapon) from anyone on a pad, ('Loadout', class, weapon) from the
-- Loadout screen or Armory EQUIP while in the lobby. Server replies ('Result', ok, message).
local setupRemote=remote('RunSetup')

-- Pad visuals: a raised light ring and a column of light that fades as it rises. White while
-- the pad is empty, red while players are on it.
local IDLE=Color3.fromRGB(240,244,248);local ACTIVE=Color3.fromRGB(239,52,62)
local RING_RADIUS=8.4;local PAD_RADIUS=9.2;local COLUMN_HEIGHT=6.5;local RING_LIFT=.45
local PAD_LIGHT_TEXTURE='rbxassetid://81762721388354' -- lobby/build_pad_light.py
local pads={}
local function part(parent,name,size,cf)
 local p=Instance.new('Part');p.Name=name;p.Anchored=true;p.CanCollide=false;p.CanQuery=false;p.CanTouch=false
 p.CastShadow=false;p.Transparency=1;p.Size=size;p.CFrame=cf;p.Parent=parent;return p
end
local function buildPad(portal)
 local zone=portal:WaitForChild('QueueZone')
 -- The old "QUEUE n · x / 4" tooltip and E prompt are replaced by stepping onto the pad.
 for _,name in {'QueueStatus','JoinQueue'} do local old=zone:FindFirstChild(name);if old then old:Destroy() end end
 local old=portal:FindFirstChild('QueuePad');if old then old:Destroy() end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances={root.Portals}
 local hit=workspace:Raycast(zone.Position+Vector3.new(0,10,0),Vector3.new(0,-30,0),params)
 local center=Vector3.new(zone.Position.X,(hit and hit.Position.Y or zone.Position.Y-2)+RING_LIFT,zone.Position.Z)
 local folder=Instance.new('Folder');folder.Name='QueuePad';folder.Parent=portal
 local tinted,strokes={},{}
 -- Ring: a bright band with a soft halo either side, drawn on a flat SurfaceGui.
 local d=RING_RADIUS*2+1.6
 local ring=part(folder,'Ring',Vector3.new(d,.05,d),CFrame.new(center))
 local surface=Instance.new('SurfaceGui');surface.Face=Enum.NormalId.Top;surface.LightInfluence=0;surface.Brightness=3
 surface.SizingMode=Enum.SurfaceGuiSizingMode.PixelsPerStud;surface.PixelsPerStud=32;surface.Parent=ring
 for _,spec in {{0,.7,.72},{.2,.42,0},{.62,.3,.8}} do -- {inset, thickness, transparency} in studs
  local f=Instance.new('Frame');f.BackgroundTransparency=1;f.AnchorPoint=Vector2.new(.5,.5);f.Position=UDim2.fromScale(.5,.5)
  f.Size=UDim2.new(1,-(spec[1]*2+.8)*32,1,-(spec[1]*2+.8)*32);f.Parent=surface
  Instance.new('UICorner',f).CornerRadius=UDim.new(.5,0)
  local s=Instance.new('UIStroke');s.Thickness=spec[2]*32;s.Transparency=spec[3];s.Color=IDLE;s.Parent=f
  table.insert(strokes,s)
 end
 -- Column: four quarter-circle beams (one seamless curved wall) textured with a fade that is
 -- solid at the ring and clear at the top. The texture's horizontal axis runs up the wall.
 local beams={}
 local base=part(folder,'Column',Vector3.one,CFrame.new(center))
 local handle=4/3*math.tan(math.pi/8)*RING_RADIUS -- Bezier handle for a quarter circle
 local function edge(theta)
  local pos=Vector3.new(math.cos(theta)*RING_RADIUS,COLUMN_HEIGHT/2,math.sin(theta)*RING_RADIUS)
  local a=Instance.new('Attachment');a.CFrame=CFrame.fromMatrix(pos,Vector3.new(-math.sin(theta),0,math.cos(theta)),Vector3.yAxis);a.Parent=base
  return a
 end
 for q=0,3 do
  local b=Instance.new('Beam');b.Attachment0=edge(q*math.pi/2);b.Attachment1=edge((q+1)*math.pi/2)
  b.CurveSize0=handle;b.CurveSize1=-handle;b.Segments=24;b.FaceCamera=false;b.Width0=COLUMN_HEIGHT;b.Width1=COLUMN_HEIGHT
  b.Texture=PAD_LIGHT_TEXTURE;b.TextureMode=Enum.TextureMode.Stretch;b.TextureLength=1;b.TextureSpeed=0
  b.LightEmission=.6;b.LightInfluence=0;b.Brightness=1.5;b.Color=ColorSequence.new(IDLE);b.Transparency=NumberSequence.new(0)
  b.Parent=base;table.insert(beams,b)
 end
 -- Floating counter: map name, big "x/4", an underline with a notch, and the status line.
 local anchor=part(folder,'Counter',Vector3.one,CFrame.new(center+Vector3.new(0,8.6,0)))
 local bb=Instance.new('BillboardGui');bb.Name='QueueCounter';bb.Size=UDim2.fromScale(11,5.8);bb.LightInfluence=0;bb.MaxDistance=150;bb.Parent=anchor
 local function label(name,y,h,text)
  local l=Instance.new('TextLabel');l.Name=name;l.BackgroundTransparency=1;l.Position=UDim2.fromScale(0,y);l.Size=UDim2.fromScale(1,h)
  l.Font=Enum.Font.FredokaOne;l.TextScaled=true;l.TextColor3=IDLE;l.TextStrokeTransparency=.35;l.Text=text;l.Parent=bb;return l
 end
 local map=label('Map',0,.17,'')
 local count=label('Count',.18,.44,'0/'..CAPACITY)
 local line=Instance.new('Frame');line.Name='Underline';line.AnchorPoint=Vector2.new(.5,.5);line.Position=UDim2.fromScale(.5,.66)
 line.Size=UDim2.fromScale(.66,.03);line.BorderSizePixel=0;line.BackgroundColor3=IDLE;line.Parent=bb
 local notch=Instance.new('Frame');notch.Name='Notch';notch.AnchorPoint=Vector2.new(.5,.5);notch.Position=UDim2.fromScale(.5,.685)
 notch.Size=UDim2.fromScale(.045,.045);notch.Rotation=45;notch.BorderSizePixel=0;notch.BackgroundColor3=IDLE;notch.Parent=bb
 Instance.new('UIAspectRatioConstraint',notch)
 local status=label('Status',.75,.22,'')
 table.insert(tinted,line);table.insert(tinted,notch)
 pads[portal:GetAttribute('PortalId')]={portal=portal,center=center,strokes=strokes,tinted=tinted,beams=beams,map=map,count=count,status=status,shown=nil}
end
local function paint(pad,color)
 for _,s in pad.strokes do s.Color=color end
 for _,f in pad.tinted do f.BackgroundColor3=color end
 for _,b in pad.beams do b.Color=ColorSequence.new(color) end
end

local function nameOf(id) local p=Players:GetPlayerByUserId(id);return p and p.DisplayName or 'Host' end
local function publish()
 for index,q in state.queues do
  local pad=pads[index];if not pad then continue end
  local portal=pad.portal;local n=#q.members;local cap=state:capacityOf(q)
  local phase=q.locked and 'Launching' or q.phase
  portal:SetAttribute('QueueCount',n);portal:SetAttribute('Capacity',cap);portal:SetAttribute('QueueState',phase)
  portal:SetAttribute('LaunchAt',q.launchAt);portal:SetAttribute('HostId',q.host);portal:SetAttribute('MapId',q.map);portal:SetAttribute('Solo',q.solo)
  portal:SetAttribute('Difficulty',q.difficulty)
  local text=phase=='Launching' and 'Entering...' or phase=='Counting' and string.format('Starting in %ds',math.max(0,math.ceil(q.launchAt-now())))
   or phase=='Choosing' and nameOf(q.host)..' is choosing' or ''
  local mapIndex=q.map and Rules.MapIndex[q.map]
  local diffText=q.difficulty and q.difficulty~='Normal' and '  ·  '..string.upper(q.difficulty) or ''
  local mapText=mapIndex and (Rules.Maps[mapIndex].name..diffText..(q.solo and '  ·  SOLO' or '')) or ''
  local shown=n..'/'..cap..'|'..text..'|'..mapText
  if pad.shown~=shown then
   pad.shown=shown;pad.count.Text=n..'/'..cap;pad.status.Text=text;pad.map.Text=mapText
   paint(pad,n>0 and ACTIVE or IDLE)
  end
 end
end

local function alive(player)
 local char=player.Character;local hrp=char and char:FindFirstChild('HumanoidRootPart');local hum=char and char:FindFirstChildOfClass('Humanoid')
 if hrp and hum and hum.Health>0 then return char,hrp end
end
local function inLobby(hrp) return (hrp.Position-origin).Magnitude<300 end
local function padUnder(hrp)
 for index,pad in pads do
  local o=hrp.Position-pad.center
  if Vector2.new(o.X,o.Z).Magnitude<=PAD_RADIUS and o.Y>-1.5 and o.Y<10 then return index end
 end
end
local function setQueue(player) player:SetAttribute('LobbyQueue',state.membership[player.UserId]) end
local function leave(player) if state:leave(player.UserId,now()) then setQueue(player);publish() end end

-- Areas -----------------------------------------------------------------------------
local function areaSpawn(area,spread)
 -- The active map's spawn; the lobby's if RunMap is somehow invalid, rather than erroring.
 local mapSpawn=Role.playerSpawn()
 local base=(area=='Lobby' or not mapSpawn) and lobbySpawn.Position or mapSpawn.Position
 local a=math.random()*math.pi*2
 return CFrame.new(base+Vector3.new(math.cos(a)*spread,4,math.sin(a)*spread))
end
local function arenaHasPlayers(except)
 for _,p in Players:GetPlayers() do
  if not except[p] and p:GetAttribute('StudioArea')=='Arena' and alive(p) then return true end
 end
 return false
end
local function moveTo(player,area,spread)
 local char=alive(player);if not char then return false end
 player:SetAttribute('StudioArea',area)
 char:PivotTo(areaSpawn(area,spread or 0))
 -- Leaving the arena empty mid-wave: stop the wave so nothing keeps chasing an empty map.
 if area=='Lobby' and not arenaHasPlayers({}) then Shop.stopWave() end
 return true
end
travelRemote.OnServerEvent:Connect(function(player,area)
 if Role.get()~='Combined' or (area~='Lobby' and area~='Arena') then return end
 if os.clock()-(last[player] or -math.huge)<.5 or player:GetAttribute('RunDown') then return end
 local index=state.membership[player.UserId]
 if index and state.queues[index].locked then return end -- already departing
 last[player]=os.clock()
 leave(player)
 moveTo(player,area,area=='Arena' and 3 or 0)
end)

-- Queue -----------------------------------------------------------------------------
leaveRemote.OnServerEvent:Connect(function(player)
 if os.clock()-(last[player] or -math.huge)<.4 then return end
 last[player]=os.clock()
 local index=state.membership[player.UserId]
 -- Standing on the pad would re-join next tick; wait until they step off first.
 if state:leave(player.UserId,now()) then stepOff[player]=index;setQueue(player);publish() end
end)
setupRemote.OnServerEvent:Connect(function(player,action,a,b,c,d,e)
 if os.clock()-(last[player] or -math.huge)<.3 then return end
 last[player]=os.clock()
 local index=state.membership[player.UserId]
 local function reply(ok,message) setupRemote:FireClient(player,'Result',ok,message) end
 if action=='Start' or action=='Play' then
  -- Lobby servers send parties to match servers (plan C); Studio can't teleport.
  if Role.get()=='Lobby' then return reply(false,'Runs start in the published game. Use the combined Studio mode to play here') end
  local mapOk,mapWhy=Rules.validMap(player,a,e);if not mapOk then return reply(false,mapWhy) end
  local okL,why=Rules.validLoadout(player,b,c);if not okL then return reply(false,why) end
  -- PLAY away from the pads: take the first empty pad and stand the player on it as host.
  if not index and action=='Play' then
   local char,hrp=alive(player)
   if not hrp or not inLobby(hrp) then return reply(false,'Return to the lobby first') end
   local free=state:freePad();if not free then return reply(false,'All portals are busy. Try again in a moment') end
   char:PivotTo(CFrame.new(pads[free].center+Vector3.new(0,3.5,0))*(hrp.CFrame-hrp.Position))
   stepOff[player]=nil
   if not state:join(player.UserId,free,now()) then return reply(false,'That portal was just taken') end
   index=free;setQueue(player)
  end
  if not index then return reply(false,'Step onto a portal pad first') end
  if not state:start(player.UserId,index,now(),a,d==true,e) then return reply(false,d==true and 'Solo needs an empty pad' or 'Only the host can start') end
  player:SetAttribute('RunClass',b);player:SetAttribute('RunWeapon',c)
  publish();reply(true,'Starting')
 elseif action=='Ready' then
  if not index then return reply(false,'Step onto a portal pad first') end
  local q=state.queues[index]
  if q.map then local mapOk,mapWhy=Rules.validMap(player,q.map,q.difficulty);if not mapOk then return reply(false,mapWhy) end end
  local okL,why=Rules.validLoadout(player,a,b);if not okL then return reply(false,why) end
  player:SetAttribute('RunClass',a);player:SetAttribute('RunWeapon',b)
  reply(true,'Ready')
 elseif action=='Loadout' then
  -- The ring shows the new starter at once (RogueliteCombat). Silent on success.
  if not player:GetAttribute('LobbyPreviewActive') then return reply(false,'Change your loadout in the lobby') end
  local okL,why=Rules.validLoadout(player,a,b);if not okL then return reply(false,why) end
  player:SetAttribute('RunClass',a);player:SetAttribute('RunWeapon',b)
 end
end)
local function launch(index)
 publish()
 local pad=pads[index]
 for _,s in pad.strokes do TweenService:Create(s,TweenInfo.new(.3,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,3,true),{Transparency=.5}):Play() end
 task.wait(1.2)
 local q=state.queues[index]
 local going={}
 for _,id in q.members do
  local p=Players:GetPlayerByUserId(id)
  -- Everyone on the pad needs this map and difficulty unlocked themselves.
  local ok,why=true,nil;if p then ok,why=Rules.validMap(p,q.map,q.difficulty) end
  if p and alive(p) and ok then going[p]=true
  elseif p and not ok then setupRemote:FireClient(p,'Result',false,why) end
 end
 -- Nobody already fighting: this group starts a fresh run at wave 1 on the chosen difficulty.
 if next(going) and not arenaHasPlayers(going) then
  combat:SetAttribute('RunMap',q.map);combat:SetAttribute('RunDifficulty',q.difficulty or 'Normal')
  Shop.resetRun()
 end
 state:finish(index)
 for p in going do setQueue(p);moveTo(p,'Arena',4) end
 publish()
end

local function attach(player)
 player:SetAttribute('StudioArea',(Role.get()=='Lobby' or root:GetAttribute('StudioStartArea')=='Lobby') and 'Lobby' or 'Arena')
 local function spawned(char)
  leave(player);stepOff[player]=nil
  local hrp=char:WaitForChild('HumanoidRootPart',10)
  if hrp and player:GetAttribute('StudioArea')=='Lobby' then
   task.wait(.15)
   if player.Character==char then char:PivotTo(areaSpawn('Lobby',0)) end
  end
 end
 player.CharacterAdded:Connect(spawned)
 if player.Character then task.spawn(spawned,player.Character) end
end
for _,portal in root.Portals:GetChildren() do buildPad(portal) end
Players.PlayerAdded:Connect(attach)
for _,p in Players:GetPlayers() do attach(p) end
Players.PlayerRemoving:Connect(function(p) state:leave(p.UserId,now());last[p]=nil;stepOff[p]=nil;publish() end)

local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.1 then return end;elapsed=0
 for _,p in Players:GetPlayers() do
  local char,hrp=alive(p)
  local lobby=hrp~=nil and inLobby(hrp)
  p:SetAttribute('LobbyPreviewActive',lobby)
  if lobby and p:GetAttribute('StudioArea')~='Lobby' then p:SetAttribute('StudioArea','Lobby') end
  if lobby and hrp.Position.Y<origin.Y-50 then char:PivotTo(areaSpawn('Lobby',0)) end
  local index=state.membership[p.UserId]
  if index and state.queues[index].locked then continue end
  local under=lobby and padUnder(hrp) or nil
  if stepOff[p] and under~=stepOff[p] then stepOff[p]=nil end
  if index and under~=index then leave(p);index=nil end
  if under and not index and stepOff[p]~=under and state:join(p.UserId,under,now()) then setQueue(p) end
 end
 -- A host who never presses START frees the pad for someone else.
 for _,id in state:stale(now()) do
  local p=Players:GetPlayerByUserId(id)
  local index=state.membership[id]
  if state:leave(id,now()) and p then
   stepOff[p]=index;setQueue(p)
   setupRemote:FireClient(p,'Result',false,'Pad released. Step off and back on to host again.')
  end
 end
 for _,index in state:due(now()) do task.spawn(launch,index) end
 publish()
end)
publish()
