-- The Armory's plates under the dais (plan K): DAMAGE, HEALTH and POWER. Tapping POWER opens a card
-- that says what Power is and shows the player's own gear adding up to it (CharacterStats.gearParts).
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local combat=RS:WaitForChild('RogueliteCombat')
local Stats=require(combat:WaitForChild('CharacterStats'))
local C=T.Color
local M={}
M.WIDTH,M.HEIGHT=624,70 -- three 200-wide plates, 12 apart
M.CARD_W,M.CARD_H=520,340
-- Power's icon: the user's flexed bicep (ui/assets/hud/power-bicep.png).
M.PowerIcon='rbxassetid://138972895415138'
local ARMOR_ICON='rbxassetid://80556274645944' -- Armor upgrade (shield)
local PET_ICON='rbxassetid://115158817562855' -- pet egg (ui/assets/hud/pet-egg.png)
local function left(l) l.TextXAlignment=Enum.TextXAlignment.Left;return l end
local function right(l) l.TextXAlignment=Enum.TextXAlignment.Right;return l end

-- The card over the row: what Power is, the gear adding up, the bonus and each map's Power.
function M.card(row,info,onClose)
 local p=info.parts
 local card=T.make('TextButton',row,{Name='PowerCard',Text='',AutoButtonColor=false,BackgroundTransparency=1,
  Position=UDim2.fromOffset(M.WIDTH-M.CARD_W,-M.CARD_H-14),Size=UDim2.fromOffset(M.CARD_W,M.CARD_H)})
 card.Activated:Connect(onClose)
 T.panel(card,'Panel',0,0,M.CARD_W,M.CARD_H,'panel')
 left(T.label(card,'Title','WHAT IS POWER?',26,20,468,34,26,C.lime))
 T.text(card,'Body',"Your gear's levels added up. Better gear = more Power = more damage and health in runs.",26,58,468,44,17)
 local rows={
  {info.weaponIcon,info.weaponName,'Tier '..T.Roman[math.clamp(p.weapon,1,4)],p.weapon},
  {ARMOR_ICON,'Armor you wear','tiers added',p.armor},
  {PET_ICON,'Pet',p.pet>0 and ('Tier '..T.Roman[math.clamp(p.pet,1,4)]) or 'none',p.pet},
 }
 for i,r in rows do
  local y=110+(i-1)*40
  T.icon(card,'Icon'..i,26,y,34,r[1])
  left(T.label(card,'Name'..i,r[2],70,y+2,220,30,19))
  T.text(card,'Sub'..i,r[3],300,y+6,110,24,15,C.muted)
  right(T.label(card,'Add'..i,'+'..r[4],410,y+2,84,30,20,C.lime))
 end
 local line=T.make('Frame',card,{Name='Rule',Position=UDim2.fromOffset(26,234),Size=UDim2.fromOffset(468,3),BackgroundColor3=C.lime,BackgroundTransparency=.5,BorderSizePixel=0})
 T.make('UICorner',line,{CornerRadius=UDim.new(1,0)})
 left(T.label(card,'Total','= POWER '..p.total,26,244,200,34,26))
 right(T.label(card,'Bonus',string.format('+%d%% damage  ·  +%d%% health',math.round((Stats.powerDamage(p.total)-1)*100),math.round((Stats.powerHealth(p.total)-1)*100)),226,248,268,28,17,C.gold))
 local maps={};for _,m in info.maps or {} do table.insert(maps,m.name..' '..m.power) end
 T.text(card,'Maps','Maps want: '..table.concat(maps,'  ·  '),26,286,468,40,15,C.cream)
 return card
end

-- cx: the row's centre x in `parent`; y: its top; w: its drawn width (it scales down to fit).
-- info: damage, health, weaponIcon, weaponName, parts {weapon, armor, pet, total}, maps.
function M.draw(parent,cx,y,w,info)
 local row=T.frame(parent,'StatPlate',cx-w/2,y,M.WIDTH,M.HEIGHT)
 T.make('UIScale',row,{Scale=w/M.WIDTH})
 local a=T.panel(row,'Damage',0,0,200,M.HEIGHT,'panel')
 T.icon(a,'Icon',10,9,52,info.weaponIcon)
 left(T.label(a,'Label','DAMAGE',72,8,118,20,15,C.muted))
 left(T.label(a,'Value',tostring(info.damage),72,26,118,36,30))
 local h=T.panel(row,'Health',212,0,200,M.HEIGHT,'panel')
 T.icon(h,'Icon',12,11,48,'heart')
 left(T.label(h,'Label','HEALTH',72,8,118,20,15,C.muted))
 left(T.label(h,'Value',tostring(info.health),72,26,118,36,30))
 local g=T.button(row,'Power','',424,0,200,M.HEIGHT,nil,false)
 g.Caption.Visible=false
 local tx=M.PowerIcon~='' and 72 or 20
 if M.PowerIcon~='' then T.icon(g,'Icon',10,9,52,M.PowerIcon) end
 left(T.label(g,'Label','POWER',tx,8,74,20,16))
 left(T.label(g,'Value',tostring(info.parts.total),tx,26,74,36,32))
 local q=T.make('Frame',g,{Name='Help',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(168,35),Size=UDim2.fromOffset(40,40),BackgroundColor3=C.well,BorderSizePixel=0})
 T.make('UICorner',q,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',q,{Color=C.ink,Thickness=3})
 T.label(q,'Mark','?',0,0,40,40,26,C.lime).Size=UDim2.fromScale(1,1)
 local card
 local function close() if card then card:Destroy();card=nil end end
 g.Activated:Connect(function() if card then close() else card=M.card(row,info,close) end end)
 return row,function() if not card then card=M.card(row,info,close) end;return card end
end
return M
