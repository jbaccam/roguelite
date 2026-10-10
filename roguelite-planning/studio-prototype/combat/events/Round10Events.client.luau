-- StarterPlayerScripts.Round10Events (unsandboxed: it plays music and drives the camera). The client
-- side of the round 10 events (Round10Service): presentation only, decides nothing.
--   workspace.Round10Event appears -> the event's cinematic (Round10Intro), its objective panel and
--     pointers (Round10Hud), its lighting (Blood Moon) and its music (Crab Rave).
--   RogueliteRunState EventPhase 'Complete' -> EVENT CLEARED; the music ends on a short fade.
--   EventCue -> the cue line (PACK EMPOWERED).
--   The folder going (the clear's wave end, an abort, leaving) -> everything restored: camera,
--     lighting, music (the playlist comes back), panel, pointers. Also on respawn and on any error.
-- World effects (Bloaters, vents, rushes, howls, tombs) run all the time through Round10World.
local Players=game:GetService('Players')
local Lighting=game:GetService('Lighting')
local SoundService=game:GetService('SoundService')
local TweenService=game:GetService('TweenService')
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Defs=require(combat:WaitForChild('Round10Defs'))
local Intro=require(combat:WaitForChild('Round10Intro'))
local Hud=require(combat:WaitForChild('Round10Hud'))
local World=require(combat:WaitForChild('Round10World'))
local player=Players.LocalPlayer
task.spawn(World.start)

-- ── Blood moon (Frozen Pass): a red grade and a red moon over the alpha's rim, faded in and out ──
local moon
local function bloodMoon(folder)
 local cc=Instance.new('ColorCorrectionEffect');cc.Name='Round10BloodMoon';cc.TintColor=Color3.new(1,1,1);cc.Parent=Lighting
 TweenService:Create(cc,TweenInfo.new(1.2),{TintColor=Color3.fromRGB(255,196,190),Saturation=.08,Contrast=.06,Brightness=-.04}):Play()
 local center=folder:GetAttribute('Center');local focus=folder:GetAttribute('Focus') or center;local players=folder:GetAttribute('Players') or center
 local dir=Vector3.new((focus-players).X,0,(focus-players).Z);dir=(dir.Magnitude>1 and dir.Unit or Vector3.new(0,0,-1))+Vector3.new(0,.55,0)
 local part=Instance.new('Part');part.Name='Round10Moon';part.Anchored=true;part.CanCollide=false;part.CanQuery=false;part.CanTouch=false;part.Transparency=1;part.Size=Vector3.one
 part.CFrame=CFrame.new((players or Vector3.zero)+dir.Unit*700);part.Parent=workspace
 local g=Instance.new('BillboardGui');g.Size=UDim2.fromScale(150,150);g.LightInfluence=0;g.Brightness=2;g.MaxDistance=5000;g.Parent=part
 local glow=Instance.new('Frame');glow.AnchorPoint=Vector2.new(.5,.5);glow.Position=UDim2.fromScale(.5,.5);glow.Size=UDim2.fromScale(1.5,1.5);glow.BackgroundColor3=Color3.fromRGB(255,60,50);glow.BackgroundTransparency=.82;glow.BorderSizePixel=0;glow.Parent=g
 Instance.new('UICorner',glow).CornerRadius=UDim.new(1,0)
 local disc=Instance.new('Frame');disc.Size=UDim2.fromScale(1,1);disc.BackgroundColor3=Color3.fromRGB(230,58,48);disc.BorderSizePixel=0;disc.Parent=g
 Instance.new('UICorner',disc).CornerRadius=UDim.new(1,0)
 local grad=Instance.new('UIGradient');grad.Rotation=35;grad.Color=ColorSequence.new(Color3.fromRGB(255,150,120),Color3.fromRGB(170,30,30));grad.Parent=disc
 moon={cc=cc,part=part}
end
local function clearMoon()
 if not moon then return end
 local m=moon;moon=nil
 TweenService:Create(m.cc,TweenInfo.new(1),{TintColor=Color3.new(1,1,1),Saturation=0,Contrast=0,Brightness=0}):Play()
 task.delay(1.05,function() m.cc:Destroy() end);m.part:Destroy()
end

-- ── Event music: the playlist is ducked (RogueliteMusic reads EventMusic on its group) ─────────
local music
local function musicGroup()
 local g=SoundService:FindFirstChild('RogueliteMusic')
 if not g then g=Instance.new('SoundGroup');g.Name='RogueliteMusic';g.Parent=SoundService end
 return g
end
local function stopMusic(fade)
 local m=music;music=nil;musicGroup():SetAttribute('EventMusic',nil)
 if not m then return end
 TweenService:Create(m,TweenInfo.new(fade or 1.2),{Volume=0}):Play()
 task.delay((fade or 1.2)+.1,function() m:Destroy() end)
end
local function startMusic(spec,introStart)
 if not spec or not spec.soundId then return end
 stopMusic(.1)
 local s=Instance.new('Sound');s.Name='Round10Music';s.SoundId=type(spec.soundId)=='number' and 'rbxassetid://'..spec.soundId or spec.soundId
 s.Volume=spec.volume or .5;s.SoundGroup=musicGroup();s.Looped=true
 -- off: 0 for the 36.7 s segment, fullOffset when the upload is the whole song (decided once it loads).
 local off=0
 local function region() pcall(function() s.PlaybackRegionsEnabled=true;s.LoopRegion=NumberRange.new(spec.loopStart+off,spec.loopEnd+off) end) end
 region()
 s.Parent=SoundService
 music=s;musicGroup():SetAttribute('EventMusic',true)
 -- The shared timeline: the drop's first beat on the DJ's claw snap, whenever this client joined.
 local function position()
  local p=spec.accent-spec.accentAtIntro+(workspace:GetServerTimeNow()-introStart)
  if p>spec.loopEnd then p=spec.loopStart+(p-spec.loopStart)%(spec.loopEnd-spec.loopStart) end
  return math.max(0,p)+off
 end
 task.spawn(function()
  local waited=0
  while music==s and not s.IsLoaded and waited<6 do waited+=task.wait(.1) end
  if music~=s then return end
  if not s.IsLoaded then stopMusic(.1);return end -- unavailable or still in moderation: the playlist plays
  if s.TimeLength>60 then off=spec.fullOffset or 0;region() end
  s.TimePosition=position();s:Play()
 end)
end

-- ── One event at a time ──────────────────────────────────────────────────────────────────────────
local active -- {folder, def, id}
local function finish()
 local a=active;active=nil
 Intro.stop();Hud.hide();clearMoon();stopMusic(1.2)
 if a and a.conns then for _,c in a.conns do c:Disconnect() end end
end
local function begin(folder)
 if active and active.folder==folder then return end
 finish()
 local id=folder:GetAttribute('EventId');local def=id and Defs.byId(id)
 if not def then return end
 local a={folder=folder,def=def,id=id,conns={}};active=a
 local run=RS:WaitForChild('RogueliteRunState',10)
 task.spawn(function() local ok,err=pcall(Intro.play,folder);if not ok then warn('Round10Events intro: '..tostring(err)) end end)
 pcall(Hud.show,def,folder)
 if id=='BloodMoonHunt' then pcall(bloodMoon,folder) end
 if def.music then pcall(startMusic,Defs.Music and Defs.Music[def.music],folder:GetAttribute('IntroStart') or workspace:GetServerTimeNow()) end
 local function phase()
  if active~=a or not run then return end
  if run:GetAttribute('EventPhase')=='Complete' and not a.cleared then
   a.cleared=true;pcall(Hud.cleared);stopMusic(2);clearMoon()
  end
 end
 local lastCue
 local function cue()
  local raw=run and run:GetAttribute('EventCue')
  if type(raw)=='string' and raw~=lastCue then lastCue=raw;local text=raw:match('^(.-)|');pcall(Hud.cue,text or raw) end
 end
 if run then
  table.insert(a.conns,run:GetAttributeChangedSignal('EventPhase'):Connect(phase))
  table.insert(a.conns,run:GetAttributeChangedSignal('EventCue'):Connect(cue))
  phase()
 end
 table.insert(a.conns,folder.AncestryChanged:Connect(function() if not folder:IsDescendantOf(workspace) and active==a then finish() end end))
end
workspace.ChildAdded:Connect(function(c) if c.Name=='Round10Event' and c:IsA('Folder') then task.defer(begin,c) end end)
workspace.ChildRemoved:Connect(function(c) if active and active.folder==c then finish() end end)
local existing=workspace:FindFirstChild('Round10Event');if existing then task.defer(begin,existing) end
-- A respawn never leaves the camera on a cinematic (UITheme cameraHeal also self-heals).
player.CharacterAdded:Connect(function() if not active then Intro.stop() end end)
