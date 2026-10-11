-- Chef pizza drops (plans/2026-10-09-chef-roster-weapon-types-design.md, "Chef"): the pure rules.
-- A Chef CLASS ability, not a Pizza Cutter one (2026-10-10, user: "make it universal for all his
-- weapons"): a Chef's kill with ANY weapon whose starter class is Chef (WeaponCatalog d.class, today
-- Frying Pan, Spatula, Molotov, Egg, Steak and Pizza Cutter) has the same 15% chance; no weapon has
-- its own rate. It follows the class tag, so moving a weapon into or out of Chef moves its drops too.
-- A non-Chef holding a Chef weapon gets none, the same as specialty (+10% only for your class's
-- weapons). Example: a Chef's Egg kill rolls 15%; a Brawler's Frying Pan kill rolls nothing.
-- A Chef's kill with a Chef weapon has a 15% chance to drop a pizza slice where the enemy died. Any
-- living player in the run who reaches it heals 10% of their own max HP, times their Recovery (the
-- heart pickups' healing path, CharacterService.heal). Example: max HP 150 -> 15 HP before Recovery;
-- with Chef's +25% Recovery that is 18.75 HP. The eater also gets a Full Belly stack (P.buffStacks
-- below): +4% damage, +4% attack speed and +3% speed each, up to 5, for 10 s after the latest slice.
-- A slice lasts 12 s and blinks for its last 3 s. Each Chef keeps at most 4 on the ground (a 5th
-- removes his oldest) and drops at most one every 1 s, so fast weapons can't flood the map.
-- 2026-10-10 (user: "make pizzas a little more common, I'm not seeing them ever"): 8% / 1.5 s ->
-- 15% / 1 s. At 0.5 kills a second (early waves) that is a slice about every 13 s instead of 25 s;
-- at 2 kills a second about one every 3.3 s instead of 6 s (the cap of 4 still bounds the ground).
-- Slices are a variant of HeartDropService's hearts: ChefPizzaService decides the drops with these
-- rules, HeartDropService runs the pickup (pull, heal, expiry, pause, clean-up) and
-- ChefPizzaVisuals draws them. No services, instances or Vector3 here, so ChefPizzaTests runs this
-- in the Luau CLI (run_chef_pizza_tests.py) or Studio Edit. Sandboxed ModuleScript in
-- ReplicatedStorage.RogueliteCombat (HeartDropService's side is sandboxed).
local P={
 CLASS='Chef',
 CHANCE=.15, -- per eligible kill
 SPACING=1, -- seconds between one Chef's drops
 MAX_PER_CHEF=4, -- slices one Chef can have on the ground
 LIFETIME=12, -- seconds on the ground
 BLINK=3, -- the last seconds it blinks
 HEAL_FRACTION=.1, -- of the picker's max HP, before Recovery
 -- Full Belly (2026-10-10, user: "he should get a little buff across his stats when he picks it up,
 -- not just a heal. Like a temp buff that stacks to a certain amount"). See P.stacksAfterPickup.
 BUFF_NAME='Full Belly',
 BUFF_STACKS=5, -- most stacks one player holds
 BUFF_SECONDS=10, -- how long the stacks last after the latest slice
 BUFF_PER_STACK={Damage=4,AttackSpeed=4}, -- points added to these percent stats per stack
 BUFF_SPEED_PER_STACK=3, -- percent of the player's Movement speed per stack
 -- Presentation (ChefPizzaVisuals). The template is scaled to WIDTH studs across, tilted TILT
 -- degrees so its toppings read from the game camera, and bobs BOB studs while it spins.
 WIDTH=2.4,TILT=30,BOB=.22,BOB_SPEED=2.7,SPIN_SPEED=1.8,
}

-- Whether the weapon that landed the kill is a Chef weapon: its class tag, the WeaponCatalog.inClass
-- rule (d.class, or d.home for a bare table). weapon = WeaponCatalog.ById[id] (nil for 'Turret',
-- 'Bloater' and other non-weapon kill credit). Godlies belong to no class. id is unused (kept for
-- callers); the 2026-10-09 fallback id list went once every catalog entry carried d.class.
function P.isChefWeapon(weapon,id)
 if type(weapon)~='table' or weapon.godly then return false end
 return (weapon.class or weapon.home)==P.CLASS
end

-- One kill. o = {class, weapon, weaponId, now, lastDrop (this Chef's last drop time or nil), rng
-- (anything with :NextNumber() in [0,1)), chance (optional override, Studio's TestPizzaChance)}.
-- Returns true when a slice drops, else false and why. The roll is only spent on an eligible kill.
-- Example: a Chef's Spatula kill 0.9 s after his last slice -> false, 'spacing', no roll.
function P.decide(o)
 if o.class~=P.CLASS then return false,'class' end
 if not P.isChefWeapon(o.weapon,o.weaponId) then return false,'weapon' end
 if type(o.lastDrop)=='number' and o.now-o.lastDrop<P.SPACING then return false,'spacing' end
 local chance=type(o.chance)=='number' and math.clamp(o.chance,0,1) or P.CHANCE
 if o.rng:NextNumber()>=chance then return false,'chance' end
 return true
end

-- One Chef's slices already on the ground, each {born=number, taken=bool} (taken: flying to a player,
-- as good as eaten). Returns the ones to remove so the new slice keeps him at MAX_PER_CHEF: his
-- oldest first, never one already flying. Example: 4 down, born 1, 2, 3, 4 -> remove the one born at 1.
function P.evictions(slices,max)
 max=max or P.MAX_PER_CHEF
 local free={}
 for _,s in slices do if not s.taken then table.insert(free,s) end end
 table.sort(free,function(a,b) return a.born<b.born end)
 local out={}
 for i=1,math.min(#slices+1-max,#free) do out[i]=free[i] end
 return out
end

function P.expiresAt(born) return born+P.LIFETIME end

-- Base heal before Recovery: CharacterService.heal multiplies it by Recovery, like a heart's.
function P.healBase(maxHealth)
 return math.max(0,tonumber(maxHealth) or 0)*P.HEAL_FRACTION
end

-- Server pickup check (HeartDropService.collect calls it for every slice). o = {exists (model still
-- there), taken (already flying to someone), born, now, rest (seconds before it can be grabbed,
-- ShardMotion.REST_SECONDS), alive, distance (server body to slice), radius}. Returns ok, why not.
function P.canCollect(o)
 if not o.exists then return false,'gone' end
 if o.taken then return false,'taken' end
 if o.now>=P.expiresAt(o.born) then return false,'expired' end
 if o.now-o.born<(o.rest or 0) then return false,'resting' end
 if not o.alive then return false,'dead' end
 if not (o.distance<=o.radius) then return false,'far' end
 return true
end

-- Full Belly. Every slice that reaches a player (the Chef or a teammate, like the heal) gives that
-- player one stack, up to BUFF_STACKS. Each pickup restarts the BUFF_SECONDS timer for all of his
-- stacks; when it runs out, all of them go at once (one clear rule: keep eating or lose it all).
-- Each stack: +4% Damage, +4% Attack speed (points on those percent stats, CharacterStats.resolve's
-- flat terms) and +3% Movement speed (a percent of the speed, resolve's percent terms).
-- Example: slices at 0 s, 6 s and 12 s -> 1, 2, then 3 stacks (+12% damage, +12% attack speed,
-- +9% speed) until 22 s; a slice at 23 s starts again at 1. The server keeps the stacks
-- (ChefPizzaService) and runs them through CharacterService.refresh; a paused run holds the timer.
-- How many stacks are live at `now`: 0 once untilTime has passed (or for bad input).
function P.buffStacks(now,stacks,untilTime)
 if type(stacks)~='number' or type(untilTime)~='number' or type(now)~='number' or not (now<untilTime) then return 0 end
 return math.clamp(math.floor(stacks),0,P.BUFF_STACKS)
end
-- One slice eaten at `now`: the new stack count and the new end time.
-- Example: 5 stacks live -> still 5, timer back to 10 s.
function P.stacksAfterPickup(now,stacks,untilTime)
 return math.min(P.BUFF_STACKS,P.buffStacks(now,stacks,untilTime)+1),now+P.BUFF_SECONDS
end
-- Seconds left (0..BUFF_SECONDS) and the share of the full timer left (0..1), for the HUD's bar.
function P.buffLeft(now,untilTime)
 if type(now)~='number' or type(untilTime)~='number' then return 0,0 end
 local left=math.clamp(untilTime-now,0,P.BUFF_SECONDS)
 return left,left/P.BUFF_SECONDS
end
-- The stat terms for `stacks`: flat (added to the percent stats) and percent (of Movement speed),
-- or nil, nil for none. Example: 3 -> {Damage=12, AttackSpeed=12}, {MoveSpeed=9}.
function P.buffBonus(stacks)
 local n=math.clamp(math.floor(tonumber(stacks) or 0),0,P.BUFF_STACKS)
 if n<=0 then return nil,nil end
 local flat={}
 for id,v in P.BUFF_PER_STACK do flat[id]=v*n end
 return flat,{MoveSpeed=P.BUFF_SPEED_PER_STACK*n}
end
-- The ability row's line (RunSetupUI): "+4% damage and attack speed, +3% speed per stack (up to 5, 10 s)".
function P.buffText()
 local d,a=P.BUFF_PER_STACK.Damage,P.BUFF_PER_STACK.AttackSpeed
 local first=d==a and ('+'..d..'% damage and attack speed') or ('+'..d..'% damage, +'..a..'% attack speed')
 return string.format('%s, +%d%% speed per stack (up to %d, %d s)',first,P.BUFF_SPEED_PER_STACK,P.BUFF_STACKS,P.BUFF_SECONDS)
end

-- Blink through the last BLINK seconds (faster in the last 1.2), never while flying to a player.
-- The heart pickups blink the same way (HeartVisuals).
function P.hidden(now,expiresAt,pulling)
 local left=expiresAt-now
 return not pulling and left<P.BLINK and (now*(left<1.2 and 8 or 4))%1<.35
end

-- Bob height (studs above its spot) and spin angle (radians about the vertical) at `now`.
function P.pose(born,now)
 local age=now-born
 return math.sin(age*P.BOB_SPEED+born%6.28)*P.BOB,age*P.SPIN_SPEED+born%6.28
end

return P
