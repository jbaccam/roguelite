-- First-join tutorial, server side (plans/2026-10-03-tutorial-design.md).
--   Lobby servers: a player who hasn't played the tutorial run yet (ProfileTutorial 'Run') goes
--     straight to a solo tutorial match (MatchService.launch with {tutorial=true}).
--   Match servers: MatchService sets RogueliteCombat.TutorialRun from the match entry; this script
--     then runs it. MatchService starts wave 1 once the player's loading screen is gone, plus
--     WELCOME_SECONDS for Eggbert's welcome.
--   Studio's Combined role: only with Workspace.StudioTutorial=true (otherwise ProfileService
--     counts every Studio profile as done); the player is put in the Pine Valley arena as a
--     Brawler with the Frying Pan and wave 1 starts the same way.
-- The tutorial is the normal run with ShopService.tutorial (waves, the Glock offer, no starting
-- shards, no shop timer), worth-5 crystals, the boss on wave 3 with a fixed health, no respawns,
-- and each wave ending once its enemies are dead. RogueliteMeta pays the reward and ends the run
-- after the boss wave; the mode switches off once nobody is left in the run.
-- Unsandboxed, like RogueliteMeta: it requires MatchService and ProfileService users.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local RS=game:GetService('ReplicatedStorage')
local SSS=game:GetService('ServerScriptService')
local Role=require(SSS:WaitForChild('ServerRole'))
local combat=RS:WaitForChild('RogueliteCombat')
local Config=require(combat:WaitForChild('TutorialConfig'))
local studio=RunService:IsStudio()

local function profileLoaded(p)
 local t0=os.clock()
 while p.Parent==Players and p:GetAttribute('ProfileLoaded')~=true and os.clock()-t0<90 do task.wait(.25) end
 return p.Parent==Players and p:GetAttribute('ProfileLoaded')==true
end
local function needsRun(p) return p:GetAttribute('ProfileTutorial')=='Run' end

-- Lobby: send them to their tutorial match. Three tries; if it can't start they play from the
-- lobby and the next join tries again.
if Role.get()=='Lobby' then
 if studio then return end -- Studio can't teleport (MatchService)
 local Match=require(SSS:WaitForChild('MatchService'))
 local function send(p)
  if not profileLoaded(p) then return end
  for attempt=1,3 do
   if p.Parent~=Players or not needsRun(p) then return end
   local ok,why=Match.launch({p},Config.Map,'Normal',{[p.UserId]={class=Config.Class,weapon=Config.Weapon}},{tutorial=true})
   if ok then return end
   warn('TutorialDirector: tutorial launch failed:',why)
   task.wait(4*attempt)
  end
 end
 Players.PlayerAdded:Connect(function(p) task.spawn(send,p) end)
 for _,p in Players:GetPlayers() do task.spawn(send,p) end
 return
end

local Shop=require(SSS:WaitForChild('ShopService'))
local Shards=require(SSS:WaitForChild('ShardDropService'))
local Death=require(combat:WaitForChild('ZombieDeath'))
local run=RS:WaitForChild('RogueliteRunState') -- ShopService (required above) creates it

-- The run mode. Attributes it sets are put back as they were when it ends.
local active=false
local saved={}
local function set(name,value)
 if saved[name]==nil then saved[name]={combat:GetAttribute(name)} end
 combat:SetAttribute(name,value)
end
local function apply(on)
 if on==active then return end
 active=on
 if on then
  Shop.tutorial={startShards=Config.START_SHARDS,waves=Config.Waves,offers=Config.Offers,waveSeconds=3600,noShopTimer=true}
  Shards.killValue=Config.CRYSTAL_VALUE
  set('HammerBossWave',Config.BOSS_WAVE);set('TutorialBossHealth',Config.BOSS_HP);set('WaveNoRespawn',true)
  -- Anyone already waiting for wave 1 got the normal starting crystals: none in the tutorial.
  if Shop.wave==1 and Shop.phase=='Shop' then
   for p,s in Shop.states do s.shards=Config.START_SHARDS;s.revision+=1;Shop.publish(p) end
  end
 else
  Shop.tutorial=nil;Shards.killValue=nil
  for name,v in saved do combat:SetAttribute(name,v[1]) end
  table.clear(saved)
 end
end
combat:GetAttributeChangedSignal('TutorialRun'):Connect(function() apply(combat:GetAttribute('TutorialRun')==true) end)
apply(combat:GetAttribute('TutorialRun')==true)

-- Each wave ends once its enemies are dead (they never respawn: WaveNoRespawn), or when none are
-- left 6 s in (one fell off the map), or after MAX_WAVE_SECONDS. Ending a wave sets WaveEndsAt to
-- now, so a boss still holds it open (ShopService) until he and his crystals are done.
local deaths,waveKey,waveStarted=0,nil,0
Death.onDeath=function(npc)
 -- Runs in the killer's (often sandboxed) thread: only count here.
 if active and Shop.phase=='Combat' and not npc:GetAttribute('IsBoss') and string.match(npc.Name,'^Zombie_%d+$') then deaths+=1 end
end
local function waveEnemiesLeft()
 local folder=workspace:FindFirstChild('RogueliteEnemies');if not folder then return 0 end
 local n=0
 for _,npc in folder:GetChildren() do
  if string.match(npc.Name,'^Zombie_%d+') and not npc:GetAttribute('DeathPopped') then n+=1 end
 end
 return n
end
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.25 then return end;elapsed=0
 if not active then return end
 -- Won (RogueliteMeta): once everyone has left the run for the results, the mode goes off.
 if run:GetAttribute('TutorialWon') and next(Shop.members)==nil then
  run:SetAttribute('TutorialWon',nil);combat:SetAttribute('TutorialRun',nil);apply(false)
  return
 end
 if Shop.phase~='Combat' then waveKey=nil;return end
 local key=Shop.runId..':'..Shop.wave
 if key~=waveKey then waveKey=key;deaths=0;waveStarted=os.clock() end
 -- Paused (the pause screen or a revive): the clock is held; leave it alone.
 local ends=run:GetAttribute('WaveEndsAt')
 if type(ends)~='number' or combat:GetAttribute('RunPaused')==true then return end
 local now=workspace:GetServerTimeNow()
 if ends<=now then return end -- already ending
 local wave=Config.Waves[Shop.wave];local quota=wave and wave.count or 0
 local age=os.clock()-waveStarted
 if deaths>=quota or (age>6 and waveEnemiesLeft()==0) or age>Config.MAX_WAVE_SECONDS then
  run:SetAttribute('WaveEndsAt',now)
 end
end)

-- Studio's Combined role: play the tutorial run right here, for a fresh profile with
-- Workspace.StudioTutorial=true, or from the admin panel (ServerStorage.TutorialControl below).
if studio and Role.get()=='Combined' then
 local Profiles=require(SSS:WaitForChild('ProfileService'))
 -- Into the Pine Valley arena as a Brawler with the Frying Pan; wave 1 once they're in the run.
 local function startHere(p)
  for q in Shop.members do if q~=p then return false,'Another run is going here' end end
  local char=p.Character;local h=char and char:FindFirstChildOfClass('Humanoid')
  if not h or h.Health<=0 then return false,'Respawn first' end
  p:SetAttribute('RunResult',nil)
  Role.setMap(Config.Map);combat:SetAttribute('RunDifficulty','Normal')
  run:SetAttribute('TutorialWon',nil)
  combat:SetAttribute('TutorialRun',true);apply(true)
  p:SetAttribute('RunClass',Config.Class);p:SetAttribute('RunWeapon',Config.Weapon)
  task.wait() -- RogueliteCombat takes the starter from RunWeapon (deferred signals)
  Shop.resetRun()
  local spawn=Role.playerSpawn()
  p:SetAttribute('StudioArea','Arena')
  if spawn then char:PivotTo(CFrame.new(spawn.Position+Vector3.new(0,4,0))) end
  task.spawn(function()
   local t0=os.clock()
   while p.Parent==Players and not Shop.isMember(p) and os.clock()-t0<20 do task.wait(.25) end
   -- On a first join their loading screen still covers the arena (MatchService waits the same way).
   while p.Parent==Players and p:GetAttribute('ClientLoaded')~=true and os.clock()-t0<30 do task.wait(.25) end
   task.wait(Config.WELCOME_SECONDS) -- the welcome line first
   if active and Shop.isMember(p) and Shop.phase=='Shop' and Shop.wave==1 then Shop.startFirstWave() end
  end)
  return true,'Tutorial started'
 end
 -- Out of it: the mode off, a fresh run, back to the lobby spawn.
 local function endHere(p)
  combat:SetAttribute('TutorialRun',nil);run:SetAttribute('TutorialWon',nil);combat:SetAttribute('CinematicUntil',nil);apply(false)
  Shop.resetRun()
  p:SetAttribute('RunResult',nil)
  local lobby=workspace:FindFirstChild('RogueliteLobby');local spawn=lobby and lobby:FindFirstChild('LobbySpawn')
  local char=p.Character
  p:SetAttribute('StudioArea','Lobby')
  if char and spawn then char:PivotTo(CFrame.new(spawn.Position+Vector3.new(0,4,0))) end
 end
 local function start(p)
  if not profileLoaded(p) or not needsRun(p) then return end
  if not (p.Character and p.Character:FindFirstChildOfClass('Humanoid')) then p.CharacterAdded:Wait() end
  local ok,why=startHere(p)
  if not ok then warn('TutorialDirector: no tutorial:',why) end
 end
 Players.PlayerAdded:Connect(function(p) task.spawn(start,p) end)
 for _,p in Players:GetPlayers() do task.spawn(start,p) end
 -- The admin panel's Tutorial buttons (AdminService checks the developer first):
 --   Start: progress back to the start (reward unpaid) and the run from the top
 --   Lobby: the run skipped: reward paid now, then the lobby steps (chests, Armory, offer, Play)
 --   End:   tutorial done, back to normal play in the lobby
 local control=game:GetService('ServerStorage'):FindFirstChild('TutorialControl') or Instance.new('BindableFunction')
 control.Name='TutorialControl'
 control.OnInvoke=function(what,p)
  if typeof(p)~='Instance' or not p:IsA('Player') then return false,'No player' end
  if what=='Start' then
   if not Profiles.tutorialAdmin(p,'Run') then return false,'Profile not ready' end
   return startHere(p)
  elseif what=='Lobby' then
   endHere(p)
   if not Profiles.tutorialAdmin(p,'Chests') then return false,'Profile not ready' end
   return true,'Tutorial lobby part: open your chests'
  elseif what=='End' then
   endHere(p);Profiles.tutorialAdmin(p,'Done')
   return true,'Tutorial ended'
  end
  return false,'Unknown tutorial action'
 end
 control.Parent=game:GetService('ServerStorage')
end
