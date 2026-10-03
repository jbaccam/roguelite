-- Full-screen chest screen (lobby), green theme (UITheme) over the 3D chest island (ChestStage).
-- Browse: the chest list on the left (owned count, price, what's inside by rarity, [i] for every
-- weapon's odds), and over the chosen chest its title with BUY / OPEN / amount (×1, ×10, ×100).
-- In the odds (rarest first) every item can be tapped for its card (ItemCardUI, 2026-10-02).
-- Opening: the camera pushes in, the player taps three times: two shakes that charge the aura,
-- then the lid bursts open and the weapons fly out onto cards. ×10 and ×100 open in one go with a
-- bigger burst and more items flying out, not one animation per chest.
-- Presentation and requests only: ProfileAction('BuyChest'|'OpenChest', kind, amount) is
-- validated and rolled by ProfileService with ChestConfig.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local Input=game:GetService('UserInputService')
local TweenService=game:GetService('TweenService')
local TextService=game:GetService('TextService')
local RunService=game:GetService('RunService')
local GuiService=game:GetService('GuiService')
local T=require(RS:WaitForChild('UITheme'))
local StoreFX=require(RS:WaitForChild('StoreFX'))
local Stage=require(RS:WaitForChild('ChestStage'))
local FX=require(RS:WaitForChild('ChestFX'))
local combat=RS:WaitForChild('RogueliteCombat')
local Chests=require(combat:WaitForChild('ChestConfig'))
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
-- Tapping an item in the odds opens its card (ItemCardUI); it also owns the one chance formatter.
local Card=require(RS:WaitForChild('ItemCardUI'))
local Armor=require(combat:WaitForChild('ArmorCatalog'))
local Pets=require(combat:WaitForChild('PetConfig'))
local Money=require(combat:WaitForChild('MonetizationConfig'))
local C=T.Color
-- Chests drop weapons and armor pieces ('Iron.Helmet'); both get an icon and a name here.
local function itemIcon(id) return WeaponIcons[id] or Armor.Icons[id] or Pets.Icons[id] end
local function itemName(id) local w=Weapons.ById[id];local p=Pets.ById[id];return w and w.name or p and p.name or Armor.pieceName(id) end
local U={}

-- Laid out on a canvas in design pixels (T.canvas, like the Armory): 1920x1080 on most screens,
-- a smaller canvas on phones (844x390 -> 1500x738) where the list and the odds scroll. See plan().
local LIST_X,LIST_W=40,610
local ROW_H,RAR_H=104,36
local WHITE=Color3.new(1,1,1)
local RANK={Common=1,Rare=2,Epic=3,Legendary=4,Godly=5}

local function tween(obj,time,props,style,dir,delay)
 local tw=TweenService:Create(obj,TweenInfo.new(time,style or Enum.EasingStyle.Quad,dir or Enum.EasingDirection.Out,0,false,delay or 0),props)
 tw:Play();return tw
end
local function fmt(n)
 n=math.floor(tonumber(n) or 0)
 local s=tostring(n):reverse():gsub('(%d%d%d)','%1,'):reverse()
 return (s:gsub('^,',''))
end
local function short(n) n=tonumber(n) or 0;if n>=1e4 then return string.format('%.1fK',n/1e3) end;return fmt(n) end
local function textWidth(text,size) return TextService:GetTextSize(text,size,T.Font,Vector2.new(4000,200)).X end
local function centred(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
local function left(l) l.TextXAlignment=Enum.TextXAlignment.Left;return l end
local function right(l) l.TextXAlignment=Enum.TextXAlignment.Right;return l end
local function corners(obj,color)
 T.setTier(obj,2)
 local c=obj:FindFirstChild('RarityCorners');if c then c.ImageColor3=color end
 return obj
end
-- Saturated colour wash inside a panel (left to right), like the store's offer cards.
local function wash(parent,color,strength,z)
 local f=T.make('Frame',parent,{Name='Wash',BackgroundColor3=color,BackgroundTransparency=1-(strength or .55),BorderSizePixel=0,Position=UDim2.fromOffset(8,8),Size=UDim2.new(1,-16,1,-16),ZIndex=z or parent.ZIndex})
 T.make('UICorner',f,{CornerRadius=UDim.new(0,10)})
 T.make('UIGradient',f,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,0),NumberSequenceKeypoint.new(.65,.55),NumberSequenceKeypoint.new(1,1)})})
 return f
end
local function plate(parent,text,x,y,size)
 size=size or 44
 local w=textWidth(text,size)+100
 local p=T.panel(parent,'TitlePlate',x,y,w,70,'panel')
 T.caps(p,48)
 local l=T.label(p,'Title',text,0,0,0,0,size);l.Size=UDim2.fromScale(1,1)
 return p,w
end
-- Amount + icon centred in a parent.
local function costRow(parent,amount,icon,size,color)
 local g=T.make('Frame',parent,{Name='Cost',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),AutomaticSize=Enum.AutomaticSize.X,Size=UDim2.fromOffset(0,size+8),ZIndex=parent.ZIndex+1})
 T.make('UIListLayout',g,{FillDirection=Enum.FillDirection.Horizontal,VerticalAlignment=Enum.VerticalAlignment.Center,HorizontalAlignment=Enum.HorizontalAlignment.Center,Padding=UDim.new(0,6),SortOrder=Enum.SortOrder.LayoutOrder})
 if icon then local i=T.icon(g,'Icon',0,0,size+6,icon);i.LayoutOrder=1;i.ZIndex=g.ZIndex end
 local l=T.label(g,'Amount',tostring(amount),0,0,textWidth(tostring(amount),size)+6,size+8,size,color);l.LayoutOrder=2;l.TextWrapped=false;l.ZIndex=g.ZIndex
 return g
end

-- opts: profile() -> LobbyUI profile, onVisible(bool) hides the lobby HUD, openWindow(name,arg),
-- need(rec) -> copies for the next tier, selection (shared table; .chest remembers the tier).
function U.new(player,opts)
 local self={}
 local request=opts.request or function(...) return combat:WaitForChild('ProfileAction'):InvokeServer(...) end
 -- Full screen minus phone notches and rounded corners; shades and flashes may reach under them.
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='ChestScreen',ResetOnSpawn=false,DisplayOrder=58,ScreenInsets=Enum.ScreenInsets.DeviceSafeInsets,ClipToDeviceSafeArea=false,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,Enabled=false})
 self.Screen=screen
 local root,canvas
 -- browse: the browse view's top-level pieces (direct children of the canvas, one per group).
 local browse,listFrame,header,actions,oddsOverlay,gemValue
 local oddsBack -- set when the store's SEE ODDS opened this screen: closing the odds goes back there
 -- The item card over the odds (ItemCardUI handle), the odds cells by item id and the odds in display order.
 local itemCard,oddsCells,oddsList
 local openLayer,resultLayer
 local conns={}
 local profile
 local selected=Chests.ById[opts.selection and opts.selection.chest or ''] and opts.selection.chest or 'Wooden'
 local amount=1
 local mode='closed' -- closed | browse | opening | results
 local busy=false

 local function readProfile() profile=opts.profile();return profile end
 local function owned(id) return profile.chests[id] or 0 end
 local function toast(text,ok) T.toast(screen,text,ok and C.lime or C.negative) end

 -- Lobby labels over the chests stay in sync even while the screen is closed.
 local function syncLabels() if Stage.Prepare() then Stage.SetCounts(opts.profile().chests) end end
 Stage.Watch(syncLabels)
 for _,a in {'ProfileChests','ProfileLoaded'} do player:GetAttributeChangedSignal(a):Connect(syncLabels) end

 -- Layout ----------------------------------------------------------------------------------------
 -- L: where the pieces go on the current canvas (canvas px), recomputed when the screen resizes.
 -- The chest is drawn by the 3D camera (ChestStage 'select' shot, 50° tall view): it shows about
 -- 0.375 x canvas height right of centre, 0.38 H wide, from 0.31 H to 0.72 H down. The title and
 -- buttons stay above or under that box. Example 1920x1080: chest x 1160-1570, y 335-778, title and
 -- buttons above it (y 56-322). 844x390 phone (canvas 1500x738): chest y 229-531, the title stays on
 -- top and the buttons go under the chest (y 590-714).
 local L
 local function plan(c)
  local l={s=c.s,w=c.w,h=c.h,top=c.top}
  l.tap=math.ceil(44/c.s) -- a comfortable tap (44 screen px) in canvas px: 88 on phones
  l.plateY=math.max(56,c.top+8) -- the plate sits in the top-left corner, under Roblox's buttons
  l.listY=l.plateY+94
  l.exitH=math.max(76,l.tap)
  l.exitY=c.h-28-l.exitH
  l.listH=l.exitY-16-l.listY
  l.info=42*c.s>=36 -- the small [i] on each row only where it is big enough to tap
  local x0=LIST_X+LIST_W+24
  local chestX=c.w/2+c.h*.375
  -- Title a little right of the chest, clear of Roblox's top-right buttons when the top bar
  -- reaches down into it (laptops, tablets, phones).
  local right=c.w-(c.top>64 and 120/c.s or 20)
  l.tw=math.min(860,right-x0)
  l.tx=math.clamp(chestX+100-l.tw/2,x0,right-l.tw)
  -- Buttons (124 tall with the hints under them): under the title when both fit above the chest,
  -- else under the chest.
  l.stacked=56+142+124<=c.h*.31
  l.aw=math.min(802,l.stacked and l.tw or c.w-20-x0)
  l.bw=math.min(300,(l.aw-170-32)/2)
  local ac=l.stacked and l.tx+l.tw/2 or math.clamp(chestX,x0+l.aw/2,c.w-20-l.aw/2)
  l.ax=ac-l.aw/2
  l.ay=l.stacked and 56+142 or c.h-24-124
  return l
 end
 local function toCanvas(abs) return (abs-canvas.AbsolutePosition)/L.s end

 local drawBrowse -- forward
 -- Buying Quick Open (or VIP) unlocks ×10 / ×100 while the screen is open.
 for _,a in {'ProfileQuickOpen','ProfileVIP'} do player:GetAttributeChangedSignal(a):Connect(function() if mode=='browse' then readProfile();drawBrowse() end end) end

 -- Browse ----------------------------------------------------------------------------------------
 local function rarityBars(parent,id,y)
  local rows=Chests.summary(id)
  for i,row in rows do
   local color=Chests.RarityColor[row.rarity]
   local bar=T.make('Frame',parent,{Name='Rarity_'..row.rarity,Position=UDim2.fromOffset(14,y+(i-1)*(RAR_H+6)),Size=UDim2.fromOffset(LIST_W-28,RAR_H),BackgroundColor3=color,BackgroundTransparency=.45,BorderSizePixel=0})
   T.make('UICorner',bar,{CornerRadius=UDim.new(0,6)})
   T.make('UIStroke',bar,{Color=color:Lerp(Color3.new(0,0,0),.55),Thickness=2})
   T.make('UIGradient',bar,{Color=ColorSequence.new(WHITE,Color3.fromRGB(150,150,150)),Rotation=0})
   left(T.label(bar,'Name',row.rarity,16,0,300,RAR_H,24,WHITE))
   right(T.label(bar,'Amount',row.text,LIST_W-28-316,0,300,RAR_H,24,WHITE))
  end
  return y+#rows*(RAR_H+6)
 end

 -- Pity reminders under the selected chest (the Godly line only once Godly weapons exist).
 local function pityLines(def)
  local out={}
  if not def.pity then return out end
  local function line(rarity,limit)
   local n=math.max(1,limit-(profile.pity[rarity] or 0))
   table.insert(out,rarity..' guaranteed within <b>'..n..'</b> chest'..(n>1 and 's' or ''))
  end
  -- A chest that always holds a Legendary already says so; a pity line for it would only confuse.
  if def.legendary<1 then line('Legendary',Chests.LegendaryPity) end
  if Chests.godlyEnabled() and (def.godly or 0)>0 then line('Godly',Chests.GodlyPity) end
  return out
 end

 -- The item card closes first (B / Esc / X / BACK / a tap outside); the controller goes back to
 -- the cell of the item it showed last. silent: closed because the odds are redrawn or closing.
 local function closeItem(silent) if itemCard then itemCard.Close(silent) end;itemCard=nil end
 local function openItem(id)
  if not (oddsOverlay and oddsList) then return end
  if itemCard then itemCard.Close(true) end
  itemCard=Card.open(canvas,L,{list=oddsList,id=id,source='chest',kind=oddsOverlay:GetAttribute('Chest'),profile=readProfile,zindex=50,
   onClose=function(lastId,silent)
    itemCard=nil
    if not silent and oddsCells and oddsCells[lastId] then Card.reselect(oddsCells[lastId]) end
   end})
 end
 local function closeOdds()
  closeItem(true)
  if oddsOverlay then oddsOverlay:Destroy();oddsOverlay=nil end
  oddsCells,oddsList=nil,nil
  if oddsBack then local back=oddsBack;oddsBack=nil;back();return end
  if actions then T.gamepadSelect(actions) end
 end
 local function openOdds(id)
  if oddsOverlay then oddsOverlay:Destroy() end
  local def=Chests.ById[id]
  local back=T.make('TextButton',canvas,{Name='Odds',Text='',AutoButtonColor=false,Selectable=false,BackgroundColor3=C.shade,BackgroundTransparency=.4,Position=UDim2.fromOffset(-1000,-400),Size=UDim2.fromOffset(L.w+2000,L.h+800),ZIndex=40})
  back:SetAttribute('AuditIgnore',true);back:SetAttribute('Chest',id) -- modal shade; Chest: redrawn on resize
  oddsOverlay=back
  back.Activated:Connect(closeOdds)
  -- One section per rarity that has items (Godly appears once Godly items exist). Each wraps into
  -- rows of cells and the sections scroll inside the panel when taller than the screen.
  -- Example: 1340 wide panel = 12 cells a row, so Rare's 20 items take two rows.
  -- Every chest with a Godly chance lists all six Godly weapons by name and icon (user, 2026-10-01).
  local odds=Chests.odds(id)
  -- Show each Godly weapon with its own icon and catalog-provided chance.
  local byR={};for _,o in odds do byR[o.rarity]=byR[o.rarity] or {};table.insert(byR[o.rarity],o) end
  -- Rarest first (user, 2026-10-02): the Godly and Legendary items are on screen without scrolling.
  local shown={};for _,r in Card.rarestFirst(Chests.Rarities) do if byR[r] then table.insert(shown,r) end end
  -- Every item can be tapped for its card; < > on the card walk this same order.
  oddsList={};oddsCells={}
  for _,r in shown do for _,o in byR[r] do table.insert(oddsList,o) end end
  local cell,gap=96,8
  local W=math.min(1340,L.w-80)
  local perRow=math.max(1,math.floor((W-72+gap)/(cell+gap)))
  local contentH=0
  for _,r in shown do contentH+=40+math.ceil(#byR[r]/perRow)*(cell+gap) end
  -- The title plate and close button poke 34 px above the panel: keep them under Roblox's top bar.
  local top=math.max(L.top+40,60)
  local H=math.min(94+contentH+12,L.h-24-top)
  local py=math.max(top,(L.h-H)/2+17)
  local p=T.panel(back,'Panel',1000+(L.w-W)/2,400+py,W,H,'panel');p.ZIndex=41;p.Active=true;corners(p,def.aura)
  -- A controller stays inside the odds while they are open.
  p.SelectionGroup=true
  p.SelectionBehaviorUp=Enum.SelectionBehavior.Stop;p.SelectionBehaviorDown=Enum.SelectionBehavior.Stop
  p.SelectionBehaviorLeft=Enum.SelectionBehavior.Stop;p.SelectionBehaviorRight=Enum.SelectionBehavior.Stop
  local pl=plate(p,def.name..'  ·  Odds',28,-34,34);pl.ZIndex=42;for _,d in pl:GetDescendants() do if d:IsA('GuiObject') then d.ZIndex=43 end end
  pl.Title.Position=UDim2.fromOffset(30,0);pl.Title.Size=UDim2.new(1,-60,1,0) -- between the stone caps, on small screens too
  local x0=36
  -- Help line: "Tap / Click any item…"; with a controller, the selected item and A Details · B Back.
  local help=left(T.text(p,'Help','',x0,54,W-72,26,20,C.muted));help.ZIndex=42
  local hint=T.frame(p,'PadHint',W-36-330,50,330,34);hint.ZIndex=42
  for i,k in {{Enum.KeyCode.ButtonA,'Details'},{Enum.KeyCode.ButtonB,'Back'}} do
   local gx=(i-1)*165
   local g=T.icon(hint,'Glyph'..i,gx,0,34,Card.keyImage(k[1]));g.ZIndex=43
   left(T.label(hint,'Say'..i,k[2],gx+40,0,120,34,22,WHITE)).ZIndex=43
  end
  local chosen
  local function setHelp()
   local input=Card.input()
   hint.Visible=input=='pad'
   help.Size=UDim2.fromOffset(W-72-(input=='pad' and 340 or 0),26)
   if input=='pad' and chosen then
    local col=Chests.RarityColor[chosen.rarity] or WHITE
    help.Text='<font color="'..T.hex(col:Lerp(WHITE,.3))..'">'..itemName(chosen.id)..'</font>   ·   '..string.upper(chosen.rarity)..'   ·   '..Card.percent(chosen.chance)
    help.TextColor3=WHITE
   else
    help.Text=(input=='touch' and 'Tap' or input=='pad' and 'Pick' or 'Click')..' any item to see its stats.  Chance that one '..def.name..' includes it · '..def.copies..' items per chest.'
    help.TextColor3=C.muted
   end
  end
  local inputConn=Input.LastInputTypeChanged:Connect(function() if back.Parent then setHelp() end end)
  back.Destroying:Connect(function() inputConn:Disconnect() end)
  local body=T.scroll(p,'Rows',8,94,W-16,H-94-12);body.ZIndex=42;body.CanvasSize=UDim2.fromOffset(0,contentH)
  x0-=8
  local y=0
  for _,r in shown do
   local list=byR[r]
   local col=Chests.RarityColor[r]
   left(T.label(body,'H_'..r,string.upper(r),x0,y,300,30,26,col)).ZIndex=42
   y+=34
   for i,o in list do
    local x=x0+((i-1)%perRow)*(cell+gap)
    oddsCells[o.id]=Card.cell(body,{name='W_'..o.id,x=x,y=y+(i-1)//perRow*(cell+gap),size=cell,color=col,icon=itemIcon(o.id),iconSize=cell-16,iconY=4,
     chance=Card.percent(o.chance),chanceY=cell-30,chanceSize=22,z=42,
     onOpen=function() openItem(o.id) end,onSelect=function() chosen=o;setHelp() end})
   end
   y+=math.ceil(#list/perRow)*(cell+gap)+6
  end
  setHelp()
  local cs=math.max(62,L.tap)
  local close=T.button(p,'Close','X',W-cs-8,-26,cs,cs,closeOdds,true);T.setTier(close,4);close.Caption.TextColor3=C.negative;close.Caption.TextSize=34;close.ZIndex=44;close.Caption.ZIndex=45
  if close:FindFirstChild('RarityCorners') then close.RarityCorners.ZIndex=45 end
  close.SelectionOrder=99 -- a controller lands on the first item, not the X
  Card.settle(p,L.s) -- text shrinks to its box on phones instead of spilling out
  T.gamepadSelect(body)
 end

 local function drawList()
  local keep=listFrame and listFrame.CanvasPosition.Y
  if listFrame then listFrame:Destroy() end
  -- Scrolls when the rows don't fit between the title and EXIT (phones, a tall selected row).
  -- 8 px left / 14 px top padding: the chest icons poke out of their rows.
  listFrame=T.scroll(canvas,'List',LIST_X-8,L.listY-14,LIST_W+20,L.listH+14)
  local oddsH=math.max(52,L.tap)
  local y,selTop,selBottom=14,0,0
  for _,id in Chests.Order do
   local def=Chests.ById[id];local sel=id==selected
   local pity=pityLines(def)
   local rowH=ROW_H+(sel and (#Chests.summary(id)*(RAR_H+6)+10+math.max(#pity*34,oddsH+8)) or 0)
   -- Tapping the chosen row again opens its odds (a big target on touch screens).
   local row=T.button(listFrame,'Row_'..id,'',8,y,LIST_W,rowH,function()
    if selected~=id then selected=id;if opts.selection then opts.selection.chest=id end;Stage.Select(id);FX.play(FX.Sounds.Chime,.18,1.4);drawBrowse()
    else openOdds(id) end
   end,true)
   row.Caption.Visible=false;corners(row,def.aura)
   wash(row,def.aura,sel and .75 or .4,row.ZIndex)
   local icon=T.icon(row,'Icon',-6,-12,124,def.icon);icon.ZIndex=row.ZIndex+2
   local n=owned(id)
   -- Stops 8 px before the price chip; long names ("Legendary Chest  (12)") shrink to fit.
   local name=left(T.label(row,'Name',def.name..(n>0 and '  <font color="#91EF14">('..n..')</font>' or ''),128,10,LIST_W-308,48,36));name.RichText=true;name.TextWrapped=false;name.ZIndex=row.ZIndex+2
   local sub=left(T.text(row,'Sub',def.copies..' items  ·  '..(def.legendary>=1 and 'Legendary guaranteed' or ('Legendary '..Card.percent(def.legendary*100))),130,56,LIST_W-230,26,20,C.cream));sub.ZIndex=row.ZIndex+2
   -- Price chip (top right).
   local chip=T.panel(row,'Price',LIST_W-172,14,154,48,'inset');chip.ZIndex=row.ZIndex+2
   if def.daily then
    local ready=profile.freeChestDay~=Money.day()
    local l=centred(T.label(chip,'Free',ready and 'FREE' or 'CLAIMED',0,0,154,48,ready and 26 or 20,ready and C.lime or C.muted));l.ZIndex=chip.ZIndex+1
   elseif def.emeralds then costRow(chip,short(def.emeralds),'emerald',24,C.emerald)
   else local l=centred(T.label(chip,'Robux','ROBUX',0,0,154,48,22,C.gold));l.ZIndex=chip.ZIndex+1 end
   for _,d in chip:GetDescendants() do if d:IsA('GuiObject') then d.ZIndex=chip.ZIndex+1 end end
   if L.info and not sel then
    local info=T.button(row,'Info','i',LIST_W-66,ROW_H-52,48,42,function() openOdds(id) end,true);info.Caption.TextSize=26;info.ZIndex=row.ZIndex+3;info.Caption.ZIndex=row.ZIndex+4
   end
   if sel then
    local yy=rarityBars(row,id,ROW_H)
    for _,d in row:GetChildren() do if d.Name:find('^Rarity_') then d.ZIndex=row.ZIndex+2;for _,e in d:GetDescendants() do if e:IsA('GuiObject') then e.ZIndex=row.ZIndex+3 end end end end
    for i,text in pity do
     local p=left(T.text(row,i==1 and 'Pity' or 'Pity'..i,text,18,yy+2+(i-1)*34,LIST_W-36-170,30,20,C.limeSoft));p.ZIndex=row.ZIndex+2
    end
    -- Every item's odds (on phones the only way in besides tapping the row again).
    local odds=T.button(row,'Odds','ODDS',LIST_W-164,yy+4,150,oddsH,function() openOdds(id) end,true)
    odds.Caption.TextSize=26;odds.ZIndex=row.ZIndex+3;odds.Caption.ZIndex=row.ZIndex+4
    selTop,selBottom=y,y+rowH
   end
   y+=rowH+10
  end
  listFrame.CanvasSize=UDim2.fromOffset(0,y)
  -- Keep the scroll position across redraws, but always bring the chosen row into view.
  local at,view=keep or 0,L.listH+14
  if selBottom-at>view then at=selBottom-view end
  if selTop-14<at then at=selTop-14 end
  listFrame.CanvasPosition=Vector2.new(0,math.max(0,at))
 end

 local function drawHeader()
  if header then header:Destroy() end
  if actions then actions:Destroy() end
  local def=Chests.ById[selected];local n=owned(selected)
  local tw=L.tw
  header=T.frame(canvas,'Header',L.tx,56,tw,132)
  local title=centred(T.label(header,'Title',def.name,0,0,tw,86,78,WHITE));title.TextWrapped=false
  T.make('UIGradient',title,{Color=ColorSequence.new(WHITE,def.aura:Lerp(WHITE,.35)),Rotation=90})
  local line=T.make('Frame',header,{Name='Underline',BackgroundColor3=WHITE,BorderSizePixel=0,AnchorPoint=Vector2.new(.5,0),Position=UDim2.fromOffset(tw/2,90),Size=UDim2.fromOffset(math.min(640,tw-40),4)})
  T.make('UIGradient',line,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.5,0),NumberSequenceKeypoint.new(1,1)})})
  centred(T.text(header,'Owned',n>0 and ('You have <b>'..n..'</b>  ·  '..def.copies..' items each') or ('None yet  ·  '..def.copies..' items each'),0,100,tw,32,26,n>0 and C.limeSoft or C.cream))
  -- Actions: BUY (price × amount) · OPEN (owned, up to amount) · amount. Under the title, or
  -- under the chest on short screens (plan()).
  local bw,bh,gap=L.bw,92,16
  actions=T.frame(canvas,'Actions',L.ax,L.ay,L.aw,124)
  local x0=(L.aw-(bw*2+170+gap*2))/2
  -- One at a time without Quick Open (VIP includes it); the server refuses more too.
  local quick=profile.quickOpen==true
  if not quick then amount=1 end
  local price=def.emeralds and def.emeralds*amount
  if def.daily then
   -- The free chest is one button: OPEN FREE CHEST claims today's chest and opens it straight away
   -- (or opens one already owned). On cooldown it shows a live countdown to 00:00 UTC instead.
   local ready=profile.freeChestDay~=Money.day()
   local can=ready or n>0
   local fw=bw*2+170+gap*2
   local free=T.button(actions,'OpenFree','',x0,0,fw,bh,function()
    if busy or not can then return end
    if owned(selected)<=0 then
     busy=true
     local r=request('BuyChest',selected,1)
     busy=false
     if not r.ok then toast(r.message or '',false);readProfile();drawBrowse();return end
     T.sound('ui_purchase');FX.play(FX.Sounds.Chime,.4,1.2)
     -- The claimed chest arrives as a profile attribute; wait for it (normally already there).
     for _=1,20 do readProfile();if owned(selected)>0 then break end;task.wait(.05) end
    end
    self.Begin(1)
   end,not can)
   free.Caption.Visible=false;free.Interactable=can
   if can then
    local l=centred(T.label(free,'Label','OPEN FREE CHEST',0,0,fw,bh,36,C.ink));l.TextStrokeTransparency=1
    StoreFX.pulse(free,.04)
   else
    local l=centred(T.label(free,'Label','NEXT FREE CHEST',0,8,fw,34,26,C.muted));l.TextStrokeTransparency=1
    local t=centred(T.label(free,'Timer','',0,44,fw,40,34,WHITE));t.TextStrokeTransparency=1
    task.spawn(function()
     while t.Parent do
      if profile.freeChestDay~=Money.day() then drawBrowse();return end
      local s=Money.secondsToReset()
      t.Text=string.format('%d:%02d:%02d',s//3600,(s%3600)//60,s%60)
      task.wait(1)
     end
    end)
   end
   free.SelectionOrder=1
   return
  end
  local buy=T.button(actions,'Buy','',x0,0,bw,bh,function()
   if busy then return end
   if not def.emeralds then self.Close();opts.openWindow('Store','Chests');return end
   busy=true
   local r=request('BuyChest',selected,def.daily and 1 or amount)
   busy=false
   if r.ok then T.sound('ui_purchase');FX.play(FX.Sounds.Chime,.4,1.2);local a=Stage.Aura(selected);if a then a:Pulse(.8) end end
   toast(r.message or '',r.ok)
   readProfile();drawBrowse()
  end)
  buy.Caption.Visible=false
  if def.emeralds then
   local l=centred(T.label(buy,'Label','BUY ×'..amount,0,8,bw,34,28,C.ink));l.TextStrokeTransparency=1
   local c=costRow(buy,fmt(price),'emerald',30,WHITE);c.Position=UDim2.new(.5,0,0,64)
  else
   local l=centred(T.label(buy,'Label','GET WITH ROBUX',0,0,bw,bh,28,C.ink));l.TextStrokeTransparency=1
  end
  local short_=def.emeralds and price-profile.gems
  if short_ and short_>0 then
   centred(T.text(actions,'Need','Need '..fmt(short_)..' more',x0,bh+6,bw,26,22,C.negative))
  end
  local n2=math.min(amount,n)
  local open=T.button(actions,'Open',n>0 and ('OPEN ×'..n2) or 'OPEN',x0+bw+gap,0,bw,bh,function() self.Begin() end,n<=0)
  open.Caption.TextSize=40;open.Interactable=n>0
  if n<=0 then centred(T.text(actions,'NoneOwned','Buy one first',x0+bw+gap,bh+6,bw,26,22,C.muted)) end
  if n>0 then StoreFX.pulse(open,.04) end
  local amt=T.button(actions,'Amount','×'..amount,x0+2*(bw+gap),0,170,bh,function()
   if not profile.quickOpen then combat.PurchaseRequest:FireServer('QuickOpen');return end
   amount=amount==1 and 10 or amount==10 and 100 or 1;FX.play(FX.Sounds.Chime,.15,1.6);drawBrowse()
  end,true)
  corners(amt,T.Tier[2]);amt.Caption.TextSize=42;amt.Caption.TextColor3=Color3.fromRGB(150,215,255)
  centred(T.text(actions,'AmountHelp',quick and 'amount' or 'Quick Open: ×10',x0+2*(bw+gap),bh+6,170,26,20,quick and C.muted or C.limeSoft))
  -- Gamepad: OPEN is the first pick once there is a chest to open, else BUY.
  open.SelectionOrder=n>0 and 1 or 2;buy.SelectionOrder=n>0 and 2 or 1;amt.SelectionOrder=3
 end

 drawBrowse=function()
  if mode~='browse' or not browse then return end
  local path=T.selectionPath(canvas)
  readProfile()
  drawList();drawHeader()
  T.restoreSelection(canvas,path)
 end

 -- Every piece of the browse view (the list, title and buttons are redrawn on their own).
 local function browsePieces()
  local t=table.clone(browse or {})
  for _,o in {listFrame or false,header or false,actions or false} do if o then table.insert(t,o) end end
  return t
 end
 local function clearBrowse()
  for _,o in browsePieces() do o:Destroy() end
  browse,listFrame,header,actions,gemValue=nil,nil,nil,nil,nil
 end
 local function buildBrowse(animate)
  clearBrowse()
  browse={}
  local function add(o) table.insert(browse,o);return o end
  -- Readability wash behind the list.
  -- Starts 1000 px left of the canvas so it reaches under notches and screen edges.
  local shade=add(T.make('Frame',canvas,{Name='ListShade',BackgroundColor3=C.shade,BorderSizePixel=0,Position=UDim2.fromOffset(-1000,-200),Size=UDim2.fromOffset(1760,L.h+400),BackgroundTransparency=.2,ZIndex=0}))
  shade:SetAttribute('AuditIgnore',true)
  T.make('UIGradient',shade,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.15),NumberSequenceKeypoint.new(.57,.15),NumberSequenceKeypoint.new(.89,.6),NumberSequenceKeypoint.new(1,1)})})
  local pl,pw=plate(canvas,'Chests',LIST_X+10,L.plateY,50);add(pl)
  -- Emeralds beside the title, with + to the store (the top centre stays free for the chest title).
  local ps=math.max(56,L.tap)
  -- A phone-size + (88) reaches 11 above the pill: still under the top bar (plateY = top+8), above the list.
  local gem=add(T.frame(canvas,'Emeralds',LIST_X+10+pw+14,L.plateY+3,240+8+ps,math.max(64,ps-11)))
  local pill=T.panel(gem,'Pill',0,0,240,64,'inset')
  T.icon(pill,'Icon',10,6,52,'emerald')
  gemValue=left(T.label(pill,'Value',fmt(profile.gems),70,6,160,52,34,C.emerald));gemValue.TextWrapped=false -- 7+ digits shrink on one line
  local plus=T.button(gem,'Plus','+',248,math.max(-11,(64-ps)/2),ps,ps,function() self.Close();opts.openWindow('Store','Emeralds') end);plus.Caption.TextSize=36
  -- Exit (bottom left); the list ends above it.
  -- EXIT sits centred under the list; in Studio it moves left to make room for +200 EMERALDS.
  local exitX=RunService:IsStudio() and LIST_X or LIST_X+(LIST_W-240)/2
  local exit=add(T.button(canvas,'Exit','EXIT',exitX,L.exitY,240,L.exitH,function() self.Close() end,true))
  T.setTier(exit,4);exit.Caption.TextSize=38;exit.Caption.TextColor3=C.negative
  if RunService:IsStudio() then
   local dev=add(T.button(canvas,'DevEmeralds','+200 EMERALDS (STUDIO)',LIST_X+256,L.exitY,290,L.exitH,function() local r=request('DevEmeralds');toast(r.message or '',r.ok);readProfile();drawBrowse() end,true))
   dev.Caption.TextSize=20
  end
  drawList();drawHeader()
  if not animate then return end
  -- Slide in while the camera flies over.
  for _,o in {listFrame,pl,gem} do local p=o.Position;o.Position=p-UDim2.fromOffset(720,0);tween(o,.55,{Position=p},Enum.EasingStyle.Back,Enum.EasingDirection.Out,.35) end
  for _,o in {header,actions} do
   local dy=o==actions and not L.stacked and 300 or -380
   local p=o.Position;o.Position=p+UDim2.fromOffset(0,dy);tween(o,.55,{Position=p},Enum.EasingStyle.Back,Enum.EasingDirection.Out,.55)
  end
  T.gamepadSelect(actions)
 end

 -- Opening -------------------------------------------------------------------------------------
 local opening -- {id, n, results, stage, best}
 local prompt
 local function bestColor(results)
  local best=1
  for _,r in results do best=math.max(best,RANK[r.rarity] or 1) end
  return best>=3 and Chests.RarityColor[Chests.Rarities[best]] or nil,best
 end
 local function flash(color,strength)
  -- Whole screen (root), reaching under notches and the top bar.
  local f=T.make('Frame',root,{Name='Flash',BackgroundColor3=color or WHITE,BackgroundTransparency=1-(strength or .8),BorderSizePixel=0,Size=UDim2.new(1,200,1,200),Position=UDim2.fromOffset(-100,-100),ZIndex=60})
  f:SetAttribute('AuditIgnore',true)
  tween(f,.6,{BackgroundTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.Out).Completed:Connect(function() f:Destroy() end)
 end

 local showResults -- forward
 local function drawPrompt()
  if prompt then prompt:Destroy() end
  prompt=T.frame(openLayer,'Prompt',L.w/2-400,L.h-215,800,200)
  local def=Chests.ById[opening.id]
  local t=centred(T.label(prompt,'Tap',opening.stage==0 and 'TAP TO OPEN!' or opening.stage==1 and 'TAP AGAIN!' or 'ONE MORE!',0,0,800,90,76,WHITE))
  T.make('UIGradient',t,{Color=ColorSequence.new(WHITE,def.aura:Lerp(WHITE,.3)),Rotation=90})
  local s=T.make('UIScale',t,{Scale=1})
  TweenService:Create(s,TweenInfo.new(.45,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true),{Scale=1.08}):Play()
  for i=1,3 do
   local on=i<=opening.stage
   local pip=T.make('Frame',prompt,{Name='Pip'..i,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(400+(i-2)*64,124),Size=UDim2.fromOffset(on and 34 or 26,on and 34 or 26),BackgroundColor3=on and def.aura:Lerp(WHITE,.3) or C.track,BorderSizePixel=0,Rotation=45})
   T.make('UICorner',pip,{CornerRadius=UDim.new(0,6)});T.make('UIStroke',pip,{Color=Color3.fromRGB(8,10,11),Thickness=3})
  end
  if opening.n>1 then
   local many=centred(T.label(prompt,'Many','OPENING ×'..opening.n..' '..string.upper(def.name)..'S',0,152,800,40,30,def.aura:Lerp(WHITE,.35)))
   many.TextStrokeTransparency=0
  end
 end
 local function advance()
  if mode~='opening' or not opening or opening.bursting then return end
  opening.stage+=1
  if opening.stage<3 then
   Stage.Charge(opening.id,opening.stage,opening.best)
   flash(Chests.ById[opening.id].aura,.18*opening.stage)
   drawPrompt()
  else
   opening.bursting=true
   if prompt then prompt:Destroy();prompt=nil end
   local scale=opening.n>=100 and 5 or opening.n>=10 and 2 or 1
   Stage.Burst(opening.id,scale,opening.best)
   flash(opening.best or WHITE,.85)
   task.delay(.35,function() if mode=='opening' then showResults() end end)
  end
 end

 function self.Begin(n)
  if mode~='browse' and mode~='results' or busy then return end
  readProfile()
  -- The server opens min(amount, owned); ask for the chosen amount and show what it opened.
  local want=Chests.validAmount(n) and n or amount
  if not profile.quickOpen then want=1 end
  n=math.min(want,owned(selected))
  if n<=0 then return end
  busy=true
  local r=request('OpenChest',selected,want)
  busy=false
  if not r.ok then toast(r.message or 'Could not open',false);return end
  local results=r.results or {}
  local total=0;for _,x in results do total+=x.count or 1 end
  local best=bestColor(results)
  opening={id=selected,n=n,results=results,total=total,stage=0,best=best}
  -- Browse slides away, the camera pushes in on the chest.
  if resultLayer then resultLayer:Destroy();resultLayer=nil end
  closeItem(true)
  if oddsOverlay then oddsOverlay:Destroy();oddsOverlay=nil;oddsCells,oddsList=nil,nil end
  if browse then
   -- Left column slides left, the title up, buttons under the chest down.
   local pieces=browsePieces();browse,listFrame,header,actions,gemValue=nil,nil,nil,nil,nil
   for _,c in pieces do
    local p=c.Position;local dx=p.X.Offset<L.w/2 and -800 or 0;local dy=dx~=0 and 0 or p.Y.Offset>L.h/2 and 420 or -420
    tween(c,.3,{Position=p+UDim2.fromOffset(dx,dy)},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
   end
   task.delay(.32,function() for _,c in pieces do c:Destroy() end end)
  end
  mode='opening'
  Stage.Settle(selected);Stage.Focus(selected)
  -- Not Selectable: a controller taps with A (InputBegan); selecting it too would double-advance.
  openLayer=T.make('TextButton',canvas,{Name='Opening',Text='',AutoButtonColor=false,BackgroundTransparency=1,Size=UDim2.fromOffset(L.w,L.h),ZIndex=30,Selectable=false})
  openLayer:SetAttribute('NoClickSound',true) -- each tap already plays the chest's shake sound
  openLayer.Activated:Connect(advance)
  drawPrompt()
 end

 -- Results: cards fly out of the chest (commons first, the best last with a bigger flash).
 local skipReveal=false
 local function card(parent,r,x,y,w,h)
  local col=Chests.RarityColor[r.rarity] or WHITE
  local c=T.panel(parent,'Card_'..r.id,x,y,w,h,'panel');corners(c,col)
  wash(c,col,RANK[r.rarity]>=3 and .7 or .5,c.ZIndex)
  if RANK[r.rarity]>=3 then local b=StoreFX.burst(c,w/2,78,w*1.25,col,RANK[r.rarity]>=4 and 40 or 22);b.ZIndex=c.ZIndex+1;for _,d in b:GetChildren() do d.ZIndex=c.ZIndex+1 end end
  local ic=T.icon(c,'Icon',(w-120)/2,18,120,itemIcon(r.id));ic.ZIndex=c.ZIndex+2
  local cnt=right(T.label(c,'Count','×'..(r.count or 1),w-110,6,98,40,36,RANK[r.rarity]>=3 and C.gold or WHITE));cnt.ZIndex=c.ZIndex+3
  local nm=centred(T.label(c,'Name',itemName(r.id),6,140,w-12,30,24,WHITE));nm.ZIndex=c.ZIndex+3;nm.TextWrapped=false;nm.TextScaled=true
  T.make('UITextSizeConstraint',nm,{MaxTextSize=24,MinTextSize=12})
  local rl=centred(T.label(c,'Rarity',string.upper(r.rarity),6,170,w-12,24,19,col:Lerp(WHITE,.25)));rl.ZIndex=c.ZIndex+3
  if r.new then
   local chip=T.chip(c,'New','NEW!',0,h-38,Color3.fromRGB(96,70,10),C.gold);chip.AnchorPoint=Vector2.new(.5,0);chip.Position=UDim2.new(.5,0,0,h-40);chip.ZIndex=c.ZIndex+3
   for _,d in chip:GetDescendants() do if d:IsA('GuiObject') then d.ZIndex=c.ZIndex+4 end end
  elseif (r.emeralds or 0)>0 then
   local e=centred(T.text(c,'Overflow','MAX  ·  +'..r.emeralds..' emeralds',8,h-40,w-16,26,17,C.emerald));e.ZIndex=c.ZIndex+3
  else
   local need=opts.need({id=r.id,tier=r.tier,have=r.have})
   local bar=T.upgradeBar(c,'Upgrade',14,h-36,w-28,22,r.have or 0,need);bar.ZIndex=c.ZIndex+3
   for _,d in bar:GetDescendants() do if d:IsA('GuiObject') then d.ZIndex=c.ZIndex+4 end end
   if need and (r.have or 0)>=need then local u=centred(T.label(c,'Ready','UPGRADE READY',6,h-62,w-12,22,16,C.lime));u.ZIndex=c.ZIndex+3 end
  end
  return c
 end

 showResults=function()
  mode='results'
  local o=opening
  if openLayer then openLayer:Destroy();openLayer=nil end
  resultLayer=T.make('TextButton',canvas,{Name='Results',Text='',AutoButtonColor=false,BackgroundTransparency=1,Size=UDim2.fromOffset(L.w,L.h),ZIndex=30})
  local dim=T.make('Frame',root,{Name='ResultsDim',BackgroundColor3=C.shade,BackgroundTransparency=1,BorderSizePixel=0,Size=UDim2.new(1,200,1,200),Position=UDim2.fromOffset(-100,-100),ZIndex=0})
  dim:SetAttribute('AuditIgnore',true)
  tween(dim,.5,{BackgroundTransparency=.38})
  resultLayer.Destroying:Connect(function() dim:Destroy() end)
  local def=Chests.ById[o.id]
  -- Short screens (phones): smaller title, more room for the cards.
  local compact=L.h<900
  local head=centred(T.label(resultLayer,'Title','YOU GOT!',0,compact and 10 or 40,L.w,compact and 72 or 90,compact and 64 or 84,WHITE));head.ZIndex=31
  T.make('UIGradient',head,{Color=ColorSequence.new(WHITE,(o.best or def.aura):Lerp(WHITE,.3)),Rotation=90})
  local sub=centred(T.text(resultLayer,'Sub',o.total..' items from '..(o.n>1 and (o.n..' '..def.name..'s') or ('a '..def.name)),0,compact and 80 or 128,L.w,34,28,C.cream));sub.ZIndex=31
  -- Grid: up to 7 per row (fewer on narrow screens); scrolls past what fits (×100 can give 30+).
  -- Phones draw the cards k times bigger so their smallest text (the 14 px NEW chip) stays about
  -- 9.5 px on screen: k = 9.5/(14 x .5) = 1.36 at scale .5.
  local list=o.results
  local cw,ch,gap=186,244,16
  local k=math.clamp(9.5/(14*L.s),1,1.4)
  local pw,ph=(cw+gap)*k,(ch+gap)*k
  local cols=math.clamp(math.floor((L.w-40+gap*k)/pw),1,math.min(7,math.max(1,#list)))
  local rows=math.ceil(#list/cols)
  local gridW=cols*pw-gap*k
  local gridY=compact and 124 or 180
  local btnY=L.h-(compact and 112 or 150)
  local viewH=math.min(rows*ph+4,btnY-16-gridY)
  local grid=T.make('ScrollingFrame',resultLayer,{Name='Grid',BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset((L.w-gridW)/2-10,gridY),Size=UDim2.fromOffset(gridW+20,viewH),CanvasSize=UDim2.fromOffset(0,rows*ph),ScrollBarThickness=8,ScrollBarImageColor3=C.lime,ScrollingDirection=Enum.ScrollingDirection.Y,ZIndex=32})
  -- Reveal order: commons first, the best last.
  local order={}
  for i=#list,1,-1 do table.insert(order,list[i]) end
  local slots={}
  for i,r in list do
   local col=(i-1)%cols;local row=math.floor((i-1)/cols)
   slots[r]=Vector2.new(10+col*pw,10+row*ph)
  end
  skipReveal=false
  local buttons
  local function finish()
   if buttons then return end
   buttons=T.frame(resultLayer,'Buttons',L.w/2-330,btnY,660,96);buttons.ZIndex=35
   local claim=T.button(buttons,'Claim','CLAIM',0,0,320,90,function() self.Claim() end);claim.Caption.TextSize=44
   local left_=owned(o.id)
   readProfile();left_=owned(o.id)
   local again=T.button(buttons,'Again',left_>0 and ('OPEN AGAIN ('..left_..')') or 'OPEN AGAIN',340,0,320,90,function()
    if owned(o.id)>0 then self.Again() end
   end,true)
   again.Caption.TextSize=30;again.Interactable=left_>0
   claim.SelectionOrder=1;again.SelectionOrder=2;T.gamepadSelect(buttons)
   buttons.Position+=UDim2.fromOffset(0,40);tween(buttons,.35,{Position=buttons.Position-UDim2.fromOffset(0,40)},Enum.EasingStyle.Back)
  end
  resultLayer.Activated:Connect(function() skipReveal=true end)
  task.spawn(function()
   -- MouthScreen is in viewport pixels (from the window's top-left corner); GUI positions are
   -- measured from under the top bar, so take the inset off before converting to canvas pixels.
   local mouth=Stage.MouthScreen(o.id)
   local start=mouth and toCanvas(mouth-GuiService:GetGuiInset()) or Vector2.new(L.w/2,L.h/2)
   -- ×10 / ×100: extra copies spray out of the chest as small icons.
   local ghosts=math.min(o.total,o.n>=100 and 60 or o.n>=10 and 26 or 8)
   for g=1,ghosts do
    local r=list[((g-1)%#list)+1]
    local ic=T.icon(canvas,'Ghost',start.X-28,start.Y-28,56,itemIcon(r.id));ic.ZIndex=33
    local a=math.rad(-90+(math.random()-.5)*150);local d=260+math.random()*420
    local to=start+Vector2.new(math.cos(a)*d,math.sin(a)*d*.8)
    ic.Rotation=math.random(-40,40)
    tween(ic,.9+math.random()*.4,{Position=UDim2.fromOffset(to.X-28,to.Y-28),ImageTransparency=1,Rotation=ic.Rotation+math.random(-120,120),Size=UDim2.fromOffset(34,34)},Enum.EasingStyle.Quad,Enum.EasingDirection.Out)
    task.delay(1.4,function() ic:Destroy() end)
    if g%4==0 then task.wait() end
   end
   for i,r in order do
    if not resultLayer or not resultLayer.Parent then return end
    local rank=RANK[r.rarity] or 1
    if not skipReveal and rank>=3 then
     -- Godly (rank 5): a longer beat, a crimson flash, a deeper fanfare and a harder shake.
     task.wait(rank>=5 and .8 or rank>=4 and .5 or .25)
     flash(Chests.RarityColor[r.rarity],rank>=5 and .8 or rank>=4 and .55 or .3)
     FX.play(rank>=4 and FX.Sounds.Legendary or FX.Sounds.Chime,rank>=4 and .6 or .5,rank>=5 and .8 or rank>=4 and 1 or .9)
     Stage.Shake(rank>=5 and .5 or rank>=4 and .3 or .15)
    end
    -- Closed or claimed mid-reveal (Escape / B): stop quietly.
    if not (canvas and grid.Parent) then return end
    local slot=slots[r]
    local holder=T.frame(grid,'Slot_'..r.id,slot.X,slot.Y,cw,ch)
    if k~=1 then T.make('UIScale',holder,{Scale=k}) end
    local c=card(holder,r,0,0,cw,ch)
    if not skipReveal then
     -- Fly from the chest mouth to the slot (in canvas space), then pop.
     local target=(grid.AbsolutePosition-canvas.AbsolutePosition)/L.s+slot-Vector2.new(0,grid.CanvasPosition.Y)
     local fly=T.icon(canvas,'Fly',start.X-50,start.Y-50,100,itemIcon(r.id));fly.ZIndex=34;fly.Rotation=math.random(-30,30)
     c.Visible=false
     tween(fly,.38,{Position=UDim2.fromOffset(target.X+(cw*k-100)/2,target.Y+30*k),Rotation=0},Enum.EasingStyle.Quad,Enum.EasingDirection.Out)
     task.delay(.36,function()
      fly:Destroy();c.Visible=true
      local s=T.make('UIScale',c,{Scale=.6});tween(s,.28,{Scale=1},Enum.EasingStyle.Back)
     end)
     if rank<=2 then FX.play(FX.Sounds.Chime,.08,1.5+rank*.1) end
     task.wait(rank>=3 and .45 or (#order>14 and .03 or .08))
    end
   end
   task.wait(skipReveal and 0 or .4)
   if mode=='results' then finish() end
  end)
 end

 function self.Claim()
  if mode~='results' then return end
  local id=opening and opening.id or selected
  if resultLayer then resultLayer:Destroy();resultLayer=nil end
  opening=nil
  Stage.Settle(id);Stage.Select(id)
  mode='browse';readProfile();buildBrowse(true)
 end
 function self.Again()
  if mode~='results' then return end
  local id=opening.id
  Stage.Settle(id)
  mode='browse'
  task.delay(.5,function() if mode=='browse' then self.Begin() end end)
 end

 -- The screen changed size (window resize, phone rotation): redraw on the new canvas.
 local function relayout()
  if mode=='browse' and browse then
   local path=T.selectionPath(canvas)
   buildBrowse(false)
   T.restoreSelection(canvas,path)
   if oddsOverlay then openOdds(oddsOverlay:GetAttribute('Chest')) end
   if itemCard then itemCard.Redraw(L) end -- same item, on the new canvas
  elseif mode=='opening' and openLayer then openLayer.Size=UDim2.fromOffset(L.w,L.h);if not opening.bursting then drawPrompt() end
  elseif resultLayer then resultLayer.Size=UDim2.fromOffset(L.w,L.h) end -- cards keep their places until CLAIM
 end

 -- Open / close ------------------------------------------------------------------------------------
 local pendingBrowse=false
 -- kind: a chest id, or {chest=id,odds=true,back=fn} from the store's SEE ODDS, which opens
 -- straight onto that chest's odds; closing them calls back() (the store reopens on its tab).
 function self.Open(kind)
  if root then self.Close() end
  local want=type(kind)=='table' and kind or nil
  if want then kind=want.chest end
  if kind and Chests.ById[kind] then selected=kind end
  readProfile()
  root=T.frame(screen,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
  screen.Enabled=true
  mode='browse'
  -- Lays out now and again whenever the root frame changes size.
  canvas,L=nil,nil
  T.canvas(root,function(c,cv)
   local first=canvas==nil
   canvas=cv;L=plan(c)
   if not first then relayout() end
  end)
  local has3d=Stage.Show(selected)
  if not has3d then
   -- No chest island installed: dim the lobby instead of showing an empty sky.
   local d=T.make('Frame',root,{Name='Dim',BackgroundColor3=C.shade,BackgroundTransparency=.35,BorderSizePixel=0,Position=UDim2.fromOffset(-100,-100),Size=UDim2.new(1,200,1,200),ZIndex=0})
   d:SetAttribute('AuditIgnore',true)
  end
  FX.play(FX.Sounds.Charge,.25,1.25)
  buildBrowse(true)
  if want and want.odds and Chests.ById[selected] then
   openOdds(selected)
   if type(want.back)=='function' then oddsBack=want.back end
  end
  T.hideTouchControls('ChestScreen',true)
  if opts.onVisible then opts.onVisible(false) end
  table.insert(conns,player.AttributeChanged:Connect(function(name)
   if (name=='ProfileGems' or name=='ProfileChests' or name=='ProfilePity' or name=='ProfileLoaded') and mode=='browse' then
    -- A purchase changes gems and chests together: one redraw after the last (drawBrowse re-checks mode).
    if not pendingBrowse then pendingBrowse=true;task.defer(function() pendingBrowse=false;drawBrowse() end) end
    if gemValue and gemValue.Parent then gemValue.Text=fmt(player:GetAttribute('ProfileGems') or 0) end
   end
   -- The open item card shows what you own and at what tier.
   if itemCard and (name=='ProfileWeapons' or name=='ProfileArmor' or name=='ProfilePets' or name=='ProfilePity' or name=='ProfileLoaded') then
    task.defer(function() if itemCard then itemCard.Redraw() end end)
   end
  end))
  table.insert(conns,Input.InputBegan:Connect(function(input,processed)
   if input.KeyCode==Enum.KeyCode.Escape or input.KeyCode==Enum.KeyCode.ButtonB then
    -- Back one step: the item card, the odds panel, then the results, then the screen.
    if itemCard then closeItem(false)
    elseif oddsOverlay then closeOdds()
    elseif mode=='results' then self.Claim() elseif mode=='browse' then self.Close() end
    return
   end
   -- LB / RB (and the arrow keys) walk the odds list on the open card.
   if itemCard then
    local k=input.KeyCode
    if k==Enum.KeyCode.ButtonL1 or k==Enum.KeyCode.Left then itemCard.Step(-1);return end
    if k==Enum.KeyCode.ButtonR1 or k==Enum.KeyCode.Right then itemCard.Step(1);return end
   end
   -- (No `processed` check: the movement sink marks Space as handled, and this screen has no text boxes.)
   local go=input.KeyCode==Enum.KeyCode.Space or input.KeyCode==Enum.KeyCode.Return or input.KeyCode==Enum.KeyCode.ButtonA
   if mode=='opening' and go then advance()
   elseif mode=='results' and go then skipReveal=true end
  end))
  -- HandlesBack: this screen handles Escape / ButtonB itself (LobbyUI should not also close it).
  return {Root=root,Close=self.Close,HandlesBack=true}
 end

 function self.Close()
  if not root then return end
  for _,c in conns do c:Disconnect() end
  table.clear(conns)
  local id=opening and opening.id or selected
  opening=nil
  Stage.Settle(id)
  Stage.Hide()
  local r=root;root=nil;r:Destroy()
  canvas,browse,listFrame,header,actions,gemValue,oddsOverlay,openLayer,resultLayer,prompt=nil,nil,nil,nil,nil,nil,nil,nil,nil,nil
  oddsBack,itemCard,oddsCells,oddsList=nil,nil,nil,nil
  mode='closed'
  screen.Enabled=false
  T.hideTouchControls('ChestScreen',false)
  if opts.onVisible then opts.onVisible(true) end
 end
 function self.IsOpen() return root~=nil end
 function self.Mode() return mode end
 function self.Select(id) if Chests.ById[id] and mode=='browse' then selected=id;Stage.Select(id);drawBrowse() end end
 function self.SetAmount(n) if Chests.validAmount(n) then amount=n;drawBrowse() end end
 function self.Advance() advance() end
 -- The odds of a chest, and an item's card over them (tests and previews).
 function self.OpenOdds(id) if mode=='browse' and canvas and Chests.ById[id or selected] then openOdds(id or selected) end end
 function self.OpenItem(id) if oddsOverlay then openItem(id) end end
 function self.CloseItem() closeItem(true) end
 -- Studio-only hook so tests can drive the real screen: TestChest:Fire('Open'|'Select'|'Begin'|'Advance'|'Claim'|'Close'|'SetAmount'|'OpenOdds'|'OpenItem', arg).
 if RunService:IsStudio() then
  local hook=Instance.new('BindableEvent');hook.Name='TestChest';hook.Parent=screen
  hook.Event:Connect(function(cmd,arg) if type(self[cmd])=='function' then self[cmd](arg) end end)
 end
 player.CharacterRemoving:Connect(function() self.Close() end)
 return self
end

return U
