-- Presentation consumes server snapshots; never sends prices, refunds or item bonuses.
local RS=game:GetService('ReplicatedStorage')
local Http=game:GetService('HttpService')
local combat=RS:WaitForChild('RogueliteCombat')
local E=require(combat.EconomyConfig)
local Catalog=require(combat.ShopCatalog)
local Weapons=require(combat.WeaponCatalog)
local Stats=require(combat.CharacterStats)
local T=require(RS:WaitForChild('UITheme'))
local Money=require(combat:WaitForChild('MonetizationConfig'))
local M={}
-- LAYOUT SETTINGS: edit these numbers in Studio, then Stop/Play to preview.
-- Heights/gaps are pixels. 0.025 means a 2.5% margin on each screen edge.
M.Layout={
 HorizontalMargin=0.025,
 HeaderTop=16,
 ContentTop=64,
 WeaponsHeight=152,
 WeaponsWidth=320,
 ItemsHeight=152,
 InventoryBottomPadding=12,
 RerollWidth=180,
 RerollHeight=34,
 InventoryGap=8,
 SlotGap=4,
 InventoryTitleHeight=26,
 ItemWidthShare=0.55,
 CardHeight=390,
 StatsWidth=310,
}
-- ModuleScript Attributes expose these controls in Studio's Properties panel.
function M.getLayout()
 local result=table.clone(M.Layout)
 for key in result do
  local value=script:GetAttribute(key)
  if type(value)=='number' and value==value and math.abs(value)<10000 then result[key]=value end
 end
 result.HorizontalMargin=math.clamp(result.HorizontalMargin,0,.1)
 result.ItemWidthShare=math.clamp(result.ItemWidthShare,.2,.7)
 result.WeaponsWidth=math.max(240,result.WeaponsWidth)
 result.RerollWidth=math.max(130,result.RerollWidth)
 result.RerollHeight=math.clamp(result.RerollHeight,28,40)
 return result
end
local white=Color3.fromRGB(245,247,248)
local green=Color3.fromRGB(132,234,75)
local red=Color3.fromRGB(250,90,99)
local tiers={Color3.fromRGB(218,224,228),Color3.fromRGB(79,183,245),Color3.fromRGB(192,116,249),Color3.fromRGB(248,88,99)}
local cream=T.Color.cream
-- Green theme: lime-cornered panels; tier II-IV cards take the rarity-tinted frame.
local function surface(parent,name,x,y,w,h,tier,kind)
 local f=T.panel(parent,name,x,y,w,h,kind or 'panel')
 if tier and tier>1 then T.setTier(f,tier) end
 return f
end
local function shard(parent,x,y,size)
 return T.icon(parent,'ShardIcon',x,y,size,'shard')
end
local primary={}
for _,id in {'MaxHP','Damage','MeleeDamage','RangedDamage','ElementalDamage','UtilityPower','AttackSpeed','CritChance','CritDamage','Armor','Dodge','Regeneration','LifeSteal','Recovery','MoveSpeed','AttackRange','Luck','PickupRadius','ShopDiscount','ShopPricePercent','ExplosionDamage','ContactReduction','LifeStealCap'} do primary[id]=true end
local function thumbnail(parent,template,x,y,w,h)
 require(RS.WeaponInventoryUI).preview(parent,template,x,y,w,h)
end
function M.statColor(id,value,base)
 local delta=value-base;if id=='ShopPricePercent' or id=='ChainEvery' then delta=-delta end
 return delta>0 and green or delta<0 and red or white
end
function M.new(player,h,refresh)
 local state=combat.PlayerStates:WaitForChild(tostring(player.UserId))
 local self={state=state,selected=nil}
 local panel,label=surface,h.label
 function self:snapshot()
  local raw=state:GetAttribute('ShopSnapshot');if not raw then return end
  local ok,data=pcall(Http.JSONDecode,Http,raw);if not ok or type(data)~='table' then return end
  -- Combat pickups update lightweight attributes; offers/items remain in the snapshot.
  -- Read them here too so opening the shop mid-wave always shows current balances.
  for field,attribute in {shards='Shards',baggedShards='BaggedShards',level='RunLevel',pendingLevels='PendingLevelUps'} do
   local value=state:GetAttribute(attribute);if value~=nil then data[field]=value end
  end
  return data
 end
 function self:send(action,arg,extra)
  local data=self:snapshot();if data then combat.ShopAction:FireServer(action,data.revision,arg,extra) end
 end
 local refreshQueued=false
 local function queueRefresh()
  if refreshQueued then return end
  refreshQueued=true
  task.defer(function() refreshQueued=false;refresh() end)
 end
 state:GetAttributeChangedSignal('ShopSnapshot'):Connect(queueRefresh)
 for _,attribute in {'Shards','BaggedShards','RunLevel','PendingLevelUps'} do
  state:GetAttributeChangedSignal(attribute):Connect(queueRefresh)
 end
 player:GetAttributeChangedSignal('ProfileRerolls'):Connect(function() task.defer(refresh) end)
 script.AttributeChanged:Connect(function() task.defer(refresh) end)
 -- Fitted text never shrinks below this many layout px; render() raises it on small layout scales
 -- so text stays 9 px on screen (at scale .65 it is 14).
 local minText=9
 local function text(p,n,t,x,y,w,ht,size,color)
  local l=label(p,n,t,x,y,w,ht,size or 14,color);l.Font=T.Body;l.TextStrokeColor3=Color3.fromRGB(3,7,10);l.TextStrokeTransparency=.55;l.TextXAlignment=Enum.TextXAlignment.Left;l.TextScaled=true;local limit=Instance.new('UITextSizeConstraint');limit.MinTextSize=math.min(size or 14,minText);limit.MaxTextSize=size or 14;limit.Parent=l;return l
 end
 local function btn(p,n,t,x,y,w,ht,fn,neutral)
  -- Lime face for primary actions, charcoal panel when neutral; dims when not Interactable.
  local b=T.button(p,n,t,x,y,w,ht,fn,neutral)
  local caption=b.Caption;caption.TextScaled=true;caption.TextStrokeTransparency=.2
  local limit=Instance.new('UITextSizeConstraint');limit.MinTextSize=math.min(20,minText);limit.MaxTextSize=20;limit.Parent=caption
  return b
 end
 -- The complete price (text + crystal) is centered as one measured group.
 local function price(parent,value,prefix,size,color)
  size=math.floor(math.max(9,math.min(size,(parent.Size.X.Offset-20)/(#((prefix or '')..tostring(value))*.65+1.2))))
  local group=Instance.new('Frame');group.Name='PriceGroup';group.BackgroundTransparency=1;group.AutomaticSize=Enum.AutomaticSize.X;group.Size=UDim2.fromOffset(0,size+4);group.AnchorPoint=Vector2.new(.5,.5);group.Position=UDim2.fromScale(.5,.5);group.Parent=parent
  local layout=Instance.new('UIListLayout');layout.FillDirection=Enum.FillDirection.Horizontal;layout.VerticalAlignment=Enum.VerticalAlignment.Center;layout.Padding=UDim.new(0,6);layout.Parent=group
  local amount=text(group,'Price',(prefix or '')..tostring(value),0,0,0,size+4,size,color);amount.Font=Enum.Font.FredokaOne;amount.UITextSizeConstraint:Destroy();amount.TextScaled=false;amount.TextWrapped=false;amount.AutomaticSize=Enum.AutomaticSize.None;amount.Size=UDim2.fromOffset(math.ceil(game:GetService('TextService'):GetTextSize(amount.Text,size,Enum.Font.FredokaOne,Vector2.new(10000,1000)).X)+4,size+8);amount.TextStrokeTransparency=.4;amount.LayoutOrder=1
  local crystal=shard(group,0,0,size+2);crystal.LayoutOrder=2
  return group
 end
 local function heading(p,n,t,x,y,w,ht,size,color)
  local l=text(p,n,t,x,y,w,ht,size,color);l.Font=Enum.Font.FredokaOne;l.TextStrokeTransparency=.25;return l
 end
 local function art(p,entry,x,y,w,ht)
  if entry.weaponId then thumbnail(p,combat.WeaponTemplates:FindFirstChild(entry.weaponId),x,y,w,ht)
  else h.icon(p,'Icon',x+(w-ht)/2,y,ht,entry.icon) end
 end
 local function effects(p,entry,x,y,w)
  local row=0
  for _,d in Stats.List do
   local v=entry.modifiers[d.id];local percent=(entry.percent or {})[d.id]
   if v or percent then
    local value=v or percent
    text(p,'Effect_'..d.id,d.label..': '..(value>0 and '+' or '')..value..(percent and '%' or d.unit),x,y+row*26,w,26,18,M.statColor(d.id,value,0));row+=1
   end
  end
  return row*26
 end
 local function weaponStats(p,base,tier,x,y,w)
  local s=Stats.read(state);local d=Stats.weapon(base,s,state:GetAttribute('Class'),tier)
  local rows={{'Damage',string.format('%.1f',d.damage),d.damage-base.damage},{'Cooldown',string.format('%.2f s',d.cooldown),base.cooldown-d.cooldown},{'Critical',string.format('x%.1f (%s)',s.CritDamage/100,Stats.format(Stats.ById.CritChance,s.CritChance)),s.CritChance-Stats.ById.CritChance.base},{'Range',string.format('%.1f',d.range),d.range-base.range}}
  for i,r in rows do
   local color=r[3]>0 and green or r[3]<0 and red or white
   local l=text(p,'WeaponStat'..i,string.format('<font color="#EADDA7">%s:</font> <font color="#%02X%02X%02X">%s</font>',r[1],math.round(color.R*255),math.round(color.G*255),math.round(color.B*255),r[2]),x,y+(i-1)*24,w,24,19)
   l.RichText=true
  end
 end
 function self:debug(parent,width)
  local data=self:snapshot();if not data or not data.debug then return 0 end
  local box=panel(parent,'ShardsEditor',0,0,width,104)
  text(box,'Title','Developer shards · '..data.shards..' SHARDS',12,7,width-24,25,18)
  local input=Instance.new('TextBox');input.Name='ShardsInput';input.Position=UDim2.fromOffset(12,40);input.Size=UDim2.fromOffset(math.max(65,width*.24),38);input.Text=tostring(data.shards);input.TextSize=16;input.Font=Enum.Font.GothamBold;input.BackgroundColor3=Color3.fromRGB(25,29,30);input.TextColor3=white;input.ClearTextOnFocus=false;input.Parent=box
  local start=22+math.max(65,width*.24);local bw=(width-start-18)/4
  for i,v in {100,1000,-100} do btn(box,'Shards'..v,(v>0 and '+' or '')..v,start+(i-1)*(bw+2),40,bw,38,function() self:send('Shards','Add',v) end,true) end
  btn(box,'SetShards','SET',start+3*(bw+2),40,bw,38,function() local v=tonumber(input.Text);if v then self:send('Shards','Set',v) end end)
  text(box,'Hint','Studio only · session shards · disabled by EconomyConfig',12,80,width-24,18,11)
  local connection=state:GetAttributeChangedSignal('ShopSnapshot'):Connect(function()
   local latest=self:snapshot();if latest then box.Title.Text='Developer shards · '..latest.shards..' SHARDS';if not input:IsFocused() then input.Text=tostring(latest.shards) end end
  end)
  box.Destroying:Connect(function() connection:Disconnect() end)
  return 114
 end
 function self:render(parent,width,height,inventoryOnly)
  local data=self:snapshot();if not data then text(parent,'Loading','Loading shop…',0,0,width,40,20);return end
  local L=M.getLayout()
  local scale=math.min(1,(width-12)/480)
  local occupied=0;for _,v in data.weapons do if v.id~='' then occupied+=1 end end
  local inventoryH=(occupied>3 or #data.items>8) and 190 or 132
  -- The wide layout (4 cards over the inventory) needs a minimum height: header, 310px cards,
  -- lock row, inventory. When the window is a little short, shrink everything to fit (down to
  -- 70%) instead of scrolling; only genuinely small screens scroll.
  local tap=0 -- layout px a touch target needs (40 px on screen) on short screens; 0 elsewhere
  if not inventoryOnly then
   local wide=(width-12)/scale*.77-28>=660
   local fitH=(height-12)/(76+310+58+inventoryH+12)
   if wide and fitH<scale then scale=math.max(fitH,.7) end
   -- Short screens (phones, under 450 px): taps grow to 40 px on screen, and the scale is picked so
   -- one whole card (310 + Buy growth) plus its Lock row fits the view: 277+80/scale <= (height-16)/scale,
   -- so scale <= (height-96)/277. Example: a 275 px tall shop gets .65 (text 16 -> 10.4 px).
   if height<450 then scale=math.max(.55,math.min(scale,(height-96)/277));tap=40/scale end
  end
  minText=math.max(9,9/scale)
  local function th(v) return math.max(v,tap) end
  local w=(width-12)/scale;local ht=(height-12)/scale
  local root=Instance.new('Frame');root.Name='ShopLayout';root.BackgroundTransparency=1;root.Size=UDim2.fromOffset(w,ht);root.Parent=parent
  local scaling=Instance.new('UIScale');scaling.Scale=scale;scaling.Parent=root
  root.Position=UDim2.fromOffset(6,6)
  local side=math.clamp(w*.23,tap>0 and 200 or 148,math.max(L.StatsWidth,tap>0 and 200 or 148));local gap=16;local leftW=w-side-gap-12
  local left=Instance.new('ScrollingFrame');left.Name='ShopMain';left.Position=UDim2.fromOffset(0,0);left.Size=UDim2.fromOffset(leftW+12,ht);left.BackgroundTransparency=1;left.BorderSizePixel=0;left.ScrollBarThickness=3;left.VerticalScrollBarInset=Enum.ScrollBarInset.None;left.ClipsDescendants=true;left.Parent=root
  local inset=Instance.new('UIPadding');inset.PaddingLeft=UDim.new(0,6);inset.PaddingTop=UDim.new(0,6);inset.Parent=left
  local startH=th(62);local statsH=math.max(90,ht-startH-10)
  local stats=surface(root,'StatsColumn',leftW+gap+12,0,side,statsH)
  local secondary=self.statTab=='Secondary'
  local statTitle=heading(stats,'Title','Stats',12,10,side-24,34,28);statTitle.TextXAlignment=Enum.TextXAlignment.Center
  local tabH=th(32)
  for i,tab in {'Primary','Secondary'} do
   local b=btn(stats,tab..'Tab',side<180 and (tab=='Primary' and 'Main' or 'Extra') or tab,9+(i-1)*(side-18)/2,52,(side-22)/2,tabH,function() self.statTab=tab;self.statPage=1;refresh() end,tab~=(self.statTab or 'Primary'))
   b.Caption.UITextSizeConstraint.MaxTextSize=side<180 and 12 or 18
  end
  local definitions={};for _,d in Stats.List do if (primary[d.id]==true)~=secondary then table.insert(definitions,d) end end
  -- Rows fill the space between the tabs and the pager (never past the panel); each row at least
  -- 18 layout px and 13 px on screen.
  local rowsTop=52+tabH+6;local rowMin=math.max(18,13/scale);local pagerH,pagerW=th(25),th(32)
  local available=statsH-rowsTop-8
  local perPage=math.max(1,math.floor(available/rowMin))
  local paged=#definitions>perPage
  if paged then available-=pagerH+5;perPage=math.max(1,math.floor(available/rowMin)) end
  if available<rowMin then perPage=math.max(1,#definitions);paged=false end -- too short for any row
  local pages=math.ceil(#definitions/perPage);local page=math.clamp(self.statPage or 1,1,pages)
  local shown=available<rowMin and 0 or math.min(perPage,#definitions-(page-1)*perPage);local rowH=shown>0 and available/shown or 0
  local scroll=Instance.new('Frame');scroll.Name='StatRows';scroll.Position=UDim2.fromOffset(9,rowsTop);scroll.Size=UDim2.fromOffset(side-18,math.max(0,available));scroll.BackgroundTransparency=1;scroll.ClipsDescendants=true;scroll.Parent=stats
  local values=Stats.read(state)
  for i=1,shown do
   local d=definitions[(page-1)*perPage+i]
   local row=Instance.new('Frame');row.Name=d.id;row.Size=UDim2.new(1,-4,0,rowH-1);row.Position=UDim2.fromOffset(0,(i-1)*rowH);row.BorderSizePixel=0;row.BackgroundColor3=Color3.fromRGB(18,22,23);row.BackgroundTransparency=1;row.Parent=scroll
   local font=side<180 and 10 or math.clamp(rowH*.86,11,19)
   text(row,'Name',d.label,4,0,side*.58-9,rowH-1,font)
   local value=d.id=='ShopPricePercent' and string.format('×%.2f',data.modifier) or Stats.format(d,values[d.id])
   local v=text(row,'Value',value,side*.58-5,0,side*.42-23,rowH-1,font,M.statColor(d.id,d.id=='ShopPricePercent' and (data.modifier-1)*100 or values[d.id],d.base));v.TextXAlignment=Enum.TextXAlignment.Right
  end
  if paged then
   local py=statsH-8-pagerH
   btn(stats,'PreviousStats','‹',10,py,pagerW,pagerH,function() self.statPage=page>1 and page-1 or pages;refresh() end,true)
   text(stats,'StatPage',page..' / '..pages,16+pagerW,py,side-32-pagerW*2,pagerH,tap>0 and 16 or 12)
   btn(stats,'NextStats','›',side-10-pagerW,py,pagerW,pagerH,function() self.statPage=page<pages and page+1 or 1;refresh() end,true)
  end
  local narrow=leftW<500
  heading(left,'ShopTitle','Shop (Wave '..data.wave..')',0,0,leftW*(narrow and .62 or .39),46,30)
  local balance=Instance.new('Frame');balance.Name='Shards';balance.BackgroundTransparency=1;balance.Position=UDim2.fromOffset(leftW*(narrow and .65 or .40),0);balance.Size=UDim2.fromOffset(leftW*(narrow and .35 or .14),46);balance.Parent=left;price(balance,data.shards,'',leftW<500 and 23 or 32,white)
  -- Robux reroll sits beside the shard reroll (hidden where paid random items are restricted).
  local paid=not player:GetAttribute('PaidRandomRestricted')
  local robuxW=paid and 118 or 0
  local rerollW=narrow and leftW-(paid and robuxW+8 or 0) or math.min(232,leftW*.30)
  local rerollH=th(46)
  local reroll=btn(left,'Reroll','',narrow and 0 or leftW-rerollW,narrow and 56 or 0,rerollW,rerollH,function() self:send('Reroll') end,true)
  local free=data.freeRerolls or 0
  if free>0 then reroll.Caption.Text='FREE REROLL ×'..free else price(reroll,data.rerollPrice,'REROLL - ',20,white) end
  reroll.Interactable=(free>0 or data.shards>=data.rerollPrice) and data.phase=='Shop'
  if paid then
   local stored=player:GetAttribute('ProfileRerolls') or 0
   local rb=btn(left,'RobuxReroll',stored>0 and ('USE ×'..stored) or ('R$ '..Money.Products.ShopReroll.robux),narrow and leftW-robuxW or leftW-rerollW-8-robuxW,narrow and 56 or 0,robuxW,rerollH,function()
    if (player:GetAttribute('ProfileRerolls') or 0)>0 then combat.RunAction:FireServer('UseReroll','Shop') else combat.PurchaseRequest:FireServer('ShopReroll') end
   end)
   rb.Interactable=data.phase=='Shop'
  end
  -- Phones (tap>0) keep four columns only when each card is still 240 wide; else two rows of two.
  local top=narrow and 78+rerollH or math.max(76,rerollH+30);local cols=leftW>=(tap>0 and 1000 or 660) and 4 or leftW>=420 and 2 or 1;local cardW=(leftW-(cols-1)*12)/cols
  local buyH,lockH=th(43),th(34) -- a taller Buy makes the card taller by the same amount
  local cardH=math.max(310+buyH-43,math.min(L.CardHeight,ht-top-inventoryH-lockH-38))
  if not inventoryOnly then
   for i,o in data.offers do
    local entry=Catalog.ById[o.id];local x=((i-1)%cols)*(cardW+12);local y=top+math.floor((i-1)/cols)*(cardH+lockH+24)
    if not o.sold then
     local card=surface(left,'Offer'..i,x,y,cardW,cardH,entry.tier)
     local well=surface(card,'IconWell',12,12,64,64,nil,'inset')
     art(well,entry,4,4,56,56)
     heading(card,'Name',entry.name..(entry.weaponId and entry.tier>1 and (' '..({'I','II','III','IV'})[entry.tier]) or ''),86,12,cardW-98,43,22,tiers[entry.tier])
     local kind=entry.weaponId and Weapons.ById[entry.weaponId].home or (entry.kind..(#entry.tags>0 and ' · '..entry.tags[1] or ''))
     text(card,'Kind',kind,86,56,cardW-98,22,17,cream)
     if entry.weaponId then
      weaponStats(card,Weapons.ById[entry.weaponId],entry.tier,14,98,cardW-28)
      text(card,'Class',entry.description,14,199,cardW-28,22,17)
      local d=Stats.weapon(Weapons.ById[entry.weaponId],Stats.read(state),state:GetAttribute('Class'),entry.tier)
      local traits={};if d.projectileCount>1 then table.insert(traits,'Projectiles: '..d.projectileCount) end;if d.nativePierce>0 then table.insert(traits,'Pierce: '..d.nativePierce) end;if d.nativeBounce>0 then table.insert(traits,'Bounce: '..d.nativeBounce) end
      if d.burn>0 then table.insert(traits,'Ignites') elseif d.poison>0 then table.insert(traits,'Poisons') elseif d.slow>0 then table.insert(traits,'Slows') elseif d.lightning then table.insert(traits,'Lightning') end
      text(card,'Traits',table.concat(traits,' · '),14,225,cardW-28,30,16,tiers[entry.tier])
     else
      local used=effects(card,entry,14,98,cardW-28)
      text(card,'Description',entry.description,14,110+used,cardW-28,math.max(40,cardH-185-used-(buyH-43)),18)
     end
     local bw=math.min(136,cardW-32)
     local buy=btn(card,'Buy','', (cardW-bw)/2,cardH-16-buyH,bw,buyH,function() T.sound('ui_purchase');self:send('Buy',i,o.token) end)
     price(buy,o.price,'',30,data.shards>=o.price and white or red);buy.Interactable=data.shards>=o.price and data.phase=='Shop'
     btn(left,'Lock'..i,o.locked and 'Locked' or 'Lock',x+8,y+cardH+10,cardW-16,lockH,function() self:send('Lock',i,o.token) end,not o.locked)
    end
   end
   top+=math.ceil(4/cols)*(cardH+lockH+24)
  end
  local split=leftW>=660
  local weaponW=split and math.min(300,leftW*.32) or leftW
  local itemW=split and leftW-weaponW-24 or leftW
  if split then top=math.max(top,ht-inventoryH-12) end
  local function inventoryRegion(name,x,y,width)
   local f=Instance.new('Frame');f.Name=name;f.BackgroundTransparency=1;f.Position=UDim2.fromOffset(x,y);f.Size=UDim2.fromOffset(width,inventoryH);f.Parent=left;return f
  end
  local items=inventoryRegion('Items',0,top,itemW)
  heading(items,'Title','Items',0,0,itemW,32,28)
  local itemCols=math.max(1,math.min(8,math.floor((itemW+8)/(th(52)+8))));local cell=math.min(th(64),(itemW-(itemCols-1)*8)/itemCols)
  local anchor
  for i,it in data.items do
   local entry=Catalog.ById[it.id];local x=((i-1)%itemCols)*(cell+8);local y=40+math.floor((i-1)/itemCols)*(cell+8)
   local b=btn(items,'ItemSlot'..i,'',x,y,cell,cell,function() self.selected={kind='Item',id=it.id};refresh() end,true)
   T.setTier(b,entry.tier)
   art(b,entry,4,4,cell-8,cell-8)
   if it.count>1 then local cs=tap>0 and 16 or 14;local count=text(b,'Count','×'..it.count,cell-cs-15,cell-cs-7,cs+12,cs+4,cs);count.TextXAlignment=Enum.TextXAlignment.Right end
   if self.selected and self.selected.kind=='Item' and self.selected.id==it.id then anchor=Vector2.new(x,top+y) end
  end
  local itemBottom=math.max(inventoryH,40+math.ceil(#data.items/itemCols)*(cell+8))
  if not split then top+=itemBottom+18 end
  local wx=split and leftW-weaponW or 0
  local owned=inventoryRegion('Weapons',wx,top,weaponW)
  local count=0;for _,copy in data.weapons do if copy.id~='' then count+=1 end end
  heading(owned,'Title','Weapons ('..count..'/6)',0,0,weaponW,32,27)
  local slotSize=math.min(th(66),(weaponW-16)/3);local shown=0
  for i,copy in data.weapons do
   local base=Weapons.ById[copy.id]
   if base then
    local x=(shown%3)*(slotSize+8);local y=40+math.floor(shown/3)*(slotSize+8);shown+=1
    local b=btn(owned,'WeaponSlot'..i,'',x,y,slotSize,slotSize,function() self.selected={kind='Weapon',slot=i,copy=copy.copy};refresh() end,true)
    T.setTier(b,copy.tier)
    thumbnail(b,combat.WeaponTemplates:FindFirstChild(copy.id),7,7,slotSize-14,slotSize-14)
    T.tierBadge(b,copy.tier,slotSize-3,slotSize-3,Vector2.new(1,1))
    if self.selected and self.selected.kind=='Weapon' and self.selected.copy==copy.copy then anchor=Vector2.new(wx+x,top+y) end
   end
  end
  top+=math.max(inventoryH,40+math.ceil(shown/3)*(slotSize+8))
  local start=btn(root,'StartWave',data.ready and 'READY · WAITING' or 'GO (Wave '..data.wave..')',leftW+gap+12,statsH+10,side,startH,function() self:send('Start') end)
  start.Caption.UITextSizeConstraint.MaxTextSize=22
  if data.phase~='Shop' then start.Caption.Text='WAVE IN PROGRESS';start.Interactable=false end
  left.CanvasSize=UDim2.fromOffset(0,top+12)
  left.ScrollBarThickness=top+12>ht+1 and 3 or 0
  if self.selected and anchor then
   local sel=self.selected;local copy=sel.kind=='Weapon' and data.weapons[sel.slot];local entry=sel.kind=='Item' and Catalog.ById[sel.id];local base=copy and Weapons.ById[copy.id]
   if (base and copy.copy==sel.copy) or entry then
    local dim=Instance.new('TextButton');dim.Name='FocusBackdrop';dim.Text='';dim.AutoButtonColor=false;dim.BackgroundColor3=Color3.new(0,0,0);dim.BackgroundTransparency=.28;dim.BorderSizePixel=0;dim.Size=UDim2.fromScale(1,1);dim.ZIndex=10;dim.Parent=root
    dim.Activated:Connect(function() self.selected=nil;refresh() end)
    -- Combine/Sell (34) and Cancel (32) grow to touch size on phones; the panel grows with them.
    local b1,b2=th(34),th(32)
    local dw=math.min(324,w-20);local dh=392+(base and 2*(b1-34) or 0)+(b2-32);local visibleH=math.min(dh,ht-16)
    local cancelY=dh-12-b2;local sellY=cancelY-7-b1;local combineY=sellY-7-b1
    local dx=math.clamp(anchor.X+6+slotSize/2-dw/2,8,w-dw-8)
    local ay=anchor.Y+6-(self[inventoryOnly and 'InventoryScroll' or 'ShopScroll'] or 0)
    local dy=math.clamp(ay-visibleH-12,8,math.max(8,ht-visibleH-8))
    local outer=surface(root,'Details',dx,dy,dw,visibleH,copy and copy.tier or entry.tier);outer.ZIndex=11;outer.Active=true
    local detail=Instance.new('ScrollingFrame');detail.Name='Body';detail.BackgroundTransparency=1;detail.BorderSizePixel=0;detail.Size=UDim2.fromScale(1,1);detail.CanvasSize=UDim2.fromOffset(0,dh);detail.ScrollBarThickness=3;detail.Parent=outer
    local well=surface(detail,'IconWell',14,14,72,72,nil,'inset')
    if base then thumbnail(well,combat.WeaponTemplates:FindFirstChild(copy.id),4,4,64,64) else art(well,entry,4,4,64,64) end
    heading(detail,'Title',(base or entry).name,98,14,dw-112,44,23,tiers[copy and copy.tier or entry.tier])
    text(detail,'Tier',E.TIER_NAMES[copy and copy.tier or entry.tier],98,60,dw-112,24,tap>0 and 16 or 14)
    if base then
     weaponStats(detail,base,copy.tier,16,104,dw-32)
     text(detail,'Type',base.home..' · '..base.kind,16,193,dw-32,24,tap>0 and 16 or 14)
     local combine=btn(detail,'Combine',copy.tier==4 and 'Maximum tier' or copy.canCombine and 'Combine → '..E.TIER_NAMES[copy.tier+1] or 'Need matching weapon + tier',14,combineY,dw-28,b1,function() T.sound('ui_upgrade');self:send('Combine',sel.slot,sel.copy);self.selected=nil end,true)
     combine.Interactable=data.phase=='Shop' and copy.canCombine==true;combine.Caption.TextColor3=combine.Interactable and white or Color3.fromRGB(135,146,150)
     local sell=btn(detail,'Sell','',14,sellY,dw-28,b1,function() self:send('Sell',sel.slot,sel.copy);self.selected=nil end,true)
     price(sell,E.refund(copy.paid),'Recycle +',19,white);sell.Interactable=data.phase=='Shop'
    else
     local used=effects(detail,entry,16,104,dw-32)
     text(detail,'Description',entry.description,16,118+used,dw-32,math.max(32,dh-178-used-(b2-32)),15)
    end
    btn(detail,'Cancel','Cancel',14,cancelY,dw-28,b2,function() self.selected=nil;refresh() end,true)
   else self.selected=nil end
  end
  local key=inventoryOnly and 'InventoryScroll' or 'ShopScroll'
  task.defer(function() if left.Parent then left.CanvasPosition=Vector2.new(0,self[key] or 0);left:GetPropertyChangedSignal('CanvasPosition'):Connect(function() self[key]=left.CanvasPosition.Y end) end end)
  return data
 end
 return self
end
return M
