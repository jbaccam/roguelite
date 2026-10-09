-- Shared tuning; only server code applies health, movement and damage.
local T = {}
-- 2026-10-05: Brotato-style fodder pacing: upgrades may one-shot ordinary enemies.
-- Wave 20: regular 41 HP, fast fodder 20, tank 229. Damage grows more gently alongside
-- the larger swarms: 22.1 / 16.4 / 38.5 before map/difficulty (see ENEMY_SCALING.md).
T.Regular = {template='Zombie_NPC',health=3,healthPerWave=2,damagePerWave=.9,speed=14,damage=5,contactRange=4.5,stopRange=3.5,radius=2,height=7,cadence=.75}
T.Baby = {template='BabyZombie_NPC',health=1,healthPerWave=1,damagePerWave=.6,speed=17,damage=5,contactRange=3.1,stopRange=2.1,radius=1,height=4,cadence=1.12}
T.Mutant = {template='MutantZombie_NPC',health=20,healthPerWave=11,minHealth=50,damagePerWave=0,speed=11,damage=0,contactRange=0,stopRange=4.5,radius=3.1,height=9,cadence=.58}
-- The Bloater (round 10, Pine Valley's POP GOES THE ZOMBIE): a slow yellow zombie that stops beside a
-- player, swells for Blast.fuse seconds and bursts (ExploderService). damage is the burst's hit on
-- players; contactRange is where it arms. Wave 10: 46 health, 24.8 damage before map/difficulty.
T.Bloater = {template='BloaterZombie_NPC',health=10,healthPerWave=4,damagePerWave=1.2,speed=11,damage=14,contactRange=5.2,stopRange=3,radius=2.3,height=6.2,cadence=.62}
-- fuse: armed until the burst. lethalFuse: a Bloater killed before it armed still bursts, this much
-- later (a dodge window; it is no longer a target). radius: the burst disc (the warning ring is this
-- exact circle). enemyDamage: the burst's hit on other enemies, x its player damage (friendly fire
-- is the point: lure crowds in). chainCap: bursts resolved per server frame; the rest wait a frame.
T.Blast = {fuse=1.5,lethalFuse=.8,radius=8,height=5,enemyDamage=3,chainCap=4,inflate=1.3}
T.Slam = {windup=.32,impact=.46,recovery=1.0,cooldown=2.15,trigger=6.2,offset=3.5,radius=6.5,damage=10,damagePerWave=1.5,maxHeight=4.5}
function T.get(kind) return T[kind] or T.Regular end
-- Linear wave growth from the supplied Brotato enemy reference; movement stays Roblox-native.
function T.scaled(kind,wave)
 local d=table.clone(T.get(kind));local numeric=tonumber(wave) or 1
 if numeric~=numeric then numeric=1 end
 local growth=math.clamp(math.floor(numeric)-1,0,999)
 -- Preserve the 50 HP early-practice floor; natural wave-8 tanks have 97 HP.
 d.health=math.max(d.minHealth or 0,d.health+d.healthPerWave*growth);d.damage=d.damage+d.damagePerWave*growth
 d.slamDamage=T.Slam.damage+T.Slam.damagePerWave*growth
 return d
end
function T.forSlot(index,wave)
    if wave and wave<8 then return index%4==2 and 'Baby' or 'Regular' end
    if index%8==5 then return 'Mutant' end
    if index%4==2 then return 'Baby' end
    return 'Regular'
end
function T.inSlam(center, position)
    local delta=position-center
    return math.abs(delta.Y)<=T.Slam.maxHeight and Vector2.new(delta.X,delta.Z).Magnitude<=T.Slam.radius
end
return T
