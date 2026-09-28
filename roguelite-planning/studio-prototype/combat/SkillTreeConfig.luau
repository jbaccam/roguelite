-- Permanent skill tree: shared data and pure helpers (server validates, UI presents).
-- Design and balance notes: roguelite-planning/SKILL_TREE.md.
-- Every node is a small flat bonus fed into CharacterStats.resolve as a flat bonus before the
-- clamp, so stat caps always hold. A fully bought tree is roughly half a weapon tier of power:
-- +24 HP, +2 Armor, +12% Damage, +1.5 move speed and a few small utility bonuses.
-- Nodes cost emeralds (the only account currency). Positions are grid units from the centre star.
local Stats=require(script.Parent.CharacterStats)
local S={List={},ById={},ROOT='Root',Currency='emeralds'}

-- Stat icons are the level-up art (LevelUpCatalog.IconIds); the root uses the Skill Tree star.
S.Icons={
 Root='rbxassetid://85339341316383',
 Hud='rbxassetid://70956867630986', -- lobby SKILLS button (user-supplied rune stone)
 MaxHP='rbxassetid://87748663271804', Damage='rbxassetid://105663077535579',
 AttackSpeed='rbxassetid://104227388119878', Armor='rbxassetid://80556274645944',
 Dodge='rbxassetid://99124374960499', Regeneration='rbxassetid://86810106921196',
 LifeSteal='rbxassetid://94341050485414', CritChance='rbxassetid://129045264697854',
 MoveSpeed='rbxassetid://117216104224040', PickupRadius='rbxassetid://133081616364253',
 Luck='rbxassetid://136231704380505', AttackRange='rbxassetid://72729393219444',
}
-- ProSoundEffects library sounds (free, Roblox-licensed). See studio-prototype/ASSETS.md.
-- Plain numbers so AssetPreloader (which preloads every rbxassetid string as an image) skips them.
S.Sounds={
 Open=9120733055,  -- Whoosh Rising Swish Airy Various Pitches 1
 Buy=9116394545,   -- Magic Glows Soft Clusters Of Chiming Hits 1
}

-- kind: 'root' | 'node' | 'capstone'. branch colours the connectors and names the arm.
local function node(id,name,x,y,parent,cost,bonus,icon,kind,blurb)
 local d={id=id,name=name,x=x,y=y,parent=parent,cost=cost,bonus=bonus,icon=S.Icons[icon] or icon,kind=kind or 'node',blurb=blurb}
 table.insert(S.List,d);S.ById[id]=d
 return d
end

node('Root','Skill Tree',0,0,nil,0,{},'Root','root','Buy skills with emeralds. Every skill is a small permanent bonus for every run.')

-- Price ladder along each arm, then the side branches and the capstone.
local ARM={100,300,700,1400}
local SIDE={500,1200}
local CAP=3000
local ROMAN={'I','II','III','IV'}

-- Toughness (left): Max Health, with Armor above and Regeneration below.
for i=1,4 do node('MaxHP'..i,'Max Health '..ROMAN[i],-i,0,i==1 and 'Root' or 'MaxHP'..(i-1),ARM[i],{MaxHP=4},'MaxHP') end
node('Armor1','Armor I',-2.5,-1,'MaxHP2',SIDE[1],{Armor=1},'Armor')
node('Armor2','Armor II',-3,-2,'Armor1',SIDE[2],{Armor=1},'Armor')
node('Regen1','Regeneration I',-2.5,1,'MaxHP2',SIDE[1],{Regeneration=.25},'Regeneration')
node('Regen2','Regeneration II',-3,2,'Regen1',SIDE[2],{Regeneration=.25},'Regeneration')
node('ToughCookie','Tough Cookie',-5,0,'MaxHP4',CAP,{MaxHP=8},'MaxHP','capstone','Crunchy outside. Extra crunchy inside.')

-- Offense (right): Damage, with Critical Chance above and Attack Speed below.
for i=1,4 do node('Damage'..i,'Damage '..ROMAN[i],i,0,i==1 and 'Root' or 'Damage'..(i-1),ARM[i],{Damage=2},'Damage') end
node('Crit1','Critical Chance I',2.5,-1,'Damage2',SIDE[1],{CritChance=2},'CritChance')
node('Crit2','Critical Chance II',3,-2,'Crit1',SIDE[2],{CritChance=2},'CritChance')
node('Haste1','Attack Speed I',2.5,1,'Damage2',SIDE[1],{AttackSpeed=3},'AttackSpeed')
node('Haste2','Attack Speed II',3,2,'Haste1',SIDE[2],{AttackSpeed=3},'AttackSpeed')
node('SharpStuff','Sharp Stuff',5,0,'Damage4',CAP,{Damage=4,CritDamage=10},'Damage','capstone','Handle with care. Or don\'t.')

-- Fortune (up): Luck, with Pickup Radius to the left and Attack Range to the right.
for i=1,4 do node('Luck'..i,'Luck '..ROMAN[i],0,-i,i==1 and 'Root' or 'Luck'..(i-1),ARM[i],{Luck=2},'Luck') end
node('Magnet1','Pickup Radius I',-1,-2.5,'Luck2',SIDE[1],{PickupRadius=1},'PickupRadius')
node('Magnet2','Pickup Radius II',-2,-3,'Magnet1',SIDE[2],{PickupRadius=1},'PickupRadius')
node('Reach1','Attack Range I',1,-2.5,'Luck2',SIDE[1],{AttackRange=3},'AttackRange')
node('Reach2','Attack Range II',2,-3,'Reach1',SIDE[2],{AttackRange=3},'AttackRange')
node('PocketClover','Pocket Clover',0,-5,'Luck4',CAP,{Luck=4,PickupRadius=1},'Luck','capstone','Found it in the wash. Still works.')

-- Agility (down): Move Speed, with Dodge to the left and Life Steal to the right.
for i=1,4 do node('Speed'..i,'Move Speed '..ROMAN[i],0,i,i==1 and 'Root' or 'Speed'..(i-1),ARM[i],{MoveSpeed=.25},'MoveSpeed') end
node('Dodge1','Dodge I',-1,2.5,'Speed2',SIDE[1],{Dodge=1.5},'Dodge')
node('Dodge2','Dodge II',-2,3,'Dodge1',SIDE[2],{Dodge=1.5},'Dodge')
node('Leech1','Life Steal I',1,2.5,'Speed2',SIDE[1],{LifeSteal=.5},'LifeSteal')
node('Leech2','Life Steal II',2,3,'Leech1',SIDE[2],{LifeSteal=.5},'LifeSteal')
node('Zoomies','Zoomies',0,5,'Speed4',CAP,{MoveSpeed=.5,Dodge=2},'MoveSpeed','capstone','Sudden urge to run laps.')

for _,d in S.List do
 d.children={}
 d.depth=math.sqrt(d.x*d.x+d.y*d.y)
end
for _,d in S.List do if d.parent then table.insert(S.ById[d.parent].children,d.id) end end

-- Owned set from the ProfileSkills attribute ('Damage1,MaxHP1'). The root is always owned;
-- unknown ids (removed nodes in old saves) are ignored.
function S.parse(text)
 local owned={Root=true}
 if type(text)=='string' then for id in string.gmatch(text,'[^,]+') do if S.ById[id] then owned[id]=true end end end
 return owned
end
function S.serialize(owned)
 local out={}
 for id in owned do if id~=S.ROOT and S.ById[id] then table.insert(out,id) end end
 table.sort(out)
 return table.concat(out,',')
end
-- 'owned' | 'available' (parent owned) | 'known' (grandparent owned) | 'hidden'.
function S.state(owned,id)
 local d=S.ById[id]
 if not d then return 'hidden' end
 if owned[id] then return 'owned' end
 if owned[d.parent] then return 'available' end
 local p=S.ById[d.parent]
 if p and owned[p.parent] then return 'known' end
 return 'hidden'
end
-- Server rule for a purchase. Returns ok, message.
function S.canBuy(owned,id,emeralds)
 local d=S.ById[id]
 if not d or d.kind=='root' then return false,'Unknown skill' end
 if owned[id] then return false,'Already owned' end
 if not owned[d.parent] then return false,'Unlock '..S.ById[d.parent].name..' first' end
 if (emeralds or 0)<d.cost then return false,'Not enough emeralds' end
 return true
end
-- Summed flat bonuses by stat id, fed into CharacterStats.resolve.
function S.bonuses(owned)
 local out={}
 for id in owned do
  local d=S.ById[id]
  if d then for stat,v in d.bonus do out[stat]=(out[stat] or 0)+v end end
 end
 return out
end
-- How many skills could be bought right now (HUD badge count).
function S.affordable(owned,emeralds)
 local n=0
 for _,d in S.List do if S.state(owned,d.id)=='available' and d.cost<=emeralds then n+=1 end end
 return n
end
function S.totalCost()
 local n=0;for _,d in S.List do n+=d.cost end;return n
end

-- '+4 Max health', '+2% Damage', '+0.25 HP/s Regeneration'.
local function num(v) return (v==math.floor(v)) and tostring(v) or string.format('%.2f',v):gsub('0+$','') end
function S.effect(stat,v)
 local d=Stats.ById[stat];if not d then return '' end
 local sign=v>=0 and '+' or ''
 local unit=d.unit
 if unit=='%' then return sign..num(v)..'% '..d.label end
 if unit=='' or unit==' HP' then return sign..num(v)..' '..d.label end
 return sign..num(v)..unit..' '..d.label
end
-- Ordered effect lines for one node (stat order follows CharacterStats.List).
function S.lines(d)
 local out={}
 for _,st in Stats.List do local v=d.bonus[st.id];if v then table.insert(out,S.effect(st.id,v)) end end
 return out
end
return S
