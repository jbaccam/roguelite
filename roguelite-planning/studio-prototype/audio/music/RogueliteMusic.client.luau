-- StarterPlayerScripts.RogueliteMusic: run music. Unsandboxed, because sandboxed scripts can't
-- play audio. Presentation only; it reads replicated state and decides nothing.
--   Lobby: silent.
--   In a run: the regular playlist, shuffled, never the same track twice in a row, crossfading.
--   Boss playlist while a boss is alive, and in Endless (past Rules.WinWave) when it gets intense:
--   your health under LOW_HEALTH or at least MOB_SWARM mobs alive at once. Intensity holds for
--   INTENSE_HOLD seconds after the last trigger so the music doesn't flip back and forth.
-- Tracks: audio/music/music_ids.json (Pixabay, loudness-matched by process_music.py).
-- The Settings music slider (Setting_MusicVolume, 0-1) scales the RogueliteMusic SoundGroup.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local SoundService=game:GetService('SoundService')
local TweenService=game:GetService('TweenService')
local CollectionService=game:GetService('CollectionService')
local player=Players.LocalPlayer
local Rules=require(RS:WaitForChild('RunSetupRules'))

-- Roblox moderation rejected regular_02, regular_06, regular_07 and boss_05 (music_ids.json);
-- regular_12 and boss_06 were added in their place.
local TRACKS={
 regular={85713999753984,110092951263724,114896912451477,82696866610833,
  87872254035105,77058244722116,109700680105754,71742442864373,131272353616369},
 boss={115913771603981,129688736633367,115583045438655,99558552359046,89877873691224},
}
local VOLUME=.24      -- track volume at 100% on the music slider (0.4, then 0.3, were too loud)
local FADE=1.5        -- seconds for fades and crossfades
local LOW_HEALTH=.3   -- Endless: under 30% health counts as intense
local MOB_SWARM=40    -- Endless: this many living mobs at once counts as intense
local INTENSE_HOLD=12 -- seconds boss music stays on after the last intense moment
local LOAD_TIMEOUT=8  -- a track that hasn't loaded by then (e.g. still in moderation) is skipped

local group=SoundService:FindFirstChild('RogueliteMusic') or Instance.new('SoundGroup')
group.Name='RogueliteMusic';group.Parent=SoundService
local function applyVolume()
 local v=player:GetAttribute('Setting_MusicVolume');group.Volume=type(v)=='number' and math.clamp(v,0,1) or 1
end
applyVolume();player:GetAttributeChangedSignal('Setting_MusicVolume'):Connect(applyVolume)

local current -- {mode=, sound=, id=, started=}
local last={}
local failed={} -- tracks that never loaded this session; skipped from then on
-- Shuffle bag per playlist: every track plays once before any repeats, and a new bag never opens
-- with the track that just played. Random.new() is seeded from entropy; math.random gave the same
-- opening picks every session, so the first boss always got the same song.
local rng=Random.new()
local bags={}
local function pick(mode)
 local bag=bags[mode]
 while bag and #bag>0 and failed[bag[#bag]] do table.remove(bag) end
 if not bag or #bag==0 then
  bag={}
  for _,id in TRACKS[mode] do if not failed[id] then table.insert(bag,id) end end
  if #bag==0 then bag=table.clone(TRACKS[mode]) end
  for i=#bag,2,-1 do local j=rng:NextInteger(1,i);bag[i],bag[j]=bag[j],bag[i] end
  if #bag>1 and bag[#bag]==last[mode] then bag[1],bag[#bag]=bag[#bag],bag[1] end
  bags[mode]=bag
 end
 local id=table.remove(bag)
 last[mode]=id;return id
end
local function start(mode)
 local id=pick(mode)
 local s=Instance.new('Sound');s.Name='Music_'..mode;s.SoundId='rbxassetid://'..id
 s.Volume=0;s.SoundGroup=group;s.Parent=SoundService;s:Play()
 TweenService:Create(s,TweenInfo.new(FADE),{Volume=VOLUME}):Play()
 return {mode=mode,sound=s,id=id,started=os.clock()}
end
local function fadeOut(entry)
 if not entry then return end
 local s=entry.sound
 TweenService:Create(s,TweenInfo.new(FADE),{Volume=0}):Play()
 task.delay(FADE+.1,function() s:Destroy() end)
end

local intenseUntil=0
local function alive(m) local h=m:FindFirstChildOfClass('Humanoid');return h and h.Health>0 end
local function wanted()
 if player:GetAttribute('LobbyPreviewActive')==true then return nil end -- in the lobby
 local run=RS:FindFirstChild('RogueliteRunState');if not run then return nil end
 local mobs,boss=0,false
 for _,m in CollectionService:GetTagged('RogueliteZombie') do
  if m:IsDescendantOf(workspace) and not m:GetAttribute('LobbyDummy') and not m:GetAttribute('PracticeTarget') and alive(m) then
   mobs+=1;if m:GetAttribute('IsBoss') then boss=true end
  end
 end
 if boss then return 'boss' end
 local now=os.clock()
 if (run:GetAttribute('Wave') or 1)>(Rules.WinWave or 20) and run:GetAttribute('Phase')=='Combat' then
  local h=player.Character and player.Character:FindFirstChildOfClass('Humanoid')
  local low=h and h.Health>0 and h.MaxHealth>0 and h.Health/h.MaxHealth<LOW_HEALTH
  if low or mobs>=MOB_SWARM then intenseUntil=now+INTENSE_HOLD end
 end
 return now<intenseUntil and 'boss' or 'regular'
end

-- Give the lobby up to 5 s to mark a joining player, so the lobby doesn't start with run music.
local joined=os.clock()
while player:GetAttribute('LobbyPreviewActive')==nil and os.clock()-joined<5 do task.wait(.25) end
-- The saved music volume arrives with the profile (ProfileService sets Setting_MusicVolume before
-- ProfileLoaded): wait for it, up to 8 s, so someone who turned music off never hears a burst of
-- it on joining a match (launch audit U1).
while player:GetAttribute('ProfileLoaded')~=true and os.clock()-joined<8 do task.wait(.25) end
while true do
 local mode=wanted()
 if (current and current.mode)~=mode then
  fadeOut(current);current=mode and start(mode) or nil
 elseif current then
  -- Crossfade into the next track of the same playlist just before this one ends.
  local s=current.sound
  if not s.IsLoaded and os.clock()-current.started>LOAD_TIMEOUT then
   failed[current.id]=true;local old=current;current=start(mode);fadeOut(old)
  elseif s.IsLoaded and (not s.Playing or (s.TimeLength>FADE*2 and s.TimePosition>=s.TimeLength-FADE)) then
   local old=current;current=start(mode);fadeOut(old)
  end
 end
 task.wait(.5)
end
