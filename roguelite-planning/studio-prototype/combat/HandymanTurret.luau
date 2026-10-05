-- Turret rules (HANDYMAN_TURRET.md). Since 2026-10-04 turrets are shop items, Brotato-style
-- (plans/2026-10-04-turret-items-engineer-design.md): any class can own up to 10, they are placed
-- for you on a ring at every wave start, and the Handyman is Brotato's Engineer. Shared and pure:
-- ShopCatalog makes the shop items from H.Items, ShopService prices, offers and caps them,
-- HandymanTurretService places and fires them, HandymanTurret.client draws them, TurretTests checks
-- them. Touches no Instances except templates(), which only looks. Turrets can't be destroyed
-- (user, 2026-10-04: "let's not let mobs destroy the turrets"): no health, mobs ignore them.
-- Studio: ReplicatedStorage.RogueliteCombat.HandymanTurret, Sandboxed = true with CharacterStats'
-- Capabilities (ShopService and ShopCatalog, sandboxed, require it).
local Stats=require(script.Parent.CharacterStats)
local Weapons=require(script.Parent.WeaponCatalog)
local H={Id='Turret',Class='Handyman',MaxTier=4}
-- Shared by every turret: 25 studs of range (the class ranged weapons average 29, the Nail Gun 30)
-- and the Nail Gun's nail speed. Neither stat changes them.
H.DAMAGE=4;H.COOLDOWN=.8;H.RANGE=25;H.SPEED=110
-- The head idles (Aim cleared) after this long without a target.
H.AIM_IDLE=1.5
-- Tier IV (the Gatling Rig) spins: each cycle fires 3 nails a third as strong, a third of the
-- cooldown apart, each at the nearest enemy then, so it sprays a crowd at the same DPS.
H.Burst={1,1,1,3}
H.GATLING_SPREAD=3 -- degrees of random yaw on each gatling nail
-- The weapon-like entry H.weapon turns into a turret's numbers. Id 'Turret' is the damage source:
-- kill credit, run analytics and the utilityKills quest count it as the owner's. A Ranged bullet
-- weapon, so CharacterStats.usesStat gives it Two Straws, Pierce and Bounce. trait 'pierce': it
-- pierces floor(tier/2) enemies (0 / 1 / 1 / 2).
H.Base={id=H.Id,name='Turret',kind='Ranged',home=H.Class,utility=true,rarity='Common',damage=H.DAMAGE,
 cooldown=H.COOLDOWN,range=H.RANGE,projectileSpeed=H.SPEED,trait='pierce',nativeKnockback=0,burn=0,poison=0,slow=0,tags={'Projectile','Handyman','Utility'}}
H.Base.tierDamage={}
for t=1,H.MaxTier do H.Base.tierDamage[t]=math.floor(H.DAMAGE*Weapons.TierGrowth^(t-1)+.5) end -- 4 / 6 / 8 / 11
H.Base.tierCooldown=table.clone(Weapons.TierCooldown) -- .8 / .72 / .64 / .56 s
function H.tier(t) return math.clamp(math.floor(tonumber(t) or 1),1,H.MaxTier) end

-- Items -----------------------------------------------------------------------------------------
-- One shop item per turret model (RogueliteCombat.HandymanTurrets T1-T4; no new models, user
-- 2026-10-04). Every copy owned is one more turret. Base prices sit in EconomyConfig's tier bands
-- and go through EconomyConfig.price like any offer: a Nail Turret is 24 + 5 + 24 x 5 x 10% = 41 at
-- wave 5.
H.Items={
 {id='turret_nail',name='Nail Turret',tier=1,price=24},
 {id='turret_twin',name='Twin Nailer',tier=2,price=46},
 {id='turret_quad',name='Quad Nailer',tier=3,price=85},
 {id='turret_gatling',name='Gatling Rig',tier=4,price=150},
}
H.ItemTier={};for _,it in H.Items do H.ItemTier[it.id]=it.tier end
-- Support items (ShopCatalog). Toolbelt is a plain +6 Utility Power item.
H.SCRAP_MAGNET='scrap_magnet';H.TOOLBELT='toolbelt'
-- At most 10 turrets per player (the shop stops offering turret items at 10) and 30 standing on the
-- server, Scrap Magnet's temporary ones included. Example: 4 players with 10 each get 8, 8, 7, 7.
H.MAX_OWNED=10;H.MAX_SERVER=30
-- items: a shop state's {id, count} list. Copies of `id`, and turret items owned in all.
function H.count(items,id) for _,it in items or {} do if it.id==id then return it.count end end;return 0 end
function H.owned(items) local n=0;for _,it in items or {} do if H.ItemTier[it.id] then n+=it.count end end;return n end
-- The turrets those items build, best first, at most MAX_OWNED. Example: 2 Nail + 1 Gatling -> {4,1,1}.
function H.tiers(items)
 local list={}
 for _,it in items or {} do local t=H.ItemTier[it.id];if t then for _=1,math.max(0,math.floor(it.count)) do table.insert(list,t) end end end
 table.sort(list,function(a,b) return a>b end)
 while #list>H.MAX_OWNED do table.remove(list) end
 return list
end
-- Whether the shop may offer `entry` to a player owning `owned` turrets: no turret item at 10.
function H.offerable(entry,owned) return not (type(entry)=='table' and entry.turret) or (owned or 0)<H.MAX_OWNED end

-- Numbers (Brotato's structure rule, 2026-10-04) -------------------------------------------------
-- Damage = base x (1 + Utility Power). Damage, Ranged damage, Attack speed, Cooldown reduction, Crit
-- and Life steal don't count, nor the class-fit +15%. Knockback doesn't either (its push starts at
-- the owner's body), and range and nail speed are fixed. Extra projectiles, Pierce, Bounce, burn,
-- slow, poison, lightning and Boss damage do count, and so does gear power (its damage share,
-- CombatEffectsService), because later maps' enemies are tougher by just that share.
-- Example: +30% Utility Power -> a Nail Turret's nail is 4 x 1.3 = 5.2.
H.Ignored={Damage=0,MeleeDamage=0,RangedDamage=0,AttackSpeed=0,CooldownReduction=0,CritChance=0,LifeSteal=0,Knockback=0,AttackRange=0,ProjectileSpeed=0,ProjectileSize=0}
-- The owner's stats as a turret's hits use them (d.stats): a copy with the ignored stats zeroed.
function H.turretStats(stats)
 local s=table.clone(stats)
 for id,v in H.Ignored do s[id]=v end
 return s
end
-- One turret's numbers as a weapon definition (damage per cycle, cooldown, range, projectileSpeed,
-- nativePierce, projectileRadius...), plus burst (nails per cycle) and structure (CombatEffectsService:
-- no dodge crit, no life steal). stats: the owner's; nil gives the base numbers.
function H.weapon(tier,stats)
 tier=H.tier(tier)
 local d=table.clone(H.Base)
 d.tier=tier;d.structure=true;d.burst=H.Burst[tier] or 1
 d.damage=H.Base.tierDamage[tier]*Stats.mult(stats and stats.UtilityPower or 0)
 d.cooldown=H.COOLDOWN*H.Base.tierCooldown[tier]
 d.range=H.RANGE;d.targetRange=H.RANGE;d.projectileSpeed=H.SPEED;d.projectileRadius=.12
 d.projectileCount=1;d.nativePierce=math.floor(tier/2);d.nativeBounce=0
 d.stats=stats and H.turretStats(stats) or nil
 return d
end
-- One nail: seconds between nails and its damage. Example, Tier IV with no bonuses: 11 damage
-- every 0.56 s is 3 nails of 3.67, 0.187 s apart (19.6 DPS either way).
function H.cadence(d) local n=d.burst or 1;return d.cooldown/n,d.damage/n,n end
-- Damage per second before Utility Power. Example: Tier I 4 / 0.8 = 5.0.
function H.baseDps(tier) tier=H.tier(tier);return H.Base.tierDamage[tier]/(H.COOLDOWN*H.Base.tierCooldown[tier]) end
-- The item card's text. Example, Tier II: 'One more turret, placed near you at every wave start. It
-- shoots 6 damage every 0.72 s within 25 studs, through 1 enemy. Utility Power raises its damage.
-- You can own 10.'
local function trim(x,places) return (string.format('%.'..places..'f',x):gsub('(%.%d-)0+$','%1'):gsub('%.$','')) end
function H.describe(tier)
 local d=H.weapon(tier,nil);local _,nail,n=H.cadence(d)
 local shot=n>1 and (n..' nails of '..trim(nail,1)..' damage') or (trim(d.damage,1)..' damage')
 local pierce=d.nativePierce>0 and (', through '..d.nativePierce..(d.nativePierce>1 and ' enemies' or ' enemy')) or ''
 return 'One more turret, placed near you at every wave start. It shoots '..shot..' every '..trim(d.cooldown,2)..' s within '..H.RANGE..' studs'..pierce..'. Utility Power raises its damage. You can own '..H.MAX_OWNED..'.'
end

-- Placement (2026-10-04) --------------------------------------------------------------------------
-- At each wave start a player's turrets stand on a ring around them, facing where they face: 8-14
-- studs out, a Handyman's 4-8 (Brotato's Engineer: "structures spawn close to each other"). Even
-- angles, each nudged up to JITTER of the step either way, at least SPACING studs apart. The ring's
-- radius is the smallest that fits them all, or a little more; when even the band's edge is too
-- small, the rest go on a second ring SPACING further out. Examples: 10 turrets fit one ring of 9+
-- studs; a Handyman's 10 are 8 at 8 studs and 2 at 13.
H.RING={8,14};H.SPACING=5;H.JITTER=.05
-- The smallest radius that fits n spots SPACING apart with the jitter: the closest two neighbours
-- are (1 - 2 x JITTER) of a step apart. Example: n = 10 -> 5 / (2 sin(0.9 pi / 10)) = 8.96.
function H.fitRadius(n) if n<2 then return 0 end;return H.SPACING/(2*math.sin(math.pi*(1-2*H.JITTER)/n)) end
-- How many fit at radius r (at least 1). Example: 8 studs -> 8.
function H.capacity(r) local n=1;while n<64 and H.fitRadius(n+1)<=r+1e-9 do n+=1 end;return n end
-- Spots for n turrets as {angle, radius} around the player (angle in radians on the ground, from
-- +X toward +Z), the first at `start` (their facing). rng (a Random) adds the jitter and a little
-- extra radius; nil gives the exact even ring.
function H.ring(n,band,rng,start)
 local spots,left,ring,radius={},math.max(0,math.floor(n)),0,0
 start=start or 0
 while left>0 do
  local r
  if ring==0 then
   local need=H.fitRadius(left)
   if need<=band[2] then r=math.max(band[1],need);r+=(band[2]-r)*.5*(rng and rng:NextNumber() or 0) else r=band[2] end
  else r=radius+H.SPACING end
  radius=r
  local k=math.min(left,H.capacity(r));local step=2*math.pi/k;local offset=start+ring*step/2
  for i=0,k-1 do
   local nudge=rng and (rng:NextNumber()*2-1)*H.JITTER*step or 0
   table.insert(spots,{angle=offset+i*step+nudge,radius=r})
  end
  left-=k;ring+=1
 end
 return spots
end
-- A spot's offset from the player on the ground.
function H.offset(spot) return Vector3.new(math.cos(spot.angle)*spot.radius,0,math.sin(spot.angle)*spot.radius) end
-- The ring angle of a facing direction (the same convention as H.offset).
function H.angle(direction) return math.atan2(direction.Z,direction.X) end
-- Keep automatic structures inside useful fighting space even when a player starts at a rim.
-- Height comes from the arena, never the player's current jump position.
function H.anchor(position,center,radius)
 if typeof(center)~='Vector3' then return position end
 local delta=Vector3.new(position.X-center.X,0,position.Z-center.Z)
 local inner=math.max(0,(radius or 60)-26)
 if delta.Magnitude>inner then delta=delta.Magnitude>.01 and delta.Unit*inner or Vector3.zero end
 return center+delta
end
-- Where one turret stands: probe(point) gives the ground under a point (nil: no ground there, out
-- of the arena or behind a wall). The ring spot, else half as far out, else the player's own spot.
-- Returns the ground point and the radius used (0 at the player). Example: a ring spot over a
-- cliff at 12 studs -> 6 studs out on the same line.
function H.spot(center,angle,radius,probe)
 local dir=Vector3.new(math.cos(angle),0,math.sin(angle))
 for _,r in {radius,radius*.5} do
  if r>.01 then local g=probe(center+dir*r);if g then return g,r end end
 end
 -- Never invent a floor at the player's feet: they may be jumping or over a cliff.
 return probe(center),0
end
-- True when every two points are at least `min` studs apart on the ground.
function H.spaced(points,min)
 for i=1,#points do for j=i+1,#points do
  local a,b=points[i],points[j]
  if Vector2.new(a.X-b.X,a.Z-b.Z).Magnitude<min-1e-6 then return false end
 end end
 return true
end
-- The server's MAX_SERVER shared out fairly: one each in turn while some is left. wants: how many
-- each player wants (an array); returns how many each gets. Example: {10,10,10,10} with 30 -> {8,8,7,7}.
function H.share(wants,budget)
 local out={};for i=1,#wants do out[i]=0 end
 budget=math.max(0,math.floor(budget or 0))
 local any=true
 while budget>0 and any do
  any=false
  for i=1,#wants do if budget>0 and out[i]<wants[i] then out[i]+=1;budget-=1;any=true end end
 end
 return out
end

-- Scrap Magnet (2026-10-04): every SCRAP_EVERY crystals picked up in a wave builds a temporary Nail
-- Turret on the player's ring, up to SCRAP_PER_COPY a wave per copy. Temporary turrets last until
-- the wave ends, don't count toward the player's 10, and do count toward the server's 30. How many
-- more to build now. Example: 2 copies, 130 crystals, 1 built -> 3 earned, 2 more.
H.SCRAP_EVERY=40;H.SCRAP_PER_COPY=3
function H.scrapBuilds(crystals,copies,built)
 local earned=math.min(math.floor(math.max(0,crystals or 0)/H.SCRAP_EVERY),H.SCRAP_PER_COPY*math.max(0,copies or 0))
 return math.max(0,earned-(built or 0))
end

-- Handyman = Brotato's Engineer (2026-10-04). His Utility Power x1.25 and Damage x0.5 gains live
-- in CharacterStats (the class's `gain`); these are the turret rules: he starts every run owning
-- one Nail Turret (it counts toward his 10), his ring is 4-8 studs, and every structure item
-- (the four turrets, Scrap Magnet, Toolbelt) costs him 20% less.
H.Engineer={class=H.Class,ring={4,8},discount=.2,free='turret_nail'}
function H.band(class) return class==H.Engineer.class and H.Engineer.ring or H.RING end
function H.startsWithTurret(class) return class==H.Engineer.class end
-- A price multiplier on top of the player's own (EconomyConfig.modifier). Example: a wave-5 Nail
-- Turret, 41 for anyone, is floor(41 x 0.8) = 32 for him.
function H.priceFactor(class,entry) return (class==H.Engineer.class and type(entry)=='table' and entry.structure) and 1-H.Engineer.discount or 1 end
-- Shop weighting, as Handyman weapons get it ("same class", ShopService): a Handyman, or anyone
-- carrying a Handyman-class weapon, has WEIGHT (+ EconomyConfig.classBonus on early waves) of item
-- rolls pick only among the structure items. carried: weapon ids. n: one draw in [0,1). Example: a
-- Handyman on wave 1 (bonus 0.15) -> 30% of his item offers come from the structure items there.
H.WEIGHT=.15
function H.favoured(class,carried)
 if class==H.Engineer.class then return true end
 for _,id in carried or {} do
  local w=Weapons.ById[id]
  if w and not w.godly and table.find(w.classes or {w.home},H.Engineer.class) then return true end
 end
 return false
end
function H.weightPool(pool,favoured,n,bonus)
 if not favoured or n>=H.WEIGHT+(bonus or 0) then return pool end
 local out={};for _,entry in pool do if entry.structure then table.insert(out,entry) end end
 return #out>0 and out or pool
end

-- Facing (a CFrame.Angles Y angle) for a flat direction: lookVector = (-sin a, 0, -cos a).
function H.yaw(direction) return math.atan2(-direction.X,-direction.Z) end
-- Item and shop art per tier: the uploaded blender-handyman-turret/previews/icon_T<n>.png (512 px).
H.Icons={'rbxassetid://100505469530773','rbxassetid://110375220181503','rbxassetid://112292832566551','rbxassetid://78790900806318'} -- previews/icon_T1-4.png, uploaded 2026-10-04
-- The installed turret models, or nil until all four are there (RogueliteCombat.HandymanTurrets
-- T1-T4, each a Model with Base, Head and Barrel parts: InstallHandymanTurret.luau).
function H.templates(combat)
 local folder=combat and combat:FindFirstChild('HandymanTurrets')
 if not folder then return nil end
 for t=1,H.MaxTier do
  local m=folder:FindFirstChild('T'..t)
  if not (m and m:IsA('Model')) then return nil end
  for _,name in {'Base','Head','Barrel'} do local p=m:FindFirstChild(name);if not (p and p:IsA('BasePart')) then return nil end end
 end
 return folder
end
return H
