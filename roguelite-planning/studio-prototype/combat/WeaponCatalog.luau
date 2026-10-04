-- Studio practice tuning. IDs match the reviewed, user-sized showcase models.
local C={Slots=6, List={}, ById={}}
local names={'Glock','Frying Pan','Nunchucks','Katana','Kusarigama','Spatula','Baseball Bat','Draco','Fart Gun','Shotgun','T-Shirt Cannon','Rocket Launcher','Boomerang','Kunai','Molotov','Egg','Steak','Rubber Duck','Deck of Cards','Boxing Gloves','Cinder Block','Yo-Yo','Bowling Ball','Bowling Pin','Nail Gun','Wrecking Ball','Shovel','Paint Roller','Vacuum Cleaner','Power Washer','Magic Staff','Mjolnir','Excalibur',"Pandora's Box","Medusa's Head",'Crystal Ball',"Reaper's Scythe","Poseidon's Trident",'Storm Bow','Shadow Daggers','Vampire Blade','Ray Gun'}
local ranged={[0]=true,[7]=true,[8]=true,[9]=true,[10]=true,[11]=true,[12]=true,[13]=true,[14]=true,[15]=true,[18]=true,[22]=true,[24]=true,[28]=true,[29]=true,[30]=true,[33]=true,[34]=true,[35]=true,[38]=true,[41]=true}
-- Tiers trade two copies for one stronger copy; some weapons improve crowd handling.
-- Range is in Roblox studs. Damage is per hit (Deck of Cards: total three-card volley).
-- {damage, cooldown, range, tierDamage, tierCooldown, trait}: damage and cooldown as authored, before
-- rarity power (below). Tier tables are built from them; only Boxing Gloves author their own.
-- The pre-2026-10-02 tier tables are kept in WEAPON_BALANCE.md (and WeaponBalanceTests' Tier IV check).
-- Melee vs ranged pass (2026-10-03, user: "ranged weapons are dominating ... mobs never get close";
-- "increase range on most melee weapons"). Ranged: range about -22% and cooldown x1.13 (-12% attack
-- rate). Melee: reach about +20%, and the five weakest (Pan, Nunchucks, Kusarigama, Shovel, Roller)
-- +10-20% damage. Godly keep their damage and cooldown (~24 DPS), only range moves. Not changed:
-- Rubber Duck (12 studs is already melee distance) and Medusa's rate (it is the slow weapon). Nail
-- Gun stays under .3 s (its shop price band) and loses more range instead. Old -> new in
-- WEAPON_BALANCE.md. Example: Glock 45 studs / 0.72 s -> 35 studs / 0.82 s; Frying Pan 6 -> 7.5 studs, 16 -> 18 dmg.
local profiles={
 {12,.82,35}, -- Glock
 {18,1.05,7.5}, -- Pan
 {7,.5,7.5}, -- Nunchucks
 {18,.95,13}, -- Katana
 {17,1.15,14}, -- Kusarigama
 {9,.55,7.5}, -- Spatula
 {20,1.25,9.5}, -- Bat
 {3,.19,33}, -- Draco
 {4,.9,22}, -- Fart Gun (poison)
 {3,1.25,19,nil,nil,'pellets'}, -- Shotgun
 {18,1.55,31,nil,nil,'pierce'}, -- T-shirt
 {32,2.7,55}, -- Rocket
 {7,1.02,27,nil,nil,'bounce'}, -- Boomerang
 {6,.55,30,nil,nil,'pierce'}, -- Kunai
 {3,1.9,30}, -- Molotov (burn)
 {10,.96,25}, -- Egg
 {16,.85,7.5}, -- Steak
 {5,.32,12,nil,nil,'bounce'}, -- Duck
 {15,1.08,33,nil,nil,'cards'}, -- Cards
 {8,.42,7.5,{8,15,28,48},{1,.94,.88,.76}}, -- Gloves: alternating quick jabs (T4 ~150 DPS: the close-range trade)
 {30,1.35,8.5}, -- Block
 {8,.8,22,nil,nil,'bounce'}, -- Yo-yo
 {24,1.8,27,nil,nil,'pierce'}, -- Ball
 {13,1.42,22}, -- Pin
 {4,.295,30,nil,nil,'pierce'}, -- Nails
 {28,1.6,14}, -- Wrecking ball
 {20,1.15,9.5}, -- Shovel
 {12,.8,10.5}, -- Roller
 {4,.36,16}, -- Vacuum
 {3,.27,23,nil,nil,'pierce'}, -- Washer
 {9,1.3,35}, -- Staff (arcane energy orb)
 {22,2,9.5}, -- Mjolnir (2.4 felt slow; 2026-10-01)
 {26,1.35,10}, -- Excalibur
 {25,2.25,39}, -- Pandora
 {5,1.2,30,nil,nil,'shots'}, -- Medusa (slow: C.SlowById)
 {13,1.19,37,nil,nil,'bounce'}, -- Crystal (lightning)
 -- Godly (plans/2026-10-01-G): ~24 single-target DPS at Tier I (power 160); specials add crowd power.
 {30,1.25,12}, -- Reaper's Scythe: 360 reap, raises wraiths
 {34,1.5,10.5}, -- Poseidon's Trident: stab, or throw + tidal wave
 {14,1.2,39}, -- Storm Bow: per storm arrow, 5 split arrows
 {16,1.3,12}, -- Shadow Daggers: per chained hit
 {32,1.3,10.5}, -- Vampire Blade: heals
 {22,.9,37}, -- Ray Gun: kills disintegrate in a burst
}
-- Native slows (2026-10-03: nobody noticed Medusa's). strength: % off the enemy's walk speed
-- (bosses take half), seconds before the Duration stat. CombatEffectsService uses the bigger of these
-- and the player's SlowStrength / SlowDuration stats (25% / 2 s by default). Example: a zombie
-- walking 12 studs/s crawls at 7.8 for 2 s after each Medusa hit.
C.SlowById={['34']={strength=35,seconds=2}}
-- Rarity (RARITY_GODLY_ARMOR.md §4): one per weapon, forever. ChestConfig builds its chest pools from
-- these lists, in this order, so chest odds, Armory tags and the run shop always agree.
C.Rarities={'Common','Rare','Epic','Legendary','Godly'}
C.RarityLists={
 Common={'01','05','00','08','12','15','19','17','24','26','30','35'},
 Rare={'02','06','09','07','13','16','23','21','27','29','34','33'},
 Epic={'04','10','14','20','28'},
 Legendary={'03','11','18','22','25','32','31'},
 Godly={'36','37','38','39','40','41'},
}
C.RarityOf={}
for _,r in C.Rarities do for _,id in C.RarityLists[r] do C.RarityOf[id]=r end end
-- Rarity power (§4; user 2026-10-02: "put it in the base stats instead of a multiplier"): damage per
-- second x1.05 Rare, x1.1 Epic, x1.2 Legendary, built into each weapon's own base numbers so the Armory
-- and shop show it. Damage rounds down to a whole number and the cooldown shortens by what rounding
-- took, so damage per second is exactly x power. Godly numbers are authored at their power (160).
-- Example: Katana 18 dmg every .95 s becomes 21 dmg every .924 s (x1.2 per second).
C.RarityPower={Common=1,Rare=1.05,Epic=1.1,Legendary=1.2,Godly=1}
-- Tiers (§6, Brotato style; user 2026-10-02): each tier x1.4 damage and cooldown x{1,.9,.8,.7}, so
-- an upgrade hits harder AND faster. Six weapons step differently to keep Tier IV within 10% of its
-- old damage per second: Shotgun, Boomerang, Deck of Cards and Nail Gun also gain pellets, bounces,
-- cards or pierce each tier, so their damage steps gentler; Frying Pan and Molotov stepped steeper
-- before. Example Glock: 12 / 17 / 24 / 33 damage every .82 / .74 / .66 / .57 s (.72 at Tier I before 2026-10-03).
C.TierGrowth=1.4;C.TierCooldown={1,.9,.8,.7}
C.TierGrowthById={['01']=1.45,['09']=1.25,['12']=1.35,['14']=1.5,['18']=1.3,['24']=1.35}
-- Godly specials, per tier where a list (index = tier). Read by GodlyWeapons (server) and
-- GodlyVisuals (client). Every special is capped and never triggers another special.
C.Godly={
 ['36']={ghostChance=1/3,ghostCap={4,4,4,6},ghostLife=6,ghostClaw=.25,ghostClawEvery=1,ghostSpeed=26,ghostReach=3,ghostSight=40,bigClaw=2},
 ['37']={waveRadius={10,10,10,14},waveFactor=.6,wavePush=32,waveTime=.5},
 ['38']={arrows={5,5,5,7},spread=10,loneMax=2},
 ['39']={chain={5,5,5,7},hop=12,loneHits=2},
 ['40']={leech={.08,.08,.08,.12},wispHeal=2,capBonus={0,0,0,5}},
 ['41']={burstRadius={6,6,6,9},burstFactor={.5,.5,.5,.75}},
}
function C.isGodly(id) return C.Godly[id]~=nil end
-- Legendary extra moves (RARITY_GODLY_ARMOR.md §8; user 2026-10-02: only at Tier IV). Read by
-- LegendaryMoves (server, owns every hit) and LegendaryVisuals (client). every = the nth attack of
-- that slot; factor = the move's hit as a share of the weapon's own hit. Every move hit is secondary
-- (no crits, chains, knockback or other specials) and capped. Radii grow with Area Size.
--   03 Katana: every 3rd swing throws a flying slash through a line of enemies
--   11 Rocket Launcher: every 4th rocket splits into 3 homing mini rockets
--   18 Deck of Cards: every 5th throw is a Royal Flush, 5 gold cards that pierce everything
--   22 Bowling Ball: a roll that hits 5+ enemies is a STRIKE! with a pin explosion where it stops
--   25 Wrecking Ball: each swing that connects sends out a ground shockwave ring
--   32 Excalibur: every swing also shoots a golden beam slash
--   31 Mjolnir: every 4th throw calls down a lightning strike where it lands
C.Legendary={
 ['03']={move='Slash',every=3,factor=.75,range=30,speed=78,width=3.4},
 ['11']={move='Split',every=4,minis=3,factor=.45,radius=5.5,splitAfter=.28,speed=58,spread=18},
 ['18']={move='Flush',every=5,cards=5,factor=.5,fan=26,rangeScale=1.25,width=1.5},
 ['22']={move='Strike',hits=5,factor=1,radius=9,push=34},
 ['25']={move='Shock',factor=.4,radius=11,time=.42,push=26},
 ['32']={move='Beam',every=1,factor=.45,range=22,speed=56,width=4.4},
 ['31']={move='Thunder',every=4,factor=1.2,radius=8,delay=.2},
}
-- A weapon's Legendary move is live at Tier IV only.
function C.legendaryMove(id,tier) return (tonumber(tier) or 1)>=4 and C.Legendary[id] or nil end

-- Player-facing lines built from the numbers above (the item card in the chest odds, 2026-10-02), so
-- the words can't drift from the tuning. Example: godlyText('40',1) = 'Every hit heals you for 8% of
-- its damage. Every kill sends a blood wisp back to you that heals 2 HP.'
local function num(x) local s=string.format('%.1f',x);return (s:gsub('%.0$','')) end
local function pct(x) return num(x*100)..'%' end
local function at(v,tier) if type(v)~='table' then return v end;return v[math.clamp(math.floor(tonumber(tier) or 1),1,#v)] end
local function ord(n) local t=n%100;return n..((t>=11 and t<=13) and 'th' or ({'st','nd','rd'})[n%10] or 'th') end
-- The special at a tier, in one or two sentences.
function C.godlyText(id,tier)
 local s=C.Godly[id];if not s then return nil end
 local function v(k) return at(s[k],tier) end
 if id=='36' then return '1 in '..math.round(1/s.ghostChance)..' kills raises a crimson wraith that hunts for '..num(s.ghostLife)..' s, clawing for '..pct(s.ghostClaw)..' of your damage (up to '..v('ghostCap')..' at once).'
 elseif id=='37' then return 'Stabs up close and throws at range. Where it lands, a '..num(v('waveRadius'))..'-stud tidal wave hits for '..pct(s.waveFactor)..' damage and pushes enemies away.'
 elseif id=='38' then return 'Each arrow splits in the sky and rains storm arrows on '..v('arrows')..' enemies.'
 elseif id=='39' then return 'The twin daggers zip from enemy to enemy, hitting up to '..v('chain')..' in a chain.'
 elseif id=='40' then return 'Every hit heals you for '..pct(v('leech'))..' of its damage. Every kill sends a blood wisp back to you that heals '..num(s.wispHeal)..' HP.'
 elseif id=='41' then return 'Kills disintegrate in a '..num(v('burstRadius'))..'-stud burst that hits nearby enemies for '..pct(v('burstFactor'))..' damage.' end
 return nil
end
-- What Tier IV adds to the special (nil when nothing changes).
function C.godlyUpgradeText(id)
 local s=C.Godly[id];if not s then return nil end
 local function v(k,t) return at(s[k],t) end
 if id=='36' and v('ghostCap',4)~=v('ghostCap',1) then return 'Tier IV keeps up to '..v('ghostCap',4)..' wraiths.'
 elseif id=='37' and v('waveRadius',4)~=v('waveRadius',1) then return 'Tier IV makes the wave '..num(v('waveRadius',4))..' studs wide.'
 elseif id=='38' and v('arrows',4)~=v('arrows',1) then return 'Tier IV rains '..v('arrows',4)..' storm arrows.'
 elseif id=='39' and v('chain',4)~=v('chain',1) then return 'Tier IV chains up to '..v('chain',4)..' enemies.'
 elseif id=='40' and v('leech',4)~=v('leech',1) then return 'Tier IV heals '..pct(v('leech',4))..(v('capBonus',4)>0 and ' and raises your healing cap by '..num(v('capBonus',4))..' HP/s.' or '.')
 elseif id=='41' and v('burstRadius',4)~=v('burstRadius',1) then return 'Tier IV makes the burst '..num(v('burstRadius',4))..' studs wide and hit for '..pct(v('burstFactor',4))..'.' end
 return nil
end
-- The special's numbers that change with tier, one table row each: label, field and how to show it.
C.GodlyRows={
 ['36']={{label='Wraiths at once',field='ghostCap'}},
 ['37']={{label='Wave size (studs)',field='waveRadius'}},
 ['38']={{label='Storm arrows',field='arrows'}},
 ['39']={{label='Enemies chained',field='chain'}},
 ['40']={{label='Heal per hit',field='leech',percent=true}},
 ['41']={{label='Burst size (studs)',field='burstRadius'},{label='Burst damage',field='burstFactor',percent=true}},
}
function C.godlyRowValue(id,row,tier) local v=at(C.Godly[id][row.field],tier);return row.percent and pct(v) or num(v),v end
-- Legendary Tier IV moves: a short name and one sentence.
C.LegendaryNames={Slash='Flying slash',Split='Mini rockets',Flush='Royal Flush',Strike='STRIKE!',Shock='Shockwave',Beam='Beam slash',Thunder='Lightning strike'}
function C.legendaryText(id)
 local m=C.Legendary[id];if not m then return nil end
 local every=m.every and (m.every==1 and 'Every' or 'Every '..ord(m.every))
 if m.move=='Slash' then return every..' swing throws a flying slash through a line of enemies for '..pct(m.factor)..' damage.'
 elseif m.move=='Split' then return every..' rocket splits into '..m.minis..' homing mini rockets ('..pct(m.factor)..' damage each).'
 elseif m.move=='Flush' then return every..' throw is a Royal Flush: '..m.cards..' gold cards that pierce everything.'
 elseif m.move=='Strike' then return 'A roll that hits '..m.hits..'+ enemies is a STRIKE! with a pin explosion.'
 elseif m.move=='Shock' then return 'Each swing that connects sends out a ground shockwave ('..pct(m.factor)..' damage).'
 elseif m.move=='Beam' then return every..' swing also shoots a golden beam slash ('..pct(m.factor)..' damage).'
 elseif m.move=='Thunder' then return every..' throw calls down a lightning strike ('..pct(m.factor)..' damage).' end
 return nil
end
-- One-line description: home class and traits (the same words as the Armory's).
local TRAITS={pellets='Fires a spread of pellets.',pierce='Shots pierce through enemies.',bounce='Bounces between enemies.',cards='Throws a three-card volley.',shots='Fires a burst of shots.'}
-- Its slow with numbers, e.g. 'Slows enemies 35% for 2 s.' (nil for a weapon that doesn't slow).
function C.slowText(w)
 if not w or (w.slow or 0)<=0 then return nil end
 return 'Slows enemies '..num(w.slowStrength or 25)..'% for '..num(w.slowFor or 2)..' s.'
end
function C.describe(w)
 if w.godly then return 'Any class can start a run with it.' end
 local out={'Home weapon of the '..w.home..' class.'}
 if TRAITS[w.trait] then table.insert(out,TRAITS[w.trait]) end
 if w.burn>0 then table.insert(out,'Sets enemies on fire.') end
 if w.poison>0 then table.insert(out,'Poisons what it hits.') end
 if w.slow>0 then table.insert(out,C.slowText(w)) end
 if w.lightning then table.insert(out,'Lightning chains to nearby enemies.') end
 if w.blastRadius then table.insert(out,'Explodes on impact.') end
 return table.concat(out,' ')
end
local HOME_MOVED={['19']='Brawler',['20']='Brawler',['05']='Juggler',['04']='Juggler'}
for i,name in names do
 local n=i-1
 local kind=ranged[n] and 'Ranged' or 'Melee'
 if n==11 or n==14 or n==33 then kind='Blast' elseif n==9 then kind='Spread' end
 local d={id=string.format('%02d',n),name=name,kind=kind}
 -- Damage/cooldown pairs are authored per weapon, not shared by an entire class.
 local profile=profiles[i]
 d.rarity=C.RarityOf[d.id] or 'Common'
 d.authoredDamage=profile[1];d.authoredCooldown=profile[2] -- before rarity power
 local raw=profile[1]*C.RarityPower[d.rarity]
 d.damage=math.floor(raw+1e-6);d.cooldown=math.round(profile[2]*d.damage/raw*1000)/1000;d.range=profile[3]
 if profile[4] then d.tierDamage=profile[4];d.tierCooldown=profile[5]
 else
  local growth=C.TierGrowthById[d.id] or C.TierGrowth
  d.tierDamage={};for t=1,4 do d.tierDamage[t]=math.floor(d.damage*growth^(t-1)+.5) end
  d.tierCooldown=table.clone(C.TierCooldown)
 end
 d.trait=profile[6] or ''
 if n==10 then d.projectileSpeed=48 end
 if n==11 then d.projectileSpeed=80;d.blastRadius=9 end
 if n==18 then d.projectileSpeed=90 end
 if n==33 then d.projectileSpeed=45;d.blastRadius=7 end
 d.home=n>=30 and 'Mage' or (n>=24 and 'Handyman' or (n>=17 and n~=18 and 'Juggler' or (n>=12 and 'Thrower' or (n==0 or n>=7) and 'Gunner' or 'Brawler')))
 -- 2026-10-03: Brawler is the hand-to-hand class, Juggler the tricks and toys. Swapped in equal-rarity
 -- pairs so every class keeps 2 Common, 2 Rare, 1 Epic, 1 Legendary: Boxing Gloves <-> Spatula (Common),
 -- Cinder Block <-> Kusarigama (Epic).
 d.home=HOME_MOVED[d.id] or d.home

 if n==17 or n==21 or n==23 then d.kind='Ranged' end
 -- Godly weapons belong to no class; any class may start with an owned one.
 if n>=36 then d.home='Godly';d.godly=true;d.special=C.Godly[d.id] end
 if n==37 then d.hybridRange=36;d.projectileSpeed=60;d.throwable=true end
 if n==38 then d.projectileSpeed=95 end
 if n==39 then d.scripted=true end -- the daggers' chain is the hit; no swing box
 if n==41 then d.projectileSpeed=150 end
 d.nativeKnockback=(n==5 and 14 or n==26 and 20 or n==20 and 16 or 0)
 if n==31 then d.hybridRange=32;d.projectileSpeed=42 end
 if n==8 then d.projectileSpeed=150 end
 local thrownSpeed={[12]=40,[13]=65,[14]=28,[15]=35,[22]=32,[23]=24}
 if thrownSpeed[n] then d.projectileSpeed=thrownSpeed[n] end
 d.elemental=d.home=='Mage' or n==8 or n==14 or n==17 or n==38 or n==41
 d.utility=d.home=='Handyman'
 d.burn=n==14 and 100 or 0;d.poison=n==8 and 100 or 0;d.slow=C.SlowById[d.id] and 100 or 0;d.lightning=n==35 or n==31
 if C.SlowById[d.id] then d.slowStrength=C.SlowById[d.id].strength;d.slowFor=C.SlowById[d.id].seconds end
 d.tags={d.kind=='Melee' and 'Melee' or 'Projectile',d.home}
 if d.elemental then table.insert(d.tags,'Elemental') end
 if d.utility then table.insert(d.tags,'Utility') end
 table.insert(C.List,d);C.ById[d.id]=d
end
function C.validSlot(slot)
 return type(slot)=='number' and slot==slot and slot%1==0 and slot>=1 and slot<=C.Slots
end
function C.validate(slot,id)
 return C.validSlot(slot) and type(id)=='string' and (id=='' or C.ById[id]~=nil)
end
return C
