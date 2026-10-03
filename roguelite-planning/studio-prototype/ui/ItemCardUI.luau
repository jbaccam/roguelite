--!nonstrict
-- Item card (approved mockup: roguelite-planning/previews/item-card-mockup, 2026-10-02). Tapping an
-- item in a chest's odds list, or a pet in the Pet Egg's list, opens a card over it with:
--   the big icon, rarity and kind; whether you own it and at what tier; the chance to get it from
--   that chest or egg (and about 1 in how many); its special in plain words; its numbers at Tier
--   I-IV (the owned tier outlined in lime); and what unlocking and upgrading it costs.
-- < > (LB / RB, the left / right arrow keys) walk through the same list without closing. X, BACK,
-- B / Esc or a tap outside close it, and the controller goes back to the item's cell.
-- Presentation only. Every number is read at runtime: WeaponCatalog (stats per tier, the Godly
-- specials GodlyWeapons runs on, Legendary moves, and their text helpers godlyText / legendaryText),
-- CharacterStats.ArmorSets / armorBonus, PetConfig, ChestConfig (odds, pity, upgrade costs) and
-- EggConfig. Ownership is the LobbyUI profile record (ProfileWeapons / ProfileArmor / ProfilePets),
-- the same one the Armory reads.
-- Also shared by ChestScreenUI and EggScreenUI: K.percent (the one chance formatter for odds cells
-- and the card), K.rarestFirst, and K.cell (a tappable odds cell with an "i" badge, press feedback
-- and a lime gamepad ring).
-- Studio: ReplicatedStorage.ItemCardUI, a ModuleScript with the same Sandboxed / Capabilities
-- settings as ReplicatedStorage.ChestScreenUI (it is required by ChestScreenUI and EggScreenUI).
local RS=game:GetService('ReplicatedStorage')
local Players=game:GetService('Players')
local Input=game:GetService('UserInputService')
local GuiService=game:GetService('GuiService')
local TextService=game:GetService('TextService')
local T=require(RS:WaitForChild('UITheme'))
local StoreFX=require(RS:WaitForChild('StoreFX'))
local combat=RS:WaitForChild('RogueliteCombat')
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Chests=require(combat:WaitForChild('ChestConfig'))
local Armor=require(combat:WaitForChild('ArmorCatalog'))
local Pets=require(combat:WaitForChild('PetConfig'))
local Eggs=require(combat:WaitForChild('EggConfig'))
local LevelUps=require(combat:WaitForChild('LevelUpCatalog'))
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local C=T.Color
local WHITE=Color3.new(1,1,1)
local BLACK=Color3.new(0,0,0)
local INK=Color3.fromRGB(8,10,11)
local K={}

-- Chance in percent as text: the one formatter for every odds cell and the card.
-- 0.2 -> '0.2%', 9.09 -> '9.1%', 12.5 -> '12.5%', 0.05 -> '0.05%', 50 -> '50%'.
function K.percent(p)
 p=tonumber(p) or 0
 local s=p>=1 and string.format('%.1f',p) or p>=.1 and string.format('%.2f',p) or string.format('%.3f',p)
 if s:find('%.') then s=s:gsub('0+$',''):gsub('%.$','') end
 return s..'%'
end
-- Odds lists show the rarest first (user, 2026-10-02): Godly, Legendary, Epic, Rare, Common.
function K.rarestFirst(rarities)
 local out={};for i=#rarities,1,-1 do table.insert(out,rarities[i]) end
 return out
end
-- 'pad' | 'touch' | 'mouse', from the last input (help lines and button glyphs follow it).
function K.input()
 local ok,t=pcall(function() return Input:GetLastInputType() end)
 if not ok or not t then return 'mouse' end
 if t.Name:find('^Gamepad') then return 'pad' end
 if t==Enum.UserInputType.Touch then return 'touch' end
 return 'mouse'
end
function K.gamepad() return K.input()=='pad' end
local function keyImage(key) local ok,img=pcall(function() return Input:GetImageForKeyCode(key) end);return ok and img or '' end
K.keyImage=keyImage
-- Put a controller's selection on `obj` (after the B press that closed something has been handled).
function K.reselect(obj)
 task.defer(function()
  if obj and obj.Parent and K.gamepad() then pcall(function() GuiService.SelectedObject=obj end) end
 end)
end
-- T.label caps text at its size and keeps it at least 60% of it, but UITextSizeConstraint counts
-- screen pixels, not canvas pixels: on a phone canvas (scale .5) that floor is bigger than the box
-- and long text spills out. Measured in Studio 2026-10-02: 'Vampire Blade' at 36 in a 150x40 box at
-- scale .5 stayed 21 px in a 75 px box. This scales the floor with the canvas (never under 9 px) and
-- keeps wrapping on, because a scaled label only shrinks to its width when TextWrapped is true.
-- exact=true (the card) also scales the cap, so text keeps its design size on every screen instead
-- of growing to fill its box; nested UIScales (tier badges) count too.
function K.settle(root,s,exact)
 s=math.min(1,tonumber(s) or 1)
 for _,d in root:GetDescendants() do
  if d:IsA('UITextSizeConstraint') and d.Name=='FitText' and d.Parent:IsA('TextLabel') then
   local l=d.Parent;local size=l.TextSize;local k=s
   if exact then
    local o=l.Parent
    while o and o~=root do local u=o:FindFirstChildOfClass('UIScale');if u then k*=u.Scale end;o=o.Parent end
    d.MaxTextSize=math.max(9,math.floor(size*k+.5))
   end
   d.MinTextSize=math.min(d.MaxTextSize,math.max(9,math.floor(size*.6*k)))
   l.TextWrapped=true
  end
 end
end

local function textWidth(text,size,font) return TextService:GetTextSize(text,size,font or T.Font,Vector2.new(4000,200)).X end
local function textHeight(text,size,width) return TextService:GetTextSize(text,size,T.Body,Vector2.new(width,4000)).Y end
local function align(l,how) l.TextXAlignment=Enum.TextXAlignment[how];return l end
local function comma(n)
 n=math.floor(tonumber(n) or 0)
 local s=tostring(n):reverse():gsub('(%d%d%d)','%1,'):reverse()
 return (s:gsub('^,',''))
end
local function num(x) local s=string.format('%.1f',x);return (s:gsub('%.0$','')) end -- PetConfig.num
local function rate(r) return (string.format('%.2f',r):gsub('0$','')) end -- the Armory's attacks / sec
local function corner(obj,r) return T.make('UICorner',obj,{CornerRadius=r and UDim.new(0,r) or UDim.new(1,0)}) end
local function stroke(obj,color,t) return T.make('UIStroke',obj,{Color=color or INK,Thickness=t or 2,ApplyStrokeMode=Enum.ApplyStrokeMode.Border}) end
-- Owned check mark drawn from frames (FredokaOne has no check glyph), like the Armory's.
local function tick(parent,x,y,size,z)
 z=z or 1
 local g=T.make('Frame',parent,{Name='Owned',BackgroundColor3=C.lime,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size,size),BorderSizePixel=0,ZIndex=z})
 corner(g);stroke(g)
 local w=math.max(2,math.floor(size*.14))
 T.make('Frame',g,{BackgroundColor3=C.ink,BorderSizePixel=0,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.36,.58),Size=UDim2.fromOffset(w,size*.3),Rotation=-45,ZIndex=z+1})
 T.make('Frame',g,{BackgroundColor3=C.ink,BorderSizePixel=0,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.58,.46),Size=UDim2.fromOffset(w,size*.56),Rotation=40,ZIndex=z+1})
 return g
end
local function wash(parent,color,strength)
 local f=T.make('Frame',parent,{Name='Wash',BackgroundColor3=color,BackgroundTransparency=1-strength,BorderSizePixel=0,Position=UDim2.fromOffset(8,8),Size=UDim2.new(1,-16,1,-16),ZIndex=0})
 corner(f,10)
 T.make('UIGradient',f,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.65,.55),NumberSequenceKeypoint.new(1,1)})})
 return f
end

-- The lime ring a controller sees on the selected cell (one shared, unparented selection image).
local RING
local function ring()
 if RING then return RING end
 RING=Instance.new('Frame')
 RING.Name='ItemRing';RING.BackgroundTransparency=1;RING.Size=UDim2.new(1,18,1,18);RING.Position=UDim2.fromOffset(-9,-9)
 corner(RING,14);stroke(RING,C.lime,5)
 return RING
end

-- A tappable odds cell (ImageButton): rarity tint, icon, optional name, chance, an "i" corner badge
-- that says "details", press feedback (smaller, brighter, white edge) and the lime gamepad ring.
-- o: name, x, y, size, color, icon, iconSize, iconY, title?, titleY, titleH, titleSize, chance,
--    chanceY, chanceH, chanceSize, chanceColor?, badge (px, default 26), owned (tick top-left), z,
--    onOpen(), onSelect().
function K.cell(parent,o)
 local s,z=o.size,o.z or 1
 local c=T.make('ImageButton',parent,{Name=o.name,Image='',AutoButtonColor=false,Selectable=true,Position=UDim2.fromOffset(o.x,o.y),Size=UDim2.fromOffset(s,s),BackgroundColor3=o.color,BackgroundTransparency=.55,BorderSizePixel=0,ZIndex=z})
 corner(c,8)
 local edge=stroke(c,o.color,2)
 local scale=T.make('UIScale',c,{Scale=1})
 c.SelectionImageObject=ring()
 local ic=T.icon(c,'Icon',(s-o.iconSize)/2,o.iconY,o.iconSize,o.icon or '');ic.ZIndex=z+1
 if o.title then
  local t=T.label(c,'Name',o.title,4,o.titleY,s-8,o.titleH,o.titleSize,WHITE);t.ZIndex=z+2
 end
 local pl=T.label(c,'Chance',o.chance,0,o.chanceY,s,o.chanceH or 28,o.chanceSize or 22,o.chanceColor or WHITE);pl.ZIndex=z+2
 local bs=o.badge or 26
 local b=T.make('Frame',c,{Name='Info',BackgroundColor3=C.well,Position=UDim2.fromOffset(s-bs-4,4),Size=UDim2.fromOffset(bs,bs),BorderSizePixel=0,ZIndex=z+3})
 corner(b);stroke(b)
 local il=T.label(b,'I','i',0,0,bs,bs,math.floor(bs*.78),C.lime);il.ZIndex=z+4;il.TextStrokeTransparency=.6
 if o.owned then tick(c,4,4,bs,z+3) end
 local hover,down,selected=false,false,false
 local function paint()
  c.BackgroundTransparency=down and .15 or (hover or selected) and .35 or .55
  edge.Color=down and WHITE or o.color
  edge.Thickness=down and 3 or 2
  scale.Scale=down and .93 or 1
 end
 local function pointer(i) return i.UserInputType==Enum.UserInputType.MouseButton1 or i.UserInputType==Enum.UserInputType.Touch end
 c.MouseEnter:Connect(function() hover=true;paint() end)
 c.MouseLeave:Connect(function() hover=false;down=false;paint() end)
 c.InputBegan:Connect(function(i) if pointer(i) then down=true;paint() end end)
 c.InputEnded:Connect(function(i) if pointer(i) then down=false;paint() end end)
 c.SelectionGained:Connect(function() selected=true;paint();if o.onSelect then o.onSelect() end end)
 c.SelectionLost:Connect(function() selected=false;paint() end)
 if o.onOpen then c.Activated:Connect(o.onOpen) end
 return c
end

-- What an id is ------------------------------------------------------------------------------------
local REVIVE='rbxassetid://93648739105819' -- ui/assets/hud/revive.png (hud/asset-ids.json)
K.ReviveIcon=REVIVE -- exported so AssetPreloader keeps it warm
-- Icons for stats and perks: the level-up art (LevelUpCatalog.IconIds), or its nearest match.
local ICON_ALIAS={BurnChance='ElementalDamage',PoisonChance='ElementalDamage',FirstHitBlock='Armor',ContactReduction='Armor',CritDamage='CritChance',
 RageAttackSpeed='AttackSpeed',FireThorns='ElementalDamage',DodgeCrit='Dodge',leech='LifeSteal',PhoenixBlast=REVIVE}
local function statIcon(key)
 local a=ICON_ALIAS[key]
 if a and a:find('^rbx') then return a end
 return LevelUps.IconIds and LevelUps.IconIds[a or key] or nil
end
-- Armor perks are flags or numbers in CharacterStats.ArmorSets (names for the table; numbers from armorBonus).
local PERKS={PhoenixBlast={label='Rise blast damage'},DodgeCrit={label='Crit after a dodge'},
 RageAttackSpeed={label='Low-HP attack speed',unit='%',plus=true},FireThorns={label='Burns attackers',unit='%'}}
-- Pet numbers that change with tier (PetConfig fields given per tier), one row each.
local PET_ROWS={{field='heal',label='Heal (HP)'},{field='radius',label='Slam size (studs)'},{field='slow',label='Slow',unit='%'},
 {field='bonus',label='Marked damage bonus',unit='%',plus=true},{field='every',label='Every (seconds)'}}
local function statLabel(id)
 local d=Stats.ById[id];if not d then return id end
 local u=(d.unit or ''):gsub('^%s+','')
 return d.label..((u~='' and u~='%') and ' ('..u..')' or '')
end
local function statValue(id,v)
 if v==nil then return '–' end
 if v==true then return true end
 local d=Stats.ById[id];local u=d and (d.unit or ''):gsub('^%s+','') or ''
 return ((v>0 and id~='FirstHitBlock') and '+' or '')..num(v)..(u=='%' and '%' or '')
end
local function sortedKeys(t) local out={};for k in t or {} do table.insert(out,k) end;table.sort(out);return out end

local function itemOf(id)
 local p=Pets.ById[id]
 if p then return {kind='pet',id=id,name=p.name,rarity=p.rarity,icon=Pets.Icons and Pets.Icons[id] or '',pet=p} end
 local w=Weapons.ById[id]
 if w then return {kind='weapon',id=id,name=w.name,rarity=Chests.RarityOf[id] or w.rarity or 'Common',icon=WeaponIcons[id] or '',w=w} end
 local setId,slot=Armor.split(id);local set=setId and Armor.ById[setId]
 if set then return {kind='armor',id=id,name=Armor.pieceName(id),rarity=set.rarity,icon=Armor.Icons[id] or '',set=set,slot=slot} end
 return nil
end
K.item=itemOf
local function ownedRec(profile,it)
 if type(profile)~='table' then return nil end
 local t=it.kind=='weapon' and profile.weapons or it.kind=='armor' and profile.armor or profile.pets
 local rec=type(t)=='table' and t[it.id] or nil
 return rec and {tier=math.clamp(tonumber(rec.tier) or 1,1,4),have=tonumber(rec.have) or 0} or nil
end

-- Table rows: {label, icon, values = 4 x (text | true for a tick), boost = 4 x bool (gold)}.
local function weaponRows(it)
 local w=it.w;local rows={}
 local function four(f) local v={};for t=1,4 do v[t]=f(t) end;return v end
 table.insert(rows,{label='Damage',icon=statIcon('Damage'),values=four(function(t) return tostring(w.tierDamage[t] or w.damage) end)})
 table.insert(rows,{label='Attacks / sec',icon=statIcon('AttackSpeed'),values=four(function(t) return rate(1/(w.cooldown*(w.tierCooldown[t] or 1))) end)})
 table.insert(rows,{label='Range (studs)',icon=statIcon('AttackRange'),values=four(function() return num(w.range) end)})
 for _,row in (Weapons.GodlyRows and Weapons.GodlyRows[it.id]) or {} do
  local v,raw,boost={},{},{}
  for t=1,4 do v[t],raw[t]=Weapons.godlyRowValue(it.id,row,t);boost[t]=t>1 and raw[t]~=raw[t-1] end
  table.insert(rows,{label=row.label,icon=statIcon(row.field),values=v,boost=boost})
 end
 local move=Weapons.Legendary and Weapons.Legendary[it.id]
 if move then table.insert(rows,{label=(Weapons.LegendaryNames and Weapons.LegendaryNames[move.move]) or move.move,values={'–','–','–',true}}) end
 return rows
end
local function armorRows(it)
 local set=it.set;local bonus=Stats.ArmorSets and Stats.ArmorSets[set.id];local rows={}
 if not bonus then return rows end
 -- The set bonus with 2 / all 4 pieces worn at each tier (CharacterStats.armorBonus does the scaling).
 local per={}
 for t=1,4 do
  local tiers,two,all={},{},{}
  for i,slot in Armor.Slots do tiers[Armor.pieceId(set.id,slot)]=t;all[slot]=set.id;if i<=2 then two[slot]=set.id end end
  local s2,p2=Stats.armorBonus(two,tiers);local s4,p4=Stats.armorBonus(all,tiers)
  per[t]={s2,p2,s4,p4}
 end
 local function add(key,pieces)
  local perk=PERKS[key];local v={}
  for t=1,4 do
   local s,pk=per[t][pieces==2 and 1 or 3],per[t][pieces==2 and 2 or 4]
   local x=s[key];if x==nil then x=pk[key] end
   if perk then v[t]=x==true and true or x==nil and '–' or ((perk.plus and '+' or '')..num(x)..(perk.unit or '')) else v[t]=statValue(key,x) end
  end
  table.insert(rows,{label=(perk and perk.label or statLabel(key))..' · '..pieces..' pc',icon=statIcon(key),values=v})
 end
 for _,k in sortedKeys(bonus.two) do add(k,2) end
 for _,k in sortedKeys(bonus.four) do add(k,4) end
 return rows
end
local function petRows(it)
 local p=it.pet;local rows={}
 for _,k in sortedKeys(p.stats) do
  local v={};for t=1,4 do v[t]=statValue(k,Pets.stats(p.id,t)[k]) end
  table.insert(rows,{label=statLabel(k),icon=statIcon(k),values=v})
 end
 if p.base then
  local d,e={},{}
  for t=1,4 do d[t]=num(Pets.damage(p.id,t,1));e[t]='+'..num((p.perWave or 0)*Pets.TierMult[t]) end
  table.insert(rows,{label='Damage at wave 1',icon=statIcon('Damage'),values=d})
  table.insert(rows,{label='Extra per wave',values=e})
 end
 for _,f in PET_ROWS do
  if type(p[f.field])=='table' then
   local v={};for t=1,4 do v[t]=(f.plus and '+' or '')..num(Pets.get(p.id,f.field,t))..(f.unit or '') end
   table.insert(rows,{label=f.label,values=v})
  end
 end
 return rows
end

-- The card ------------------------------------------------------------------------------------------
-- args: list = odds entries {id, rarity, chance (percent)} in display order, id, source ('chest' |
-- 'egg'), kind (the chest id), profile() -> LobbyUI profile, zindex, onClose(lastId, silent).
-- Returns {Root, Id(), Step(d), Redraw(L), Close(silent)}. Laid out on the caller's canvas (T.canvas):
-- PC (canvas 900+ tall) a 1240 x 800 card; phones (1500x738 at T.READABLE_SCALE) a 1440 wide card
-- with the < > under the icon and the copies line beside BACK, every text 20+ canvas px (10+ on screen).
function K.open(canvas,L,args)
 local self={}
 local list=args.list or {}
 local index=1
 for i,o in list do if o.id==args.id then index=i end end
 local root
 local closed=false
 local draw
 function self.Id() return list[index] and list[index].id end
 function self.Close(silent)
  if closed then return end
  closed=true
  if root then root:Destroy();root=nil end
  self.Root=nil
  if args.onClose then args.onClose(self.Id(),silent==true) end
 end
 function self.Step(d)
  if closed or #list<2 then return end
  index=(index-1+d)%#list+1
  draw()
 end
 function self.Redraw(newL) if closed then return end;if newL then L=newL end;draw() end
 local function close() self.Close(false) end

 draw=function()
  if root then root:Destroy();root=nil end
  local entry=list[index];local it=entry and itemOf(entry.id)
  if not it then return end
  local profile=args.profile and args.profile() or nil
  local own=ownedRec(profile,it)
  local compact=L.h<900
  local tap=L.tap or math.ceil(44/L.s)
  local top=math.max(L.top+40,60)
  local W=compact and math.min(1440,L.w-60) or math.min(1240,L.w-120)
  local H=compact and L.h-12-top or math.min(800,L.h-24-top)
  local X=math.floor((L.w-W)/2)
  local Y=math.max(top,math.floor((L.h-H)/2+17))
  local pad=24
  local col=Chests.RarityColor[it.rarity] or WHITE
  local colL=col:Lerp(WHITE,.35)
  local egg=args.source=='egg'
  local def=not egg and Chests.ById[args.kind or ''] or nil
  root=T.frame(canvas,'ItemCard',0,0,L.w,L.h);root.ZIndex=args.zindex or 50
  root:SetAttribute('Item',entry.id)
  self.Root=root
  -- Modal shade: a tap outside the card closes it.
  local shade=T.make('TextButton',root,{Name='Shade',Text='',AutoButtonColor=false,Selectable=false,Active=true,BackgroundColor3=C.shade,BackgroundTransparency=.45,BorderSizePixel=0,Position=UDim2.fromOffset(-1000,-400),Size=UDim2.fromOffset(L.w+2000,L.h+800),ZIndex=0})
  shade:SetAttribute('AuditIgnore',true)
  shade.Activated:Connect(close)
  local p=T.panel(root,'Card',X,Y,W,H,'panel');p.Active=true;p.ZIndex=1
  T.setTier(p,2);if p:FindFirstChild('RarityCorners') then p.RarityCorners.ImageColor3=col end
  -- A controller stays inside the card while it is open.
  p.SelectionGroup=true
  p.SelectionBehaviorUp=Enum.SelectionBehavior.Stop;p.SelectionBehaviorDown=Enum.SelectionBehavior.Stop
  p.SelectionBehaviorLeft=Enum.SelectionBehavior.Stop;p.SelectionBehaviorRight=Enum.SelectionBehavior.Stop
  wash(p,col,.22)
  -- Title plate (the item's name, shrinking when long) and the red X.
  local cs=math.max(62,tap)
  local ps=compact and 36 or 38
  local pw=math.min(textWidth(it.name,ps)+100,W-28-cs-24)
  local plate=T.panel(p,'TitlePlate',28,-34,pw,70,'panel');plate.ZIndex=3
  T.caps(plate,48)
  T.label(plate,'Title',it.name,40,0,pw-80,70,ps,WHITE)
  local x=T.button(p,'Close','X',W-cs-8,-26,cs,cs,close,true);T.setTier(x,4);x.Caption.TextColor3=C.negative;x.Caption.TextSize=34;x.ZIndex=3;x.SelectionOrder=4

  -- Left: the hero ---------------------------------------------------------------------------------
  local hw=compact and 320 or 430
  local ab=compact and math.max(tap,62) or 70
  local bottomY=H-pad-ab
  local wy=compact and 40 or 52
  local subH,ph,chH=32,compact and 56 or 66,compact and 80 or 104
  local below=6+subH+8+ph+8+chH
  local limit=compact and bottomY-10 or H-pad-34
  local wh=math.clamp(limit-wy-below,140,compact and 260 or 384)
  local well=T.panel(p,'Hero',pad,wy,hw,wh,'inset')
  local clip=T.make('Frame',well,{Name='Glow',BackgroundTransparency=1,ClipsDescendants=true,Position=UDim2.fromOffset(8,8),Size=UDim2.fromOffset(hw-16,wh-16),ZIndex=1})
  StoreFX.burst(clip,(hw-16)/2,(wh-16)/2,wh*1.7,col:Lerp(WHITE,.45),10)
  local ic=wh-(compact and 40 or 64)
  local art=T.icon(well,'Icon',(hw-ic)/2,(wh-ic)/2,ic,it.icon);art.ZIndex=2
  local rt=string.upper(it.rarity);local tw=textWidth(rt,22)+28
  local tag=T.make('Frame',well,{Name='Rarity',BackgroundColor3=col:Lerp(BLACK,.35),Position=UDim2.fromOffset(12,12),Size=UDim2.fromOffset(tw,36),BorderSizePixel=0,ZIndex=3})
  corner(tag,8);stroke(tag)
  T.label(tag,'Text',rt,0,0,tw,36,22,WHITE).ZIndex=4
  if own then
   local b=T.tierBadge(well,own.tier,hw-12,12,Vector2.new(1,0));T.make('UIScale',b,{Scale=1.7})
  else
   T.icon(well,'Lock',hw-58,8,46,'lock').ZIndex=3
  end
  -- What it is (the rarity is already on the tag): 'MELEE · ANY CLASS', 'ARMOR · CHEST', 'PET · FIRE'.
  local kind=it.kind=='weapon' and (it.w.godly and (it.w.kind..' · any class') or (it.w.kind..' · '..it.w.home))
   or it.kind=='armor' and ('armor · '..it.slot) or ('pet · '..it.pet.suit)
  local ky=wy+wh+6
  if it.kind=='weapon' and not it.w.godly then
   -- A class weapon: two tags, its class (with the class's starter icon) and its type.
   local th=subH-2
   local _,cw1=T.tag(p,'ClassTag',string.upper(it.w.home),pad,ky+1,{h=th,size=th-12,icon=WeaponIcons[Stats.Signature[it.w.home]]})
   T.tag(p,'TypeTag',string.upper(it.w.kind=='Blast' and 'Explosive' or it.w.kind),pad+cw1+8,ky+1,{h=th,size=th-12,color=Color3.fromRGB(27,33,37),textColor=C.muted})
  else
   T.label(p,'Kind',string.upper(kind),pad,ky,hw,subH,compact and 22 or 24,C.cream)
  end
  -- Owned or not, and at what tier.
  local py=ky+subH+8
  local pill=T.panel(p,'Owned',pad,py,hw,ph,'inset')
  if own then
   local ts=compact and 30 or 34
   tick(pill,14,(ph-ts)/2,ts,2)
   align(T.label(pill,'Text','YOU OWN IT',14+ts+10,0,hw-ts-150,ph,compact and 24 or 28,C.lime),'Left')
   local bw=compact and 100 or 110
   local tb=T.make('Frame',pill,{Name='Tier',BackgroundColor3=T.TierFill[own.tier],Position=UDim2.fromOffset(hw-bw-12,(ph-38)/2),Size=UDim2.fromOffset(bw,38),BorderSizePixel=0,ZIndex=2})
   corner(tb,6);stroke(tb)
   T.label(tb,'Text','TIER '..T.Roman[own.tier],0,0,bw,38,22,WHITE).ZIndex=3
  else
   T.icon(pill,'Lock',14,(ph-40)/2,40,'lock')
   align(T.label(pill,'Text','NOT OWNED YET',64,0,hw-80,ph,compact and 24 or 28,C.muted),'Left')
  end
  -- The chance from this chest or egg.
  local cy=py+ph+8
  local chance=T.panel(p,'Chance',pad,cy,hw,chH,'inset')
  local is=compact and 60 or 76
  T.icon(chance,'Icon',10,(chH-is)/2,is,egg and (Eggs.Icon or '') or (def and def.icon or ''))
  local pctText=K.percent(entry.chance);local psz=compact and 34 or 40
  local pw2=textWidth(pctText,psz)+16;local cx=is+18
  align(T.label(chance,'Percent',pctText,cx,compact and 4 or 10,pw2,compact and 40 or 46,psz,C.gold),'Left')
  local per=egg and 'per Pet Egg' or compact and 'per chest' or ('from each '..(def and def.name or 'chest'))
  T.text(chance,'Per',per,cx+pw2+6,compact and 6 or 12,hw-cx-pw2-18,compact and 36 or 40,compact and 21 or 22,WHITE)
  local n=(entry.chance or 0)>0 and math.max(1,math.round(100/entry.chance)) or 0
  local only=not egg and Chests.OnlyIn and Chests.OnlyIn[entry.id]
  only=only and #only==1 and only[1]==args.kind
  local oneIn=(compact and '1 in ' or 'about 1 in ')..comma(n)..(egg and ' eggs' or ' chests')..(only and ' · only here' or '')
   ..((egg and not compact) and (' · '..comma(Eggs.Emeralds)..' emeralds each') or '')
  T.text(chance,'OneIn',oneIn,cx,compact and 42 or 58,hw-cx-12,compact and 30 or 34,compact and 20 or 21,C.muted)
  -- Pity (PC): how many chests until this rarity is guaranteed (ChestConfig pity, the profile's count).
  if not compact and def and def.pity then
   local pity=profile and profile.pity or {}
   local text
   if it.rarity=='Godly' then
    local left=math.max(1,Chests.GodlyPity-(pity.Godly or 0));text='A Godly item is guaranteed within '..left..' chest'..(left>1 and 's' or '')
   elseif it.rarity=='Legendary' then
    if def.legendary>=1 then text='Every '..def.name..' holds 1 Legendary item'
    else local left=math.max(1,Chests.LegendaryPity-(pity.Legendary or 0));text='A Legendary item is guaranteed within '..left..' chest'..(left>1 and 's' or '') end
   end
   if text then align(T.text(p,'Pity',text,pad,cy+chH+8,hw,26,18,C.dim),'Center') end
  end

  -- Right: what it does and its numbers by tier ---------------------------------------------------------
  local rx=pad+hw+24
  local rw=W-rx-pad
  local ry=wy
  local availH=bottomY-10-ry
  local body=T.frame(p,'Body',rx,ry,rw,availH)
  local y=0
  local function head(text)
   align(T.label(body,'Heading',text,0,y,rw,34,compact and 26 or 28,colL),'Left')
   y+=compact and 38 or 42
  end
  local function para(name,text,size,color)
   if not text or text=='' then return end
   -- Measured a little narrower than drawn, so rounding on small screens never adds a line.
   local h=textHeight(text,size,rw-16)+6
   local l=T.text(body,name,text,0,y,rw,h,size,color);l.TextYAlignment=Enum.TextYAlignment.Top
   y+=h+4
  end
  local t0=own and own.tier or 1
  local rows
  if it.kind=='weapon' then
   local w=it.w
   if w.godly then
    head('GODLY SPECIAL')
    para('Text',Weapons.godlyText(it.id,t0),24,WHITE)
    para('More',((t0<4 and Weapons.godlyUpgradeText(it.id)) and (Weapons.godlyUpgradeText(it.id)..' ') or '')..Weapons.describe(w),20,C.muted)
   elseif Weapons.Legendary and Weapons.Legendary[it.id] then
    local m=Weapons.Legendary[it.id]
    head('TIER IV MOVE  ·  '..string.upper((Weapons.LegendaryNames and Weapons.LegendaryNames[m.move]) or m.move))
    para('Text',Weapons.legendaryText(it.id),24,WHITE)
    para('More',Weapons.describe(w)..(compact and '' or ' Starts runs only as a '..w.home..'; any class can buy it in the run shop.'),20,C.muted)
   else
    head('ABOUT')
    para('Text',Weapons.describe(w),24,WHITE)
   end
   -- Damage by class: this weapon's column of CharacterStats.ClassFit, the loadout's class tagged YOU.
   if not w.godly then
    local lp=Players.LocalPlayer;local mine=lp and lp:GetAttribute('LoadoutClass') or 'Brawler'
    y+=4
    y+=T.section(body,'FitTitle','DAMAGE BY CLASS',0,y,rw,compact and 24 or 20,'you play '..mine)+(compact and 18 or 14)
    local entries={}
    for _,c in Stats.ClassOrder do
     local _,pct=Stats.classFit(w,c)
     table.insert(entries,{name=c,image=WeaponIcons[Stats.Signature[c]],pct=pct,own=c==w.home,you=c==mine})
    end
    local _,fh=T.fitTiles(body,'WeaponFit',0,y,rw,entries,{icon=compact and 44 or 34,nameSize=compact and 19 or 14,pctSize=compact and 26 or 20,youSize=compact and 17 or 13,gap=compact and 8 or 8})
    y+=fh+6
   end
   rows=weaponRows(it)
  elseif it.kind=='armor' then
   local set=it.set;local bonus=Stats.ArmorSets and Stats.ArmorSets[set.id]
   head(string.upper(set.name)..' SET BONUS')
   if bonus and bonus.text then
    local nw=compact and 118 or 124
    for _,pieces in {2,4} do
     local key=sortedKeys(pieces==2 and bonus.two or bonus.four)[1]
     local text=pieces==2 and bonus.text.two or bonus.text.four
     local h=math.max(36,textHeight(text,22,rw-48-nw)+4)
     local ico=key and statIcon(key);if ico then T.icon(body,'Icon'..pieces,0,y-2,40,ico) end
     align(T.label(body,'Pieces'..pieces,pieces..' PIECES',48,y,nw,36,compact and 21 or 22,C.lime),'Left')
     local l=T.text(body,'Bonus'..pieces,text,48+nw,y+(h>36 and 0 or 0),rw-48-nw,h,22,WHITE);if h>36 then l.TextYAlignment=Enum.TextYAlignment.Top end
     y+=h+(compact and 4 or 8)
    end
   end
   rows=armorRows(it)
  else
   local pet=it.pet
   head('ABILITY  ·  '..string.upper(pet.suit))
   para('Text',Pets.effectText(pet.id,t0),24,WHITE)
   para('More',pet.description,20,C.muted)
   rows=petRows(it)
  end
  -- Unlock / upgrade costs (ChestConfig.upgradeCost / upgradeEmeralds, by rarity), ticks for owned tiers.
  local costs={}
  for t=1,4 do
   if own and own.tier>=t then costs[t]=true
   elseif t==1 then costs[t]={unlock=true}
   else costs[t]={copies=Chests.upgradeCost(it.id,t-1) or 0,gems=Chests.upgradeEmeralds(it.id,t-1) or 0} end
  end
  table.insert(rows,{label=own and 'Upgrade cost' or 'Unlock / upgrade',values=costs,cost=true})
  -- The table.
  y+=compact and (own and 18 or 6) or 10
  local tableTitle=it.kind=='armor' and 'SET BONUS BY TIER' or it.kind=='pet' and 'ABILITY BY TIER' or 'STATS BY TIER'
  if not compact then align(T.label(body,'TableTitle',tableTitle,0,y,rw*.6,30,24,C.muted),'Left');y+=36 end
  local lw=compact and 300 or 250
  local cw=(rw-lw)/4
  local hh,rh,costH=compact and 36 or 42,compact and 40 or 48,compact and 54 or 60
  local tH=hh+(#rows-1)*rh+costH
  local tb=T.frame(body,'Tiers',0,y,rw,tH)
  if own then
   local ox=lw+(own.tier-1)*cw
   local band=T.make('Frame',tb,{Name='Yours',BackgroundColor3=C.lime,BackgroundTransparency=.9,BorderSizePixel=0,Position=UDim2.fromOffset(ox+3,-6),Size=UDim2.fromOffset(cw-6,tH+10),ZIndex=1})
   corner(band,12)
   local edge=T.make('Frame',tb,{Name='YoursEdge',BackgroundTransparency=1,Position=UDim2.fromOffset(ox+3,-6),Size=UDim2.fromOffset(cw-6,tH+10),ZIndex=3})
   corner(edge,12);stroke(edge,C.lime,3)
   local ys=compact and 22 or 20
   local yw=textWidth('YOU',ys)+22
   local chip=T.make('Frame',tb,{Name='You',BackgroundColor3=C.lime,BorderSizePixel=0,Position=UDim2.fromOffset(ox+cw/2-yw/2,-6-(ys+8)/2),Size=UDim2.fromOffset(yw,ys+8),ZIndex=4})
   corner(chip,7);stroke(chip)
   local yl=T.label(chip,'Text','YOU',0,0,yw,ys+8,ys,C.ink);yl.TextStrokeTransparency=1;yl.ZIndex=5
  end
  if compact then align(T.label(tb,'Title',tableTitle,4,0,lw-8,hh,21,C.muted),'Left') end
  for t=1,4 do
   local b=T.tierBadge(tb,t,lw+(t-1)*cw+cw/2,hh/2,Vector2.new(.5,.5));T.make('UIScale',b,{Scale=compact and 1.5 or 1.4})
  end
  for i,r in rows do
   local rowY=hh+(i-1)*rh
   local h=r.cost and costH or rh
   local row=T.make('Frame',tb,{Name='Row'..i,BackgroundColor3=BLACK,BackgroundTransparency=i%2==1 and .68 or .82,BorderSizePixel=0,Position=UDim2.fromOffset(0,rowY+2),Size=UDim2.fromOffset(rw,h-4),ZIndex=2})
   corner(row,8)
   local lx=10
   if r.icon then local s=compact and 30 or 34;T.icon(row,'Icon',8,(h-4-s)/2,s,r.icon).ZIndex=3;lx=s+16 end
   align(T.text(row,'Label',r.label,lx,0,lw-lx-6,h-4,compact and 21 or 22,C.cream),'Left').ZIndex=3
   for t,v in r.values do
    local vx=lw+(t-1)*cw
    if v==true then
     local s=compact and 28 or 30;tick(row,vx+cw/2-s/2,(h-4-s)/2,s,3)
    elseif type(v)=='table' then
     local s=compact and 22 or 21
     if v.unlock then
      T.label(row,'Copies'..t,'1 copy',vx,compact and 2 or 4,cw,(h-4)/2,s,WHITE).ZIndex=3
      T.text(row,'Unlocks'..t,'unlocks it',vx+4,(h-4)/2,cw-8,(h-4)/2-2,compact and 21 or 19,C.muted).TextXAlignment=Enum.TextXAlignment.Center
     else
      T.label(row,'Copies'..t,v.copies..' '..(v.copies==1 and 'copy' or 'copies'),vx,compact and 2 or 4,cw,(h-4)/2,s,WHITE).ZIndex=3
      local gt=comma(v.gems);local gw=textWidth(gt,s)+12;local gx=vx+cw/2-(24+gw)/2
      T.icon(row,'Gem'..t,gx,(h-4)/2+((h-4)/2-22)/2-1,22,'emerald').ZIndex=3
      align(T.label(row,'Gems'..t,gt,gx+24,(h-4)/2-2,gw,(h-4)/2,s,C.emerald),'Left').ZIndex=3
     end
    else
     local dim=v=='–'
     local gold=r.boost and r.boost[t]
     T.label(row,'Value'..t,v,vx,0,cw,h-4,dim and 24 or (compact and 26 or 28),gold and C.gold or dim and C.dim or WHITE).ZIndex=3
    end
   end
  end
  y+=tH+(compact and 10 or 16)

  -- Copies toward the next tier, your armor set, or a note (PC: under the table; phone: beside BACK).
  local bw=240;local bx=W-pad-bw
  local function sectionC(parent,x0,y0,maxW)
   local s=compact and 21 or 22
   if it.kind=='armor' then
    local set=it.set;local ownedN=0
    for _,sl in Armor.Slots do if profile and profile.armor and profile.armor[Armor.pieceId(set.id,sl)] then ownedN+=1 end end
    local sz=compact and 60 or 56
    local label=(compact and 'YOUR SET  ' or ('YOUR '..string.upper(set.name)..' SET  '))..ownedN..' / 4'
    local lw2=compact and 190 or 350
    align(T.label(parent,'SetTitle',label,x0,y0+(sz-34)/2,lw2,34,s,C.muted),'Left')
    for i,sl in Armor.Slots do
     local pid=Armor.pieceId(set.id,sl);local o=profile and profile.armor and profile.armor[pid];local me=pid==it.id
     local b=T.make('Frame',parent,{Name='Piece_'..sl,BackgroundColor3=o and col or BLACK,BackgroundTransparency=o and .55 or .65,BorderSizePixel=0,Position=UDim2.fromOffset(x0+lw2+(i-1)*(sz+14),y0),Size=UDim2.fromOffset(sz,sz),ZIndex=2})
     corner(b,9);stroke(b,me and WHITE or o and col or Color3.fromRGB(70,76,80),me and 3 or 2)
     local pi=T.icon(b,'Icon',4,4,sz-8,Armor.Icons[pid] or '');pi.ZIndex=3;if not o then pi.ImageTransparency=.55 end
     if o then local tb2=T.tierBadge(b,math.clamp(tonumber(o.tier) or 1,1,4),-4,-6);T.make('UIScale',tb2,{Scale=compact and 1.6 or 1.4})
     else T.icon(b,'Lock',sz-24,sz-26,22,'lock').ZIndex=4 end
    end
    return sz+8
   elseif own and own.tier<4 then
    local need=Chests.upgradeCost(it.id,own.tier) or 0;local gems=Chests.upgradeEmeralds(it.id,own.tier) or 0
    local t1='→ TIER '..T.Roman[own.tier+1]..': '..need..' '..(need==1 and 'copy' or 'copies')..' +'
    local w1=textWidth(t1,s,T.Body)+16;local gt=comma(gems);local gw=textWidth(gt,s)+14
    local barW=math.clamp(maxW-110-14-w1-26-gw,120,300)
    align(T.label(parent,'CopiesTitle','COPIES',x0,y0,104,34,s,C.muted),'Left')
    local copies=T.upgradeBar(parent,'Copies',x0+110,y0+3,barW,28,own.have,need)
    if copies:FindFirstChild('Count') then copies.Count.TextSize=compact and 22 or 20 end -- the bar's own 16 px count is too small on phones
    local nx=x0+110+barW+14
    align(T.text(parent,'NextTier',t1,nx,y0,w1,34,s,WHITE),'Left')
    T.icon(parent,'Gem',nx+w1,y0+5,24,'emerald')
    align(T.label(parent,'NextGems',gt,nx+w1+26,y0,gw,34,s,C.emerald),'Left')
    local used=42
    if it.kind=='weapon' and not compact then
     local w=it.w;local t=own.tier+1
     local d=math.floor((w.tierDamage[t]/w.tierDamage[t-1]-1)*100+.5)
     local sp=math.floor((w.tierCooldown[t-1]/w.tierCooldown[t]-1)*100+.5)
     align(T.text(parent,'Gains','Tier '..T.Roman[t]..' adds +'..d..'% damage and +'..sp..'% attack speed.',x0,y0+used,maxW,28,20,C.muted),'Left')
     used+=32
    end
    return used
   elseif own then
    align(T.label(parent,'Max','MAX TIER',x0,y0,maxW,34,s,C.lime),'Left');return 42
   elseif it.kind=='weapon' and it.w.godly then
    align(T.text(parent,'Note',compact and 'One Godly per run · never in the run shop' or 'One Godly per run. It is never sold in the run shop.',x0,y0,maxW,34,compact and 21 or 20,C.muted),'Left');return 38
   elseif it.kind=='pet' and not own then
    align(T.text(parent,'Note','Hatches from the Pet Egg at the egg merchant.',x0,y0,maxW,34,compact and 21 or 20,C.muted),'Left');return 38
   end
   return 0
  end
  if compact then sectionC(p,rx,bottomY+(ab-(it.kind=='armor' and 60 or 34))/2,bx-16-rx)
  else y+=sectionC(body,0,y,rw) end
  -- The right column scrolls when it is taller than the card (short phones).
  if y>availH then
   local sc=T.scroll(p,'BodyScroll',rx,ry,rw+10,availH);sc.CanvasSize=UDim2.fromOffset(0,y)
   body.Parent=sc;body.Position=UDim2.new();body.Size=UDim2.fromOffset(rw,y)
  else body.Size=UDim2.fromOffset(rw,y) end

  -- Bottom: walk the list (PC: right column; phone: under the icon) and BACK.
  local arrX=compact and pad or rx
  local prev=T.button(p,'Prev','<',arrX,bottomY,ab,ab,function() self.Step(-1) end,true);prev.Caption.TextSize=40
  local nextB=T.button(p,'Next','>',arrX+ab+12,bottomY,ab,ab,function() self.Step(1) end,true);nextB.Caption.TextSize=40
  local same,pos=0,0
  for i,o in list do if o.rarity==entry.rarity then same+=1;if i==index then pos=same end end end
  local cntX=arrX+2*ab+24
  local cntW=compact and (pad+hw-cntX) or 240
  T.label(p,'Count',compact and (pos..' / '..same) or (pos..' / '..same..'  '..string.upper(entry.rarity)),cntX,bottomY,cntW,ab,compact and 24 or 22,C.muted)
  local back=T.button(p,'Back','BACK',bx,bottomY,bw,ab,close,true);back.Caption.TextSize=30
  if K.gamepad() then
   -- Controller glyphs: LB / RB on the arrows, B on BACK (Roblox's art for the connected pad).
   for _,pair in {{prev,Enum.KeyCode.ButtonL1},{nextB,Enum.KeyCode.ButtonR1}} do
    local img=keyImage(pair[2])
    if img~='' then pair[1].Caption.Visible=false;local g=T.icon(pair[1],'Glyph',ab*.2,ab*.2,ab*.6,img);g.ZIndex=pair[1].ZIndex+1 end
   end
   local bimg=keyImage(Enum.KeyCode.ButtonB)
   if bimg~='' then local g=T.icon(back,'Glyph',16,(ab-40)/2,40,bimg);g.ZIndex=back.ZIndex+1 end
  end
  back.SelectionOrder=1;prev.SelectionOrder=2;nextB.SelectionOrder=3
  -- Now and once more after T.label's own TextSize handlers (deferred) have run for the captions.
  K.settle(root,L.s,true)
  local drawn=root
  task.defer(function() if drawn.Parent then K.settle(drawn,L.s,true) end end)
  K.reselect(back)
 end
 draw()
 return self
end

return K
