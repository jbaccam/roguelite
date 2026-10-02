-- Stat upgrades only. Values use this game's percentage-based damage schema.
local Stats=require(script.Parent.CharacterStats)
local C={List={},ById={},OFFER_COUNT=4}
local function add(id,name,icon,description,values)
 local d={id=id,name=name,icon=icon,description=description,values=values}
 table.insert(C.List,d);C.ById[id]=d
end
add('MaxHP','Vitality','heart','Increases your maximum health.',{8,12,16,24})
add('Damage','Damage','sword','Increases damage dealt to enemies.',{5,8,12,18})
add('AttackSpeed','Attack Speed','speed','Increases weapon attack speed.',{5,8,12,18})
add('Armor','Armor','shield','Reduces the damage you take.',{1,2,3,4})
add('Dodge','Dodge','wing','Gives a chance to evade incoming attacks.',{3,5,7,10})
add('Regeneration','Regeneration','cross','Restores health over time.',{.5,1,1.5,2})
add('LifeSteal','Life Steal','heart','Heals you when your attacks deal damage.',{1,2,3,4})
add('CritChance','Critical Chance','spark','Increases your chance to land a critical hit.',{3,5,7,10})
add('MeleeDamage','Melee Damage','sword','Strengthens your close-range attacks.',{8,12,18,25})
add('RangedDamage','Ranged Damage','arrows','Strengthens shots and thrown weapons.',{8,12,18,25})
add('ElementalDamage','Elemental Damage','spark','Strengthens elemental hits and status damage.',{8,12,18,25})
add('UtilityPower','Utility Power','cross','Strengthens construction and utility weapons.',{8,12,18,25})
add('MoveSpeed','Movement Speed','wing','Increases how fast you move.',{.5,1,1.5,2})
add('PickupRadius','Pickup Radius','spark','Pulls crystals in from farther away.',{1,1.5,2,3})
add('Luck','Luck','spark','Improves shop rarity and health-drop chance.',{3,5,7,10})
add('AttackRange','Attack Range','arrows','Increases targeting reach and attack travel distance.',{5,8,12,18})
function C.pool(stats,banished,excluded)
 local pool={}
 for _,d in C.List do
  if not (banished or {})[d.id] and not (excluded or {})[d.id] and stats[d.id]<Stats.ById[d.id].max then table.insert(pool,d) end
 end
 return pool
end
-- A card's tier: one draw n in [0,1) against these growing limits for Tier IV, III and II (Luck
-- 0-100 scales them). tierOdds turns them into {I,II,III,IV} for the REROLL odds note (LevelUpUI).
-- Example, level 10 with no Luck: limits .05 / .25 / .43, so IV 5%, III 20%, II 18%, I 57%.
function C.thresholds(level,luck)
 local l=1+math.clamp(luck or 0,0,100)/100
 return math.min(.08,.005*level*l),math.min(.28,.025*level*l),math.min(.65,.18+.025*level*l)
end
function C.tierOdds(level,luck) local a,b,c=C.thresholds(level,luck);return {1-c,c-b,b-a,a} end
function C.roll(stats,banished,level,rng)
 local pool=C.pool(stats,banished);local offers={}
 -- Roll each card independently; offers appear immediately.
 local four,three,two=C.thresholds(level,stats.Luck)
 for _=1,math.min(C.OFFER_COUNT,#pool) do
  local n=rng:NextNumber()
  local tier=n<four and 4 or n<three and 3 or n<two and 2 or 1
  local d=table.remove(pool,rng:NextInteger(1,#pool))
  table.insert(offers,{id=d.id,tier=tier,amount=math.min(d.values[tier],Stats.ById[d.id].max-stats[d.id])})
 end
 return offers
end
-- Distinct level-up art; the same stat image is used at every rarity.
C.IconIds={
 MaxHP='rbxassetid://87748663271804', Damage='rbxassetid://105663077535579',
 AttackSpeed='rbxassetid://118215254503921', Armor='rbxassetid://80556274645944',
 Dodge='rbxassetid://99124374960499', Regeneration='rbxassetid://86810106921196',
 LifeSteal='rbxassetid://94341050485414', CritChance='rbxassetid://129045264697854',
 MeleeDamage='rbxassetid://95614914114816', RangedDamage='rbxassetid://79016661829505',
 ElementalDamage='rbxassetid://104925573900277', UtilityPower='rbxassetid://133538769433103',
 MoveSpeed='rbxassetid://117216104224040', PickupRadius='rbxassetid://133081616364253',
 Luck='rbxassetid://136231704380505', AttackRange='rbxassetid://72729393219444',
}
function C.icon(id)
 local asset=script:GetAttribute('Icon_'..id)
 return type(asset)=='string' and asset or C.IconIds[id] or ''
end
return C
