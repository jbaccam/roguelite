-- Run setup data shared by the lobby UI (display) and the lobby server (validation):
-- the map ladder, the wave track, class signature weapons and what a player may pick.
-- Reads the saved-progression attributes ProfileService publishes on the Player.
local RS=game:GetService('ReplicatedStorage')
local combat=RS:WaitForChild('RogueliteCombat')
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Playable=require(combat:WaitForChild('MapConfig'))
local R={}

-- PROGRESSION_AND_SESSION_FLOW.md: five maps, each won at wave 20, and three difficulties per map.
-- The next map opens after winning the previous one on Hard.
-- power: the map's recommended gear power (GEAR_POWER.md, CharacterStats.gearPower), 4 more per
-- map, about one more tier on every slot. Enemies there get the health a player at that power
-- deals extra damage against, and the damage they have extra health for (R.enemyScale), so gear
-- that matches the map plays like a fresh account in Pine Valley. Example, Desert Basin (power 9):
-- enemies x1.96 health and x1.48 damage; a power 9 player deals x1.96 and has x1.48 health.
-- Each map's Normal stays under the previous map's Hard (x1.6 health).
-- bossBase: how much tougher than the Hammer (18,000) the map's boss is authored (MapBossDefs),
-- which the power scaling replaces rather than stacks on (R.bossScale).
R.Maps={
 {id='PineValley',name='Pine Valley',boss='Hammer Zombie Boss',emeralds=20,unlock='Available after the tutorial',power=1,bossBase=1},
 {id='BeachCove',name='Beach Cove',boss='Giant King Crab',emeralds=40,unlock='Win Pine Valley on Hard',power=5,bossBase=21000/18000},
 {id='DesertBasin',name='Desert Basin',boss='Pharaoh',emeralds=60,unlock='Win Beach Cove on Hard',power=9,bossBase=24000/18000},
 {id='FrozenPass',name='Frozen Pass',boss='Frost Cyclops',emeralds=80,unlock='Win Desert Basin on Hard',power=13,bossBase=27000/18000},
 {id='VolcanicCrater',name='Volcanic Crater',boss='Dragon',emeralds=100,unlock='Win Frozen Pass on Hard',power=17,bossBase=31500/18000},
}
-- Difficulty multiplies enemy health and damage and the emeralds a run pays (reward).
R.Difficulties={
 {id='Normal',hp=1,damage=1,reward=1},
 {id='Hard',hp=1.6,damage=1.3,reward=1.5},
 {id='Nightmare',hp=2.5,damage=1.6,reward=2},
}
R.DifficultyIndex={};for i,d in R.Difficulties do R.DifficultyIndex[d.id]=d end
function R.difficulty(id) return R.DifficultyIndex[id] or R.Difficulties[1] end
-- The map a run is on (MapConfig ids; Pine Valley when unset or unknown).
local function mapOf(mapId)
 return R.Maps[R.MapIndex[mapId or combat:GetAttribute('RunMap')] or 1]
end
-- Bosses: health x the difficulty's hp x (1 + BossPlayerHp per extra player) x the map's power
-- health / its bossBase; damage x the difficulty's damage x the map's power damage. Normal solo
-- in Pine Valley is the authored number (a 2-player Normal Hammer: 18,000 x 1.75 = 31,500). A
-- Normal solo Dragon: 31,500 x 2.92 / 1.75 = 52,560 = the Hammer's 18,000 x 2.92.
R.BossPlayerHp=.75
function R.bossScale(id,players,mapId)
 local d=R.difficulty(id);local m=mapOf(mapId)
 return d.hp*(1+R.BossPlayerHp*math.max(0,(players or 1)-1))*Stats.powerDamage(m.power)/(m.bossBase or 1),d.damage*Stats.powerHealth(m.power)
end
-- Regular enemies on a map and difficulty: (extra waves of health growth, health multiplier,
-- damage multiplier). The first is always 0 now (the spawner still reads it). Example, a Frozen
-- Pass werewolf (power 13) at wave 1 on Hard: 8 HP x2.44 x1.6 = 31 HP; 1.8 damage x1.72 x1.3 = 4.
function R.enemyScale(mapId,diff)
 local m=mapOf(mapId);local d=R.difficulty(diff)
 return 0,Stats.powerDamage(m.power)*d.hp,Stats.powerHealth(m.power)*d.damage
end
-- A player's gear power with `weapon` as the starter (CharacterStats.gearPower), for the lobby.
function R.power(player,weapon)
 return Stats.gearPower(function(name) return player:GetAttribute(name) end,weapon or player:GetAttribute('RunWeapon') or R.Signature.Brawler)
end
-- The same power split into weapon, armor and pet tiers (the Armory's Power card, plan K).
function R.powerParts(player,weapon)
 return Stats.gearParts(function(name) return player:GetAttribute(name) end,weapon or player:GetAttribute('RunWeapon') or R.Signature.Brawler)
end
-- Saved win / best-wave key: Normal keeps the plain map id (older saves stay valid).
function R.runKey(mapId,diff) return (diff==nil or diff=='Normal') and mapId or mapId..'/'..diff end
R.MapIndex={};for i,m in R.Maps do R.MapIndex[m.id]=i end
R.WinWave=20
-- Run setup's wave markers: plain ticks at 5, 10 and 15 (each pays a block of run emeralds) and the
-- wave-20 boss. The ELITE (5, 15) and HORDE (10) tags promised waves that were never built, so they're
-- gone (the user, 2026-10-02; audit G5).
R.Milestones={{5},{10},{15},{20,'BOSS'}}
R.Signature={Brawler='01',Gunner='00',Thrower='12',Juggler='17',Handyman='24',Mage='30'} -- Juggler: Rubber Duck since 2026-10-03 (was Boxing Gloves)
R.ClassUnlock={Thrower='Reach wave 10 on Pine Valley',Juggler='Win Pine Valley',Handyman='Defeat 1,000 enemies with Utility weapons'}
-- Emeralds a run pays: one payout per 5 waves reached (wave 12 on Pine Valley Normal = 2 x 20 = 40).
function R.runEmeralds(index,diff,wave)
 local m=R.Maps[index] or R.Maps[1]
 return math.floor(math.floor(math.max(0,wave-1)/5)*m.emeralds*R.difficulty(diff).reward)
end
-- Emeralds for reaching wave 20, and the one-time first-win bonus.
function R.winEmeralds(index,diff) return math.floor(4*R.Maps[index].emeralds*R.difficulty(diff).reward) end
function R.firstWinEmeralds(index,diff) return math.floor(100*index*R.difficulty(diff).reward+.5) end

local function csvSet(text) local out={};for v in string.gmatch(text or '','[^,]+') do out[v]=true end;return out end
-- Classes, owned weapons and map wins. Before a profile loads, a fresh account's defaults.
function R.progress(player)
 local connected=player:GetAttribute('ProfileLoaded')==true
 local p={classes=connected and csvSet(player:GetAttribute('ProfileClasses')) or {Brawler=true,Gunner=true,Mage=true},weapons={},wins=csvSet(player:GetAttribute('ProfileMapWins'))}
 if connected then
  for id in string.gmatch(player:GetAttribute('ProfileWeapons') or '','([^,:]+):%d+:%d+') do p.weapons[id]=true end
 else for class in p.classes do p.weapons[R.Signature[class]]=true end end
 return p
end
function R.mapUnlocked(wins,index) return index==1 or wins[R.runKey(R.Maps[index-1].id,'Hard')]==true end
-- Normal follows the map; Hard needs a Normal win on that map; Nightmare needs a Hard win.
function R.difficultyUnlocked(wins,index,diff)
 if not R.mapUnlocked(wins,index) then return false end
 local id=R.Maps[index].id
 if diff=='Hard' then return wins[R.runKey(id,'Normal')]==true end
 if diff=='Nightmare' then return wins[R.runKey(id,'Hard')]==true end
 return diff=='Normal'
end
function R.difficultyLock(index,diff)
 return diff=='Hard' and 'Beat Normal to unlock Hard' or diff=='Nightmare' and 'Beat Hard to unlock Nightmare' or R.Maps[index].unlock
end
-- Owned classes first, each group in the catalog's order.
function R.classOrder(classes)
 local out={}
 for pass=1,2 do for _,c in Stats.ClassOrder do if (classes[c]==true)==(pass==1) then table.insert(out,c) end end end
 return out
end
function R.homeWeapons(class) local out={};for _,w in Weapons.List do if w.home==class then table.insert(out,w) end end;return out end
-- Godlies this profile owns (any class can start with one); unowned Godlies are never listed.
function R.ownedGodlies(weapons) local out={};for _,w in Weapons.List do if w.godly and weapons[w.id] then table.insert(out,w) end end;return out end

-- Server checks for a run request. Returns true or false plus a short reason.
function R.validMap(player,mapId,diff)
 local index=type(mapId)=='string' and R.MapIndex[mapId]
 if not index then return false,'Unknown map' end
 -- Only maps with match folders can be played (MapConfig); the rest show as coming soon.
 if not Playable.valid(mapId) then return false,'Coming soon' end
 diff=diff or 'Normal'
 if type(diff)~='string' or not R.DifficultyIndex[diff] then return false,'Unknown difficulty' end
 if not R.difficultyUnlocked(R.progress(player).wins,index,diff) then
  return false,R.mapUnlocked(R.progress(player).wins,index) and R.difficultyLock(index,diff) or R.Maps[index].unlock
 end
 return true
end
function R.validLoadout(player,class,weapon)
 if type(class)~='string' or not Stats.Classes[class] then return false,'Unknown class' end
 local p=R.progress(player)
 if not p.classes[class] then return false,'Class locked' end
 local w=type(weapon)=='string' and Weapons.ById[weapon]
 -- An owned Godly starts a run with any class (it is the run's one Godly: the shop never sells one).
 if not w or (w.home~=class and not w.godly) or not p.weapons[weapon] then return false,'Weapon not owned' end
 return true
end
return R
