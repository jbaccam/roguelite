-- Four immediate stat offers, drawn with the shared green theme like the shop.
local Http=game:GetService('HttpService')
local Input=game:GetService('UserInputService')
local C=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Catalog=require(C:WaitForChild('LevelUpCatalog'))
local Stats=require(C.CharacterStats)
local ShopUI=require(game.ReplicatedStorage.ShopUI)
local T=require(game.ReplicatedStorage:WaitForChild('UITheme'))
local Money=require(C:WaitForChild('MonetizationConfig'))
local M={}
local white=Color3.fromRGB(245,247,248)
local green=Color3.fromRGB(132,234,75)
local colors={Color3.fromRGB(218,224,228),Color3.fromRGB(79,183,245),Color3.fromRGB(192,116,249),Color3.fromRGB(248,88,99)}
local roman={'',' II',' III',' IV'}
local initials={MaxHP='HP',Damage='DMG',AttackSpeed='AS',Armor='AR',Dodge='DG',Regeneration='RE',LifeSteal='LS',CritChance='CR',MeleeDamage='MD',RangedDamage='RD',ElementalDamage='ED',UtilityPower='UP',MoveSpeed='MS',PickupRadius='PR',Luck='LK',AttackRange='RG'}
local function make(kind,parent,props)
 local o=Instance.new(kind);for k,v in props do o[k]=v end;o.Parent=parent;return o
end
local function box(parent,name,x,y,w,h,color)
 return make('Frame',parent,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),BackgroundColor3=color or T.Color.shade,BorderSizePixel=0})
end
local function text(parent,name,value,x,y,w,h,size,color)
 local t=make('TextLabel',parent,{Name=name,BackgroundTransparency=1,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,h),Text=value,TextColor3=color or white,Font=T.Body,TextSize=size,TextScaled=true,TextWrapped=true,TextXAlignment=Enum.TextXAlignment.Left,TextStrokeTransparency=.55})
 make('UITextSizeConstraint',t,{MinTextSize=9,MaxTextSize=size});return t
end
local function button(parent,name,label,x,y,w,h,callback,neutral)
 local b=T.button(parent,name,label,x,y,w,h,callback,neutral);b.Modal=true
 local caption=b.Caption;caption.TextScaled=true;caption.TextStrokeTransparency=.2
 make('UITextSizeConstraint',caption,{MinTextSize=9,MaxTextSize=26})
 return b
end
local function icon(parent,id,x,y,size)
 local asset=Catalog.icon(id)
 local base=T.panel(parent,'Icon',x,y,size,size,'inset')
 if asset~='' then make('ImageLabel',base,{Name='Art',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),Image=asset,ScaleType=Enum.ScaleType.Fit})
 else local t=text(base,'Placeholder',initials[id] or '',3,0,size-6,size,23,Color3.fromRGB(174,183,185));t.TextXAlignment=Enum.TextXAlignment.Center end
end
function M.mount(player,onOpen,onDone)
 local state=C:WaitForChild('PlayerStates'):WaitForChild(tostring(player.UserId))
 -- Full screen minus phone notches and rounded corners; the backdrop reaches under them.
 local gui=make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='LevelUpOffers',ResetOnSpawn=false,DisplayOrder=60,ScreenInsets=Enum.ScreenInsets.DeviceSafeInsets,ClipToDeviceSafeArea=false,Enabled=false,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
 local shade=box(gui,'Backdrop',-100,-100,0,0,T.Color.shade);shade.Size=UDim2.new(1,200,1,200);shade.BackgroundTransparency=.1;shade.Active=true
 -- Root of the layout: the safe area. Everything is placed from its AbsoluteSize.
 local content=box(gui,'Content',0,0,0,0);content.BackgroundTransparency=1;content.Size=UDim2.fromScale(1,1)
 local self={};local data;local token;local busy=false;local tab='Primary';local smallStats=false;local render
 local banishMode=false -- after BANISH: the next card clicked is banished
 local function snapshot()
  local raw=state:GetAttribute('ShopSnapshot');if not raw then return end
  local ok,d=pcall(Http.JSONDecode,Http,raw);return ok and d or nil
 end
 local function send(action,index)
  if busy or not data then return end
  busy=true
  C.ShopAction:FireServer(action,data.revision,index,data.upgradeToken)
  local sent=token
  task.delay(1,function() if token==sent then busy=false end end)
 end
 render=function()
  if not gui.Enabled or not data then return end
  local path=T.selectionPath(content) -- a controller's selection survives the redraw
  content:ClearAllChildren()
  local w,h=content.AbsoluteSize.X,content.AbsoluteSize.Y
  local inset=58;pcall(function() inset=game:GetService('GuiService'):GetGuiInset().Y end)
  local cornerTop=math.max(inset,36)+6 -- pieces in the top corners start below Roblox's top bar
  local desktop=w>=1000;local margin=math.max(14,w*.025)
  -- Compact (phones, short windows): 40+ px taps and a tight stack from title to status line.
  local compact=not desktop or h<600
  local side=desktop and math.min(310,w*.22) or 0
  local leftW=w-2*margin-(desktop and side+20 or 0)
  local columns=(desktop or leftW>=750 or (w>h and w>=600)) and 4 or 2
  local gap=12;local cw=(leftW-gap*(columns-1))/columns
  local rows=math.ceil(#data.upgradeOffers/columns)
  local chooseH=compact and 42 or 37
  local bh=compact and 56 or 66 -- BANISH / REROLL
  local gapB=compact and 12 or 28
  -- Under the cards: the button row (banish mode on desktops stacks its hint over CANCEL: 82),
  -- then the status line. Example, 750x369 phone: 12+56+6+20+6 = 100 px.
  local blockH=(banishMode and not compact) and 82 or bh
  local below=gapB+blockH+6+20+6
  local minTop=compact and 100 or 128 -- title plate (58) and level line (24) above the cards
  if not desktop then minTop=math.max(minTop,cornerTop+48) end -- Show Stats sits above the cards
  local cardH=math.clamp(h*(columns==4 and .34 or .25),145,310)
  local total=math.max(1,rows)*cardH+math.max(0,rows-1)*gap
  local top=math.max(145,(h-total)*.46)
  if top+total+below>h then top=minTop;cardH=math.max(120,(h-top-below-gap*(math.max(1,rows)-1))/math.max(1,rows));total=math.max(1,rows)*cardH+gap*(math.max(1,rows)-1) end
  local plate=T.panel(content,'TitlePlate',margin+(leftW-320)/2,top-92,320,58,'panel');T.caps(plate,42)
  local title=text(plate,'Title','LEVEL UP!',0,0,320,58,36);title.Font=T.Font;title.TextXAlignment=Enum.TextXAlignment.Center;title.TextStrokeTransparency=.1
  local pending=text(content,'Pending','Level '..(data.level-data.pendingLevels+1)..'  ·  '..data.pendingLevels..' to choose',margin,top-30,leftW,24,17,T.Color.muted);pending.TextXAlignment=Enum.TextXAlignment.Center
  local balance=text(content,'Balance',tostring(data.shards)..' shards   ·   '..tostring(data.baggedShards or 0)..' bagged',margin,cornerTop,leftW*.7,32,23)
  balance.Visible=h>=500 and top-92>=cornerTop+36 -- only where the title plate is clear below it
  local cards=box(content,'Cards',margin,top,leftW,total);cards.BackgroundTransparency=1
  for i,o in data.upgradeOffers do
   local d=Catalog.ById[o.id]
   local card=T.panel(cards,'Offer'..i,((i-1)%columns)*(cw+gap),math.floor((i-1)/columns)*(cardH+gap),cw,cardH,'panel')
   T.setTier(card,o.tier) -- Rarity-tinted frame for II-IV.
   local size=math.min(64,cw*.26,cardH*.28)
   icon(card,o.id,12,12,size)
   text(card,'Name',d.name..roman[o.tier],size+23,11,cw-size-32,size*.60,24,colors[o.tier])
   -- Short cards (phones) drop the "Upgrade" line so the effect gets its room.
   local short=cardH<190
   if not short then text(card,'Kind','Upgrade',size+23,12+size*.60,cw-size-32,size*.40,19,Color3.fromRGB(220,217,166)) end
   -- The effect ends 6 px above Choose (Choose at cardH-12-chooseH).
   local chooseY=cardH-12-chooseH;local effectY=short and size+18 or size+30
   local effect=text(card,'Effect','<font color="#91EF14">+'..Stats.format(Stats.ById[o.id],o.amount)..'</font> '..Stats.ById[o.id].label,12,effectY,cw-24,math.min(math.max(40,cardH-size-100),chooseY-6-effectY),25);effect.RichText=true;effect.TextYAlignment=Enum.TextYAlignment.Top
   local choose=button(card,'Choose','Choose',12,chooseY,cw-24,chooseH,function() send('Upgrade',i) end)
   choose.Selectable=not banishMode -- in banish mode a controller moves between the BANISH overlays
   if banishMode then
    -- Pick mode: red corners and a full-card click target.
    T.setTier(card,4)
    local pickB=make('TextButton',card,{Name='BanishPick',Text='',AutoButtonColor=false,BackgroundColor3=Color3.fromRGB(120,10,20),BackgroundTransparency=.72,Size=UDim2.fromScale(1,1),ZIndex=5})
    make('UICorner',pickB,{CornerRadius=UDim.new(0,10)})
    local tag=text(pickB,'Tag','BANISH',0,0,cw,cardH,34,T.Color.white);tag.TextXAlignment=Enum.TextXAlignment.Center;tag.Font=T.Font;tag.ZIndex=6;tag.TextStrokeTransparency=0
    pickB.Activated:Connect(function() banishMode=false;C.RunAction:FireServer('UseBanish',i);render() end)
   end
  end
  -- Bottom bar: BANISH | REROLL, both Robux (or saved ones). No shard rerolls on level-ups.
  -- Hidden where paid random items are restricted.
  local ry=top+total+gapB
  local paid=not player:GetAttribute('PaidRandomRestricted')
  local bw=math.min(280,(leftW-24)/2)
  local bx=margin+(leftW-bw*2-24)/2
  local function bigButton(name,label,sub,x,red,callback)
   local bb=button(content,name,label,x,ry,bw,bh,callback,red)
   -- Caption on top, price under it, split in the button's height (66: 40 + 20).
   local capH=math.floor(bh*.6)
   bb.Caption.Size=UDim2.new(1,-16,0,capH);bb.Caption.Position=UDim2.fromOffset(8,4);bb.Caption.UITextSizeConstraint.MaxTextSize=32
   if red then T.setTier(bb,4);bb.Caption.TextColor3=T.Color.negative end
   local sl=text(bb,'Price',sub,8,capH+2,bw-16,bh-capH-6,17,red and Color3.fromRGB(255,190,190) or T.Color.white);sl.TextXAlignment=Enum.TextXAlignment.Center;sl.Font=T.Font
   return bb
  end
  local reroll
  if banishMode and compact then
   -- One row on short screens: the hint, then CANCEL at the right.
   local hint=text(content,'BanishHint','Pick the card you want to banish',margin,ry,leftW-232,bh,24,T.Color.negative);hint.TextXAlignment=Enum.TextXAlignment.Center;hint.Font=T.Font
   reroll=button(content,'CancelBanish','CANCEL',margin+leftW-220,ry+(bh-46)/2,220,46,function() banishMode=false;render() end,true)
  elseif banishMode then
   local hint=text(content,'BanishHint','Click the card you want to banish',margin,ry,leftW,30,24,T.Color.negative);hint.TextXAlignment=Enum.TextXAlignment.Center;hint.Font=T.Font
   reroll=button(content,'CancelBanish','CANCEL',margin+(leftW-220)/2,ry+36,220,46,function() banishMode=false;render() end,true)
  elseif paid and #data.upgradeOffers>0 then
   local banishes=player:GetAttribute('ProfileBanishes') or 0
   local rerolls=player:GetAttribute('ProfileRerolls') or 0
   bigButton('Banish','BANISH',banishes>0 and (banishes..' SAVED') or ('R$ '..Money.Products.Banish.robux),bx,true,function()
    if (player:GetAttribute('ProfileBanishes') or 0)>0 then banishMode=true;render() else C.PurchaseRequest:FireServer('Banish') end
   end)
   reroll=bigButton('Reroll','REROLL',rerolls>0 and (rerolls..' SAVED') or ('R$ '..Money.Products.UpgradeReroll.robux),bx+bw+24,false,function()
    if (player:GetAttribute('ProfileRerolls') or 0)>0 then C.RunAction:FireServer('UseReroll','Upgrade') else C.PurchaseRequest:FireServer('UpgradeReroll') end
   end)
  end
  if #data.upgradeOffers==0 then
   text(cards,'Capped','All available stats are at their caps.',12,20,leftW-24,60,26)
   reroll=button(content,'Continue','Continue',margin+(leftW-300)/2,ry,300,46,function() send('UpgradeSkip') end)
  end
  -- Status line under the button row (it used to be pushed up onto BANISH / REROLL on phones).
  local status=text(content,'Status',data.message or '',margin,ry+blockH+6,leftW,20,17);status.TextXAlignment=Enum.TextXAlignment.Center
  if not desktop then button(content,'ShowStats',smallStats and 'Hide Stats' or 'Show Stats',w-margin-125,cornerTop,125,40,function() smallStats=not smallStats;render() end,true) end
  if desktop or smallStats then
   local sw=desktop and side or math.min(340,w-28)
   local sx=desktop and w-margin-side or (w-sw)/2
   local sy=desktop and cornerTop or cornerTop+46 -- below the top bar (and the Show Stats button)
   local panel=T.panel(content,'Stats',sx,sy,sw,h-sy-(desktop and 30 or 8),'panel');panel.ZIndex=2
   local heading=text(panel,'Title','Stats',12,12,sw-24,36,30);heading.Font=Enum.Font.FredokaOne;heading.TextXAlignment=Enum.TextXAlignment.Center
   local tabH=compact and 40 or 31
   for j,name in {'Primary','Secondary'} do button(panel,name,name,10+(j-1)*(sw-20)/2,57,(sw-24)/2,tabH,function() tab=name;render() end,tab~=name).Caption.UITextSizeConstraint.MaxTextSize=18 end
   local scroll=make('ScrollingFrame',panel,{Name='Rows',BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset(12,72+tabH),Size=UDim2.new(1,-24,1,-83-tabH),CanvasSize=UDim2.new(),ScrollBarThickness=3})
   local defs={}
   for _,d in Stats.List do if (Catalog.ById[d.id]~=nil)==(tab=='Primary') then table.insert(defs,d) end end
   local values=Stats.read(state);local rowH=math.max(25,math.min(34,(h-sy-144)/#defs))
   for i,d in defs do
    local y=(i-1)*rowH;local color=ShopUI.statColor(d.id,values[d.id],d.base)
    if Catalog.icon(d.id)~='' then make('ImageLabel',scroll,{Name=d.id..'Icon',Image=Catalog.icon(d.id),BackgroundTransparency=1,Position=UDim2.fromOffset(0,y+2),Size=UDim2.fromOffset(20,20)}) end
    text(scroll,d.id,d.label,24,y,(sw-24)*.64-24,rowH,20,color)
    local v=text(scroll,d.id..'Value',Stats.format(d,values[d.id]),(sw-24)*.64,y,(sw-24)*.36-6,rowH,19,color);v.TextXAlignment=Enum.TextXAlignment.Right
   end
   scroll.CanvasSize=UDim2.fromOffset(0,#defs*rowH)
  end
  -- Controller: banish mode starts on the first card's BANISH overlay (A banishes, not buys);
  -- otherwise keep the selection across redraws, or start on the first Choose.
  -- Protected: this module is sandboxed, and a missing capability must not break the cards.
  pcall(function()
   if not Input:GetLastInputType().Name:find('^Gamepad') then return end
   local first=cards:FindFirstChild('Offer1');local GS=game:GetService('GuiService')
   local lastName=path and path[#path]
   if banishMode then GS.SelectedObject=first and first:FindFirstChild('BanishPick') or reroll
   elseif path and lastName~='BanishPick' and lastName~='CancelBanish' then T.restoreSelection(content,path)
   else GS.SelectedObject=first and first:FindFirstChild('Choose') or reroll end
  end)
 end
 function self:Close() gui.Enabled=false;token=nil;busy=false;T.hideTouchControls('LevelUp',false) end
 function self:Show()
  data=snapshot();if not data or data.phase~='Shop' or (data.pendingLevels or 0)<=0 then return false end
  if not gui.Enabled then onOpen();gui.Enabled=true;token=nil;T.hideTouchControls('LevelUp',true) end
  if token~=data.upgradeToken then token=data.upgradeToken;busy=false;banishMode=false;render() end
  return true
 end
 local queued=false
 local function changed()
  if queued then return end;queued=true
  task.defer(function()
   queued=false;data=snapshot();if not data then return end
   if data.phase=='Shop' and (data.pendingLevels or 0)>0 then
    if token~=data.upgradeToken or not gui.Enabled then self:Show() else busy=false;render() end
   elseif gui.Enabled then self:Close();onDone(data.phase) end
  end)
 end
 state:GetAttributeChangedSignal('ShopSnapshot'):Connect(changed)
 player:GetAttributeChangedSignal('ProfileBanishes'):Connect(function() if gui.Enabled then render() end end)
 player:GetAttributeChangedSignal('ProfileRerolls'):Connect(function() if gui.Enabled then render() end end)
 content:GetPropertyChangedSignal('AbsoluteSize'):Connect(function() if gui.Enabled then render() end end)
 -- A bought banish arrives as a saved banish; go straight to picking the card.
 C:WaitForChild('PurchaseResult').OnClientEvent:Connect(function(key,ok)
  if ok and key=='Banish' and gui.Enabled then banishMode=true;render() end
 end)
 task.defer(changed);return self
end
return M
