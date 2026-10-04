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
-- weapons (CharacterStats.usesStat: extra shots, pierce, bounce, explosions, area, lightning) are
-- offered only to a player carrying one (ShopService), and their cards name which (C.worksWith).
item('protein','Protein Shake',1,14,'rbxassetid://83194367813542',{Damage=8},'All your weapons deal 8% more damage.')
item('cheese','Emergency Cheese',1,9,'rbxassetid://90250262957329',{MaxHP=5},'+5 max health.')
item('potato','Support Potato',1,20,'rbxassetid://83830925182356',{MaxHP=8},'+8 max health, and you grab crystals from 10% farther away.',5,'Item',{PickupRadius=10})
item('shoes','Sport Shoes',1,18,'rbxassetid://107662510054482',{},'You move 6% faster.',5,'Utility',{MoveSpeed=6})
item('headband','Sweaty Headband',1,18,'rbxassetid://135907983584957',{AttackSpeed=8},'All your weapons attack 8% faster.')
item('glasses','Large Glasses',1,16,'rbxassetid://96052817991093',{AttackRange=15},'All your weapons reach 15% farther.')
item('potlid','Pot Lid',1,14,'rbxassetid://95875975195945',{Armor=2},'+2 armor: every hit you take does a bit less damage.')
item('sock','Lucky Sock',1,18,'rbxassetid://107984529281974',{Luck=10},'+10 luck: better shop offers and more heart drops.')
item('magnet','Fridge Magnet',1,12,'rbxassetid://79860440384816',{},'Grab crystals from 25% farther away.',5,'Utility',{PickupRadius=25})
item('coupons',"Grandma's Coupons",2,35,'rbxassetid://88520618235310',{ShopDiscount=5},'New shop offers cost 5% less. Locked prices stay the same.',5,'Utility')
item('ketchup','Support Ketchup',1,22,'rbxassetid://131244011688920',{ExplosionDamage=15},'Explosive weapons deal 15% more damage.')
item('hotsauce','Hot Sauce',2,32,'rbxassetid://119160485990749',{AreaSize=15},'Explosions, fire and gas puddles and lightning chains reach 15% wider.')
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
item('straws','Two Straws',4,145,'rbxassetid://103855013199609',{ProjectileCount=1},'+1 shot or throw every attack: guns, staffs, cards and throwing weapons. Not melee, boomerangs or sprays.',1)
item('bouncy','Bouncy Ball',4,130,'rbxassetid://72472678515992',{Bounce=1},'Shots and throws bounce to 1 more enemy (60% damage). Not melee, explosives or sprays.',1)
item('pencil','Sharp Pencil',3,65,'rbxassetid://108647088361466',{Pierce=1},'Shots and throws go through 1 more enemy (70% damage). Not melee, explosives or sprays.',1)
item('antlers','Tinfoil Antlers',3,68,'rbxassetid://90516946916091',{ChainBonus=1},'Your lightning chains jump to 1 more enemy. Needs lightning: a lightning weapon, Battery Pack or Mage.',2)
-- Oven Mitt lights its own fires too (2026-10-03; was {BurnSpread=1}, dead without a burn source).
item('mitt',"Grandma's Oven Mitt",3,62,'rbxassetid://140473103768001',{BurnChance=10,BurnSpread=1},'10% of your hits set enemies on fire, and a burning enemy that dies passes its fire to 1 enemy nearby.',1)
item('bubble','Bubble Wrap Vest',4,145,'rbxassetid://136728170000690',{FirstHitBlock=1},'Blocks the first hit you take each wave.',1)
item('bandage','Bandage Roll',2,32,'rbxassetid://86023323568594',{Regeneration=1},'Heal 1 HP every second.',5,'Utility')
item('fang','Vampire Fang',3,64,'rbxassetid://93247265104136',{LifeSteal=3},'Heal 3% of the damage you deal (up to your healing cap each second).')
item('lighter','Lighter',2,42,'rbxassetid://131511231922178',{BurnChance=15},'15% of your hits set enemies on fire: 6 damage a second for 3 s. Any weapon.')
-- Ice Cube slows as hard as Medusa's Head (WeaponCatalog.SlowById: 35% for 2 s) through the same
-- slow status (CombatEffectsService), so the two read the same (2026-10-03; was {SlowChance=15}, 25%).
item('ice','Ice Cube',2,37,'rbxassetid://107793797321617',{SlowChance=15,SlowStrength=10},"15% of your hits slow enemies 35% for 2 s, like Medusa's Head (bosses half as much). Any weapon.")
item('battery','Battery Pack',3,72,'rbxassetid://77920495517577',{ChainCount=1},'Every 5th hit zaps 1 more enemy nearby with lightning for 40% damage. Any weapon.',2)
item('toxic','Toxic Barrel',2,45,'rbxassetid://70439693967934',{PoisonChance=15},'15% of your hits poison enemies: 3 damage a second for 4 s, stacking 3 times. Any weapon.')
item('teeth',"Tooth Fairy's Collection",2,46,'rbxassetid://138418894713581',{CritDamage=15},'Critical hits hit harder: x1.5 becomes x1.65.')
item('nightmare','Bottled Nightmare',2,33,'rbxassetid://131703819690946',{Damage=12,MaxHP=-3},'All your weapons deal 12% more damage, but you have 3 less max health.')
item('mask','Cracked Burial Mask',3,70,'rbxassetid://79342628709582',{Armor=2,ContactReduction=10},'+2 armor, and enemy hits deal 10% less damage.')
item('alien','Alien Battery',2,38,'rbxassetid://96598846243561',{AttackSpeed=6,ChainDamage=15},'All your weapons attack 6% faster, and your lightning chains hit 15% harder.')
-- Bone Crown adds a little damage everywhere too (2026-10-03; was {BossDamage=15}): there are no
-- elite waves, so it did nothing until the wave 20 boss.
item('crown','Bone Crown',2,44,'rbxassetid://121286333601812',{Damage=5,BossDamage=20},'All your weapons deal 5% more damage, and 20% more to bosses.')
-- Player buffs (user, 2026-10-03: "more items that give buffs instead of directly contributing to
-- buffs that your weapons give you"). Icons are the stat's level-up art (LevelUpCatalog.IconIds:
-- Dodge, Armor, MaxHP, MoveSpeed, PickupRadius, Regeneration, Luck).
item('banana','Banana Peel',1,18,'rbxassetid://99124374960499',{Dodge=5},'5% of enemy hits miss you completely.')
item('cushion','Couch Cushion',1,17,'rbxassetid://80556274645944',{Armor=1,MaxHP=6},'+1 armor and +6 max health.')
item('penny','Lucky Penny',1,17,'rbxassetid://136231704380505',{Luck=6,Dodge=3},'+6 luck (better shop offers, more heart drops), and 3% of enemy hits miss you.')
item('soup','Chicken Soup',2,34,'rbxassetid://87748663271804',{MaxHP=6,Recovery=15},'+6 max health, and all your healing heals 15% more.')
item('skates','Roller Skates',2,38,'rbxassetid://117216104224040',{Dodge=3},'You move 10% faster, and 3% of enemy hits miss you.',5,'Utility',{MoveSpeed=10})
item('detector','Metal Detector',2,36,'rbxassetid://133081616364253',{Luck=8},'+8 luck, and you grab crystals from 20% farther away.',5,'Utility',{PickupRadius=20})
item('gummies','Vitamin Gummies',3,66,'rbxassetid://86810106921196',{Regeneration=2,MaxHP=10},'Heal 2 HP every second, and +10 max health.')
local itemTags={
 protein={'Damage'},cheese={'Health'},potato={'Health'},shoes={'Mobility'},headband={'AttackSpeed'},glasses={'Range'},
 potlid={'Armor'},sock={'Luck'},magnet={'Economy'},coupons={'Economy'},ketchup={'Explosion'},hotsauce={'Explosion'},
 marshmallow={'Burn'},peas={'Slow'},stinkysock={'Poison'},energy={'AttackSpeed'},helmet={'Armor','Health'},
 broken={'Crit'},ballchain={'Damage','Melee'},backpack={'Health'},straws={'Projectile'},bouncy={'Bounce','Projectile'},
 pencil={'Pierce','Projectile'},antlers={'Lightning'},mitt={'Burn'},bubble={'Armor'},bandage={'Health'},
 fang={'Health','Damage'},lighter={'Burn'},ice={'Slow'},battery={'Lightning'},toxic={'Poison'},teeth={'Crit'},
 nightmare={'Damage'},mask={'Armor'},alien={'AttackSpeed'},crown={'Damage','Boss'},
 banana={'Mobility'},cushion={'Armor','Health'},penny={'Luck'},soup={'Health'},skates={'Mobility'},detector={'Luck','Economy'},gummies={'Health'},
}
for _,entry in C.List do
 if entry.kind~='Weapon' then entry.tags=itemTags[entry.id] or {} end
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
return C
