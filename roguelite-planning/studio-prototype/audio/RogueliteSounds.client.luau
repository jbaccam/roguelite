-- StarterPlayerScripts.RogueliteSounds: plays every roguelite sound effect except the chest's own.
-- It must stay unsandboxed. Sandboxed scripts lack the Audio capability, so they call UITheme's
-- T.sound(name), which fires ReplicatedStorage.RogueliteSoundCue for this script to play.
-- Presentation only: reads replicated attributes and remote events, never decides outcomes.
-- Files, sources and processing: roguelite-planning/studio-prototype/audio/ (uploaded_ids.json).
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local SoundService=game:GetService('SoundService')
local ContentProvider=game:GetService('ContentProvider')
local TweenService=game:GetService('TweenService')
local RunService=game:GetService('RunService')
local player=Players.LocalPlayer
local combat=RS:WaitForChild('RogueliteCombat')
local Motion=require(combat:WaitForChild('WeaponMotion'))
local ShardMotion=require(combat:WaitForChild('ShardMotion'))

-- Volume groups for the Settings sliders (Setting_SfxVolume, 0-1, default 1). Every sound here
-- plays through RogueliteSFX; ChestFX, SkillTreeUI and BossPresentation join it too.
-- RogueliteMusic owns the RogueliteMusic group the same way.
local sfxGroup=SoundService:FindFirstChild('RogueliteSFX') or Instance.new('SoundGroup')
sfxGroup.Name='RogueliteSFX';sfxGroup.Parent=SoundService
local function applySfxVolume()
 local v=player:GetAttribute('Setting_SfxVolume');sfxGroup.Volume=type(v)=='number' and math.clamp(v,0,1) or 1
end
applySfxVolume();player:GetAttributeChangedSignal('Setting_SfxVolume'):Connect(applySfxVolume)

local ID={
 swing_light=110995909999492,swing_blade=131695208823730,swing_pan=132910373775599,
 swing_heavy=86064050435898,swing_heaviest=71697578984386,swing_soft=133587546110540,
 hit_blunt=126552999279978,hit_thud=100368763538547,hit_punch=87873993825984,
 shot_pistol=139261460675652,shot_draco=82326169888700,shot_shotgun=74898444247244,
 shot_rocket=132175910958130,shot_magic_a=135375221005856,shot_magic_b=119292797745740,
 shot_magic_c=81221579347540,zap=76417564351871,shot_fart=137155830413625,
 mob_zombie=137815495955079,mob_crab=72782149017873,mob_skeleton=137871010589209,
 mob_ghost=114184431473436,mob_goo=122369988012288,
 ui_click=108497767890698,ui_equip=97493789475544,ui_error=127419360737876,
 ui_purchase=81834205196662,ui_upgrade=99405716010813,
 player_damage=107723670570555,player_death=139324006502013,
 washer_loop=131922039707440,crystal_pickup=119199604552182,
 -- Roblox library sounds the map bosses already use (bosses/BossVfxAssets): Godly specials.
 water_bubbles=9120309620,thunder_crack=9114157695,ghost_rise=9120733055,
}

-- Weapon id (WeaponCatalog) -> attack sound. pitch reshapes one file for several weapons:
-- above 1 sounds lighter and quicker, below 1 heavier. hit = optional layer when it lands.
-- loop = a continuous weapon's seamless loop (loopLength = one copy, in seconds).
-- Vacuum Cleaner has no sound yet.
local WEAPON={
 ['00']={sound='shot_pistol',pitch=1,volume=.5},                                  -- Glock
 ['01']={sound='swing_pan',pitch=1,volume=.55,hit='hit_blunt',hitPitch=1.1,hitVolume=.35}, -- Frying Pan
 ['02']={sound='swing_light',pitch=1.2,volume=.5},                                -- Nunchucks
 ['03']={sound='swing_blade',pitch=1.1,volume=.55},                               -- Katana
 ['04']={sound='swing_light',pitch=.9,volume=.55},                                -- Kusarigama
 ['05']={sound='swing_soft',pitch=1.2,volume=.5},                                 -- Spatula
 ['06']={sound='swing_heavy',pitch=1,volume=.55,hit='hit_blunt',hitPitch=1,hitVolume=.4}, -- Baseball Bat
 ['07']={sound='shot_draco',pitch=1,volume=.35},                                  -- Draco (fires fast)
 ['08']={sound='shot_fart',pitch=1,volume=.5},                                    -- Fart Gun
 ['09']={sound='shot_shotgun',pitch=1,volume=.5},                                 -- Shotgun
 ['10']={sound='shot_rocket',pitch=1.35,volume=.4},                               -- T-Shirt Cannon
 ['11']={sound='shot_rocket',pitch=1,volume=.55},                                 -- Rocket Launcher
 ['12']={sound='swing_light',pitch=.85,volume=.5},                                -- Boomerang
 ['13']={sound='swing_blade',pitch=1.35,volume=.45},                              -- Kunai
 ['14']={sound='swing_soft',pitch=.9,volume=.5},                                  -- Molotov
 ['15']={sound='swing_soft',pitch=1.3,volume=.45},                                -- Egg
 ['16']={sound='swing_soft',pitch=.9,volume=.5,hit='hit_punch',hitPitch=.9,hitVolume=.35}, -- Steak
 ['17']={sound='swing_soft',pitch=1.4,volume=.45},                                -- Rubber Duck
 ['18']={sound='swing_blade',pitch=1.5,volume=.35,count=3},                       -- Deck of Cards (three cards)
 ['19']={sound='swing_soft',pitch=1.25,volume=.45,hit='hit_punch',hitPitch=1.1,hitVolume=.45}, -- Boxing Gloves
 ['20']={sound='swing_heaviest',pitch=1,volume=.55,hit='hit_thud',hitPitch=.9,hitVolume=.4}, -- Cinder Block
 ['21']={sound='swing_light',pitch=1.3,volume=.45},                               -- Yo-Yo
 ['22']={sound='swing_heaviest',pitch=.9,volume=.55},                             -- Bowling Ball
 ['23']={sound='swing_heavy',pitch=1.15,volume=.5},                               -- Bowling Pin
 ['24']={sound='shot_pistol',pitch=1.4,volume=.3},                                -- Nail Gun
 ['25']={sound='swing_heaviest',pitch=.8,volume=.6,hit='hit_thud',hitPitch=.75,hitVolume=.45}, -- Wrecking Ball
 ['26']={sound='swing_pan',pitch=.9,volume=.55,hit='hit_blunt',hitPitch=1.1,hitVolume=.35}, -- Shovel
 ['27']={sound='swing_soft',pitch=1,volume=.5},                                   -- Paint Roller
 ['29']={loop='washer_loop',loopLength=3.4,volume=.8},                            -- Power Washer (continuous)
 ['30']={sound='shot_magic_a',pitch=1,volume=.45},                                -- Magic Staff
 ['31']={sound='swing_heavy',pitch=.85,volume=.6,hit='zap',hitPitch=1,hitVolume=.35}, -- Mjolnir
 ['32']={sound='swing_blade',pitch=.9,volume=.55},                                -- Excalibur
 ['33']={sound='shot_magic_c',pitch=.8,volume=.5},                                -- Pandora's Box
 ['34']={sound='shot_magic_b',pitch=.85,volume=.45},                              -- Medusa's Head
 ['35']={sound='zap',pitch=1,volume=.4},                                          -- Crystal Ball
 -- Godly (plans/2026-10-01-G): heavier, lower takes on the kit; specials add layers (GodlyFX below).
 ['36']={sound='swing_heaviest',pitch=.8,volume=.65,hit='hit_thud',hitPitch=.8,hitVolume=.35}, -- Reaper's Scythe
 ['37']={sound='swing_heavy',pitch=.95,volume=.6,hit='hit_blunt',hitPitch=.85,hitVolume=.3},  -- Poseidon's Trident
 ['38']={sound='shot_magic_a',pitch=1.25,volume=.5},                              -- Storm Bow
 ['39']={sound='swing_blade',pitch=1.3,volume=.55},                               -- Shadow Daggers
 ['40']={sound='swing_blade',pitch=.75,volume=.6,hit='hit_thud',hitPitch=1.1,hitVolume=.3},  -- Vampire Blade
 ['41']={sound='zap',pitch=.75,volume=.5},                                        -- Ray Gun
}

-- EnemyId (EnemyCatalog) -> {hit sound, pitch, volume scale}. Crab-family crunches are
-- softened (user, 2026-09-29): kills play at the scale, ordinary hits at its square root. There is no death sound: the killing hit
-- plays the same splat a little louder and lower. Ice mobs borrow the crab crunch for now.
local MOB={
 ['regular-zombie']={'mob_zombie',1},['baby-zombie']={'mob_zombie',1.25},['tank-zombie']={'mob_zombie',.75},
 ['spitter-zombie']={'mob_zombie',1.05},['werewolf']={'mob_zombie',.9},['fire-goblin']={'mob_zombie',1.2},
 ['ember-spider']={'mob_zombie',1.15},
 ['crab']={'mob_crab',1,.45},['hermit-crab']={'mob_crab',.85,.45},['rock-throwing-crab']={'mob_crab',.95,.45},
 ['scorpion']={'mob_crab',1.1,.45},['obsidian-ogre']={'mob_crab',.7,.45},
 ['frozen-knight']={'mob_crab',.8,.45},['ice-elf']={'mob_crab',1.25,.45},
 ['skeleton']={'mob_skeleton',1},['bow-skeleton']={'mob_skeleton',1.05},
 ['mummy']={'mob_ghost',.9},['frost-ghost']={'mob_ghost',1.1},['ash-shaman']={'mob_ghost',1},
 ['snake']={'mob_goo',1.15},['lava-slime']={'mob_goo',1},
}
local MOB_DEFAULT={'mob_zombie',.85}

-- Named cues from UI modules (T.sound) and how loud each plays.
local CUE={ui_error=.5,ui_equip=.6,ui_purchase=.6,ui_upgrade=.6}

-- At most this many sounds of a kind start within a quarter second, so hordes stay crisp.
local LIMIT={weapon=12,mob=8,impact=6,ui=4,player=2,pickup=10}
local recent={}
local function allow(kind)
 local now=os.clock();local list=recent[kind];if not list then list={};recent[kind]=list end
 for i=#list,1,-1 do if now-list[i]>.25 then table.remove(list,i) end end
 if #list>=(LIMIT[kind] or 4) then return false end
 table.insert(list,now);return true
end

-- Every sound reuses a few already-loaded Sound objects per name, round-robin. A brand-new Sound
-- has to load before it makes a noise, which made clicks and splats start late.
-- Flat (2D) copies sit in SoundService; four cover overlapping plays (fast guns, card volleys).
-- Positioned copies each sit on their own attachment on Terrain, moved to the hit before playing.
local FLAT_COPIES,SPOT_COPIES=4,8
local spot={}
local function spotSound(name)
 local pool=spot[name]
 if not pool then
  pool={next=0}
  for i=1,SPOT_COPIES do
   local a=Instance.new('Attachment');a.Name='RogueliteSound_'..name..i;a.Parent=workspace.Terrain
   local s=Instance.new('Sound');s.Name=name;s.SoundId='rbxassetid://'..ID[name];s.SoundGroup=sfxGroup
   s.RollOffMode=Enum.RollOffMode.InverseTapered;s.RollOffMinDistance=40;s.RollOffMaxDistance=180;s.Parent=a
   pool[i]=s
  end
  spot[name]=pool
 end
 pool.next=pool.next%SPOT_COPIES+1
 return pool[pool.next]
end
local flat={}
local function flatSound(name)
 local pool=flat[name]
 if not pool then
  pool={next=0}
  for i=1,FLAT_COPIES do
   local s=Instance.new('Sound');s.Name=name;s.SoundId='rbxassetid://'..ID[name];s.SoundGroup=sfxGroup
   s.Parent=SoundService;pool[i]=s
  end
  flat[name]=pool
 end
 pool.next=pool.next%FLAT_COPIES+1
 return pool[pool.next]
end

-- region = {start s, end s}: play only that slice of a file holding several variations.
local function play(name,kind,volume,pitch,at,jitter,region)
 local id=ID[name];if not id or not allow(kind) then return end
 local s=at and spotSound(name) or flatSound(name)
 if at then s.Parent.WorldPosition=at end
 s.Volume=volume;s.PlaybackSpeed=(pitch or 1)*(1+(math.random()*2-1)*(jitter or .05))
 if region then
  s.PlaybackRegionsEnabled=true;s.PlaybackRegion=NumberRange.new(region[1],region[2]);s.TimePosition=region[1]
 else s.TimePosition=0 end
 s:Play()
end

-- Build the pools at start so they are loaded before the first hit or click: every one-shot
-- sound gets flat copies (UI, player, your own weapons), mob and impact sounds positioned ones.
-- Other players' weapon sounds build their positioned pool on first use.
task.spawn(function()
 local list={}
 for name in ID do
  if name~='washer_loop' then flatSound(name);for i=1,FLAT_COPIES do table.insert(list,flat[name][i]) end end
 end
 for _,name in {'mob_zombie','mob_crab','mob_skeleton','mob_ghost','mob_goo','hit_blunt','hit_thud','hit_punch','zap'} do
  spotSound(name);for i=1,SPOT_COPIES do table.insert(list,spot[name][i]) end
 end
 local loop=Instance.new('Sound');loop.SoundId='rbxassetid://'..ID.washer_loop;table.insert(list,loop)
 ContentProvider:PreloadAsync(list)
end)

-- Weapon attacks: the server stamps StartTime on a weapon slot at every attack, melee or ranged.
-- Swings are timed to the blade's active frames; shots and throws play at once.
local LEAD=.05
local states=combat:WaitForChild('PlayerStates')

-- Continuous weapons (Power Washer) hold one looping sound per weapon slot instead of a sound
-- per shot. Each attack keeps it alive; it fades out once attacks stop for LOOP_HOLD seconds.
-- The file holds three copies of a seamless loop and LoopRegion loops the middle one.
local LOOP_HOLD=.4
local loops={}
local function keepLoop(slot,w,mine,root)
 local l=loops[slot]
 if not l then
  local s=Instance.new('Sound');s.Name=w.loop;s.SoundId='rbxassetid://'..ID[w.loop];s.Volume=0;s.SoundGroup=sfxGroup
  s.Looped=true;s.PlaybackRegionsEnabled=true;s.LoopRegion=NumberRange.new(w.loopLength,w.loopLength*2)
  local holder
  if mine then s.Parent=SoundService
  else
   holder=Instance.new('Attachment');holder.Name='RogueliteLoop';holder.Parent=root
   s.RollOffMode=Enum.RollOffMode.InverseTapered;s.RollOffMinDistance=40;s.RollOffMaxDistance=180;s.Parent=holder
  end
  s:Play()
  TweenService:Create(s,TweenInfo.new(.06),{Volume=w.volume*(mine and 1 or .6)}):Play()
  l={sound=s,holder=holder};loops[slot]=l
 end
 l.last=os.clock()
end
RunService.Heartbeat:Connect(function()
 local now=os.clock()
 for slot,l in loops do
  if now-l.last>LOOP_HOLD or not l.sound.Parent then
   loops[slot]=nil
   local s,holder=l.sound,l.holder
   TweenService:Create(s,TweenInfo.new(.15),{Volume=0}):Play()
   task.delay(.16,function() s:Destroy();if holder then holder:Destroy() end end)
  end
 end
end)

local function onAttack(state,slot)
 local id=slot:GetAttribute('WeaponId');local w=WEAPON[id];local start=slot:GetAttribute('StartTime')
 if not w or type(start)~='number' then return end
 local mine=state.Name==tostring(player.UserId)
 local owner=not mine and Players:GetPlayerByUserId(tonumber(state.Name) or 0)
 local root=owner and owner.Character and owner.Character:FindFirstChild('HumanoidRootPart')
 if not mine and not root then return end
 if w.loop then keepLoop(slot,w,mine,root);return end
 local kind=slot:GetAttribute('AttackKind');local offset=0
 if kind=='Melee' or id=='32' then
  offset=Motion.attackTiming(id,kind,slot:GetAttribute('AttackStyle'))/(slot:GetAttribute('MotionRate') or 1)-LEAD
 end
 local wait=math.clamp(start+offset-workspace:GetServerTimeNow(),0,.5)
 for i=1,w.count or 1 do
  task.delay(wait+(i-1)*.06,function()
   play(w.sound,'weapon',w.volume*(mine and 1 or .6),w.pitch,root and root.Position,.05)
  end)
 end
end
local function watchState(state)
 local function watchSlot(slot)
  if slot:IsA('Folder') and slot.Name:match('^Slot%d') then
   slot:GetAttributeChangedSignal('StartTime'):Connect(function() onAttack(state,slot) end)
  end
 end
 for _,slot in state:GetChildren() do watchSlot(slot) end
 state.ChildAdded:Connect(watchSlot)
end
for _,state in states:GetChildren() do watchState(state) end
states.ChildAdded:Connect(watchState)

-- Mob hits: the creature's splat plus the weapon's optional impact layer. Damage-over-time
-- ticks (secondary) stay silent so poison and burn don't drown out real hits.
combat:WaitForChild('Hit').OnClientEvent:Connect(function(position,_,npc,impactPosition,lethal,secondary,weaponId)
 if secondary then return end
 local at=typeof(impactPosition)=='Vector3' and impactPosition or position
 if typeof(at)~='Vector3' then return end
 local m=typeof(npc)=='Instance' and MOB[npc:GetAttribute('EnemyId')] or MOB_DEFAULT
 local scale=m[3] or 1
 play(m[1],'mob',lethal and .315*scale or .225*math.sqrt(scale),m[2]*(lethal and .9 or 1),at,.08)
 local w=WEAPON[weaponId]
 if w and w.hit then play(w.hit,'impact',w.hitVolume,w.hitPitch,at,.05) end
end)

-- Godly specials (GodlyWeapons -> GodlyFX): the wraith's rise and claws, the tidal wave, the
-- storm arrows' thunder, the dagger chain's slashes, the blood wisp and the Ray Gun's burst.
local function npcAt(npc) local r=typeof(npc)=='Instance' and npc.Parent and npc:FindFirstChild('HumanoidRootPart');return r and r.Position end
combat:WaitForChild('GodlyFX').OnClientEvent:Connect(function(kind,...)
 local a={...}
 if kind=='Rise' then
  play('ghost_rise','impact',.45,.7,a[3],.08);play('mob_ghost','impact',.35,.6,a[3],.08)
 elseif kind=='Claw' then
  local at=npcAt(a[2]);if at then play('swing_light','impact',.3,1.45,at,.1) end
 elseif kind=='Wave' then
  play('swing_heaviest','impact',.6,.6,a[2],.05);play('water_bubbles','impact',.6,1,a[2],.05)
 elseif kind=='Rain' then
  local split=a[4];local wait=math.clamp((a[7] or 0)+(a[8] or 0)-workspace:GetServerTimeNow(),0,.8)
  task.delay(wait,function() play('thunder_crack','impact',.55,1.1,split,.06) end)
 elseif kind=='Chain' then
  local points,start,step=a[4],a[6] or 0,a[7] or .09
  for i,point in points do
   task.delay(math.clamp(start+.08+(i-1)*step-workspace:GetServerTimeNow(),0,1),function() play('swing_blade','weapon',.35,1.5,point,.08) end)
  end
 elseif kind=='Wisp' then
  local mine=a[1]==player.UserId
  task.delay(.5,function() play('crystal_pickup','pickup',mine and .3 or .15,.7,not mine and a[2] or nil,0,{2.55,2.6189}) end)
 elseif kind=='Burst' then
  play('shot_magic_a','impact',.45,.6,a[2],.06);play('zap','impact',.3,.6,a[2],.06)
 end
end)

-- Legendary Tier IV moves (LegendaryMoves -> LegendaryFX): the same kit, pitched. Spawned so a
-- place without LegendaryFX yet never holds up the sounds below.
task.spawn(function()
 local fx=combat:WaitForChild('LegendaryFX')
 local function at(t,fn) task.delay(math.clamp((t or 0)-workspace:GetServerTimeNow(),0,1.5),fn) end
 fx.OnClientEvent:Connect(function(kind,...)
  local a={...}
  if kind=='Slash' then -- Katana: a sharp, airy cut
   play('swing_blade','impact',.45,.82,a[4],.06);play('zap','impact',.14,1.7,a[4],.08)
  elseif kind=='Beam' then -- Excalibur: a heavier, ringing sweep
   play('swing_heavy','impact',.38,1.25,a[4],.05);play('shot_magic_b','impact',.3,.78,a[4],.06)
  elseif kind=='Flush' then -- the deck fans and five cards whip out
   play('shot_magic_c','impact',.32,1.3,a[3],.05);play('ui_upgrade','impact',.25,1.15,a[3],.03)
   for i=1,3 do task.delay(.12+i*.04,function() play('swing_light','impact',.22,1.7,a[3],.1) end) end
  elseif kind=='Split' then -- the rocket pops apart, then each mini lands
   at(a[6],function() play('shot_rocket','impact',.32,1.6,a[4],.06) end)
   for _,m in a[7] or {} do at(m[1],function() play('hit_thud','impact',.32,.75,m[2],.1) end) end
  elseif kind=='Strike' then -- STRIKE: the crash, then the pins clattering down
   play('hit_blunt','impact',.5,.8,a[2],.04);play('swing_heaviest','impact',.3,1.4,a[2],.05)
   for i=1,4 do task.delay(.18+i*.07,function() play('hit_punch','impact',.18,1.5+i*.1,a[2],.1) end) end
  elseif kind=='Shock' then -- the Wrecking Ball's ground slam
   play('swing_heaviest','impact',.5,.55,a[2],.05);play('hit_thud','impact',.4,.6,a[2],.05)
  elseif kind=='Thunder' then -- Mjolnir: the crack lands with the bolt
   at(a[4],function() play('thunder_crack','impact',.6,1,a[2],.05);play('zap','impact',.25,.7,a[2],.06) end)
  end
 end)
end)

-- Crystal pickups: one plop per crystal as it reaches you, timed to the visible pull (the
-- server starts it at MagnetStart; it lands ShardMotion.PULL_SECONDS later). The file holds 11
-- plops sorted low to high (audio/sprites.json): quick pickups climb the ladder, a short pause
-- starts it over, and a long streak stays near the top.
local PLOPS={
 {.05,.1239},{.3,.3888},{.55,.6239},{.8,.8839},{1.05,1.1538},{1.3,1.3938},
 {1.55,1.6189},{1.8,1.8888},{2.05,2.1239},{2.3,2.3689},{2.55,2.6189},
}
local LADDER_RESET=.6
local rung,lastPickup=0,0
local function pickup()
 local now=os.clock()
 if now-lastPickup>LADDER_RESET then rung=0 end
 lastPickup=now;rung+=1
 local i=rung<=#PLOPS and rung or #PLOPS-math.random(0,2)
 play('crystal_pickup','pickup',.175,1,nil,0,PLOPS[i])
end
task.spawn(function()
 local drops=workspace:WaitForChild('RogueliteShardDrops')
 local scheduled={}
 local function check(m)
  local start=m:GetAttribute('MagnetStart')
  if m:GetAttribute('MagnetUserId')~=player.UserId or type(start)~='number' or scheduled[m]==start then return end
  scheduled[m]=start
  task.delay(math.max(0,start+ShardMotion.PULL_SECONDS-workspace:GetServerTimeNow()),function()
   scheduled[m]=nil
   if m:GetAttribute('MagnetStart')==start then pickup() end -- a cancelled pull stays silent
  end)
 end
 local function watch(m)
  m:GetAttributeChangedSignal('MagnetStart'):Connect(function() check(m) end)
  m:GetAttributeChangedSignal('MagnetUserId'):Connect(function() check(m) end)
  check(m)
 end
 for _,m in drops:GetChildren() do watch(m) end
 drops.ChildAdded:Connect(watch)
end)

combat:WaitForChild('PlayerDamaged').OnClientEvent:Connect(function(damage)
 if type(damage)=='number' and damage>0 then play('player_damage','player',.6,1,nil,.04) end
end)
local function watchCharacter(character)
 local humanoid=character:WaitForChild('Humanoid',10)
 if humanoid then humanoid.Died:Connect(function() play('player_death','player',.7,1,nil,0) end) end
end
if player.Character then task.spawn(watchCharacter,player.Character) end
player.CharacterAdded:Connect(watchCharacter)

-- Mute Roblox's default death "oomph": RbxCharacterSounds puts a Sound named Died in every
-- character's root part on each client. Footsteps, jumps and landings are left alone.
local function muteDefaultDeath(character)
 local root=character:WaitForChild('HumanoidRootPart',10);if not root then return end
 local function mute(child)
  if child:IsA('Sound') and child.Name=='Died' then
   child.Volume=0
   child:GetPropertyChangedSignal('Volume'):Connect(function() if child.Volume~=0 then child.Volume=0 end end)
  end
 end
 for _,child in root:GetChildren() do mute(child) end
 root.ChildAdded:Connect(mute)
end
local function watchPlayer(p)
 if p.Character then task.spawn(muteDefaultDeath,p.Character) end
 p.CharacterAdded:Connect(muteDefaultDeath)
end
for _,p in Players:GetPlayers() do watchPlayer(p) end
Players.PlayerAdded:Connect(watchPlayer)

-- Every button click, played on press (mouse down / finger down) rather than on release so it
-- feels instant; gamepad and keyboard presses click on activation. Pressing a disabled button
-- (can't afford, not available) plays the error. NoClickSound buttons (the chest's tap layer)
-- stay silent, and one press never clicks twice when buttons overlap.
local lastPress=0
-- Menus can reparent the same button. Bind once without retaining destroyed UI.
local hookedButtons=setmetatable({}, {__mode='k'})
local function hookButton(b)
 if not b:IsA('GuiButton') or hookedButtons[b] then return end
 hookedButtons[b]=true
 b.InputBegan:Connect(function(input)
  local t=input.UserInputType
  if t~=Enum.UserInputType.MouseButton1 and t~=Enum.UserInputType.Touch then return end
  if b:GetAttribute('NoClickSound') or os.clock()-lastPress<.05 then return end
  lastPress=os.clock()
  if b.Interactable then play('ui_click','ui',.5,1,nil,.03) else play('ui_error','ui',.5,1,nil,0) end
 end)
 b.Activated:Connect(function(input)
  local t=input and input.UserInputType
  if t==Enum.UserInputType.MouseButton1 or t==Enum.UserInputType.Touch then return end
  if not b:GetAttribute('NoClickSound') then play('ui_click','ui',.5,1,nil,.03) end
 end)
end
local gui=player:WaitForChild('PlayerGui')
for _,d in gui:GetDescendants() do hookButton(d) end
gui.DescendantAdded:Connect(hookButton)

-- The cue is saved in the place as a sandboxed BindableEvent (audio/InstallSoundCue.luau): a
-- sandboxed module can only fire an event that is itself sandboxed.
local cue=RS:WaitForChild('RogueliteSoundCue',10)
if not cue then
 warn('RogueliteSounds: ReplicatedStorage.RogueliteSoundCue is missing; run audio/InstallSoundCue.luau')
 cue=Instance.new('BindableEvent');cue.Name='RogueliteSoundCue';cue.Parent=RS
end
cue.Event:Connect(function(name)
 if CUE[name] then play(name,'ui',CUE[name],1,nil,.02) end
end)
