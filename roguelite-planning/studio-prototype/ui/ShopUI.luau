-- Presentation consumes server snapshots; never sends prices, refunds or item bonuses.
local RS=game:GetService('ReplicatedStorage')
local Http=game:GetService('HttpService')
local combat=RS:WaitForChild('RogueliteCombat')
local E=require(combat.EconomyConfig)
local Catalog=require(combat.ShopCatalog)
local Weapons=require(combat.WeaponCatalog)
local Stats=require(combat.CharacterStats)
local M={}
-- LAYOUT SETTINGS: edit these numbers in Studio, then Stop/Play to preview.
-- Heights/gaps are pixels. 0.025 means a 2.5% margin on each screen edge.
M.Layout={
 HorizontalMargin=0.025,
 HeaderTop=16,
 ContentTop=64,
 WeaponsHeight=112,
 ItemsHeight=112,
 InventoryGap=8,
 SlotGap=4,
 InventoryTitleHeight=26,
 ItemWidthShare=0.55,
 CardHeight=248,
 StatsWidth=250,
}
local white=Color3.fromRGB(240,243,239)
local green=Color3.fromRGB(145,239,20)
local red=Color3.fromRGB(255,105,105)
local tiers={white,green,Color3.fromRGB(108,184,255),Color3.fromRGB(236,171,255)}
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
 local panel,label,button=h.panel,h.label,h.button
 function self:snapshot()
  local raw=state:GetAttribute('ShopSnapshot');if not raw then return end
  local ok,data=pcall(Http.JSONDecode,Http,raw);return ok and data or nil
 end
 function self:send(action,arg,extra)
  local data=self:snapshot();if data then combat.ShopAction:FireServer(action,data.revision,arg,extra) end
 end
 state:GetAttributeChangedSignal('ShopSnapshot'):Connect(function() task.defer(refresh) end)
 local function text(p,n,t,x,y,w,ht,size,color)
  local l=label(p,n,t,x,y,w,ht,size or 14,color);l.TextXAlignment=Enum.TextXAlignment.Left;return l
 end
 local function btn(p,n,t,x,y,w,ht,fn,neutral)
  local b=button(p,n,t,x,y,w,ht,fn,neutral);b.Caption.TextSize=14;return b
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
    text(p,'Effect_'..d.id,(value>0 and '+' or '')..value..(percent and '%' or d.unit)..' '..d.label,x,y+row*22,w,22,13,M.statColor(d.id,value,0));row+=1
   end
  end
  return row*22
 end
 local function weaponStats(p,base,tier,x,y,w)
  local s=Stats.read(state);local d=Stats.weapon(base,s,state:GetAttribute('Class'),tier)
  local rows={{'Damage',string.format('%.1f',d.damage),d.damage-base.damage},{'Cooldown',string.format('%.2f s',d.cooldown),base.cooldown-d.cooldown},{'Critical chance',Stats.format(Stats.ById.CritChance,s.CritChance),s.CritChance-Stats.ById.CritChance.base},{'Range',string.format('%.1f',d.range),d.range-base.range}}
  for i,r in rows do text(p,'WeaponStat'..i,r[1]..'  '..r[2],x,y+(i-1)*21,w,21,13,r[3]>0 and green or r[3]<0 and red or white) end
 end
 function self:debug(parent,width)
  local data=self:snapshot();if not data or not data.debug then return 0 end
  local box=panel(parent,'GoldEditor',0,0,width,104)
  text(box,'Title','Developer gold · '..data.gold..' GOLD',12,7,width-24,25,18)
  local input=Instance.new('TextBox');input.Name='GoldInput';input.Position=UDim2.fromOffset(12,40);input.Size=UDim2.fromOffset(math.max(65,width*.24),38);input.Text=tostring(data.gold);input.TextSize=16;input.Font=Enum.Font.GothamBold;input.BackgroundColor3=Color3.fromRGB(25,29,30);input.TextColor3=white;input.ClearTextOnFocus=false;input.Parent=box
  local start=22+math.max(65,width*.24);local bw=(width-start-18)/4
  for i,v in {100,1000,-100} do btn(box,'Gold'..v,(v>0 and '+' or '')..v,start+(i-1)*(bw+2),40,bw,38,function() self:send('Gold','Add',v) end,true) end
  btn(box,'SetGold','SET',start+3*(bw+2),40,bw,38,function() local v=tonumber(input.Text);if v then self:send('Gold','Set',v) end end)
  text(box,'Hint','Studio only · session gold · disabled by EconomyConfig',12,80,width-24,18,11)
  local connection=state:GetAttributeChangedSignal('ShopSnapshot'):Connect(function()
   local latest=self:snapshot();if latest then box.Title.Text='Developer gold · '..latest.gold..' GOLD';if not input:IsFocused() then input.Text=tostring(latest.gold) end end
  end)
  box.Destroying:Connect(function() connection:Disconnect() end)
  return 114
 end
 function self:render(parent,width,height,inventoryOnly)
  local data=self:snapshot();if not data then text(parent,'Loading','Loading shop…',0,0,width,40,20);return end
  local L=M.Layout
  local scale=math.min(1,width/480);local w=width/scale;local ht=height/scale
  local root=Instance.new('Frame');root.Name='ShopLayout';root.BackgroundTransparency=1;root.Size=UDim2.fromOffset(w,ht);root.Parent=parent
  local scaling=Instance.new('UIScale');scaling.Scale=scale;scaling.Parent=root
  root.Position=UDim2.fromOffset((width-w*scale)/2,0)
  local side=math.clamp(w*.22,148,L.StatsWidth);local gap=10;local leftW=w-side-gap
  local left=Instance.new('ScrollingFrame');left.Name='ShopMain';left.Position=UDim2.fromOffset(0,0);left.Size=UDim2.fromOffset(leftW,ht);left.BackgroundTransparency=1;left.BorderSizePixel=0;left.ScrollBarThickness=3;left.ClipsDescendants=true;left.Parent=root
  local startH=62;local statsH=math.max(90,ht-startH-10)
  local stats=panel(root,'StatsColumn',leftW+gap,0,side,statsH)
  local secondary=self.statTab=='Secondary'
  text(stats,'Title',secondary and 'Secondary stats' or 'Primary stats',12,7,side-24,26,18)
  for i,tab in {'Primary','Secondary'} do
   local b=btn(stats,tab..'Tab',tab,9+(i-1)*(side-18)/2,36,(side-22)/2,29,function() self.statTab=tab;self.statPage=1;refresh() end,tab~=(self.statTab or 'Primary'))
   b.Caption.TextSize=side<180 and 10 or 12
  end
  local definitions={};for _,d in Stats.List do if (primary[d.id]==true)~=secondary then table.insert(definitions,d) end end
  local available=math.max(20,statsH-78)
  local perPage=math.max(1,math.floor(available/11))
  local paged=#definitions>perPage
  if paged then available=math.max(11,available-30);perPage=math.max(1,math.floor(available/11)) end
  local pages=math.ceil(#definitions/perPage);local page=math.clamp(self.statPage or 1,1,pages)
  local shown=math.min(perPage,#definitions-(page-1)*perPage);local rowH=available/shown
  local scroll=Instance.new('Frame');scroll.Name='StatRows';scroll.Position=UDim2.fromOffset(9,70);scroll.Size=UDim2.fromOffset(side-18,available);scroll.BackgroundTransparency=1;scroll.ClipsDescendants=true;scroll.Parent=stats
  local values=Stats.read(state)
  for i=1,shown do
   local d=definitions[(page-1)*perPage+i]
   local row=Instance.new('Frame');row.Name=d.id;row.Size=UDim2.new(1,-4,0,rowH-1);row.Position=UDim2.fromOffset(0,(i-1)*rowH);row.BorderSizePixel=0;row.BackgroundColor3=Color3.fromRGB(18,22,23);row.BackgroundTransparency=i%2==0 and .4 or .75;row.Parent=scroll
   local font=side<180 and 10 or math.clamp(rowH*.69,10,14)
   text(row,'Name',d.label,4,0,side*.58-9,rowH-1,font)
   local value=d.id=='ShopPricePercent' and string.format('×%.2f',data.modifier) or Stats.format(d,values[d.id])
   local v=text(row,'Value',value,side*.58-5,0,side*.42-23,rowH-1,font,M.statColor(d.id,d.id=='ShopPricePercent' and (data.modifier-1)*100 or values[d.id],d.base));v.TextXAlignment=Enum.TextXAlignment.Right
  end
  if paged then
   btn(stats,'PreviousStats','‹',10,statsH-33,32,25,function() self.statPage=page>1 and page-1 or pages;refresh() end,true)
   text(stats,'StatPage',page..' / '..pages,48,statsH-33,side-96,25,12)
   btn(stats,'NextStats','›',side-42,statsH-33,32,25,function() self.statPage=page<pages and page+1 or 1;refresh() end,true)
  end
  h.icon(left,'GoldBag',4,0,38,'bag');text(left,'Gold',tostring(data.gold)..' GOLD',46,0,leftW*.4-40,38,20)
  local reroll=btn(left,'Reroll','REROLL · '..data.rerollPrice..' GOLD',leftW*.48,0,leftW*.52,38,function() self:send('Reroll') end)
  if data.gold<data.rerollPrice or data.phase~='Shop' then reroll.ImageColor3=Color3.fromRGB(105,105,105);reroll.Caption.TextColor3=red end
  local top=46;local cols=leftW>=660 and 4 or 2;local cardW=(leftW-(cols-1)*8)/cols;local cardH=math.max(230,L.CardHeight)
  if not inventoryOnly then
   for i,o in data.offers do
    local entry=Catalog.ById[o.id];local x=((i-1)%cols)*(cardW+8);local y=top+math.floor((i-1)/cols)*(cardH+8)
    local card=panel(left,'Offer'..i,x,y,cardW,cardH)
    art(card,entry,8,7,52,52)
    text(card,'Name',entry.name,65,8,cardW-75,40,16,tiers[entry.tier])
    text(card,'Kind',E.TIER_NAMES[entry.tier]..' · '..entry.kind,12,62,cardW-24,22,12,tiers[entry.tier])
    if entry.weaponId then
     weaponStats(card,Weapons.ById[entry.weaponId],entry.tier,12,89,cardW-24)
     text(card,'Class',entry.description,12,173,cardW-24,27,12)
    else
     local used=effects(card,entry,12,88,cardW-24)
     text(card,'Description',entry.description,12,93+used,cardW-24,math.max(24,103-used),12)
    end
    local buy=btn(card,'Buy',o.sold and 'SOLD' or 'BUY · '..o.price,9,cardH-42,cardW-70,33,function() if not o.sold then self:send('Buy',i,o.token) end end)
    buy.Caption.TextSize=13
    if o.sold or data.gold<o.price or data.phase~='Shop' then buy.ImageColor3=Color3.fromRGB(95,95,95);buy.Caption.TextColor3=o.sold and white or red end
    local lock=btn(card,'Lock',o.locked and 'LOCKED' or 'LOCK',cardW-61,cardH-42,52,33,function() if not o.sold then self:send('Lock',i,o.token) end end,true);lock.Caption.TextSize=10;lock.Caption.TextColor3=o.locked and green or white
   end
   top+=math.ceil(4/cols)*(cardH+8)
  end
  if self.selected or inventoryOnly then
   local detailWidth=inventoryOnly and leftW or math.min(460,leftW-16)
   local detail=panel(inventoryOnly and left or root,'Details',inventoryOnly and 0 or 8,inventoryOnly and top or 46,detailWidth,246)
   detail.ZIndex=5;detail.Active=true
   local leftW=detailWidth
   btn(detail,'BackOffers','← Offers',leftW-105,8,96,30,function() self.selected=nil;refresh() end,true)
   local sel=self.selected
   if sel and sel.kind=='Weapon' then
    local copy=data.weapons[sel.slot];local base=copy and Weapons.ById[copy.id]
    if base and copy.copy==sel.copy then
     text(detail,'Title',base.name..' · '..E.TIER_NAMES[copy.tier],14,10,leftW-130,30,20,tiers[copy.tier])
     thumbnail(detail,combat.WeaponTemplates:FindFirstChild(copy.id),12,48,100,108)
     weaponStats(detail,base,copy.tier,125,49,leftW-139)
     text(detail,'Type',base.home..' · '..base.kind,125,138,leftW-139,24,14)
     local effect=base.id=='11' and 'Explosive splash' or base.burn>0 and 'Ignites targets' or base.slow>0 and 'Slows targets' or base.poison>0 and 'Poisons targets' or base.lightning and 'Lightning chains' or 'Uses your compatible character effects'
     text(detail,'Special',effect,14,166,leftW-28,25,13)
     text(detail,'Paid','Paid '..copy.paid..' GOLD · Wave '..copy.wave,14,195,leftW-170,36,12)
     btn(detail,'Sell','SELL +'..E.refund(copy.paid)..' GOLD',leftW-159,198,148,36,function() self:send('Sell',sel.slot,sel.copy);self.selected=nil end)
    else self.selected=nil;text(detail,'Empty','Select a weapon below.',14,58,leftW-28,40,18) end
   elseif sel and sel.kind=='Item' then
    local entry=Catalog.ById[sel.id];text(detail,'Title',entry.name,14,10,leftW-130,40,20,tiers[entry.tier]);art(detail,entry,12,60,80,80)
    effects(detail,entry,108,60,leftW-122);text(detail,'Description',entry.description..' · Maximum '..entry.cap..' copies',14,154,leftW-28,72,15)
   else text(detail,'Title','Your equipment',14,16,leftW-145,30,22);text(detail,'Hint','Select a weapon to inspect or sell. Select an item to see its bonuses.',14,60,leftW-28,100,18) end
   if inventoryOnly then top+=254 end
  end
  local split=leftW>=700;local itemW=split and math.floor(leftW*L.ItemWidthShare)-L.InventoryGap/2 or leftW
  local itemHeight=math.max(92,L.ItemsHeight);local weaponHeight=math.max(92,L.WeaponsHeight)
  local titleH=L.InventoryTitleHeight
  local items=panel(left,'Items',0,top,itemW,itemHeight);text(items,'Title','Items · '..#data.items..' / '..E.ITEM_CAPACITY,10,3,itemW-20,titleH-2,16)
  local cell=(itemW-22)/8
  local itemH=(itemHeight-titleH-8-L.SlotGap)/2
  for i=1,E.ITEM_CAPACITY do
   local it=data.items[i];local b=btn(items,'ItemSlot'..i,'',10+((i-1)%8)*cell,titleH+math.floor((i-1)/8)*(itemH+L.SlotGap),cell-L.SlotGap,itemH,function() if it then self.selected={kind='Item',id=it.id};refresh() end end,true)
   if it then local entry=Catalog.ById[it.id];local size=math.min(cell-10,itemH-12);art(b,entry,3,(itemH-size)/2,cell-10,size);text(b,'Count','×'..it.count,cell-25,itemH-20,21,17,12,green) end
  end
  if not split then top+=itemHeight+L.InventoryGap end
  local weaponW=split and leftW-itemW-L.InventoryGap or leftW
  local owned=panel(left,'Weapons',split and itemW+L.InventoryGap or 0,top,weaponW,weaponHeight);local count=0;for _,copy in data.weapons do if copy.id~='' then count+=1 end end
  text(owned,'Title','Weapons ('..count..'/6)',10,3,weaponW-20,titleH-2,16)
  local slotW=(weaponW-22)/3;local slotH=(weaponHeight-titleH-8-L.SlotGap)/2
  for i=1,6 do
   local copy=data.weapons[i];local base=copy and Weapons.ById[copy.id]
   local b=btn(owned,'WeaponSlot'..i,'',10+((i-1)%3)*slotW,titleH+math.floor((i-1)/3)*(slotH+L.SlotGap),slotW-L.SlotGap,slotH,function() if base then self.selected={kind='Weapon',slot=i,copy=copy.copy};refresh() end end,true)
   if base then thumbnail(b,combat.WeaponTemplates:FindFirstChild(copy.id),4,2,slotW*.36,slotH-4);text(b,'Tier','T'..copy.tier,4,1,20,13,9,tiers[copy.tier]);local l=text(b,'Name',base.name,slotW*.4,3,slotW*.6-10,slotH-6,11);l.TextXAlignment=Enum.TextXAlignment.Left
   elseif copy then text(b,'Empty','+',slotW/2-10,slotH/2-12,20,24,20)
   else b.Interactable=false;b.ImageColor3=Color3.fromRGB(110,110,110);local l=text(b,'Locked','LOCKED',5,slotH/2-10,slotW-15,20,11,Color3.fromRGB(150,157,157));l.TextXAlignment=Enum.TextXAlignment.Center end
  end
  top+=(split and math.max(itemHeight,weaponHeight) or weaponHeight)+2
  local start=btn(root,'StartWave',data.ready and 'READY · WAITING' or 'START\nWAVE '..data.wave,leftW+gap,statsH+10,side,startH,function() self:send('Start') end)
  start.Caption.TextSize=22
  if data.phase~='Shop' then start.Caption.Text='WAVE IN PROGRESS';start.ImageColor3=Color3.fromRGB(100,100,100) end
  left.CanvasSize=UDim2.fromOffset(0,top)
  local key=inventoryOnly and 'InventoryScroll' or 'ShopScroll'
  task.defer(function() if left.Parent then left.CanvasPosition=Vector2.new(0,self[key] or 0);left:GetPropertyChangedSignal('CanvasPosition'):Connect(function() self[key]=left.CanvasPosition.Y end) end end)
  return data
 end
 return self
end
return M
