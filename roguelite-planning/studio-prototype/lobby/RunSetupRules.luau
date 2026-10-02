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
-- Regular enemies get tougher down the ladder (R.enemyScale), on top of wave growth and
-- difficulty. enemyWaves: their health starts that many waves further along; enemyHp then
-- multiplies it, enemyDamage multiplies their hits. Example, a Volcanic Crater goblin at wave 1:
-- 4 HP +2 a wave, 16 waves ahead = 36, x1.6 = 58 HP, four Tier I pan hits (16 each); at wave 20,
-- 119 HP against a Pine Valley zombie's 41. Each map's Normal stays a little under the previous
-- map's Hard (x1.6 HP). Map bosses have their own health (MapBossDefs).
R.Maps={
 {id='PineValley',name='Pine Valley',boss='Hammer Zombie Boss',emeralds=20,unlock='Available after the tutorial',enemyWaves=0,enemyHp=1,enemyDamage=1},
 {id='BeachCove',name='Beach Cove',boss='Giant King Crab',emeralds=40,unlock='Win Pine Valley on Hard',enemyWaves=4,enemyHp=1.15,enemyDamage=1.2},
 {id='DesertBasin',name='Desert Basin',boss='Pharaoh',emeralds=60,unlock='Win Beach Cove on Hard',enemyWaves=8,enemyHp=1.3,enemyDamage=1.4},
 {id='FrozenPass',name='Frozen Pass',boss='Frost Cyclops',emeralds=80,unlock='Win Desert Basin on Hard',enemyWaves=12,enemyHp=1.45,enemyDamage=1.6},
 {id='VolcanicCrater',name='Volcanic Crater',boss='Dragon',emeralds=100,unlock='Win Frozen Pass on Hard',enemyWaves=16,enemyHp=1.6,enemyDamage=1.8},
}
-- Difficulty multiplies enemy health and damage and the emeralds a run pays (reward).
R.Difficulties={
 {id='Normal',hp=1,damage=1,reward=1},
 {id='Hard',hp=1.6,damage=1.3,reward=1.5},
 {id='Nightmare',hp=2.5,damage=1.6,reward=2},
}
R.DifficultyIndex={};for i,d in R.Difficulties do R.DifficultyIndex[d.id]=d end
function R.difficulty(id) return R.DifficultyIndex[id] or R.Difficulties[1] end
-- Bosses: health x the difficulty's hp x (1 + BossPlayerHp per extra player); damage x its damage.
-- Normal solo is the authored number (a 2-player Normal Hammer: 18,000 x 1.75 = 31,500).
R.BossPlayerHp=.75
function R.bossScale(id,players)
 local d=R.difficulty(id)
 return d.hp*(1+R.BossPlayerHp*math.max(0,(players or 1)-1)),d.damage
end
-- Regular enemies on a map and difficulty: extra waves of health growth, then the health and
-- damage multipliers. Example, a Frozen Pass werewolf at wave 1 on Hard: 8 HP +3 a wave, 12
-- waves ahead = 44, x1.45 x1.6 = 103 HP; 1.8 damage x1.6 x1.3 = 3.7 per hit.
function R.enemyScale(mapId,diff)
 local m=R.Maps[R.MapIndex[mapId] or 1];local d=R.difficulty(diff)
 return m.enemyWaves or 0,(m.enemyHp or 1)*d.hp,(m.enemyDamage or 1)*d.damage
end
-- Saved win / best-wave key: Normal keeps the plain map id (older saves stay valid).
function R.runKey(mapId,diff) return (diff==nil or diff=='Normal') and mapId or mapId..'/'..diff end
R.MapIndex={};for i,m in R.Maps do R.MapIndex[m.id]=i end
R.WinWave=20
R.Milestones={{5,'ELITE'},{10,'HORDE'},{15,'ELITE'},{20,'BOSS'}}
R.Signature={Brawler='01',Gunner='00',Thrower='12',Juggler='19',Handyman='24',Mage='30'}
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
 if not w or w.home~=class or not p.weapons[weapon] then return false,'Weapon not owned' end
 return true
end
return R
