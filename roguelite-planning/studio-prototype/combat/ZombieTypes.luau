-- Shared tuning; only server code applies health, movement and damage.
local T = {}
T.Regular = {template='Zombie_NPC',health=3,healthPerWave=2,damagePerWave=.6,speed=16,damage=1,contactRange=4.5,stopRange=3.5,radius=2,height=7,cadence=.75}
T.Baby = {template='BabyZombie_NPC',health=1,healthPerWave=1,damagePerWave=.6,speed=20,damage=1,contactRange=3.1,stopRange=2.1,radius=1,height=4,cadence=1.12}
T.Mutant = {template='MutantZombie_NPC',health=20,healthPerWave=11,damagePerWave=0,speed=12.5,damage=0,contactRange=0,stopRange=4.5,radius=3.1,height=9,cadence=.58}
T.Slam = {windup=.32,impact=.46,recovery=1.0,cooldown=2.15,trigger=6.2,offset=3.5,radius=5.2,damage=2,maxHeight=4.5}
function T.get(kind) return T[kind] or T.Regular end
-- Linear wave growth from the supplied Brotato enemy reference; movement stays Roblox-native.
function T.scaled(kind,wave)
 local d=table.clone(T.get(kind));local growth=math.clamp(math.floor(tonumber(wave) or 1)-1,0,999)
 d.health=d.health+d.healthPerWave*growth;d.damage=d.damage+d.damagePerWave*growth
 d.slamDamage=T.Slam.damage+.85*growth
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
