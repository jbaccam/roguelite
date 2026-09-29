-- Pure balance checks; run as a temporary server Script after syncing modules.
local C=game.ReplicatedStorage.RogueliteCombat
local Weapons=require(C.WeaponCatalog)
local Stats=require(C.CharacterStats)
local Types=require(C.ZombieTypes)
local checked=0
local function check(ok,label) checked+=1;assert(ok,label) end
local ok,err=xpcall(function()
 local neutral=Stats.resolve('Brawler',0,{Damage=0,MeleeDamage=0,RangedDamage=0,ElementalDamage=0,UtilityPower=0,ExplosionDamage=0,AttackSpeed=0,CooldownReduction=0})
 local signatures={}
 for _,w in Weapons.List do
  local previous
  signatures[tostring(w.damage)..':'..tostring(w.cooldown)]=true
  for tier=1,4 do
   local d=Stats.weapon(w,neutral,'Brawler',tier)
   check(math.abs(d.damage-w.tierDamage[tier])<.001,'actual tier damage '..w.id)
   check(d.cooldown>0 and d.range>0,'positive combat values '..w.id)
   if previous then check(d.damage>previous.damage and d.cooldown<previous.cooldown,'tier progression '..w.id) end
   check(d.nativePierce<=4 and d.nativeBounce<=4 and d.projectileCount<=8,'bounded traits '..w.id)
   previous=d
  end
 end
 local count=0;for _ in signatures do count+=1 end
 check(count>=30,'distinct damage/cadence identities')
 check(Stats.weapon(Weapons.ById['09'],neutral,'Brawler',4).projectileCount==8,'shotgun gains pellets')
 check(Stats.weapon(Weapons.ById['12'],neutral,'Brawler',4).nativeBounce==3,'boomerang gains rebounds')
 check(Stats.weapon(Weapons.ById['24'],neutral,'Brawler',4).nativePierce==2,'nails gain piercing')
 check(Stats.weapon(Weapons.ById['34'],neutral,'Brawler',2).projectileCount==2,'Medusa gains projectile')
 for _,wave in {1,5,10,20} do
  check(Types.scaled('Regular',wave).health==3+2*(wave-1),'regular wave HP')
  check(Types.scaled('Baby',wave).health==wave,'baby wave HP')
  check(Types.scaled('Mutant',wave).health==math.max(80,20+11*(wave-1)),'mutant wave HP')
  check(Types.scaled('Mutant',wave).damage==0,'mutant never adds contact damage')
  check(math.abs(Types.scaled('Mutant',wave).slamDamage-(2+.85*(wave-1)))<.001,'mutant slam wave damage')
  check(math.abs(Types.scaled('Regular',wave).damage-(1+.6*(wave-1)))<.001,'contact growth')
 end
 check(Types.forSlot(5,1)=='Regular' and Types.forSlot(5,8)=='Mutant','mutant wave gate')
 check(Types.Regular.health==3,'scaling does not mutate shared base')
end,debug.traceback)
script:SetAttribute('Result',game.HttpService:JSONEncode({passed=ok,assertions=checked,error=ok and '' or err}))
