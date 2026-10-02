local Weapons=require(script.Parent.WeaponCatalog)
local Economy=require(script.Parent.EconomyConfig)
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
item('protein','Protein Shake',1,14,'rbxassetid://83194367813542',{Damage=8},'General damage for every weapon.')
item('cheese','Emergency Cheese',1,9,'rbxassetid://90250262957329',{MaxHP=5},'Extra maximum health.')
item('potato','Support Potato',1,20,'rbxassetid://83830925182356',{MaxHP=8},'More health and a little help gathering shards.',5,'Item',{PickupRadius=10})
item('shoes','Sport Shoes',1,18,'rbxassetid://107662510054482',{},'Faster character movement.',5,'Utility',{MoveSpeed=6})
item('headband','Sweaty Headband',1,18,'rbxassetid://135907983584957',{AttackSpeed=8},'Faster compatible attacks.')
item('glasses','Large Glasses',1,16,'rbxassetid://96052817991093',{AttackRange=15},'Longer attack reach.')
item('potlid','Pot Lid',1,14,'rbxassetid://95875975195945',{Armor=2},'Incoming damage reduction.')
item('sock','Lucky Sock',1,18,'rbxassetid://107984529281974',{Luck=10},'Improves the chance of higher-tier shop offers, within rarity caps.')
item('magnet','Fridge Magnet',1,12,'rbxassetid://79860440384816',{},'Pull crystal shards from farther away.',5,'Utility',{PickupRadius=25})
item('coupons',"Grandma's Coupons",2,35,'rbxassetid://88520618235310',{ShopDiscount=5},'Discounts new, unlocked offers. Locked prices stay fixed.',5,'Utility')
item('ketchup','Support Ketchup',1,22,'rbxassetid://131244011688920',{ExplosionDamage=15},'Stronger explosive hits.')
item('hotsauce','Hot Sauce',2,32,'rbxassetid://119160485990749',{AreaSize=15},'Wider explosions and chain searches.')
item('marshmallow','Microwaved Marshmallow',1,20,'rbxassetid://126733361101751',{BurnDamage=20},'Amplifies burn; does not ignite on its own.')
item('peas','Freezer-Burned Peas',1,16,'rbxassetid://83565201991578',{},'Longer slows; requires a slow source.',5,'Item',{SlowDuration=25})
item('stinkysock','Stinky Sock',1,19,'rbxassetid://92934200477984',{PoisonDamage=20},'Amplifies existing poison damage.')
item('energy','Energy Drink',2,31,'rbxassetid://136079535507930',{AttackSpeed=15,MaxHP=-3},'Fast attacks with a health tradeoff.')
item('helmet','Safety Helmet',2,34,'rbxassetid://73191633018679',{Armor=3},'More armor, slightly slower movement.',5,'Item',{MoveSpeed=-3})
item('broken','Broken Glasses',2,38,'rbxassetid://118717032933610',{CritChance=6,AttackRange=-10},'More critical hits, shorter reach.')
item('ballchain','Literal Ball and Chain',2,39,'rbxassetid://116486378397548',{Damage=15},'Higher damage with a movement penalty.',5,'Item',{MoveSpeed=-5})
item('backpack','Backpack of Rocks',2,36,'rbxassetid://72326129404039',{MaxHP=12},'More health at the cost of speed.',5,'Item',{MoveSpeed=-4})
item('straws','Two Straws',4,145,'rbxassetid://103855013199609',{ProjectileCount=1},'One extra shot for compatible projectile weapons.',1)
item('bouncy','Bouncy Ball',4,130,'rbxassetid://72472678515992',{Bounce=1},'One extra enemy bounce; 60% damage on added bounce.',1)
item('pencil','Sharp Pencil',3,65,'rbxassetid://108647088361466',{Pierce=1},'Pierce one more enemy; 70% damage on added hit.',1)
item('antlers','Tinfoil Antlers',3,68,'rbxassetid://90516946916091',{ChainBonus=1},'Existing lightning chains hit one more enemy.',2)
item('mitt',"Grandma's Oven Mitt",3,62,'rbxassetid://140473103768001',{BurnSpread=1},'Burn spreads on death to one nearby enemy.',1)
item('bubble','Bubble Wrap Vest',4,145,'rbxassetid://136728170000690',{FirstHitBlock=1},'Block the first damaging hit each wave.',1)
item('bandage','Bandage Roll',2,32,'rbxassetid://86023323568594',{Regeneration=1},'Passive healing every second.',5,'Utility')
item('fang','Vampire Fang',3,64,'rbxassetid://93247265104136',{LifeSteal=3},'Heal from actual damage, within the life-steal cap.')
item('lighter','Lighter',2,42,'rbxassetid://131511231922178',{BurnChance=15},'Direct hits can ignite enemies.')
item('ice','Ice Cube',2,37,'rbxassetid://107793797321617',{SlowChance=15},'Direct hits can briefly slow enemies.')
item('battery','Battery Pack',3,72,'rbxassetid://77920495517577',{ChainCount=1},'Triggers bounded lightning on the configured hit cadence.',2)
item('toxic','Toxic Barrel',2,45,'rbxassetid://70439693967934',{PoisonChance=15},'Direct hits can stack poison.')
item('teeth',"Tooth Fairy's Collection",2,46,'rbxassetid://138418894713581',{CritDamage=15},'Higher critical-hit multiplier.')
item('nightmare','Bottled Nightmare',2,33,'rbxassetid://131703819690946',{Damage=12,MaxHP=-3},'Stronger damage, less health.')
item('mask','Cracked Burial Mask',3,70,'rbxassetid://79342628709582',{Armor=2,ContactReduction=10},'Armor plus protection from contact damage.')
item('alien','Alien Battery',2,38,'rbxassetid://96598846243561',{AttackSpeed=6,ChainDamage=15},'Faster attacks and stronger lightning chains.')
item('crown','Bone Crown',2,44,'rbxassetid://121286333601812',{BossDamage=15},'Extra damage against elites and bosses.')
local itemTags={
 protein={'Damage'},cheese={'Health'},potato={'Health'},shoes={'Mobility'},headband={'AttackSpeed'},glasses={'Range'},
 potlid={'Armor'},sock={'Luck'},magnet={'Economy'},coupons={'Economy'},ketchup={'Explosion'},hotsauce={'Explosion'},
 marshmallow={'Burn'},peas={'Slow'},stinkysock={'Poison'},energy={'AttackSpeed'},helmet={'Armor','Health'},
 broken={'Crit'},ballchain={'Damage','Melee'},backpack={'Health'},straws={'Projectile'},bouncy={'Bounce','Projectile'},
 pencil={'Pierce','Projectile'},antlers={'Lightning'},mitt={'Burn'},bubble={'Armor'},bandage={'Health'},
 fang={'Health','Damage'},lighter={'Burn'},ice={'Slow'},battery={'Lightning'},toxic={'Poison'},teeth={'Crit'},
 nightmare={'Damage'},mask={'Armor'},alien={'AttackSpeed'},crown={'Boss'},
}
for _,entry in C.List do
 if entry.kind~='Weapon' then entry.tags=itemTags[entry.id] or {} end
end
return C
