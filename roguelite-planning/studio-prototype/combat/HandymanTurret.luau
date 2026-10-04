-- Handyman turret rules (HANDYMAN_TURRET.md, 2026-10-03). Shared and pure: HandymanTurretService
-- (server) builds, aims and fires from these numbers, ShopService prices and checks the upgrade,
-- HandymanTurret.client draws it and shows BUILD, TurretTests checks them. Touches no Instances
-- except templates(), which only looks. Since 2026-10-04 mobs can break it: health, break and
-- rebuild rules below, and H.posts (server only) for the mob scripts.
-- Studio: ReplicatedStorage.RogueliteCombat.HandymanTurret, Sandboxed = true with CharacterStats'
-- Capabilities (ShopService, sandboxed, requires it).
--
-- The turret counts as a ranged Handyman Utility weapon for every bonus (CharacterStats.weapon):
-- Damage, Ranged damage, Utility power, the Handyman's own-class +15%, Attack speed, Cooldown
-- reduction, Attack range, Projectile speed, Pierce and Extra projectiles. Its tiers step like the
-- weapons' (WeaponCatalog: damage x1.4, cooldown x1 / .9 / .8 / .7).
-- Size (2026-10-03, after the melee vs ranged pass): Tier I is 4 damage every 0.8 s = 5.0 DPS,
-- 45% of an average Tier I ranged weapon (11.2 DPS over the 22 class ranged weapons), with 25 studs
-- of range (they average 29; the Nail Gun has 30). TurretTests checks both against WeaponCatalog.
local Stats=require(script.Parent.CharacterStats)
local Weapons=require(script.Parent.WeaponCatalog)
local E=require(script.Parent.EconomyConfig)
local H={Id='Turret',Class='Handyman',MaxTier=4}
H.DAMAGE=4;H.COOLDOWN=.8;H.RANGE=25;H.SPEED=110
-- Seconds between BUILDs (moving the turret to you). The wave-start build doesn't start it.
H.BUILD_COOLDOWN=8
-- Studs in front of the player it lands, pulled in before a wall.
H.BUILD_AHEAD=3.5
-- The head idles (Aim cleared) after this long without a target.
H.AIM_IDLE=1.5
-- BUILD: B on a keyboard and R1 on a gamepad, and an on-screen button. Taken in a run: Q / pad X
-- (the melee dash), E / pad Y (the revive prompt), pad B (back out of menus); L1/R1 only cycle
-- the death screen's spectating, when BUILD is hidden.
H.Keys={Keyboard=Enum.KeyCode.B,Gamepad=Enum.KeyCode.ButtonR1}
-- Tier IV is a gatling: the barrel cluster spins and each cycle fires 3 nails a third as strong, a
-- third of the cooldown apart, each at the nearest enemy then, so it sprays a crowd at the same DPS.
H.Burst={1,1,1,3}
H.GATLING_SPREAD=3 -- degrees of random yaw on each gatling nail
-- The weapon-like entry CharacterStats.weapon turns into the turret's numbers (id 'Turret' is the
-- damage source: kill credit, run analytics and the utilityKills quest count it as the owner's).
-- trait 'pierce': like the Nail Gun, it pierces floor(tier/2) more enemies (0 / 1 / 1 / 2).
H.Base={id=H.Id,name='Turret',kind='Ranged',home=H.Class,utility=true,rarity='Common',damage=H.DAMAGE,
 cooldown=H.COOLDOWN,range=H.RANGE,projectileSpeed=H.SPEED,trait='pierce',nativeKnockback=0,burn=0,poison=0,slow=0,tags={'Projectile','Handyman','Utility'}}
H.Base.tierDamage={}
for t=1,H.MaxTier do H.Base.tierDamage[t]=math.floor(H.DAMAGE*Weapons.TierGrowth^(t-1)+.5) end -- 4 / 6 / 8 / 11
H.Base.tierCooldown=table.clone(Weapons.TierCooldown) -- .8 / .72 / .64 / .56 s
function H.tier(t) return math.clamp(math.floor(tonumber(t) or 1),1,H.MaxTier) end
-- The turret's numbers for this owner, as a weapon definition (damage per cycle, cooldown, range,
-- projectileSpeed, nativePierce, projectileRadius...), plus burst (nails per cycle).
function H.weapon(tier,stats,class)
 local d=Stats.weapon(H.Base,stats,class,H.tier(tier))
 d.burst=H.Burst[d.tier] or 1
 return d
end
-- One nail: seconds between nails and its damage. Example, Tier IV with no bonuses: 11 damage
-- every 0.56 s is 3 nails of 3.67, 0.187 s apart (19.6 DPS either way).
function H.cadence(d) local n=d.burst or 1;return d.cooldown/n,d.damage/n,n end
-- Damage per second before character bonuses (the doc's table). Example: Tier I 4 / 0.8 = 5.0.
function H.baseDps(tier) tier=H.tier(tier);return H.Base.tierDamage[tier]/(H.COOLDOWN*H.Base.tierCooldown[tier]) end

-- Upgrades (bought in the run shop, between waves): Tier I -> II, II -> III, III -> IV each cost
-- what one more weapon copy of the tier you have costs (combining two copies is a weapon's tier
-- step): the middle of that tier's weapon price band, 18 / 42 / 77, then the shop's wave inflation
-- and the player's discounts (EconomyConfig.price), like any offer.
-- Example: Tier II on wave 5 costs 18 + 5 + 18 x 5 x 10% = 32 shards.
H.UPGRADE_BASE={}
for t=1,H.MaxTier-1 do local band=E.TIER_PRICE_BANDS[t];H.UPGRADE_BASE[t]=math.floor((band[1]+band[2])/2) end
-- Price to go from `tier` to the next, nil at Tier IV.
function H.upgradePrice(tier,wave,modifier)
 local base=H.UPGRADE_BASE[math.floor(tonumber(tier) or 0)];if not base then return nil end
 return E.price(base,math.max(1,math.floor(tonumber(wave) or 1)),modifier or 1)
end
-- ShopService's check (it already checked phase Shop, revision, rate and that the player is alive
-- in the run). seen: the tier the player's button showed, so a stale click can't buy twice.
-- Returns true,nil,price or false,reason.
function H.canUpgrade(class,tier,seen,shards,wave,modifier,ready)
 if not ready then return false,'Turrets are not installed yet' end
 if class~=H.Class then return false,'Only a Handyman has a turret' end
 tier=H.tier(tier)
 if tier>=H.MaxTier then return false,'Your turret is already Tier IV' end
 if seen~=tier then return false,'Turret changed. Please try again.' end
 local price=H.upgradePrice(tier,wave,modifier)
 if type(shards)~='number' or shards<price then return false,'Not enough shards' end
 return true,nil,price
end
-- The shop snapshot's turret row (ShopService.publish -> ShopUI): nil for anyone without one.
function H.offer(class,tier,wave,modifier,ready)
 if not ready or class~=H.Class then return nil end
 tier=H.tier(tier)
 local nextTier=tier<H.MaxTier and tier+1 or nil
 return {tier=tier,next=nextTier,price=nextTier and H.upgradePrice(tier,wave,modifier) or nil}
end
-- BUILD (RunAction 'BuildTurret') and the wave-start build. c: {ready, class, admin (an ADMIN panel
-- turret, any class), member, lobby, alive, down, phase, paused, frozen, now, readyAt}.
-- Returns true or false,reason.
function H.canBuild(c)
 if not c.ready then return false,'Turrets are not installed yet' end
 if c.class~=H.Class and not c.admin then return false,'Only a Handyman can build a turret' end
 if not c.member or c.lobby then return false,'Not in a run' end
 if not c.alive or c.down then return false,'Get back on your feet first' end
 if c.phase~='Combat' and c.phase~='Practice' then return false,'Build during a wave' end
 if c.paused or c.frozen then return false,'Not while the run is held' end
 if (c.now or 0)<(c.readyAt or 0) then return false,'Still cooling down' end
 return true
end
-- Facing (a CFrame.Angles Y angle) for a flat direction: lookVector = (-sin a, 0, -cos a).
function H.yaw(direction) return math.atan2(-direction.X,-direction.Z) end

-- Health (2026-10-04, user: "lets let mobs destroy it"). Every number is here to retune once the
-- turret's cost is decided. Tier I: 60 + 15 a wave after the first; x1.5 each tier above I; times the
-- owner's gear power health share (CharacterStats.powerHealth, +6% a point above 1, like their own
-- max health), because a later map's mobs hit harder by just that much (RunSetupRules.enemyScale).
-- Waves 1 / 5 / 10 / 20 at power 1:
--   Tier I 60 / 120 / 195 / 345, II 90 / 180 / 293 / 518, III 135 / 270 / 439 / 776, IV 203 / 405 / 658 / 1164.
-- That is about 11 hits from a regular zombie of the same wave (5 + 1.5 a wave, a hit every 0.8 s).
-- Example, wave 5 Tier I (120 HP) vs zombies hitting 11: one alone needs 11 hits, about 8 s;
-- three, 2.9 s; a swarm of ten, under a second.
H.HEALTH=60;H.HEALTH_PER_WAVE=15;H.HEALTH_TIER=1.5
-- After it breaks, BUILD works again this many seconds later (sooner if its own cooldown ends first).
H.REBUILD_DELAY=5
-- Its health bar turns from lime to red under this share.
H.LOW_HEALTH=.3
function H.maxHealth(tier,wave,power)
 wave=math.max(1,math.floor(tonumber(wave) or 1))
 return math.floor((H.HEALTH+H.HEALTH_PER_WAVE*(wave-1))*H.HEALTH_TIER^(H.tier(tier)-1)*Stats.powerHealth(power)+.5)
end
-- What one hit takes off: the mob's damage against a player, after the owner's armour and contact
-- resistance exactly as for the player (CharacterStats.incoming). None of the player-only defences
-- (dodge, first-hit block, pet shield, the zombies' shared swing gap). Example: 11 with 5 armour ->
-- 11 / (1 + 5 / 15) = 8.25; no stats -> 11.
function H.damageTaken(amount,stats)
 amount=math.max(0,tonumber(amount) or 0)
 if type(stats)~='table' or type(stats.Armor)~='number' or type(stats.ContactReduction)~='number' then return amount end
 return Stats.incoming(amount,stats)
end
-- A hit on a turret with `hp` left: the hp after it, and true when that hit broke it. A broken one
-- (0) takes nothing. Example: 6 HP, a hit of 6 -> 0, true.
function H.takeHit(hp,amount,stats)
 if not (hp>0) then return 0,false end
 local left=math.max(0,hp-H.damageTaken(amount,stats))
 return left,left<=0
end
-- When BUILD works again after a break at `now`: REBUILD_DELAY later, or when its own cooldown
-- (readyAt) ends if that is sooner. Examples, broken at 100: moved at 99 (ready 107) -> 105; moved
-- at 96 (ready 104) -> 104; ready since 95 -> 95, so right away.
function H.rebuildAt(now,readyAt) return math.min(readyAt or now,now+H.REBUILD_DELAY) end

-- Mob targets (server only; empty on clients). HandymanTurretService keeps one table per turret in
-- H.posts, built by H.newPost. RogueliteZombieChase makes it a mob's target when it is nearer than
-- every living player (H.nearer); EnemyAttacks and ZombieAttacks then swing, shoot and slam at it as
-- at a player's root: Position (its middle), Parent (its Folder), AssemblyLinearVelocity (still).
-- A hit adds the mob's damage to `taken`; the service takes it off hp with the owner's armour.
-- hp > 0 while it stands. pad: how far its edge sits past a player's half-body (BODY, the 0.75 in
-- EnemyCatalog.Reach), added to reach and stop distances so mobs stop at its edge as at a body.
-- Plain data, never functions: the service is sandboxed and those scripts are not.
H.BODY=.75
H.posts={}
function H.newPost(folder)
 local post={turret=true,Parent=folder,Position=Vector3.zero,AssemblyLinearVelocity=Vector3.zero,userId=0,hp=0,pad=.25,taken=0}
 post.root=post -- the chase reads .root and .userId from the row it picks
 return post
end
-- A mob's target: `best` (its nearest living player's row, `distance` studs away on the ground)
-- unless a standing turret is nearer, measured on the ground to its edge as to a body. Works for any
-- number of turrets and owners. Example: a zombie 10 studs from you and 6 from your turret goes for
-- the turret; you step to 5 studs from it and it comes back to you.
function H.nearer(posts,from,best,distance)
 distance=distance or math.huge
 for _,post in posts do
  if post.hp>0 then
   local d=Vector2.new(post.Position.X-from.X,post.Position.Z-from.Z).Magnitude-post.pad
   if d<distance then best,distance=post,math.max(0,d) end
  end
 end
 return best,distance
end
-- BUILD button and shop art per tier: the uploaded blender-handyman-turret/previews/icon_T<n>.png
-- (512 px). Empty until they're uploaded in Studio; the button shows a live view of the model then.
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
