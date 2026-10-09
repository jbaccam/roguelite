local Weapons=require(script.Parent.WeaponCatalog)
local Economy=require(script.Parent.EconomyConfig)
local Stats=require(script.Parent.CharacterStats)
local C={List={},ById={}}
local function add(d) C.ById[d.id]=d;table.insert(C.List,d) end
for i,w in Weapons.List do
 -- Godly weapons are never sold in a run: they come only from chests and bundles.
 if w.godly then continue end
 -- Authored cooldown: rarity power's slightly faster cooldown doesn't move a weapon's price band.
 local base=w.kind=='Blast' and 25 or ((w.authoredCooldown or w.cooldown)<.3 and 21 or 12+(i*7)%13)
 -- Rarer weapons cost more (EconomyConfig.RARITY_PRICE): a Legendary x1.5.
 local rarityPrice=Economy.RARITY_PRICE and Economy.RARITY_PRICE[w.rarity or 'Common'] or 1
 for tier=1,4 do
  local band=Economy.TIER_PRICE_BANDS[tier]
  local price=math.floor(math.floor(band[1]+(base-12)/13*(band[2]-band[1]))*rarityPrice+.5)
  add({id='weapon_'..w.id..'_'..tier,weaponId=w.id,name=w.name,kind='Weapon',tier=tier,basePrice=price,icon=w.id=='01' and 'pan' or w.home=='Mage' and 'staff' or 'pan',description=w.home..' · '..w.kind,modifiers={}})
 end
end
local function item(id,name,tier,price,icon,mods,description,cap,kind,percent)
 add({id=id,name=name,kind=kind or 'Item',tier=tier,basePrice=price,icon=icon,modifiers=mods,percent=percent or {},description=description,cap=cap or Economy.MAX_ITEM_COPIES})
end
-- Card text says exactly what happens, in plain words (user, 2026-10-03). Items that only help some
-- weapons (CharacterStats.usesStat: extra shots, pierce, bounce, explosions, area, lightning, and
-- since 2026-10-09 melee, ranged and elemental damage) are offered only to a player carrying one
-- (C.usable), and their cards name which (C.worksWith). Kind 'Item' for every passive (2026-10-09;
-- 'Utility' read like Utility Power on cards such as "Utility · Health").
item('protein','Protein Shake',1,14,'rbxassetid://83194367813542',{Damage=8},'All your weapons deal 8% more damage.')
-- Family items (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md "Items"; items audit
-- 6.1): one direct damage item per attack family, Tier I so the first shops can offer them, with the
-- level-up card art of the same stat (LevelUpCatalog.IconIds). 12 for 16 keeps Protein's ratio (8
-- Damage for 14) at the level-up cards' 1.5x family value; Elemental gets 10 because it also scales
-- every burn and poison tick from any weapon. Each is offered only to a build that uses it
-- (C.usable -> CharacterStats.usesStat). Working names from the art; the user can rename them.
-- Example price: 21 / 29 / 36 / 44 / 55 / 68 at shop waves 2 / 5 / 8 / 11 / 15 / 20.
item('knee','Knee of Justice',1,16,'rbxassetid://95614914114816',{MeleeDamage=12},'Your melee weapons (swings, stabs and punches) deal 12% more damage.')
item('fingercannon','Finger Cannon',1,16,'rbxassetid://79016661829505',{RangedDamage=12},'Your ranged weapons deal 12% more damage: guns, throws, explosives, sprays and streams.')
item('pocketweather','Pocket Weather',1,16,'rbxassetid://104925573900277',{ElementalDamage=10},'Elemental weapons deal 10% more damage, and all your burns and poison deal 10% more.')
item('cheese','Emergency Cheese',1,9,'rbxassetid://90250262957329',{MaxHP=5},'+5 max health.')
item('potato','Support Potato',1,20,'rbxassetid://83830925182356',{MaxHP=8},'+8 max health, and you grab crystals from 10% farther away.',5,'Item',{PickupRadius=10})
item('shoes','Sport Shoes',1,18,'rbxassetid://107662510054482',{},'You move 6% faster.',5,'Item',{MoveSpeed=6})
item('headband','Sweaty Headband',1,18,'rbxassetid://135907983584957',{AttackSpeed=8},'All your weapons attack 8% faster.')
item('glasses','Large Glasses',1,16,'rbxassetid://96052817991093',{AttackRange=15},'All your weapons reach 15% farther.')
item('potlid','Pot Lid',1,14,'rbxassetid://95875975195945',{Armor=2},'+2 armor: every hit you take does a bit less damage.')
item('sock','Lucky Sock',1,18,'rbxassetid://107984529281974',{Luck=10},'+10 luck: better shop offers and level-up cards, and more heart drops.')
item('magnet','Fridge Magnet',1,12,'rbxassetid://79860440384816',{},'Grab crystals from 25% farther away.',5,'Item',{PickupRadius=25})
item('coupons',"Grandma's Coupons",2,35,'rbxassetid://88520618235310',{ShopDiscount=5},'New shop offers cost 5% less. Locked prices stay the same.')
item('ketchup','Support Ketchup',1,22,'rbxassetid://131244011688920',{ExplosionDamage=15},"Rocket Launcher, Pandora's Box and Molotov deal 15% more damage.")
-- Area Size also widens the Rubber Duck's spray and the Power Washer / Vacuum streams (2026-10-09,
-- UtilityWeapons.areaScale), so Hot Sauce names them too.
item('hotsauce','Hot Sauce',2,32,'rbxassetid://119160485990749',{AreaSize=15},'Explosions, fire and gas puddles, lightning chains, sprays and streams reach 15% wider.')
-- Status boosters bring a small chance of their own (2026-10-03), so they work with any weapon.
-- Before, Marshmallow, Peas and Stinky Sock only boosted a status something else had to cause (a
-- Lighter, a Molotov, the Mage class), so most builds bought nothing. Were {BurnDamage=20},
-- {SlowDuration=25%} and {PoisonDamage=20}.
item('marshmallow','Microwaved Marshmallow',1,20,'rbxassetid://126733361101751',{BurnChance=5,BurnDamage=20},'5% of your hits set enemies on fire, and all your burns deal 20% more damage.')
item('peas','Freezer-Burned Peas',1,16,'rbxassetid://83565201991578',{SlowChance=5},'5% of your hits slow enemies, and all your slows last 25% longer.',5,'Item',{SlowDuration=25})
item('stinkysock','Stinky Sock',1,19,'rbxassetid://92934200477984',{PoisonChance=5,PoisonDamage=20},'5% of your hits poison enemies, and all your poison deals 20% more damage.')
item('energy','Energy Drink',2,31,'rbxassetid://136079535507930',{AttackSpeed=15,MaxHP=-3},'All your weapons attack 15% faster, but you have 3 less max health.')
item('helmet','Safety Helmet',2,34,'rbxassetid://73191633018679',{Armor=3},'+3 armor, but you move 3% slower.',5,'Item',{MoveSpeed=-3})
item('broken','Broken Glasses',2,38,'rbxassetid://118717032933610',{CritChance=6,AttackRange=-10},'+6% chance of a critical hit, but your weapons reach 10% less far.')
item('ballchain','Literal Ball and Chain',2,39,'rbxassetid://116486378397548',{Damage=15},'All your weapons deal 15% more damage, but you move 5% slower.',5,'Item',{MoveSpeed=-5})
item('backpack','Backpack of Rocks',2,36,'rbxassetid://72326129404039',{MaxHP=12},'+12 max health, but you move 4% slower.',5,'Item',{MoveSpeed=-4})
-- Projectile mods a tier lower (2026-10-09, items audit 6.5), so a build can find them before wave
-- 12: Two Straws Tier IV 145 -> III 90, Bouncy Ball IV 130 -> III 80, Sharp Pencil III 65 -> II 42.
-- All stay 1 copy. Texts name what really uses them (CharacterStats.usesStat): guns never bounce,
-- and thrown bounces deal 65%.
item('straws','Two Straws',3,90,'rbxassetid://103855013199609',{ProjectileCount=1},'+1 shot or throw every attack: guns, rockets, staffs, cards, throws and turrets. Not melee, returning throws (Boomerang, Mjolnir) or sprays.',1)
item('bouncy','Bouncy Ball',3,80,'rbxassetid://72472678515992',{Bounce=1},'Throws, cards, yo-yos and magic bolts bounce to 1 more enemy (60-65% damage). Not guns, melee, explosives, fire or gas throws, bowling balls or sprays.',1)
item('pencil','Sharp Pencil',2,42,'rbxassetid://108647088361466',{Pierce=1},'Bullets, throws, cards and magic bolts go through 1 more enemy (70% damage). Not melee, explosives, gas clouds, bowling balls or sprays.',1)
item('antlers','Tinfoil Antlers',3,68,'rbxassetid://90516946916091',{ChainBonus=1},'Your lightning chains jump to 1 more enemy. Needs lightning: a lightning weapon, Battery Pack or Mage.',2)
-- Oven Mitt lights its own fires too (2026-10-03; was {BurnSpread=1}, dead without a burn source).
item('mitt',"Grandma's Oven Mitt",3,62,'rbxassetid://140473103768001',{BurnChance=10,BurnSpread=1},'10% of your hits set enemies on fire, and a burning enemy that dies passes its fire to 1 enemy nearby.',1)
item('bubble','Bubble Wrap Vest',4,145,'rbxassetid://136728170000690',{FirstHitBlock=1},'Blocks the first hit you take each wave.',1)
item('bandage','Bandage Roll',2,32,'rbxassetid://86023323568594',{Regeneration=1},'Heal 1 HP every second.')
item('fang','Vampire Fang',3,64,'rbxassetid://93247265104136',{LifeSteal=3},'Heal 3% of the damage you deal (up to your healing cap each second).')
item('lighter','Lighter',2,42,'rbxassetid://131511231922178',{BurnChance=15},'15% of your hits set enemies on fire: 6 damage a second for 3 s. Any weapon.')
-- Ice Cube slows as hard as Medusa's Head (WeaponCatalog.SlowById: 35% for 2 s) through the same
-- slow status (CombatEffectsService), so the two read the same (2026-10-03; was {SlowChance=15}, 25%).
item('ice','Ice Cube',2,37,'rbxassetid://107793797321617',{SlowChance=15,SlowStrength=10},"15% of your hits slow enemies 35% for 2 s, like Medusa's Head (bosses half as much). Any weapon.")
-- Battery Pack: lightning weapons (Crystal Ball, Mjolnir) get +1 target from the first copy too
-- (2026-10-09, CombatEffectsService adds ChainCount to their own chain instead of taking the larger).
item('battery','Battery Pack',3,72,'rbxassetid://77920495517577',{ChainCount=1},'Every 5th hit you land zaps 1 enemy nearby with lightning for 40% damage. Any weapon. Lightning weapons zap 1 more.',2)
item('toxic','Toxic Barrel',2,45,'rbxassetid://70439693967934',{PoisonChance=15},'15% of your hits poison enemies: 3 damage a second for 4 s, stacking 3 times. Any weapon.')
item('teeth',"Tooth Fairy's Collection",2,46,'rbxassetid://138418894713581',{CritDamage=15},'Critical hits hit harder: x1.5 becomes x1.65.')
item('nightmare','Bottled Nightmare',2,33,'rbxassetid://131703819690946',{Damage=12,MaxHP=-3},'All your weapons deal 12% more damage, but you have 3 less max health.')
item('mask','Cracked Burial Mask',3,70,'rbxassetid://79342628709582',{Armor=2,ContactReduction=10},'+2 armor, and enemy hits deal 10% less damage.')
item('alien','Alien Battery',2,38,'rbxassetid://96598846243561',{AttackSpeed=6,ChainDamage=15},'All your weapons attack 6% faster, and your lightning chains hit 15% harder.')
-- Bone Crown adds a little damage everywhere too (2026-10-03; was {BossDamage=15}): there are no
-- elite waves, so it did nothing until the wave 20 boss.
item('crown','Bone Crown',2,44,'rbxassetid://121286333601812',{Damage=5,BossDamage=20},'All your weapons deal 5% more damage, and 20% more to bosses.')
-- Player buffs (user, 2026-10-03: "more items that give buffs instead of directly contributing to
-- buffs that your weapons give you"). Their icons are their own art, not the level-up cards'; only
-- Toolbelt and the three family items reuse level-up art (items audit, 2026-10-09).
item('banana','Banana Peel',1,18,'rbxassetid://91220324140044',{Dodge=5},'5% of enemy hits miss you completely.')
item('cushion','Couch Cushion',1,17,'rbxassetid://134119315378177',{Armor=1,MaxHP=6},'+1 armor and +6 max health.')
item('penny','Lucky Penny',1,17,'rbxassetid://84866645691857',{Luck=6,Dodge=3},'+6 luck (better shop offers and level-up cards, more heart drops), and 3% of enemy hits miss you.')
item('soup','Chicken Soup',2,34,'rbxassetid://134653604976810',{MaxHP=6,Recovery=15},'+6 max health, and all your healing heals 15% more.')
item('skates','Roller Skates',2,38,'rbxassetid://84335919314680',{Dodge=3},'You move 10% faster, and 3% of enemy hits miss you.',5,'Item',{MoveSpeed=10})
item('detector','Metal Detector',2,36,'rbxassetid://135461885570276',{Luck=8},'+8 luck, and you grab crystals from 20% farther away.',5,'Item',{PickupRadius=20})
item('gummies','Vitamin Gummies',3,66,'rbxassetid://96244325205305',{Regeneration=2,MaxHP=10},'Heal 2 HP every second, and +10 max health.')
-- Turret items (2026-10-04, Brotato's structures; HANDYMAN_TURRET.md): every copy owned is one more
-- turret, placed near you at each wave start, at most 10 (cap). Any class can buy them. structure:
-- the Handyman (Engineer) gets 20% off them (ShopService). Since 2026-10-09 they are preferred by
-- builds carrying Tool weapons or owning turrets (C.wants), not by class. Their numbers and icons
-- come from HandymanTurret, looked up so a place without it still loads the catalog.
local turretOk,Turret=pcall(require,script.Parent:FindFirstChild('HandymanTurret'))
if turretOk and type(Turret)=='table' and Turret.Items then
 for _,it in Turret.Items do
  item(it.id,it.name,it.tier,it.price,Turret.Icons[it.tier],{},Turret.describe(it.tier),Turret.MAX_OWNED,'Turret')
  C.ById[it.id].turret=it.tier;C.ById[it.id].structure=true
 end
 -- Scrap Magnet: the Fridge Magnet's art. Toolbelt: the Utility Power level-up art (LevelUpCatalog.IconIds).
 item(Turret.SCRAP_MAGNET,'Scrap Magnet',2,40,'rbxassetid://79860440384816',{},'Each '..Turret.SCRAP_EVERY..' crystals you pick up in a wave builds a temporary Nail Turret near you, up to '..Turret.SCRAP_PER_COPY..' a wave per copy. They go when the wave ends.')
 -- Toolbelt is the Utility family item (2026-10-09, items audit 6.2): +10 Utility Power (was 6), base
 -- 16 (was 18), offered only to a build carrying a utility weapon or owning a turret item (C.usable).
 item(Turret.TOOLBELT,'Toolbelt',1,16,'rbxassetid://133538769433103',{UtilityPower=10},'Utility weapons and turrets deal 10% more damage (+10% Utility Power).')
 C.ById[Turret.SCRAP_MAGNET].structure=true;C.ById[Turret.TOOLBELT].structure=true
end
local itemTags={
 protein={'Damage'},cheese={'Health'},potato={'Health'},shoes={'Mobility'},headband={'AttackSpeed'},glasses={'Range'},
 potlid={'Armor'},sock={'Luck'},magnet={'Economy'},coupons={'Economy'},ketchup={'Explosion'},hotsauce={'Explosion'},
 marshmallow={'Burn'},peas={'Slow'},stinkysock={'Poison'},energy={'AttackSpeed'},helmet={'Armor','Health'},
 broken={'Crit'},ballchain={'Damage'},backpack={'Health'},straws={'Projectile'},bouncy={'Bounce','Projectile'},
 pencil={'Pierce','Projectile'},antlers={'Lightning'},mitt={'Burn'},bubble={'Armor'},bandage={'Health'},
 fang={'Health','Damage'},lighter={'Burn'},ice={'Slow'},battery={'Lightning'},toxic={'Poison'},teeth={'Crit'},
 nightmare={'Damage'},mask={'Armor'},alien={'AttackSpeed'},crown={'Damage','Boss'},
 banana={'Mobility'},cushion={'Armor','Health'},penny={'Luck'},soup={'Health'},skates={'Mobility'},detector={'Luck','Economy'},gummies={'Health'},
 -- 2026-10-09: the family items, and Toolbelt reads "Item · Utility". Ball and Chain lost Melee (it
 -- is general damage), so melee preference goes to Knee of Justice.
 knee={'Melee','Damage'},fingercannon={'Ranged','Projectile'},pocketweather={'Elemental','Burn','Poison'},toolbelt={'Utility','Structure'},
}
for _,entry in C.List do
 if entry.kind~='Weapon' then entry.tags=itemTags[entry.id] or (entry.structure and {'Structure'}) or {} end
end
-- "Works with" (2026-10-03). An item whose every stat only some weapons use (CharacterStats
-- .usesStat) lists them; nil for an item that helps every build. Example: Sharp Pencil -> {'Pierce'};
-- Protein Shake -> nil.
function C.weaponStats(entry)
 if not entry or entry.kind=='Weapon' then return nil end
 local list={}
 for _,t in {entry.modifiers or {},entry.percent or {}} do
  for id in t do if not Stats.WeaponStats[id] then return nil end;table.insert(list,id) end
 end
 table.sort(list)
 return #list>0 and list or nil
end
-- Which of the weapon ids in `ids` an item works with (each once, in order), or nil when it works
-- with every weapon. stats: the player's stats (Battery Pack or Mage lightning counts for every
-- weapon). Example: Two Straws with {'01','00','30'} (Frying Pan, Glock, Magic Staff) -> {'00','30'}.
-- The shop's offers (ShopService) and the cards (ShopUI) both ask this.
function C.worksWith(entry,ids,stats)
 local need=C.weaponStats(entry);if not need then return nil end
 local out,seen={},{}
 for _,id in ids do
  local base=Weapons.ById[id]
  if base and not seen[id] then
   for _,stat in need do if Stats.usesStat(base,stat,stats) then seen[id]=true;table.insert(out,id);break end end
  end
 end
 return out
end
-- Whether the shop may offer item `entry` to this build (2026-10-09). It must work with a carried
-- weapon (C.worksWith), and an item that raises Utility Power (Toolbelt) also needs a utility weapon
-- or a turret item, since nothing else uses that stat. carried: weapon ids; stats: the player's;
-- turrets: turret items owned. Example: a lone Glock never sees Toolbelt; Glock + 1 Nail Turret does.
function C.usable(entry,carried,stats,turrets)
 local utility=(entry.modifiers or {}).UtilityPower~=nil
 if utility and (turrets or 0)>0 then return true end
 local works=C.worksWith(entry,carried or {},stats)
 if works~=nil and #works==0 then return false end
 if utility then
  for _,id in carried or {} do local w=Weapons.ById[id];if w and w.utility then return true end end
  return false
 end
 return true
end
-- Build preference (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md "Items"). It
-- replaces ShopService's per-class wanted lists and same-class weapon pool, and HandymanTurret
-- .favoured: the shop now prefers what suits the weapons you have equipped, counted by copies.
-- How often: PREFER_ITEMS of item rolls; for weapons PREFER_SAME_WEAPON an equipped weapon (a copy
-- merges a tier up), else PREFER_TYPE (+ EconomyConfig.classBonus, the waves 1-5 bonus) a weapon
-- sharing a type with an equipped copy.
C.PREFER_ITEMS=.15;C.PREFER_SAME_WEAPON=.10;C.PREFER_TYPE=.15
-- What a weapon type wants from the shop, as item tags: Blade sets add crit, Blunt sets armor; Gun
-- and Thrown shots take extra shots and pierce (Gun sets add attack speed, thrown weapons bounce);
-- Explosive weapons are the blast ones; Elemental weapons scale every burn and poison (and Medusa
-- slows); Tool covers the turret items, Scrap Magnet and Toolbelt (Turret.favoured folded in);
-- Culinary hits heal; Trick sets add dodge. Turret items owned count as one more copy that wants
-- TurretWants.
C.TypeWants={Blade={'Crit'},Blunt={'Armor'},Gun={'Projectile','Pierce','AttackSpeed'},Thrown={'Projectile','Pierce','Bounce'},
 Explosive={'Explosion'},Elemental={'Burn','Poison','Lightning','Slow'},Tool={'Structure'},Culinary={'Health'},Trick={'Mobility','Bounce'}}
C.TurretWants={'Utility','Structure'}
-- One equipped copy's wants, a set of item tags: its attack family (Melee; Ranged for every
-- non-melee attack and the throwing hybrids, Mjolnir and the Trident; Elemental / Utility for the
-- flagged weapons), then its weapon types. Example: a Katana (melee, Blade) wants Melee and Crit;
-- a Nail Gun (Gun, Tool, utility) wants Ranged, Utility, Projectile, Pierce, AttackSpeed, Structure.
function C.wants(id)
 local w=Weapons.ById[id];local set={}
 if not w then return set end
 if w.kind=='Melee' then set.Melee=true end
 if w.kind~='Melee' or w.hybridRange~=nil then set.Ranged=true end -- as usesStat('RangedDamage')
 if w.elemental then set.Elemental=true end
 if w.utility then set.Utility=true end
 for _,t in w.types or {} do for _,tag in C.TypeWants[t] or {} do set[tag]=true end end
 return set
end
-- How many equipped copies an item suits: each copy that wants one of its tags counts once, and
-- owning turret items counts as one more. equipped: one weapon id per filled slot (repeats kept, so
-- copies count). Example: Knee of Justice with 3 Katanas + 1 Glock = 3, Finger Cannon = 1, Protein
-- Shake (Damage) = 0: general items help every build and get no preference.
function C.preferenceWeight(entry,equipped,turrets)
 local tags=entry and entry.tags or {}
 if #tags==0 then return 0 end
 local function suits(set) for _,tag in tags do if set[tag] then return true end end;return false end
 local n=0
 for _,id in equipped or {} do if suits(C.wants(id)) then n+=1 end end
 if (turrets or 0)>0 then
  local set={};for _,tag in C.TurretWants do set[tag]=true end
  if suits(set) then n+=1 end
 end
 return n
end
-- The preferred item pool: items of tier maxTier or lower that suit the equipped copies, and their
-- weights (copies). pool: the items the shop may offer now (C.usable, under their cap, not on show).
-- Example, a Tier II roll with Katanas: Knee of Justice (I) and Broken Glasses (II) join, Two
-- Straws (III) can't.
function C.preferredItems(pool,equipped,turrets,maxTier)
 local out,weights={},{}
 for _,entry in pool do
  if entry.kind~='Weapon' and entry.tier<=(maxTier or 4) then
   local n=C.preferenceWeight(entry,equipped,turrets)
   if n>0 then table.insert(out,entry);table.insert(weights,n) end
  end
 end
 return out,weights
end
-- The preferred weapon pool: offers that share a weapon type with an equipped copy, each weighted by
-- how many equipped copies it shares a type with (Godlies count: they have types). Example: 2 Katanas
-- (Blade) + 1 Glock (Gun): Kusarigama (Blade) weighs 2, Draco (Gun) 1; Frying Pan (Blunt, Culinary)
-- is left out.
function C.preferredWeapons(pool,equipped)
 local out,weights={},{}
 for _,entry in pool do
  local w=entry.weaponId and Weapons.ById[entry.weaponId]
  if w then
   local n=0
   for _,id in equipped or {} do
    local other=Weapons.ById[id]
    if other then for _,t in other.types or {} do if table.find(w.types or {},t) then n+=1;break end end end
   end
   if n>0 then table.insert(out,entry);table.insert(weights,n) end
  end
 end
 return out,weights
end
-- One pick by weight; n is one draw in [0,1). nil when nothing has weight. Example: weights {1,3}:
-- n = 0.2 -> list[1], n = 0.3 -> list[2].
function C.pickWeighted(list,weights,n)
 local total=0;for i in list do total+=weights[i] or 0 end
 if total<=0 then return nil end
 local x=n*total
 for i,entry in list do x-=weights[i] or 0;if x<0 then return entry end end
 return list[#list]
end
return C
