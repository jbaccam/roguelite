-- Full-screen egg screen (lobby), green theme (UITheme) over the 3D egg pedestal (EggStage),
-- opened by walking up to the egg merchant on the quest-board island. Modelled on the chest screen:
-- Browse: the egg card on the left (owned count, every pet's odds by rarity), and over the egg its
-- title with BUY / HATCH / amount (×1, ×3, ×10). Hatching: the camera pushes in, the player taps
-- three times: two wobbles that crack the egg (the aura grows each time), then the top bursts off,
-- the best pet pops out of the egg and every pet flies out onto cards. ×3 and ×10 hatch in one go
-- with a bigger burst, not one animation per egg. The merchant reacts to all of it (EggMerchant).
-- Presentation and requests only: ProfileAction('BuyEgg'|'OpenEgg', amount) is validated and
-- rolled by ProfileService with EggConfig.
local Players=game:GetService('Players')
local RS=game:GetService('ReplicatedStorage')
local Input=game:GetService('UserInputService')
local TweenService=game:GetService('TweenService')
local TextService=game:GetService('TextService')
local RunService=game:GetService('RunService')
local GuiService=game:GetService('GuiService')
local T=require(RS:WaitForChild('UITheme'))
local StoreFX=require(RS:WaitForChild('StoreFX'))
local Stage=require(RS:WaitForChild('EggStage'))
local Merchant=require(RS:WaitForChild('EggMerchant'))
local FX=require(RS:WaitForChild('ChestFX'))
local combat=RS:WaitForChild('RogueliteCombat')
local Eggs=require(combat:WaitForChild('EggConfig'))
local Chests=require(combat:WaitForChild('ChestConfig'))
local Pets=require(combat:WaitForChild('PetConfig'))
-- Tapping a pet opens its card (ItemCardUI, like the chest odds); it also owns the chance formatter.
local Card=require(RS:WaitForChild('ItemCardUI'))
local C=T.Color
local U={}

local LIST_X,LIST_W=40,610
local WHITE=Color3.new(1,1,1)
local RANK={Common=1,Rare=2,Epic=3,Legendary=4}
local function petIcon(id) return Pets.Icons and Pets.Icons[id] or '' end
local function petName(id) local p=Pets.ById[id];return p and p.name or id end

local function tween(obj,time,props,style,dir,delay)
 local tw=TweenService:Create(obj,TweenInfo.new(time,style or Enum.EasingStyle.Quad,dir or Enum.EasingDirection.Out,0,false,delay or 0),props)
 tw:Play();return tw
end
local function fmt(n)
 n=math.floor(tonumber(n) or 0)
 local s=tostring(n):reverse():gsub('(%d%d%d)','%1,'):reverse()
 return (s:gsub('^,',''))
end
local function textWidth(text,size) return TextService:GetTextSize(text,size,T.Font,Vector2.new(4000,200)).X end
local function centred(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end
local function left(l) l.TextXAlignment=Enum.TextXAlignment.Left;return l end
local function right(l) l.TextXAlignment=Enum.TextXAlignment.Right;return l end
local function corners(obj,color)
 T.setTier(obj,2)
 local c=obj:FindFirstChild('RarityCorners');if c then c.ImageColor3=color end
 return obj
end
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
local function costRow(parent,amount,icon,size,color)
 local g=T.make('Frame',parent,{Name='Cost',BackgroundTransparency=1,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),AutomaticSize=Enum.AutomaticSize.X,Size=UDim2.fromOffset(0,size+8),ZIndex=parent.ZIndex+1})
 T.make('UIListLayout',g,{FillDirection=Enum.FillDirection.Horizontal,VerticalAlignment=Enum.VerticalAlignment.Center,HorizontalAlignment=Enum.HorizontalAlignment.Center,Padding=UDim.new(0,6),SortOrder=Enum.SortOrder.LayoutOrder})
 if icon then local i=T.icon(g,'Icon',0,0,size+6,icon);i.LayoutOrder=1;i.ZIndex=g.ZIndex end
 local l=T.label(g,'Amount',tostring(amount),0,0,textWidth(tostring(amount),size)+6,size+8,size,color);l.LayoutOrder=2;l.TextWrapped=false;l.ZIndex=g.ZIndex
 return g
end
local function zAll(obj,z) for _,d in obj:GetDescendants() do if d:IsA('GuiObject') then d.ZIndex=z end end end
-- Owned check mark drawn from frames (FredokaOne has no check glyph), like the Armory's.
local function tick(parent,x,y,size,z)
 local g=T.make('Frame',parent,{Name='Owned',BackgroundColor3=C.lime,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(size,size),BorderSizePixel=0,ZIndex=z})
 T.make('UICorner',g,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',g,{Color=Color3.fromRGB(8,10,11),Thickness=2})
 local w=math.max(2,math.floor(size*.14))
 T.make('Frame',g,{BackgroundColor3=C.ink,BorderSizePixel=0,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.36,.58),Size=UDim2.fromOffset(w,size*.3),Rotation=-45,ZIndex=z+1})
 T.make('Frame',g,{BackgroundColor3=C.ink,BorderSizePixel=0,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.58,.46),Size=UDim2.fromOffset(w,size*.56),Rotation=40,ZIndex=z+1})
 return g
end

-- opts: profile() -> LobbyUI profile, onVisible(bool) hides the lobby HUD, openWindow(name,arg),
-- need(rec) -> copies for the next tier.
function U.new(player,opts)
 local self={}
 local request=opts.request or function(...) return combat:WaitForChild('ProfileAction'):InvokeServer(...) end
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='EggScreen',ResetOnSpawn=false,DisplayOrder=58,ScreenInsets=Enum.ScreenInsets.DeviceSafeInsets,ClipToDeviceSafeArea=false,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,Enabled=false})
 self.Screen=screen
 local root,canvas
 local browse,card,header,actions,gemValue
 -- The pet card over the egg screen (ItemCardUI handle), the pet cells by id and the pets in display order.
 local itemCard,petCells,petList
 local openLayer,resultLayer,prompt
 local conns={}
 local amount=1
 local mode='closed' -- closed | browse | opening | results
 local busy=false

 local function owned() return player:GetAttribute('ProfileEggs') or 0 end
 local function gems() return player:GetAttribute('ProfileGems') or 0 end
 -- ×3 / ×10 needs the Quick Open pass (VIP includes it), like chests; the server refuses more too.
 local function quick() return player:GetAttribute('ProfileQuickOpen')==true or player:GetAttribute('ProfileVIP')==true end
 local function toast(text,ok) T.toast(screen,text,ok and C.lime or C.negative) end

 -- The pedestal's aura runs from the start; the merchant animates via EggStage.
 Stage.Watch()

 -- Layout: the same canvas plan as the chest screen. The egg is drawn by the 3D camera ('select'
 -- shot) right of centre; title and buttons sit above it, or under it on short screens. Example
 -- 1920x1080: egg about x 1160-1570, y 335-778; the title and buttons above it (y 56-322).
 local L
 local function plan(c)
  local l={s=c.s,w=c.w,h=c.h,top=c.top}
  l.tap=math.ceil(44/c.s)
  l.plateY=math.max(56,c.top+8)
  l.listY=l.plateY+94
  l.exitH=math.max(76,l.tap)
  l.exitY=c.h-28-l.exitH
  l.listH=l.exitY-16-l.listY
  local x0=LIST_X+LIST_W+24
  local eggX=c.w/2+c.h*.375
  local rightEdge=c.w-(c.top>64 and 120/c.s or 20)
  l.tw=math.min(860,rightEdge-x0)
  l.tx=math.clamp(eggX+100-l.tw/2,x0,rightEdge-l.tw)
  l.stacked=56+142+124<=c.h*.31
  l.aw=math.min(802,l.stacked and l.tw or c.w-20-x0)
  l.bw=math.min(300,(l.aw-170-32)/2)
  local ac=l.stacked and l.tx+l.tw/2 or math.clamp(eggX,x0+l.aw/2,c.w-20-l.aw/2)
  l.ax=ac-l.aw/2
  l.ay=l.stacked and 56+142 or c.h-24-124
  return l
 end
 local function toCanvas(abs) return (abs-canvas.AbsolutePosition)/L.s end

 local drawBrowse

 -- Browse ----------------------------------------------------------------------------------------
 -- The egg card: icon, name, owned count, then every pet by rarity with its chance (12 pets fit
 -- without an overlay). Scrolls when the screen is short (phones).
 -- The pet card closes first (B / Esc / X / BACK / a tap outside); the controller goes back to the
 -- cell of the pet it showed last. silent: closed because the screen is redrawn or closing.
 local function closeItem(silent) if itemCard then itemCard.Close(silent) end;itemCard=nil end
 local function openItem(id)
  if mode~='browse' or not (canvas and petList) then return end
  if itemCard then itemCard.Close(true) end
  itemCard=Card.open(canvas,L,{list=petList,id=id,source='egg',profile=opts.profile,zindex=50,
   onClose=function(lastId,silent)
    itemCard=nil
    if not silent and petCells and petCells[lastId] then Card.reselect(petCells[lastId]) end
   end})
 end
 local function drawCard()
  local keep=card and card.CanvasPosition.Y
  if card then card:Destroy() end
  card=T.scroll(canvas,'Card',LIST_X-8,L.listY-14,LIST_W+20,L.listH+14)
  local panelH=0
  -- 112 px cells: the whole card (about 810 px) fits a 1080p screen without scrolling. Where 15 px
  -- names would draw under 9.5 screen px (phones and 4:3 tablets, canvas scale under .63) the card
  -- uses three bigger cells a row (188 px, 22 px names) and scrolls.
  local big=L.s<.63
  local cell,gap=big and 188 or 112,8
  local perRow=big and 3 or 4
  local odds=Eggs.odds()
  local byR={};for _,o in odds do byR[o.rarity]=byR[o.rarity] or {};table.insert(byR[o.rarity],o) end
  -- Rarest first, like the chest odds (user, 2026-10-02); the card's < > walk the same order.
  local order=Card.rarestFirst(Eggs.Rarities)
  petList={};petCells={}
  for _,r in order do for _,o in byR[r] or {} do table.insert(petList,o) end end
  for _,r in order do if byR[r] then panelH+=44+math.ceil(#byR[r]/perRow)*(cell+gap)+6 end end
  local p=T.panel(card,'Egg',8,14,LIST_W,112+panelH+18,'panel');corners(p,Eggs.Aura)
  wash(p,Eggs.Aura,.45,p.ZIndex)
  local ic=T.icon(p,'Icon',12,0,104,Eggs.Icon or '');ic.ZIndex=p.ZIndex+2
  local n=owned()
  local name=left(T.label(p,'Name',Eggs.Name..(n>0 and '  <font color="#91EF14">('..n..')</font>' or ''),128,10,LIST_W-310,48,38));name.RichText=true;name.TextWrapped=false;name.ZIndex=p.ZIndex+2
  local sub=left(T.text(p,'Sub','Hatches 1 random pet  ·  tap a pet for details',130,70,LIST_W-150,28,21,C.cream));sub.ZIndex=p.ZIndex+2
  local chip=T.panel(p,'Price',LIST_W-172,18,154,48,'inset');chip.ZIndex=p.ZIndex+2
  costRow(chip,fmt(Eggs.Emeralds),'emerald',24,C.emerald);zAll(chip,chip.ZIndex+1)
  local held=opts.profile and opts.profile().pets
  local y=112
  for _,r in order do
   local list=byR[r]
   if list then
    local col=Chests.RarityColor[r]
    local bar=T.make('Frame',p,{Name='Rarity_'..r,Position=UDim2.fromOffset(14,y),Size=UDim2.fromOffset(LIST_W-28,36),BackgroundColor3=col,BackgroundTransparency=.45,BorderSizePixel=0,ZIndex=p.ZIndex+2})
    T.make('UICorner',bar,{CornerRadius=UDim.new(0,6)});T.make('UIStroke',bar,{Color=col:Lerp(Color3.new(0,0,0),.55),Thickness=2})
    T.make('UIGradient',bar,{Color=ColorSequence.new(WHITE,Color3.fromRGB(150,150,150))})
    left(T.label(bar,'Name',string.upper(r),16,0,300,36,24,WHITE)).ZIndex=bar.ZIndex+1
    right(T.label(bar,'Amount',Card.percent(Eggs.Odds[r]),LIST_W-28-316,0,300,36,24,WHITE)).ZIndex=bar.ZIndex+1
    y+=44
    for i,o in list do
     local x=14+((i-1)%perRow)*(cell+gap)
     -- Tappable: opens the pet's card ("i" corner, press feedback, lime ring on a controller).
     petCells[o.id]=Card.cell(p,{name='Pet_'..o.id,x=x,y=y+(i-1)//perRow*(cell+gap),size=cell,color=col,icon=petIcon(o.id),
      -- 112 px cells: the name gets two lines, so "Golden Retriever" stays 15 px instead of shrinking.
      iconSize=big and 112 or 54,iconY=big and 6 or 2,title=petName(o.id),titleY=big and 122 or 56,titleH=big and 28 or 38,titleSize=big and 22 or 15,
      chance=Card.percent(o.chance),chanceY=big and 152 or 93,chanceH=big and 28 or 18,chanceSize=big and 22 or 17,chanceColor=col:Lerp(WHITE,.55),
      badge=big and 30 or 24,owned=type(held)=='table' and held[o.id]~=nil,z=p.ZIndex+2,
      onOpen=function() openItem(o.id) end})
    end
    y+=math.ceil(#list/perRow)*(cell+gap)+6
   end
  end
  Card.settle(p,L.s) -- text shrinks to its box on phones instead of spilling out
  card.CanvasSize=UDim2.fromOffset(0,p.Size.Y.Offset+28)
  card.CanvasPosition=Vector2.new(0,keep or 0)
 end

 local function drawHeader()
  if header then header:Destroy() end
  if actions then actions:Destroy() end
  local n=owned()
  local tw=L.tw
  header=T.frame(canvas,'Header',L.tx,56,tw,132)
  local title=centred(T.label(header,'Title',Eggs.Name,0,0,tw,86,78,WHITE));title.TextWrapped=false
  T.make('UIGradient',title,{Color=ColorSequence.new(WHITE,Eggs.Aura:Lerp(WHITE,.35)),Rotation=90})
  local line=T.make('Frame',header,{Name='Underline',BackgroundColor3=WHITE,BorderSizePixel=0,AnchorPoint=Vector2.new(.5,0),Position=UDim2.fromOffset(tw/2,90),Size=UDim2.fromOffset(math.min(640,tw-40),4)})
  T.make('UIGradient',line,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.5,0),NumberSequenceKeypoint.new(1,1)})})
  centred(T.text(header,'Owned',n>0 and ('You have <b>'..n..'</b>  ·  1 pet each') or 'None yet  ·  1 pet each',0,100,tw,32,26,n>0 and C.limeSoft or C.cream))
  local bw,bh,gap=L.bw,92,16
  actions=T.frame(canvas,'Actions',L.ax,L.ay,L.aw,124)
  local x0=(L.aw-(bw*2+170+gap*2))/2
  -- One at a time without Quick Open (VIP includes it), like the chest screen.
  local multi=quick()
  if not multi then amount=1 end
  local price=Eggs.price(amount)
  local short=price-gems()
  -- Charcoal (not lime) when you can't afford it; still tappable so the merchant says why.
  local buy=T.button(actions,'Buy','',x0,0,bw,bh,function()
   if busy then return end
   busy=true
   local r=request('BuyEgg',amount)
   busy=false
   if r.ok then
    T.sound('ui_purchase');FX.play(FX.Sounds.Chime,.4,1.2)
    local a=Stage.Aura();if a then a:Pulse(.8) end
    Merchant.Nod();Merchant.Say(Merchant.pick('bought'),2.4)
   elseif tostring(r.message):find('emerald') then Merchant.Say(Merchant.pick('broke'),2.4) end
   toast(r.message or '',r.ok)
   drawBrowse()
  end,short>0)
  buy.Caption.Visible=false
  local bl=centred(T.label(buy,'Label','BUY ×'..amount,0,8,bw,34,28,short>0 and C.muted or C.ink));bl.TextStrokeTransparency=1
  local c=costRow(buy,fmt(price),'emerald',30,WHITE);c.Position=UDim2.new(.5,0,0,64)
  if short>0 then centred(T.text(actions,'Need','Need '..fmt(short)..' more',x0,bh+6,bw,26,22,C.negative)) end
  local n2=math.min(amount,n)
  local hatch=T.button(actions,'Hatch',n>0 and ('HATCH ×'..n2) or 'HATCH',x0+bw+gap,0,bw,bh,function() self.Begin() end,n<=0)
  hatch.Caption.TextSize=40;hatch.Interactable=n>0
  if n<=0 then centred(T.text(actions,'NoneOwned','Buy one first',x0+bw+gap,bh+6,bw,26,22,C.muted)) end
  if n>0 then StoreFX.pulse(hatch,.04) end
  local amt=T.button(actions,'Amount','×'..amount,x0+2*(bw+gap),0,170,bh,function()
   if not quick() then combat:WaitForChild('PurchaseRequest'):FireServer('QuickOpen');return end
   local i=table.find(Eggs.Amounts,amount) or 1
   amount=Eggs.Amounts[i%#Eggs.Amounts+1];FX.play(FX.Sounds.Chime,.15,1.6);drawBrowse()
  end,true)
  corners(amt,T.Tier[2]);amt.Caption.TextSize=42;amt.Caption.TextColor3=Color3.fromRGB(150,215,255)
  centred(T.text(actions,'AmountHelp',multi and 'amount' or 'Quick Open: ×10',x0+2*(bw+gap),bh+6,170,26,20,multi and C.muted or C.limeSoft))
  hatch.SelectionOrder=n>0 and 1 or 2;buy.SelectionOrder=n>0 and 2 or 1;amt.SelectionOrder=3
 end

 drawBrowse=function()
  if mode~='browse' or not browse then return end
  local path=T.selectionPath(canvas)
  drawCard();drawHeader()
  if itemCard then itemCard.Redraw() else T.restoreSelection(canvas,path) end -- the open card shows the new tier
 end

 local function browsePieces()
  local t=table.clone(browse or {})
  for _,o in {card or false,header or false,actions or false} do if o then table.insert(t,o) end end
  return t
 end
 local function clearBrowse()
  for _,o in browsePieces() do o:Destroy() end
  browse,card,header,actions,gemValue=nil,nil,nil,nil,nil
 end
 local function buildBrowse(animate)
  clearBrowse()
  browse={}
  local function add(o) table.insert(browse,o);return o end
  local shade=add(T.make('Frame',canvas,{Name='ListShade',BackgroundColor3=C.shade,BorderSizePixel=0,Position=UDim2.fromOffset(-1000,-200),Size=UDim2.fromOffset(1760,L.h+400),BackgroundTransparency=.2,ZIndex=0}))
  shade:SetAttribute('AuditIgnore',true)
  T.make('UIGradient',shade,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.15),NumberSequenceKeypoint.new(.57,.15),NumberSequenceKeypoint.new(.89,.6),NumberSequenceKeypoint.new(1,1)})})
  local pl,pw=plate(canvas,'Eggs',LIST_X+10,L.plateY,50);add(pl)
  local ps=math.max(56,L.tap)
  local gem=add(T.frame(canvas,'Emeralds',LIST_X+10+pw+14,L.plateY+3,240+8+ps,math.max(64,ps-11)))
  local pill=T.panel(gem,'Pill',0,0,240,64,'inset')
  T.icon(pill,'Icon',10,6,52,'emerald')
  gemValue=left(T.label(pill,'Value',fmt(gems()),70,6,160,52,34,C.emerald));gemValue.TextWrapped=false
  local plus=T.button(gem,'Plus','+',248,math.max(-11,(64-ps)/2),ps,ps,function() self.Close();opts.openWindow('Store','Emeralds') end);plus.Caption.TextSize=36
  -- EXIT sits centred under the egg card; in Studio it moves left to make room for +200 EMERALDS.
  local exitX=RunService:IsStudio() and LIST_X or LIST_X+(LIST_W-240)/2
  local exit=add(T.button(canvas,'Exit','EXIT',exitX,L.exitY,240,L.exitH,function() self.Close() end,true))
  T.setTier(exit,4);exit.Caption.TextSize=38;exit.Caption.TextColor3=C.negative
  if RunService:IsStudio() then
   local dev=add(T.button(canvas,'DevEmeralds','+200 EMERALDS (STUDIO)',LIST_X+256,L.exitY,290,L.exitH,function() local r=request('DevEmeralds');toast(r.message or '',r.ok);drawBrowse() end,true))
   dev.Caption.TextSize=20
  end
  drawCard();drawHeader()
  if not animate then return end
  for _,o in {card,pl,gem} do local p=o.Position;o.Position=p-UDim2.fromOffset(720,0);tween(o,.55,{Position=p},Enum.EasingStyle.Back,Enum.EasingDirection.Out,.35) end
  for _,o in {header,actions} do
   local dy=o==actions and not L.stacked and 300 or -380
   local p=o.Position;o.Position=p+UDim2.fromOffset(0,dy);tween(o,.55,{Position=p},Enum.EasingStyle.Back,Enum.EasingDirection.Out,.55)
  end
  T.gamepadSelect(actions)
 end

 -- Hatching -----------------------------------------------------------------------------------
 local opening -- {n, results, total, stage, best, bestRank, petId}
 local function bestOf(results)
  local best,rank,id=nil,0,nil
  for _,r in results do local k=RANK[r.rarity] or 1;if k>rank then rank,id=k,r.id end end
  best=rank>=2 and Chests.RarityColor[Eggs.Rarities[rank]] or nil
  return best,rank,id
 end
 local function flash(color,strength)
  local f=T.make('Frame',root,{Name='Flash',BackgroundColor3=color or WHITE,BackgroundTransparency=1-(strength or .8),BorderSizePixel=0,Size=UDim2.new(1,200,1,200),Position=UDim2.fromOffset(-100,-100),ZIndex=60})
  f:SetAttribute('AuditIgnore',true)
  tween(f,.6,{BackgroundTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.Out).Completed:Connect(function() f:Destroy() end)
 end

 local showResults
 local function drawPrompt()
  if prompt then prompt:Destroy() end
  prompt=T.frame(openLayer,'Prompt',L.w/2-400,L.h-215,800,200)
  local t=centred(T.label(prompt,'Tap',opening.stage==0 and 'TAP TO CRACK!' or opening.stage==1 and 'TAP AGAIN!' or 'ONE MORE!',0,0,800,90,76,WHITE))
  T.make('UIGradient',t,{Color=ColorSequence.new(WHITE,Eggs.Aura:Lerp(WHITE,.3)),Rotation=90})
  local s=T.make('UIScale',t,{Scale=1})
  TweenService:Create(s,TweenInfo.new(.45,Enum.EasingStyle.Sine,Enum.EasingDirection.InOut,-1,true),{Scale=1.08}):Play()
  for i=1,3 do
   local on=i<=opening.stage
   local pip=T.make('Frame',prompt,{Name='Pip'..i,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(400+(i-2)*64,124),Size=UDim2.fromOffset(on and 34 or 26,on and 34 or 26),BackgroundColor3=on and Eggs.Aura:Lerp(WHITE,.3) or C.track,BorderSizePixel=0,Rotation=45})
   T.make('UICorner',pip,{CornerRadius=UDim.new(0,6)});T.make('UIStroke',pip,{Color=Color3.fromRGB(8,10,11),Thickness=3})
  end
  if opening.n>1 then
   local many=centred(T.label(prompt,'Many','HATCHING ×'..opening.n..' EGGS',0,152,800,40,30,Eggs.Aura:Lerp(WHITE,.35)))
   many.TextStrokeTransparency=0
  end
 end
 local function advance()
  if mode~='opening' or not opening or opening.bursting then return end
  opening.stage+=1
  if opening.stage<3 then
   Stage.Charge(opening.stage,opening.best)
   flash(Eggs.Aura,.18*opening.stage)
   drawPrompt()
  else
   opening.bursting=true
   if prompt then prompt:Destroy();prompt=nil end
   Stage.Burst(Eggs.burstScale(opening.n),opening.best,opening.petId)
   flash(opening.best or WHITE,.85)
   task.delay(.9,function() if mode=='opening' then showResults() end end)
  end
 end

 function self.Begin(n)
  if mode~='browse' and mode~='results' or busy then return end
  local want=Eggs.validAmount(n) and n or amount
  if not quick() then want=1 end
  n=math.min(want,owned())
  if n<=0 then return end
  busy=true
  local r=request('OpenEgg',want)
  busy=false
  if not r.ok then toast(r.message or 'Could not hatch',false);return end
  local results=r.results or {}
  local total=0;for _,x in results do total+=x.count or 1 end
  local best,rank,petId=bestOf(results)
  opening={n=total,results=results,total=total,stage=0,best=best,bestRank=rank,petId=petId}
  if resultLayer then resultLayer:Destroy();resultLayer=nil end
  closeItem(true)
  if browse then
   local pieces=browsePieces();browse,card,header,actions,gemValue=nil,nil,nil,nil,nil
   for _,c in pieces do
    local p=c.Position;local dx=p.X.Offset<L.w/2 and -800 or 0;local dy=dx~=0 and 0 or p.Y.Offset>L.h/2 and 420 or -420
    tween(c,.3,{Position=p+UDim2.fromOffset(dx,dy)},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
   end
   task.delay(.32,function() for _,c in pieces do c:Destroy() end end)
  end
  mode='opening'
  Stage.Settle();Stage.Focus()
  Merchant.Present(true)
  openLayer=T.make('TextButton',canvas,{Name='Opening',Text='',AutoButtonColor=false,BackgroundTransparency=1,Size=UDim2.fromOffset(L.w,L.h),ZIndex=30,Selectable=false})
  openLayer:SetAttribute('NoClickSound',true)
  openLayer.Activated:Connect(advance)
  drawPrompt()
 end

 local skipReveal=false
 local function resultCard(parent,r,x,y,w,h)
  local col=Chests.RarityColor[r.rarity] or WHITE
  local c=T.panel(parent,'Card_'..r.id,x,y,w,h,'panel');corners(c,col)
  wash(c,col,RANK[r.rarity]>=3 and .7 or .5,c.ZIndex)
  if RANK[r.rarity]>=3 then local b=StoreFX.burst(c,w/2,78,w*1.25,col,RANK[r.rarity]>=4 and 40 or 22);b.ZIndex=c.ZIndex+1;for _,d in b:GetChildren() do d.ZIndex=c.ZIndex+1 end end
  local ic=T.icon(c,'Icon',(w-120)/2,18,120,petIcon(r.id));ic.ZIndex=c.ZIndex+2
  local cnt=right(T.label(c,'Count','×'..(r.count or 1),w-110,6,98,40,36,RANK[r.rarity]>=3 and C.gold or WHITE));cnt.ZIndex=c.ZIndex+3
  local nm=centred(T.label(c,'Name',petName(r.id),6,140,w-12,30,24,WHITE));nm.ZIndex=c.ZIndex+3;nm.TextWrapped=false;nm.TextScaled=true
  T.make('UITextSizeConstraint',nm,{MaxTextSize=24,MinTextSize=12})
  local rl=centred(T.label(c,'Rarity',string.upper(r.rarity),6,170,w-12,24,19,col:Lerp(WHITE,.25)));rl.ZIndex=c.ZIndex+3
  if r.new then
   local chip=T.chip(c,'New','NEW!',0,h-38,Color3.fromRGB(96,70,10),C.gold);chip.AnchorPoint=Vector2.new(.5,0);chip.Position=UDim2.new(.5,0,0,h-40);chip.ZIndex=c.ZIndex+3
   zAll(chip,c.ZIndex+4)
  elseif (r.emeralds or 0)>0 then
   local e=centred(T.text(c,'Overflow','MAX  ·  +'..r.emeralds..' emeralds',8,h-40,w-16,26,17,C.emerald));e.ZIndex=c.ZIndex+3
  else
   local need=opts.need and opts.need({id=r.id,tier=r.tier,have=r.have})
   local bar=T.upgradeBar(c,'Upgrade',14,h-36,w-28,22,r.have or 0,need);bar.ZIndex=c.ZIndex+3
   zAll(bar,c.ZIndex+4)
   if need and (r.have or 0)>=need then local u=centred(T.label(c,'Ready','UPGRADE READY',6,h-62,w-12,22,16,C.lime));u.ZIndex=c.ZIndex+3 end
  end
  return c
 end

 showResults=function()
  mode='results'
  local o=opening
  if openLayer then openLayer:Destroy();openLayer=nil end
  resultLayer=T.make('TextButton',canvas,{Name='Results',Text='',AutoButtonColor=false,BackgroundTransparency=1,Size=UDim2.fromOffset(L.w,L.h),ZIndex=30})
  -- Dim only toward the bottom (behind the cards): the hatched pet stands over the egg mid-screen.
  local dim=T.make('Frame',root,{Name='ResultsDim',BackgroundColor3=C.shade,BackgroundTransparency=1,BorderSizePixel=0,Size=UDim2.new(1,200,1,200),Position=UDim2.fromOffset(-100,-100),ZIndex=0})
  dim:SetAttribute('AuditIgnore',true)
  T.make('UIGradient',dim,{Rotation=90,Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.55),NumberSequenceKeypoint.new(.3,.85),NumberSequenceKeypoint.new(.55,.8),NumberSequenceKeypoint.new(1,0)})})
  tween(dim,.5,{BackgroundTransparency=.3})
  resultLayer.Destroying:Connect(function() dim:Destroy() end)
  local compact=L.h<900
  local head=centred(T.label(resultLayer,'Title','YOU HATCHED!',0,compact and 10 or 40,L.w,compact and 72 or 90,compact and 64 or 84,WHITE));head.ZIndex=31
  T.make('UIGradient',head,{Color=ColorSequence.new(WHITE,(o.best or Eggs.Aura):Lerp(WHITE,.3)),Rotation=90})
  local sub=centred(T.text(resultLayer,'Sub',o.total>1 and (o.total..' pets from '..o.total..' eggs') or '1 pet from a '..Eggs.Name,0,compact and 80 or 128,L.w,34,28,C.cream));sub.ZIndex=31
  -- The merchant reacts to the best pet.
  local bestRarity=Eggs.Rarities[math.max(1,o.bestRank)]
  Merchant.Say(Merchant.pick(bestRarity),3)
  if o.bestRank>=3 then Merchant.Cheer() else Merchant.Nod() end
  -- Cards: centred on the screen (user, 2026-10-02), kept between the subtitle and the buttons.
  -- Up to 7 per row; ×10 can wrap to 2 rows and scrolls past what fits.
  local list=o.results
  local cw,ch,gap=186,244,16
  local k=math.clamp(9.5/(14*L.s),1,1.4)*(#list>4 and .8 or 1)
  local pw,ph=(cw+gap)*k,(ch+gap)*k
  local cols=math.clamp(math.floor((L.w-40+gap*k)/pw),1,math.min(7,math.max(1,#list)))
  local rows=math.ceil(#list/cols)
  local gridW=cols*pw-gap*k
  local btnY=L.h-(compact and 112 or 150)
  local gridH=math.min(rows*ph+4,btnY-16-(compact and 124 or 180))
  local top=compact and 124 or 180
  local gridY=math.clamp((L.h-gridH)/2,top,math.max(top,btnY-16-gridH))
  local grid=T.make('ScrollingFrame',resultLayer,{Name='Grid',BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset((L.w-gridW)/2-10,gridY),Size=UDim2.fromOffset(gridW+20,gridH),CanvasSize=UDim2.fromOffset(0,rows*ph),ScrollBarThickness=8,ScrollBarImageColor3=C.lime,ScrollingDirection=Enum.ScrollingDirection.Y,ZIndex=32})
  local order={};for i=#list,1,-1 do table.insert(order,list[i]) end
  local slots={}
  for i,r in list do slots[r]=Vector2.new(10+((i-1)%cols)*pw,10+math.floor((i-1)/cols)*ph) end
  skipReveal=false
  local buttons
  local function finish()
   if buttons then return end
   buttons=T.frame(resultLayer,'Buttons',L.w/2-330,btnY,660,96);buttons.ZIndex=35
   local claim=T.button(buttons,'Claim','CLAIM',0,0,320,90,function() self.Claim() end);claim.Caption.TextSize=44
   local left_=owned()
   local again=T.button(buttons,'Again',left_>0 and ('HATCH AGAIN ('..left_..')') or 'HATCH AGAIN',340,0,320,90,function()
    if owned()>0 then self.Again() end
   end,true)
   again.Caption.TextSize=30;again.Interactable=left_>0
   claim.SelectionOrder=1;again.SelectionOrder=2;T.gamepadSelect(buttons)
   buttons.Position+=UDim2.fromOffset(0,40);tween(buttons,.35,{Position=buttons.Position-UDim2.fromOffset(0,40)},Enum.EasingStyle.Back)
  end
  resultLayer.Activated:Connect(function() skipReveal=true end)
  task.spawn(function()
   local mouth=Stage.MouthScreen()
   local start=mouth and toCanvas(mouth-GuiService:GetGuiInset()) or Vector2.new(L.w/2,L.h/2)
   for _,r in order do
    if not resultLayer or not resultLayer.Parent then return end
    local rank=RANK[r.rarity] or 1
    if not skipReveal and rank>=3 then
     task.wait(rank>=4 and .5 or .25)
     flash(Chests.RarityColor[r.rarity],rank>=4 and .55 or .3)
     FX.play(rank>=4 and FX.Sounds.Legendary or FX.Sounds.Chime,rank>=4 and .6 or .5,rank>=4 and 1 or .9)
     Stage.Shake(rank>=4 and .3 or .15)
    end
    if not (canvas and grid.Parent) then return end
    local slot=slots[r]
    local holder=T.frame(grid,'Slot_'..r.id,slot.X,slot.Y,cw,ch)
    if k~=1 then T.make('UIScale',holder,{Scale=k}) end
    local c=resultCard(holder,r,0,0,cw,ch)
    if not skipReveal then
     local target=(grid.AbsolutePosition-canvas.AbsolutePosition)/L.s+slot-Vector2.new(0,grid.CanvasPosition.Y)
     local fly=T.icon(canvas,'Fly',start.X-50,start.Y-50,100,petIcon(r.id));fly.ZIndex=34;fly.Rotation=math.random(-30,30)
     c.Visible=false
     tween(fly,.38,{Position=UDim2.fromOffset(target.X+(cw*k-100)/2,target.Y+30*k),Rotation=0},Enum.EasingStyle.Quad,Enum.EasingDirection.Out)
     task.delay(.36,function()
      fly:Destroy();c.Visible=true
      local s=T.make('UIScale',c,{Scale=.6});tween(s,.28,{Scale=1},Enum.EasingStyle.Back)
     end)
     if rank<=2 then FX.play(FX.Sounds.Chime,.08,1.5+rank*.1) end
     task.wait(rank>=3 and .45 or (#order>6 and .06 or .12))
    end
   end
   task.wait(skipReveal and 0 or .4)
   if mode=='results' then finish() end
  end)
 end

 function self.Claim()
  if mode~='results' then return end
  if resultLayer then resultLayer:Destroy();resultLayer=nil end
  opening=nil
  Stage.Settle();Stage.Select()
  Merchant.Present(true)
  mode='browse';buildBrowse(true)
 end
 function self.Again()
  if mode~='results' then return end
  Stage.Settle()
  mode='browse'
  task.delay(.5,function() if mode=='browse' then self.Begin() end end)
 end

 local function relayout()
  if mode=='browse' and browse then
   local path=T.selectionPath(canvas)
   buildBrowse(false)
   T.restoreSelection(canvas,path)
   if itemCard then itemCard.Redraw(L) end -- same pet, on the new canvas
  elseif mode=='opening' and openLayer then openLayer.Size=UDim2.fromOffset(L.w,L.h);if not opening.bursting then drawPrompt() end
  elseif resultLayer then resultLayer.Size=UDim2.fromOffset(L.w,L.h) end
 end

 -- Open / close ------------------------------------------------------------------------------------
 local pendingBrowse=false
 function self.Open()
  if root then self.Close() end
  root=T.frame(screen,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
  screen.Enabled=true
  mode='browse'
  canvas,L=nil,nil
  T.canvas(root,function(c,cv)
   local first=canvas==nil
   canvas=cv;L=plan(c)
   if not first then relayout() end
  end)
  local has3d=Stage.Show()
  if not has3d then
   local d=T.make('Frame',root,{Name='Dim',BackgroundColor3=C.shade,BackgroundTransparency=.35,BorderSizePixel=0,Position=UDim2.fromOffset(-100,-100),Size=UDim2.new(1,200,1,200),ZIndex=0})
   d:SetAttribute('AuditIgnore',true)
  end
  Merchant.Present(true);Merchant.Say(Merchant.pick('open'),3)
  FX.play(FX.Sounds.Charge,.25,1.25)
  buildBrowse(true)
  T.hideTouchControls('EggScreen',true)
  if opts.onVisible then opts.onVisible(false) end
  table.insert(conns,player.AttributeChanged:Connect(function(name)
   if (name=='ProfileGems' or name=='ProfileEggs' or name=='ProfilePets' or name=='ProfileLoaded' or name=='ProfileQuickOpen' or name=='ProfileVIP') and mode=='browse' then
    if not pendingBrowse then pendingBrowse=true;task.defer(function() pendingBrowse=false;drawBrowse() end) end
    if gemValue and gemValue.Parent then gemValue.Text=fmt(gems()) end
   end
  end))
  table.insert(conns,Input.InputBegan:Connect(function(input)
   if input.KeyCode==Enum.KeyCode.Escape or input.KeyCode==Enum.KeyCode.ButtonB then
    -- Back one step: the pet card, then the results, then the screen.
    if itemCard then closeItem(false)
    elseif mode=='results' then self.Claim() elseif mode=='browse' then self.Close() end
    return
   end
   -- LB / RB (and the arrow keys) walk the pet list on the open card.
   if itemCard then
    local k=input.KeyCode
    if k==Enum.KeyCode.ButtonL1 or k==Enum.KeyCode.Left then itemCard.Step(-1);return end
    if k==Enum.KeyCode.ButtonR1 or k==Enum.KeyCode.Right then itemCard.Step(1);return end
   end
   local go=input.KeyCode==Enum.KeyCode.Space or input.KeyCode==Enum.KeyCode.Return or input.KeyCode==Enum.KeyCode.ButtonA
   if mode=='opening' and go then advance()
   elseif mode=='results' and go then skipReveal=true end
  end))
  return {Root=root,Close=self.Close,HandlesBack=true}
 end

 function self.Close()
  if not root then return end
  for _,c in conns do c:Disconnect() end
  table.clear(conns)
  opening=nil
  Stage.Settle()
  Stage.Hide()
  Merchant.Present(false);Merchant.Say(Merchant.pick('bye'),2.2)
  local r=root;root=nil;r:Destroy()
  canvas,browse,card,header,actions,gemValue,openLayer,resultLayer,prompt=nil,nil,nil,nil,nil,nil,nil,nil,nil
  itemCard,petCells,petList=nil,nil,nil
  mode='closed'
  screen.Enabled=false
  T.hideTouchControls('EggScreen',false)
  if opts.onVisible then opts.onVisible(true) end
 end
 function self.IsOpen() return root~=nil end
 function self.Mode() return mode end
 function self.SetAmount(n) if Eggs.validAmount(n) then amount=n;drawBrowse() end end
 function self.Advance() advance() end
 function self.OpenItem(id) openItem(id) end -- a pet's card (tests and previews)
 function self.CloseItem() closeItem(true) end
 -- Studio-only hook so tests can drive the real screen: TestEgg:Fire('Open'|'Begin'|'Advance'|'Claim'|'Close'|'SetAmount'|'OpenItem', arg).
 if RunService:IsStudio() then
  local hook=Instance.new('BindableEvent');hook.Name='TestEgg';hook.Parent=screen
  hook.Event:Connect(function(cmd,arg) if type(self[cmd])=='function' then self[cmd](arg) end end)
 end
 player.CharacterRemoving:Connect(function() self.Close() end)
 return self
end

return U
