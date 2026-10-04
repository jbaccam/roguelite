-- Handyman turret rules (HANDYMAN_TURRET.md, 2026-10-03). Shared and pure: HandymanTurretService
-- (server) builds, aims and fires from these numbers, ShopService prices and checks the upgrade,
-- HandymanTurret.client draws it and shows BUILD, TurretTests checks them. Touches no Instances
-- except templates(), which only looks.
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
-- BUILD button and shop art per tier: the uploaded blender-handyman-turret/previews/icon_T<n>.png
-- (512 px). Empty until they're uploaded in Studio; the button shows a live view of the model then.
H.Icons={'','','',''}
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
