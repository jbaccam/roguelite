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
 local gui=make('ScreenGui',player:WaitForChild('PlayerGui'),{Name='LevelUpOffers',ResetOnSpawn=false,DisplayOrder=60,IgnoreGuiInset=true,Enabled=false,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
 local shade=box(gui,'Backdrop',0,0,0,0,T.Color.shade);shade.Size=UDim2.fromScale(1,1);shade.BackgroundTransparency=.1;shade.Active=true
 local content=box(shade,'Content',0,0,0,0);content.BackgroundTransparency=1;content.Size=UDim2.fromScale(1,1)
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
  content:ClearAllChildren()
  local w,h=shade.AbsoluteSize.X,shade.AbsoluteSize.Y
  local desktop=w>=1000;local margin=math.max(14,w*.025)
  local side=desktop and math.min(310,w*.22) or 0
  local leftW=w-2*margin-(desktop and side+20 or 0)
  local columns=(desktop or leftW>=750 or (w>h and w>=600)) and 4 or 2
  local gap=12;local cw=(leftW-gap*(columns-1))/columns
  local rows=math.ceil(#data.upgradeOffers/columns)
  local cardH=math.clamp(h*(columns==4 and .34 or .25),145,310)
  local total=math.max(1,rows)*cardH+math.max(0,rows-1)*gap
  local top=math.max(145,(h-total)*.46)
  if top+total+100>h then top=128;cardH=math.max(120,(h-top-95-gap*(math.max(1,rows)-1))/math.max(1,rows));total=math.max(1,rows)*cardH+gap*(math.max(1,rows)-1) end
  local plate=T.panel(content,'TitlePlate',margin+(leftW-320)/2,top-92,320,58,'panel');T.caps(plate,42)
  local title=text(plate,'Title','LEVEL UP!',0,0,320,58,36);title.Font=T.Font;title.TextXAlignment=Enum.TextXAlignment.Center;title.TextStrokeTransparency=.1
  local pending=text(content,'Pending','Level '..(data.level-data.pendingLevels+1)..'  ·  '..data.pendingLevels..' to choose',margin,top-30,leftW,24,17,T.Color.muted);pending.TextXAlignment=Enum.TextXAlignment.Center
  local balance=text(content,'Balance',tostring(data.shards)..' shards   ·   '..tostring(data.baggedShards or 0)..' bagged',margin,51,leftW*.7,32,23)
  balance.Visible=h>=500
  local cards=box(content,'Cards',margin,top,leftW,total);cards.BackgroundTransparency=1
  for i,o in data.upgradeOffers do
   local d=Catalog.ById[o.id]
   local card=T.panel(cards,'Offer'..i,((i-1)%columns)*(cw+gap),math.floor((i-1)/columns)*(cardH+gap),cw,cardH,'panel')
   T.setTier(card,o.tier) -- Rarity-tinted frame for II-IV.
   local size=math.min(64,cw*.26,cardH*.28)
   icon(card,o.id,12,12,size)
   text(card,'Name',d.name..roman[o.tier],size+23,11,cw-size-32,size*.60,24,colors[o.tier])
   text(card,'Kind','Upgrade',size+23,12+size*.60,cw-size-32,size*.40,19,Color3.fromRGB(220,217,166))
   local effect=text(card,'Effect','<font color="#91EF14">+'..Stats.format(Stats.ById[o.id],o.amount)..'</font> '..Stats.ById[o.id].label,12,size+30,cw-24,math.max(40,cardH-size-100),25);effect.RichText=true;effect.TextYAlignment=Enum.TextYAlignment.Top
   button(card,'Choose','Choose',12,cardH-49,cw-24,37,function() send('Upgrade',i) end)
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
  local ry=top+total+28
  local paid=not player:GetAttribute('PaidRandomRestricted')
  local bw,bh=math.min(280,(leftW-24)/2),66
  local bx=margin+(leftW-bw*2-24)/2
  local function bigButton(name,label,sub,x,red,callback)
   local bb=button(content,name,label,x,ry,bw,bh,callback,red)
   bb.Caption.Size=UDim2.new(1,-16,0,40);bb.Caption.Position=UDim2.fromOffset(8,4);bb.Caption.UITextSizeConstraint.MaxTextSize=32
   if red then T.setTier(bb,4);bb.Caption.TextColor3=T.Color.negative end
   local sl=text(bb,'Price',sub,8,42,bw-16,20,17,red and Color3.fromRGB(255,190,190) or T.Color.white);sl.TextXAlignment=Enum.TextXAlignment.Center;sl.Font=T.Font
   return bb
  end
  local reroll
  if banishMode then
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
  ry+=bh-46
  local status=text(content,'Status',data.message or '',margin,math.min(ry+51,h-22),leftW,20,17);status.TextXAlignment=Enum.TextXAlignment.Center
  if not desktop then button(content,'ShowStats',smallStats and 'Hide Stats' or 'Show Stats',w-margin-125,51,125,32,function() smallStats=not smallStats;render() end,true) end
  if desktop or smallStats then
   local sw=desktop and side or math.min(340,w-28)
   local sx=desktop and w-margin-side or (w-sw)/2
   local sy=desktop and 55 or 95
   local panel=T.panel(content,'Stats',sx,sy,sw,h-sy-30,'panel');panel.ZIndex=2
   local heading=text(panel,'Title','Stats',12,12,sw-24,36,30);heading.Font=Enum.Font.FredokaOne;heading.TextXAlignment=Enum.TextXAlignment.Center
   for j,name in {'Primary','Secondary'} do button(panel,name,name,10+(j-1)*(sw-20)/2,57,(sw-24)/2,31,function() tab=name;render() end,tab~=name).Caption.UITextSizeConstraint.MaxTextSize=18 end
   local scroll=make('ScrollingFrame',panel,{Name='Rows',BackgroundTransparency=1,BorderSizePixel=0,Position=UDim2.fromOffset(12,103),Size=UDim2.new(1,-24,1,-114),CanvasSize=UDim2.new(),ScrollBarThickness=3})
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
  if Input:GetLastInputType()==Enum.UserInputType.Gamepad1 then local first=cards:FindFirstChild('Offer1');game:GetService('GuiService').SelectedObject=first and first.Choose or reroll end
 end
 function self:Close() gui.Enabled=false;token=nil;busy=false end
 function self:Show()
  data=snapshot();if not data or data.phase~='Shop' or (data.pendingLevels or 0)<=0 then return false end
  if not gui.Enabled then onOpen();gui.Enabled=true;token=nil end
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
 shade:GetPropertyChangedSignal('AbsoluteSize'):Connect(function() if gui.Enabled then render() end end)
 -- A bought banish arrives as a saved banish; go straight to picking the card.
 C:WaitForChild('PurchaseResult').OnClientEvent:Connect(function(key,ok)
  if ok and key=='Banish' and gui.Enabled then banishMode=true;render() end
 end)
 task.defer(changed);return self
end
return M
