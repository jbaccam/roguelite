-- Full-screen chest screen (lobby), green theme (UITheme) over the 3D chest island (ChestStage).
-- Browse: the chest list on the left (owned count, price, what's inside by rarity, [i] for every
-- weapon's odds), and over the chosen chest its title with BUY / OPEN / amount (×1, ×10, ×100).
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
local T=require(RS:WaitForChild('UITheme'))
local StoreFX=require(RS:WaitForChild('StoreFX'))
local Stage=require(RS:WaitForChild('ChestStage'))
local FX=require(RS:WaitForChild('ChestFX'))
local combat=RS:WaitForChild('RogueliteCombat')
local Chests=require(combat:WaitForChild('ChestConfig'))
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local Armor=require(combat:WaitForChild('ArmorCatalog'))
local Money=require(combat:WaitForChild('MonetizationConfig'))
local C=T.Color
-- Chests drop weapons and armor pieces ('Iron.Helmet'); both get an icon and a name here.
local function itemIcon(id) return WeaponIcons[id] or Armor.Icons[id] end
local function itemName(id) local w=Weapons.ById[id];return w and w.name or Armor.pieceName(id) end
local U={}

-- Authored at 1920x1080 and scaled to the viewport (like the Armory and Skill Tree).
local DW,DH=1920,1080
local LIST_X,LIST_Y,LIST_W=40,150,610
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
 local screen=T.make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='ChestScreen',ResetOnSpawn=false,DisplayOrder=58,IgnoreGuiInset=true,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,Enabled=false})
 self.Screen=screen
 local root,canvas,canvasScale
 local browse,listFrame,header,actions,oddsOverlay
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

 local function fit()
  if not canvas then return end
  local v=workspace.CurrentCamera.ViewportSize
  canvasScale.Scale=math.min(v.X/DW,v.Y/DH)
 end
 local function toCanvas(abs) return (abs-canvas.AbsolutePosition)/canvasScale.Scale end

 local drawBrowse -- forward

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
  line('Legendary',Chests.LegendaryPity)
  if Chests.godlyEnabled() and (def.godly or 0)>0 then line('Godly',Chests.GodlyPity) end
  return out
 end

 local function openOdds(id)
  if oddsOverlay then oddsOverlay:Destroy() end
  local def=Chests.ById[id]
  local back=T.make('TextButton',canvas,{Name='Odds',Text='',AutoButtonColor=false,BackgroundColor3=C.shade,BackgroundTransparency=.4,Position=UDim2.fromOffset(-1000,-200),Size=UDim2.fromOffset(DW+2000,DH+400),ZIndex=40})
  oddsOverlay=back
  back.Activated:Connect(function() back:Destroy();oddsOverlay=nil end)
  -- One row per rarity that has weapons (Godly appears once Godly weapons exist).
  local odds=Chests.odds(id)
  local byR={};for _,o in odds do byR[o.rarity]=byR[o.rarity] or {};table.insert(byR[o.rarity],o) end
  local shown={};for _,r in Chests.Rarities do if byR[r] then table.insert(shown,r) end end
  local W,H=1340,math.max(740,130+#shown*144)
  local p=T.panel(back,'Panel',1000+(DW-W)/2,200+(DH-H)/2+20,W,H,'panel');p.ZIndex=41;p.Active=true;corners(p,def.aura)
  local pl=plate(p,def.name..'  ·  Odds',28,-34,34);pl.ZIndex=42;for _,d in pl:GetDescendants() do if d:IsA('GuiObject') then d.ZIndex=43 end end
  local x0,y=36,54
  local help=left(T.text(p,'Help','Chance that one '..def.name..' includes each item. '..def.copies..' items per chest (weapons and armor).',x0,y,W-72,26,20,C.muted));help.ZIndex=42
  y+=40
  local cell,gap=96,8
  for _,r in shown do
   local list=byR[r]
   local col=Chests.RarityColor[r]
   left(T.label(p,'H_'..r,string.upper(r),x0,y,300,30,26,col)).ZIndex=42
   y+=34
   for i,o in list do
    local x=x0+(i-1)*(cell+gap)
    local c=T.make('Frame',p,{Name='W_'..o.id,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(cell,cell),BackgroundColor3=col,BackgroundTransparency=.55,BorderSizePixel=0,ZIndex=42})
    T.make('UICorner',c,{CornerRadius=UDim.new(0,8)});T.make('UIStroke',c,{Color=col,Thickness=2})
    local ic=T.icon(c,'Icon',8,4,cell-16,itemIcon(o.id));ic.ZIndex=43
    local pct=o.chance>=10 and string.format('%.0f%%',o.chance) or o.chance>=1 and string.format('%.1f%%',o.chance) or string.format('%.2f%%',o.chance)
    local l=centred(T.label(c,'Chance',pct,0,cell-30,cell,28,22,WHITE));l.ZIndex=44
   end
   y+=cell+14
  end
  local close=T.button(p,'Close','X',W-70,-26,62,62,function() back:Destroy();oddsOverlay=nil end,true);T.setTier(close,4);close.Caption.TextColor3=C.negative;close.Caption.TextSize=34;close.ZIndex=44;close.Caption.ZIndex=45
  if close:FindFirstChild('RarityCorners') then close.RarityCorners.ZIndex=45 end
 end

 local function drawList()
  if listFrame then listFrame:Destroy() end
  listFrame=T.frame(browse,'List',LIST_X,LIST_Y,LIST_W,900)
  local y=0
  for _,id in Chests.Order do
   local def=Chests.ById[id];local sel=id==selected
   local rowH=ROW_H+(sel and (#Chests.summary(id)*(RAR_H+6)+10+#pityLines(def)*34) or 0)
   local row=T.button(listFrame,'Row_'..id,'',0,y,LIST_W,rowH,function()
    if selected~=id then selected=id;if opts.selection then opts.selection.chest=id end;Stage.Select(id);FX.play(FX.Sounds.Chime,.18,1.4);drawBrowse() end
   end,true)
   row.Caption.Visible=false;corners(row,def.aura)
   wash(row,def.aura,sel and .75 or .4,row.ZIndex)
   local icon=T.icon(row,'Icon',-6,-12,124,def.icon);icon.ZIndex=row.ZIndex+2
   local n=owned(id)
   local name=left(T.label(row,'Name',def.name..(n>0 and '  <font color="#91EF14">('..n..')</font>' or ''),128,10,LIST_W-300,48,36));name.RichText=true;name.TextWrapped=false;name.ZIndex=row.ZIndex+2
   local sub=left(T.text(row,'Sub',def.copies..' items  ·  '..(def.legendary>=1 and 'Legendary guaranteed' or ('Legendary '..Chests.percent(def.legendary))),130,56,LIST_W-230,26,20,C.cream));sub.ZIndex=row.ZIndex+2
   -- Price chip (top right).
   local chip=T.panel(row,'Price',LIST_W-172,14,154,48,'inset');chip.ZIndex=row.ZIndex+2
   if def.daily then
    local ready=profile.freeChestDay~=Money.day()
    local l=centred(T.label(chip,'Free',ready and 'FREE' or 'CLAIMED',0,0,154,48,ready and 26 or 20,ready and C.lime or C.muted));l.ZIndex=chip.ZIndex+1
   elseif def.emeralds then costRow(chip,short(def.emeralds),'emerald',24,C.emerald)
   else local l=centred(T.label(chip,'Robux','ROBUX',0,0,154,48,22,C.gold));l.ZIndex=chip.ZIndex+1 end
   for _,d in chip:GetDescendants() do if d:IsA('GuiObject') then d.ZIndex=chip.ZIndex+1 end end
   local info=T.button(row,'Info','i',LIST_W-66,ROW_H-52,48,42,function() openOdds(id) end,true);info.Caption.TextSize=26;info.ZIndex=row.ZIndex+3;info.Caption.ZIndex=row.ZIndex+4
   if sel then
    local yy=rarityBars(row,id,ROW_H)
    for _,d in row:GetChildren() do if d.Name:find('^Rarity_') then d.ZIndex=row.ZIndex+2;for _,e in d:GetDescendants() do if e:IsA('GuiObject') then e.ZIndex=row.ZIndex+3 end end end end
    for i,text in pityLines(def) do
     local p=left(T.text(row,i==1 and 'Pity' or 'Pity'..i,text,18,yy+2+(i-1)*34,LIST_W-36,30,20,C.limeSoft));p.ZIndex=row.ZIndex+2
    end
   end
   y+=rowH+10
  end
 end

 local function drawHeader()
  if header then header:Destroy() end
  local def=Chests.ById[selected];local n=owned(selected)
  header=T.frame(browse,'Header',1040,56,860,330)
  local title=centred(T.label(header,'Title',def.name,0,0,860,86,78,WHITE));title.TextWrapped=false
  T.make('UIGradient',title,{Color=ColorSequence.new(WHITE,def.aura:Lerp(WHITE,.35)),Rotation=90})
  local line=T.make('Frame',header,{Name='Underline',BackgroundColor3=WHITE,BorderSizePixel=0,AnchorPoint=Vector2.new(.5,0),Position=UDim2.fromOffset(430,90),Size=UDim2.fromOffset(640,4)})
  T.make('UIGradient',line,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,1),NumberSequenceKeypoint.new(.5,0),NumberSequenceKeypoint.new(1,1)})})
  centred(T.text(header,'Owned',n>0 and ('You have <b>'..n..'</b>  ·  '..def.copies..' items each') or ('None yet  ·  '..def.copies..' items each'),0,100,860,32,26,n>0 and C.limeSoft or C.cream))
  -- Actions: BUY (price × amount) · OPEN (owned, up to amount) · amount.
  local bw,bh,gap=300,92,16
  local x0=(860-(bw*2+170+gap*2))/2
  local price=def.emeralds and def.emeralds*amount
  local freeReady=def.daily and profile.freeChestDay~=Money.day()
  local buy=T.button(header,'Buy','',x0,150,bw,bh,function()
   if busy then return end
   if def.daily and not freeReady then return end
   if not def.emeralds and not def.daily then self.Close();opts.openWindow('Store','Chests');return end
   busy=true
   local r=request('BuyChest',selected,def.daily and 1 or amount)
   busy=false
   if r.ok then FX.play(FX.Sounds.Chime,.4,1.2);local a=Stage.Aura(selected);if a then a:Pulse(.8) end end
   toast(r.message or '',r.ok)
   readProfile();drawBrowse()
  end)
  buy.Caption.Visible=false
  if def.daily then
   -- Free once a day (resets at 00:00 UTC, Money.day()).
   local s=Money.secondsToReset()
   local l=centred(T.label(buy,'Label',freeReady and 'CLAIM FREE' or 'NEXT FREE',0,freeReady and 0 or 8,bw,freeReady and bh or 34,freeReady and 34 or 28,C.ink));l.TextStrokeTransparency=1
   if not freeReady then
    local t=centred(T.label(buy,'Timer',string.format('in %dh %dm',s//3600,(s%3600)//60),0,48,bw,34,26,C.ink));t.TextStrokeTransparency=1
    buy.Interactable=false
   end
  elseif def.emeralds then
   local l=centred(T.label(buy,'Label','BUY ×'..amount,0,8,bw,34,28,C.ink));l.TextStrokeTransparency=1
   local c=costRow(buy,fmt(price),'emerald',30,WHITE);c.Position=UDim2.new(.5,0,0,64)
  else
   local l=centred(T.label(buy,'Label','GET WITH ROBUX',0,0,bw,bh,28,C.ink));l.TextStrokeTransparency=1
  end
  local short_=def.emeralds and price-profile.gems
  if short_ and short_>0 then
   centred(T.text(header,'Need','Need '..fmt(short_)..' more',x0,150+bh+6,bw,26,22,C.negative))
  end
  local n2=math.min(amount,n)
  local open=T.button(header,'Open',n>0 and ('OPEN ×'..n2) or 'OPEN',x0+bw+gap,150,bw,bh,function() self.Begin() end,n<=0)
  open.Caption.TextSize=40;open.Interactable=n>0
  if n<=0 then centred(T.text(header,'NoneOwned','Buy one first',x0+bw+gap,150+bh+6,bw,26,22,C.muted)) end
  if n>0 then StoreFX.pulse(open,.04) end
  local amt=T.button(header,'Amount','×'..amount,x0+2*(bw+gap),150,170,bh,function()
   amount=amount==1 and 10 or amount==10 and 100 or 1;FX.play(FX.Sounds.Chime,.15,1.6);drawBrowse()
  end,true)
  corners(amt,T.Tier[2]);amt.Caption.TextSize=42;amt.Caption.TextColor3=Color3.fromRGB(150,215,255)
  centred(T.text(header,'AmountHelp','amount',x0+2*(bw+gap),150+bh+6,170,26,20,C.muted))
 end

 drawBrowse=function()
  if mode~='browse' or not browse then return end
  readProfile()
  drawList();drawHeader()
 end

 local function buildBrowse()
  browse=T.frame(canvas,'Browse',0,0,DW,DH)
  -- Readability wash behind the list.
  -- Starts 1000 px left of the 16:9 canvas so wide screens stay shaded to their left edge.
  local shade=T.make('Frame',browse,{Name='ListShade',BackgroundColor3=C.shade,BorderSizePixel=0,Position=UDim2.fromOffset(-1000,-200),Size=UDim2.fromOffset(1760,DH+400),BackgroundTransparency=.2,ZIndex=0})
  T.make('UIGradient',shade,{Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.15),NumberSequenceKeypoint.new(.57,.15),NumberSequenceKeypoint.new(.89,.6),NumberSequenceKeypoint.new(1,1)})})
  local pl=plate(browse,'Chests',LIST_X+10,56,50)
  -- Emeralds (top centre) with + to the store.
  local gem=T.panel(browse,'Emeralds',DW/2-170,30,260,64,'inset')
  T.icon(gem,'Icon',10,6,52,'emerald')
  local v=left(T.label(gem,'Value',fmt(profile.gems),70,6,180,52,34,C.emerald));v.Name='Value'
  local plus=T.button(browse,'EmeraldsPlus','+',DW/2+98,34,56,56,function() self.Close();opts.openWindow('Store','Emeralds') end);plus.Caption.TextSize=36
  -- Exit (bottom left).
  local exit=T.button(browse,'Exit','EXIT',LIST_X,DH-104,240,76,function() self.Close() end,true)
  T.setTier(exit,4);exit.Caption.TextSize=38;exit.Caption.TextColor3=C.negative
  if RunService:IsStudio() then
   local dev=T.button(browse,'DevEmeralds','+200 EMERALDS (STUDIO)',DW-330,DH-84,290,56,function() local r=request('DevEmeralds');toast(r.message or '',r.ok);readProfile();drawBrowse() end,true)
   dev.Caption.TextSize=18
  end
  -- Slide in while the camera flies over.
  listFrame=nil;header=nil
  drawList();drawHeader()
  for _,o in {listFrame,pl} do local p=o.Position;o.Position=p-UDim2.fromOffset(720,0);tween(o,.55,{Position=p},Enum.EasingStyle.Back,Enum.EasingDirection.Out,.35) end
  local hp=header.Position;header.Position=hp-UDim2.fromOffset(0,380);tween(header,.55,{Position=hp},Enum.EasingStyle.Back,Enum.EasingDirection.Out,.55)
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
  -- Full screen (root), not the 16:9 canvas, so wide screens get no side bands.
  local f=T.make('Frame',root,{Name='Flash',BackgroundColor3=color or WHITE,BackgroundTransparency=1-(strength or .8),BorderSizePixel=0,Size=UDim2.new(1,0,1,120),Position=UDim2.fromOffset(0,-60),ZIndex=60})
  tween(f,.6,{BackgroundTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.Out).Completed:Connect(function() f:Destroy() end)
 end

 local showResults -- forward
 local function drawPrompt()
  if prompt then prompt:Destroy() end
  prompt=T.frame(openLayer,'Prompt',DW/2-400,DH-215,800,200)
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
  if browse then
   local b=browse;browse=nil
   for _,c in b:GetChildren() do if c:IsA('GuiObject') then tween(c,.3,{Position=c.Position+UDim2.fromOffset(c.Position.X.Offset<DW/2 and -800 or 0,c.Position.X.Offset<DW/2 and 0 or -420)},Enum.EasingStyle.Quad,Enum.EasingDirection.In) end end
   task.delay(.32,function() b:Destroy() end)
  end
  mode='opening'
  Stage.Settle(selected);Stage.Focus(selected)
  openLayer=T.make('TextButton',canvas,{Name='Opening',Text='',AutoButtonColor=false,BackgroundTransparency=1,Size=UDim2.fromOffset(DW,DH),ZIndex=30})
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
  resultLayer=T.make('TextButton',canvas,{Name='Results',Text='',AutoButtonColor=false,BackgroundTransparency=1,Size=UDim2.fromOffset(DW,DH),ZIndex=30})
  local dim=T.make('Frame',root,{Name='ResultsDim',BackgroundColor3=C.shade,BackgroundTransparency=1,BorderSizePixel=0,Size=UDim2.new(1,0,1,120),Position=UDim2.fromOffset(0,-60),ZIndex=0})
  tween(dim,.5,{BackgroundTransparency=.38})
  resultLayer.Destroying:Connect(function() dim:Destroy() end)
  local def=Chests.ById[o.id]
  local head=centred(T.label(resultLayer,'Title','YOU GOT!',0,40,DW,90,84,WHITE));head.ZIndex=31
  T.make('UIGradient',head,{Color=ColorSequence.new(WHITE,(o.best or def.aura):Lerp(WHITE,.3)),Rotation=90})
  local sub=centred(T.text(resultLayer,'Sub',o.total..' items from '..(o.n>1 and (o.n..' '..def.name..'s') or ('a '..def.name)),0,128,DW,34,28,C.cream));sub.ZIndex=31
  -- Grid: up to 7 per row; scrolls past three rows (×100 can give 30+ weapons).
  local list=o.results
  local cols=math.min(7,math.max(1,#list));local cw,ch,gap=186,244,16
  local rows=math.ceil(#list/cols)
  local gridW=cols*cw+(cols-1)*gap
  local viewH=math.min(rows*(ch+gap)+4,DH-170-186)
  local grid=T.make('ScrollingFrame',resultLayer,{Name='Grid',BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset((DW-gridW)/2-10,180),Size=UDim2.fromOffset(gridW+20,viewH),CanvasSize=UDim2.fromOffset(0,rows*(ch+gap)),ScrollBarThickness=8,ScrollBarImageColor3=C.lime,ScrollingDirection=Enum.ScrollingDirection.Y,ZIndex=32})
  -- Reveal order: commons first, the best last.
  local order={}
  for i=#list,1,-1 do table.insert(order,list[i]) end
  local slots={}
  for i,r in list do
   local col=(i-1)%cols;local row=math.floor((i-1)/cols)
   slots[r]=Vector2.new(10+col*(cw+gap),10+row*(ch+gap))
  end
  skipReveal=false
  local buttons
  local function finish()
   if buttons then return end
   buttons=T.frame(resultLayer,'Buttons',DW/2-330,DH-150,660,96);buttons.ZIndex=35
   local claim=T.button(buttons,'Claim','CLAIM',0,0,320,90,function() self.Claim() end);claim.Caption.TextSize=44
   local left_=owned(o.id)
   readProfile();left_=owned(o.id)
   local again=T.button(buttons,'Again',left_>0 and ('OPEN AGAIN ('..left_..')') or 'OPEN AGAIN',340,0,320,90,function()
    if owned(o.id)>0 then self.Again() end
   end,true)
   again.Caption.TextSize=30;again.Interactable=left_>0
   buttons.Position+=UDim2.fromOffset(0,40);tween(buttons,.35,{Position=buttons.Position-UDim2.fromOffset(0,40)},Enum.EasingStyle.Back)
  end
  resultLayer.Activated:Connect(function() skipReveal=true end)
  task.spawn(function()
   local mouth=Stage.MouthScreen(o.id) or workspace.CurrentCamera.ViewportSize/2
   local start=toCanvas(mouth)
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
     task.wait(rank>=4 and .5 or .25)
     flash(Chests.RarityColor[r.rarity],rank>=4 and .55 or .3)
     FX.play(rank>=4 and FX.Sounds.Legendary or FX.Sounds.Chime,rank>=4 and .6 or .5,rank>=4 and 1 or .9)
     Stage.Shake(rank>=4 and .3 or .15)
    end
    local slot=slots[r]
    local c=card(grid,r,slot.X,slot.Y,cw,ch)
    if not skipReveal then
     -- Fly from the chest mouth to the slot (in canvas space), then pop.
     local target=grid.AbsolutePosition/canvasScale.Scale-canvas.AbsolutePosition/canvasScale.Scale+slot-Vector2.new(0,grid.CanvasPosition.Y)
     local fly=T.icon(canvas,'Fly',start.X-50,start.Y-50,100,itemIcon(r.id));fly.ZIndex=34;fly.Rotation=math.random(-30,30)
     c.Visible=false
     tween(fly,.38,{Position=UDim2.fromOffset(target.X+(cw-100)/2,target.Y+30),Rotation=0},Enum.EasingStyle.Quad,Enum.EasingDirection.Out)
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
  mode='browse';readProfile();buildBrowse()
 end
 function self.Again()
  if mode~='results' then return end
  local id=opening.id
  Stage.Settle(id)
  mode='browse'
  task.delay(.5,function() if mode=='browse' then self.Begin() end end)
 end

 -- Open / close ------------------------------------------------------------------------------------
 function self.Open(kind)
  if root then self.Close() end
  if kind and Chests.ById[kind] then selected=kind end
  readProfile()
  root=T.frame(screen,'Root',0,0,0,0);root.Size=UDim2.fromScale(1,1)
  canvas=T.frame(root,'Canvas',0,0,DW,DH);canvas.AnchorPoint=Vector2.new(.5,.5);canvas.Position=UDim2.fromScale(.5,.5)
  canvasScale=T.make('UIScale',canvas,{Scale=1});canvas.ZIndex=1
  screen.Enabled=true
  fit()
  mode='browse'
  local has3d=Stage.Show(selected)
  if not has3d then
   -- No chest island installed: dim the lobby instead of showing an empty sky.
   local d=T.make('Frame',root,{Name='Dim',BackgroundColor3=C.shade,BackgroundTransparency=.35,BorderSizePixel=0,Size=UDim2.fromScale(1,1),ZIndex=0})
  end
  FX.play(FX.Sounds.Charge,.25,1.25)
  buildBrowse()
  if opts.onVisible then opts.onVisible(false) end
  table.insert(conns,workspace.CurrentCamera:GetPropertyChangedSignal('ViewportSize'):Connect(fit))
  table.insert(conns,player.AttributeChanged:Connect(function(name)
   if (name=='ProfileGems' or name=='ProfileChests' or name=='ProfilePity' or name=='ProfileLoaded') and mode=='browse' then
    task.defer(drawBrowse)
    if browse and browse:FindFirstChild('Emeralds') then browse.Emeralds.Value.Text=fmt(player:GetAttribute('ProfileGems') or 0) end
   end
  end))
  table.insert(conns,Input.InputBegan:Connect(function(input,processed)
   if input.KeyCode==Enum.KeyCode.Escape or input.KeyCode==Enum.KeyCode.ButtonB then
    if mode=='results' then self.Claim() elseif mode=='browse' then self.Close() end
    return
   end
   -- (No `processed` check: the movement sink marks Space as handled, and this screen has no text boxes.)
   if mode=='opening' and (input.KeyCode==Enum.KeyCode.Space or input.KeyCode==Enum.KeyCode.Return or input.KeyCode==Enum.KeyCode.ButtonA) then advance()
   elseif mode=='results' and (input.KeyCode==Enum.KeyCode.Space or input.KeyCode==Enum.KeyCode.Return) then skipReveal=true end
  end))
  return {Root=root,Close=self.Close}
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
  canvas,browse,listFrame,header,oddsOverlay,openLayer,resultLayer,prompt=nil,nil,nil,nil,nil,nil,nil,nil
  mode='closed'
  screen.Enabled=false
  if opts.onVisible then opts.onVisible(true) end
 end
 function self.IsOpen() return root~=nil end
 function self.Mode() return mode end
 function self.Select(id) if Chests.ById[id] and mode=='browse' then selected=id;Stage.Select(id);drawBrowse() end end
 function self.SetAmount(n) if Chests.validAmount(n) then amount=n;drawBrowse() end end
 function self.Advance() advance() end
 -- Studio-only hook so tests can drive the real screen: TestChest:Fire('Open'|'Select'|'Begin'|'Advance'|'Claim'|'Close'|'SetAmount', arg).
 if RunService:IsStudio() then
  local hook=Instance.new('BindableEvent');hook.Name='TestChest';hook.Parent=screen
  hook.Event:Connect(function(cmd,arg) if type(self[cmd])=='function' then self[cmd](arg) end end)
 end
 player.CharacterRemoving:Connect(function() self.Close() end)
 return self
end

return U
