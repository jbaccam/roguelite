-- The lobby: step-on queue pads where the first player (host) picks the map and presses START,
-- and a countdown that launches the group into wave 1. A queued player stays on the pad until LEAVE.
-- Parties (PartyState, the Party window): when one member joins a pad, by PLAY or by stepping on,
-- the rest of the party standing in the lobby is put on the same pad; so is someone who accepts an
-- invite while the party is on one. Everyone put on a pad gets the class step (LobbyUI).
-- Lobby servers send the group to its own match server (MatchService); the Combined role (Studio)
-- walks it into the arena here, and keeps a travel remote for testing either area directly.
-- workspace.RogueliteLobby.StudioStartArea ('Arena' or 'Lobby') picks where Combined Play starts.
local RunService=game:GetService('RunService')
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
local Match=require(SSS:WaitForChild('MatchService'))
local Profiles=require(SSS:WaitForChild('ProfileService')) -- MatchService loads it already
local CAPACITY=4
local state=State.new(4,CAPACITY)
local Party=require(script:WaitForChild('PartyState'))
local parties=Party.new(CAPACITY)
local last,stepOff={},{}
local travelling={}
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
-- Run setup screen: ('Start', mapId, class, weapon, private, difficulty) from a pad's host,
-- ('Play', same arguments) from PLAY away from the pads (claims a free pad and moves the caller
-- onto it), ('Ready', class, weapon) from anyone on a pad, ('Loadout', class, weapon) from the
-- Loadout screen or Armory EQUIP while in the lobby. Server replies ('Result', ok, message).
local setupRemote=remote('RunSetup')
-- Party window: ('Invite', userId), ('Accept', inviter userId), ('Decline'), ('Leave'). Only
-- players in this server; the server replies ('Result', ok, message).
local partyRemote=remote('Party')

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
 -- The client keeps a queued player inside this circle (RogueliteLobbyPreview.client).
 portal:SetAttribute('PadCenter',center);portal:SetAttribute('PadRadius',RING_RADIUS-1)
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
  -- How many on the pad still have to lock in a class (the banner says so; QueueState waits for them).
  portal:SetAttribute('Picking',n>0 and state:picking(index) or nil)
  local text=phase=='Launching' and 'Entering...' or phase=='Counting' and string.format('Starting in %ds',math.max(0,math.ceil(q.launchAt-now())))
   or phase=='Choosing' and nameOf(q.host)..' is choosing' or ''
  local mapIndex=q.map and Rules.MapIndex[q.map]
  local diffText=q.difficulty and q.difficulty~='Normal' and '  ·  '..string.upper(q.difficulty) or ''
  local mapText=mapIndex and (Rules.Maps[mapIndex].name..diffText..(q.solo and '  ·  PRIVATE' or '')) or ''
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
-- Loose server check for a queued player: the client already holds them inside the ring.
local function nearPad(hrp,pad)
 local o=hrp.Position-pad.center
 return Vector2.new(o.X,o.Z).Magnitude<=PAD_RADIUS+2 and math.abs(o.Y)<20
end
-- LobbyQueue: the pad they are on. LobbyLockedIn: they locked in a class on it (START or LOCK IN),
-- so the banner shows that class instead of asking them to pick one.
local function setQueue(player)
 local index=state.membership[player.UserId]
 player:SetAttribute('LobbyQueue',index)
 player:SetAttribute('LobbyLockedIn',index and state.queues[index].picked[player.UserId] or nil)
end
local function leave(player) if state:leave(player.UserId,now()) then setQueue(player);publish() end end

-- Parties ---------------------------------------------------------------------------
-- Every player's PartyMembers ('id,id' in join order, nil when not in one) and pending invite
-- (PartyInviteFrom = inviter's user id, PartyInviteUntil = server time it expires).
local function publishParties()
 for _,p in Players:GetPlayers() do
  local party=parties.partyOf[p.UserId]
  local ids={};if party then for _,id in party do table.insert(ids,tostring(id)) end end
  p:SetAttribute('PartyMembers',party and table.concat(ids,',') or nil)
  local invite=parties.invites[p.UserId]
  p:SetAttribute('PartyInviteFrom',invite and invite.from or nil);p:SetAttribute('PartyInviteUntil',invite and invite.expires or nil)
 end
end
-- The rest of player's party follows them onto pad `index`: anyone standing in the lobby who isn't
-- queued, travelling, or just pressed LEAVE on this pad. Each still needs the map unlocked at launch.
-- Each gets the class step on arrival (LobbyUI), and the countdown waits for their pick (QueueState).
-- A Private pad of player's takes members who joined the party after START too; a full or departing
-- pad says why (2026-10-03). note (optional): what the pulled players are told instead.
local function pullParty(player,index,note)
 local pad=pads[index];if not pad then return end
 local q=state.queues[index]
 if q.solo and q.allow and q.allow[player.UserId] then state:allowParty(index,parties:members(player.UserId),now()) end
 for _,id in parties:members(player.UserId) do
  local p=id~=player.UserId and Players:GetPlayerByUserId(id)
  if not p or state.membership[id] or travelling[p] or p:GetAttribute('MapTravelPending') or stepOff[p]==index then continue end
  local char,hrp=alive(p)
  if not (hrp and inLobby(hrp)) then continue end
  if state:join(id,index,now()) then
   local a=math.random()*math.pi*2
   char:PivotTo(CFrame.new(pad.center+Vector3.new(math.cos(a)*3,3.5,math.sin(a)*3))*(hrp.CFrame-hrp.Position))
   stepOff[p]=nil;setQueue(p)
   partyRemote:FireClient(p,'Result',true,note or player.DisplayName..' took the party to portal '..index)
  else
   local cap=state:capacityOf(q)
   partyRemote:FireClient(p,'Result',false,q.locked and ('Portal %d is already leaving'):format(index) or ("Portal %d is full (%d / %d), so you couldn't join %s"):format(index,#q.members,cap,player.DisplayName))
  end
 end
 publish()
end
-- An accepted invite (user, 2026-10-03: "if player 1 is in a portal and invites player 2 to his party
-- it doesn't put player 2 in his portal"): the new member goes onto the pad the party is on (the
-- inviter's, else another member's), stepping off their own pad if they were on one and there is
-- room. If no one else is on a pad but they are, the party comes to theirs, as when stepping on.
-- Example: Ana counts down on Private portal 2, Ben accepts her invite -> Ben on portal 2 (2 / 2),
-- class step open, the launch waits for his pick.
local function joinPartyPad(player,from)
 local anchor=from and state.membership[from.UserId] and from or nil
 if not anchor then
  for _,id in parties:members(player.UserId) do
   local p=id~=player.UserId and state.membership[id] and Players:GetPlayerByUserId(id)
   if p then anchor=p;break end
  end
 end
 local mine=state.membership[player.UserId]
 if not anchor then
  if mine and not state.queues[mine].locked then pullParty(player,mine) end
  return
 end
 local index=state.membership[anchor.UserId]
 if mine==index then return end
 local q=state.queues[index]
 if q.solo and q.allow and q.allow[anchor.UserId] then state:allowParty(index,parties:members(anchor.UserId),now()) end
 if mine then
  if state.queues[mine].locked then return end -- already leaving from their own pad
  if q.locked or #q.members>=state:capacityOf(q) then
   return partyRemote:FireClient(player,'Result',false,('Portal %d is %s, so you stay on portal %d'):format(index,q.locked and 'already leaving' or 'full',mine))
  end
  leave(player)
 end
 stepOff[player]=nil
 pullParty(anchor,index,('You joined %s on portal %d'):format(anchor.DisplayName,index))
end
local lastParty={}
partyRemote.OnServerEvent:Connect(function(player,action,arg)
 if os.clock()-(lastParty[player] or -math.huge)<.3 then return end
 lastParty[player]=os.clock()
 local function reply(ok,message) partyRemote:FireClient(player,'Result',ok,message) end
 if action=='Invite' then
  local other=type(arg)=='number' and Players:GetPlayerByUserId(arg)
  if not other then return reply(false,'That player is not in this server') end
  local ok,why=parties:invite(player.UserId,other.UserId,now())
  if not ok then return reply(false,why) end
  reply(true,'Invited '..other.DisplayName)
 elseif action=='Accept' then
  local ok,why=parties:accept(player.UserId,arg,now())
  local from=type(arg)=='number' and Players:GetPlayerByUserId(arg)
  if ok and from then partyRemote:FireClient(from,'Result',true,player.DisplayName..' joined your party') end
  reply(ok,not ok and why or from and ('You joined '..from.DisplayName.."'s party") or 'You joined the party')
  if ok then publishParties();joinPartyPad(player,from or nil) end
 elseif action=='Decline' then parties:decline(player.UserId)
 elseif action=='Leave' then if parties:leave(player.UserId) then reply(true,'You left the party') end
 else return end
 publishParties()
end)

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
 travelling[player]=true
 local destination=areaSpawn(area,spread or 0)
 -- Preload the destination before moving across the large gaps between arena vistas.
 if workspace.StreamingEnabled then
  local ok,err=pcall(player.RequestStreamAroundAsync,player,destination.Position,5)
  if not ok then travelling[player]=nil;warn('Arena stream request failed:',err);return false end
 end
 if not char.Parent or player.Character~=char then travelling[player]=nil;return false end
 player:SetAttribute('StudioArea',area)
 char:PivotTo(destination)
 travelling[player]=nil
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
-- Just outside a pad's ring on the side facing the lobby spawn (never radially, which could be an
-- island edge or the portal), on the ground found by a raycast.
local function besidePad(pad,char)
 local toward=Vector3.new(lobbySpawn.Position.X-pad.center.X,0,lobbySpawn.Position.Z-pad.center.Z)
 toward=toward.Magnitude>.5 and toward.Unit or Vector3.zAxis
 local spot=pad.center+toward*(PAD_RADIUS+4)
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances={char}
 local hit=workspace:Raycast(spot+Vector3.new(0,12,0),Vector3.new(0,-40,0),params)
 spot=Vector3.new(spot.X,(hit and hit.Position.Y or pad.center.Y)+3.5,spot.Z)
 return CFrame.lookAt(spot,spot+toward)
end
leaveRemote.OnServerEvent:Connect(function(player)
 if os.clock()-(last[player] or -math.huge)<.4 then return end
 last[player]=os.clock()
 local index=state.membership[player.UserId]
 -- LEAVE puts them off the pad at once (user, 2026-10-03: "when you click leave when your in
 -- queue it should force you off the pad"). LobbyQueue is cleared first, so the client stops
 -- holding them in the ring; stepOff still keeps them from re-joining until they walk back on.
 if state:leave(player.UserId,now()) then
  stepOff[player]=index;setQueue(player);publish()
  local pad=pads[index];local char,hrp=alive(player)
  if pad and hrp then char:PivotTo(besidePad(pad,char)) end
 end
end)
-- A class and starter that passed Rules.validLoadout: this server's run uses them, and the profile
-- keeps them for the next lobby (ProfileService.setLoadout).
local function pick(player,class,weapon)
 player:SetAttribute('RunClass',class);player:SetAttribute('RunWeapon',weapon)
 Profiles.setLoadout(player,class,weapon)
end
setupRemote.OnServerEvent:Connect(function(player,action,a,b,c,d,e)
 if os.clock()-(last[player] or -math.huge)<.3 then return end
 last[player]=os.clock()
 local index=state.membership[player.UserId]
 local function reply(ok,message) setupRemote:FireClient(player,'Result',ok,message) end
 if action=='Start' or action=='Play' then
  -- Lobby servers send parties to match servers (MatchService); Studio can't teleport.
  if Role.get()=='Lobby' and RunService:IsStudio() then return reply(false,'Runs start in the published game. Use the combined Studio mode to play here') end
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
  -- d: Private (only this player's party may join; just them when not in one), else Open.
  local allow={};for _,id in parties:members(player.UserId) do allow[id]=true end
  if not state:start(player.UserId,index,now(),a,d==true,e,allow) then return reply(false,d==true and 'Private needs a pad with only you and your party on it' or 'Only the host can start') end
  pick(player,b,c);setQueue(player) -- START is the host's lock-in (QueueState.start)
  -- The party comes along (Open or Private; a Private pad holds exactly the party).
  pullParty(player,index)
  local q=state.queues[index]
  publish();reply(true,('Starting in %ds'):format(math.max(1,math.ceil((q.launchAt or now())-now()))))
 elseif action=='Ready' then
  if not index then return reply(false,'Step onto a portal pad first') end
  local q=state.queues[index]
  if q.map then local mapOk,mapWhy=Rules.validMap(player,q.map,q.difficulty);if not mapOk then return reply(false,mapWhy) end end
  local okL,why=Rules.validLoadout(player,a,b);if not okL then return reply(false,why) end
  pick(player,a,b)
  -- Locked in: the countdown stops waiting for this player (QueueState.lockIn), and the run uses
  -- this class and starter (launch reads RunClass / RunWeapon; the match server re-checks them).
  state:lockIn(player.UserId,now());setQueue(player);publish()
  -- What happens next, not just "Ready" (2026-10-03: "are we readied up and is it gonna start").
  reply(true,q.launchAt and ('Locked in as %s. Starting in %ds'):format(a,math.max(1,math.ceil(q.launchAt-now()))) or ('Locked in as %s. Waiting for the host to start'):format(a))
 elseif action=='Loadout' then
  -- The ring shows the new starter at once (RogueliteCombat). Silent on success.
  if not player:GetAttribute('LobbyPreviewActive') then return reply(false,'Change your loadout in the lobby') end
  local okL,why=Rules.validLoadout(player,a,b);if not okL then return reply(false,why) end
  pick(player,a,b)
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
 -- Lobby servers: the group gets its own match server. Each member's loadout is checked again
 -- here and once more against their own save on the match server.
 if Role.get()=='Lobby' then
  -- The pad's map and difficulty, read BEFORE finish resets the queue. They used to be read after
  -- it, so every pad launch went out with map=nil and the match server, unable to set a map, sent
  -- the party straight back to a lobby (trip log, 2026-10-03: "it just queues me into the lobby").
  local map,difficulty=q.map,q.difficulty or 'Normal'
  local leader=q.solo and q.host or nil -- a Private pad's host leads its party (LEAVE WITH PARTY, 2026-10-03)
  state:finish(index)
  local list,loadouts={},{}
  for p in going do
   local class,weapon=p:GetAttribute('RunClass'),p:GetAttribute('RunWeapon')
   -- A weapon that changed class (2026-10-03) falls back to that class's starter first.
   if not Rules.validLoadout(p,class,weapon) and Rules.validLoadout(p,class,Rules.Signature[class]) then weapon=Rules.Signature[class] end
   if not Rules.validLoadout(p,class,weapon) then class='Brawler';weapon=Rules.Signature.Brawler end
   loadouts[p.UserId]={class=class,weapon=weapon}
   table.insert(list,p);travelling[p]=true;setQueue(p)
  end
  publish()
  if #list==0 then return end
  local ok,why=Match.launch(list,map,difficulty,loadouts,leader and {leader=leader} or nil)
  -- On success they stay "travelling" until they leave, so the pad they stand on can't re-queue them.
  if not ok then for _,p in list do travelling[p]=nil;setupRemote:FireClient(p,'Result',false,why) end end
  return
 end
 -- Nobody already fighting: this group starts a fresh run at wave 1 on the chosen difficulty.
 local fresh=next(going)~=nil and not arenaHasPlayers(going)
 if fresh then
  Role.setMap(q.map);combat:SetAttribute('RunDifficulty',q.difficulty or 'Normal')
  Shop.resetRun()
  if Match.setParty then Match.setParty(q.solo and q.host or nil,q.members) end -- Private: its party (LEAVE WITH PARTY)
 end
 state:finish(index)
 for p in going do setQueue(p);moveTo(p,'Arena',4) end
 -- Wave 1 starts as they land; the first shop follows it. A group joining a run already under
 -- way keeps that run's phase.
 if fresh and arenaHasPlayers({}) then Shop.startFirstWave() end
 publish()
end

-- Back in a lobby (after a run, a rejoin or on a new server): the class and starter they last
-- picked (ProfileService.loadout), not Brawler and the Frying Pan (user, 2026-10-03: "it keeps
-- resetting me back to brawler and the pan"). Checked like a launch: a starter that moved class
-- falls back to that class's own. A pick made here before the save loaded wins.
local function restoreLoadout(player)
 local started=os.clock()
 while player.Parent==Players and player:GetAttribute('ProfileLoaded')~=true and os.clock()-started<90 do task.wait(.25) end
 if player.Parent~=Players or player:GetAttribute('RunClass')~=nil then return end
 local class,weapon=Profiles.loadout(player)
 if not class then return end
 if not Rules.validLoadout(player,class,weapon) and Rules.validLoadout(player,class,Rules.Signature[class]) then weapon=Rules.Signature[class] end
 if not Rules.validLoadout(player,class,weapon) then return end
 player:SetAttribute('RunClass',class);player:SetAttribute('RunWeapon',weapon)
 -- The lobby screens (LobbyUI, ArmoryUI, RunSetupUI) show the pick from these.
 player:SetAttribute('LoadoutClass',class);player:SetAttribute('LoadoutWeapon',weapon)
end
-- Back from LEAVE WITH PARTY (2026-10-03): the match server sends the party home in one teleport
-- with {leader, ids} in its teleport data (MatchService.toLobby), and the party is put back together
-- here with the leader first. Teleport data passes through the client, so a member is only added
-- when both their data and the leader's list each other. Example: Ana (leader) and Ben land, each
-- listing both -> party {Ana, Ben}; Cal claiming to be in it is listed by neither -> not added.
local homecoming={} -- userId -> {leader=,ids={[userId]=true},at=}, kept 60 s
local function regroup(player)
 local ok,data=pcall(function() return player:GetJoinData().TeleportData end)
 local claim=ok and type(data)=='table' and type(data.party)=='table' and data.party or nil
 if not claim or type(claim.leader)~='number' or type(claim.ids)~='table' then return end
 local mine={leader=claim.leader,ids={},at=now()}
 for _,id in claim.ids do if type(id)=='number' then mine.ids[id]=true end end
 if not mine.ids[player.UserId] or not mine.ids[claim.leader] then return end
 for id,c in homecoming do if now()-c.at>60 then homecoming[id]=nil end end
 homecoming[player.UserId]=mine
 local leader=mine.leader
 local function agree(id) local c=homecoming[id];return c~=nil and c.leader==leader and c.ids[player.UserId]==true and mine.ids[id]==true and Players:GetPlayerByUserId(id)~=nil end
 local function add(id) if parties:invite(leader,id,now()) then parties:accept(id,leader,now()) end end
 if player.UserId==leader then for id in mine.ids do if id~=leader and agree(id) then add(id) end end
 elseif agree(leader) then add(player.UserId) end
 publishParties()
end
local function attach(player)
 task.spawn(restoreLoadout,player)
 task.spawn(regroup,player)
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
-- A teleport that failed after it started (TeleportInitFailed): the player is still here.
Match.onTeleportFailed=function(p,message) travelling[p]=nil;setupRemote:FireClient(p,'Result',false,message) end
Players.PlayerAdded:Connect(attach)
for _,p in Players:GetPlayers() do attach(p) end
Players.PlayerRemoving:Connect(function(p)
 state:leave(p.UserId,now());last[p]=nil;stepOff[p]=nil;travelling[p]=nil;publish()
 parties:remove(p.UserId);lastParty[p]=nil;publishParties()
end)

local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.1 then return end;elapsed=0
 for _,p in Players:GetPlayers() do
  -- A departing player must not rejoin the pad while destination streaming yields.
  if travelling[p] or p:GetAttribute('MapTravelPending') then continue end
  local char,hrp=alive(p)
  local lobby=hrp~=nil and inLobby(hrp)
  p:SetAttribute('LobbyPreviewActive',lobby)
  if lobby and p:GetAttribute('StudioArea')~='Lobby' then p:SetAttribute('StudioArea','Lobby') end
  if lobby and hrp.Position.Y<origin.Y-50 then char:PivotTo(areaSpawn('Lobby',0)) end
  local index=state.membership[p.UserId]
  if index and state.queues[index].locked then continue end
  local under=lobby and padUnder(hrp) or nil
  if stepOff[p] and under~=stepOff[p] then stepOff[p]=nil end
  -- Queued players are locked to their pad until they press LEAVE. Dying or being moved out of
  -- the lobby (travel) still ends the queue; anyone who got off the pad is put back on it.
  if index and not lobby then leave(p);index=nil
  elseif index and pads[index] and not nearPad(hrp,pads[index]) then char:PivotTo(CFrame.new(pads[index].center+Vector3.new(0,3.5,0))*(hrp.CFrame-hrp.Position)) end
  if under and not index and stepOff[p]~=under then
   if state:join(p.UserId,under,now()) then setQueue(p);pullParty(p,under)
   elseif state.queues[under].solo then
    -- Someone else's Private pad: say so once (stepOff holds until they walk off).
    stepOff[p]=under;setupRemote:FireClient(p,'Result',false,'That portal is private')
   end
  end
 end
 if parties:expire(now()) then publishParties() end
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
