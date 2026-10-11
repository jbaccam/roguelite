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
local WeaponIcons=require(RS:WaitForChild('WeaponInventoryUI')).Icons
local Signature=Stats.Signature
local M={}
-- Seconds until the shop timer starts the next wave (RogueliteRunState.ShopEndsAt, set by
-- ShopService at each wave clear), or nil when no timer runs. clock(105) = '1:45'.
function M.shopSecondsLeft()
 local state=RS:FindFirstChild('RogueliteRunState');local ends=state and state:GetAttribute('ShopEndsAt')
 if type(ends)~='number' then return nil end
 return math.max(0,math.ceil(ends-workspace:GetServerTimeNow()))
end
function M.clock(s) return string.format('%d:%02d',s//60,s%60) end
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
-- The REROLL odds note (shop and level-up): odds is {I,II,III,IV} from EconomyConfig.tierOdds or
-- LevelUpCatalog.tierOdds, the same numbers the server rolls with. Each tier in its card colour.
-- Example: oddsLine('Reroll odds per offer',{.46,.465,.075,0}) ->
-- 'Reroll odds per offer: Tier I 46% · II 47% · III 7.5% · IV 0%'.
function M.oddsLine(label,odds)
 local parts={}
 for tier=1,4 do
  local p=(odds[tier] or 0)*100
  local pct=p>=10 and string.format('%.0f%%',p) or p>=1 and string.format('%.1f%%',p):gsub('%.0%%','%%') or p>0 and string.format('%.2f%%',p) or '0%'
  local c=tiers[tier]
  table.insert(parts,string.format('<font color="#%02X%02X%02X">%s %s</font>',math.round(c.R*255),math.round(c.G*255),math.round(c.B*255),tier==1 and 'Tier I' or T.Roman[tier],pct))
 end
 return label..': '..table.concat(parts,' · ')
end
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
-- Weapon types' literal icons (2026-10-09): Blade = Katana, Blunt = Baseball Bat, Gun = Glock,
-- Thrown = Kunai, Explosive = Rocket Launcher, Elemental = Crystal Ball, Tool = Shovel, Culinary =
-- Frying Pan, Trick = Deck of Cards. The same table as ItemCardUI.TypeIcon (this module is sandboxed
-- and can't require that lobby one).
local TYPE_ICON={Blade='03',Blunt='06',Gun='00',Thrown='13',Explosive='11',Elemental='35',Tool='26',Culinary='01',Trick='18'}
M.TypeIcon=TYPE_ICON
-- Your class's own drawback on a weapon (no class-vs-class penalty since 2026-10-09): the first
-- negative of its family's damage (MeleeDamage / RangedDamage) or Damage in the class's buffs, as
-- the value and stat id, or nil. Brawler + Glock: -15, 'RangedDamage'.
local function drawback(class,w)
 local c=Stats.Classes[class];if not c or type(w)~='table' then return nil end
 for _,id in {w.kind=='Melee' and 'MeleeDamage' or 'RangedDamage','Damage'} do local v=c.buffs[id];if v and v<0 then return v,id end end
 return nil
end
-- The attack and what its damage scales with (ItemCardUI.attack's rules): 'Melee · scales with Melee Damage'.
function M.attackLine(w)
 local word=w.kind=='Melee' and 'Melee' or w.kind=='Blast' and 'Explosive' or table.find(w.types or {},'Thrown') and 'Thrown' or 'Ranged'
 local parts={w.kind=='Melee' and 'Melee Damage' or 'Ranged Damage'}
 if w.elemental then table.insert(parts,'Elemental Damage') end
 if w.utility then table.insert(parts,'Utility Power') end
 if w.kind=='Blast' then table.insert(parts,'Explosion Damage') end
 return word..' · scales with '..(#parts==1 and parts[1] or table.concat(parts,', ',1,#parts-1)..' + '..parts[#parts])
end
-- A set's step in a few words, from CharacterStats (no numbers here): setShort('Blade', 3) =
-- '+7% dmg · +4% critical chance'; 'you' flavors end '(you)': '+4% dmg · +1 armor (you)'.
function M.setShort(t,n)
 local set=Stats.TypeSets[t];if not set then return '' end
 local v=Stats.setBonus(t,n);local d=Stats.ById[set.stat]
 local out='+'..Stats.setDamage(n)..'% dmg'
 if v>0 then
  local label=string.lower(d.label);if d.unit~='%' and v==1 then label=label:gsub('s$','') end
  out..=' · +'..v..(d.unit=='%' and '%' or '')..' '..label..(set.scope=='you' and ' (you)' or '')
 end
 return out
end
function M.statColor(id,value,base)
 local delta=value-base;if id=='ShopPricePercent' or id=='ChainEvery' then delta=-delta end
 return delta>0 and green or delta<0 and red or white
end

-- BUY effect (user, 2026-10-03) ------------------------------------------------------------------
-- Once the server confirms a buy (its offer comes back sold): the card punches 6% and fades over a
-- soft glow and rays, and 3-5 copies of the bought thing's own icon (a Glock, a Spatula, a Pot Lid)
-- burst up out of it spinning, then swoop into the inventory slot it landed in, which bumps; about
-- 0.8 s. The card is copied at click time, because the redraw on the result removes it. Flat images
-- and tweens on their own layer in the ScreenGui (QuestsUI's CLAIM effect is a lobby module, which
-- this sandboxed one can't require); nothing in it takes input, and the layer goes after 1.2 s.
local TweenService=game:GetService('TweenService')
local GLOW='rbxassetid://101092695897243' -- StoreFX.Asset.glow
local RAYS='rbxassetid://75268019571051' -- StoreFX.Asset.rays
local function tween(o,time,props,style,dir)
 local tw=TweenService:Create(o,TweenInfo.new(time,style or Enum.EasingStyle.Quad,dir or Enum.EasingDirection.Out),props);tw:Play();return tw
end
local function later(t,o,fn) task.delay(t,function() if o.Parent then fn() end end) end
local function fadeOut(root,time)
 local all=root:GetDescendants();table.insert(all,root)
 for _,o in all do
  local goal={}
  if o:IsA('GuiObject') and o.BackgroundTransparency<1 then goal.BackgroundTransparency=1 end
  if o:IsA('ImageLabel') or o:IsA('ImageButton') or o:IsA('ViewportFrame') then goal.ImageTransparency=1 end
  if o:IsA('TextLabel') or o:IsA('TextButton') then goal.TextTransparency=1;goal.TextStrokeTransparency=1 end
  if o:IsA('UIStroke') then goal.Transparency=1 end
  if next(goal) then tween(o,time,goal,Enum.EasingStyle.Quad,Enum.EasingDirection.In) end
 end
end
-- Scale bump on the slot it landed in; a slot with its own UIScale is left alone.
local function bump(o,peak)
 if not (o and o.Parent) then return end
 local s=o:FindFirstChild('BuyPop')
 if not s then
  if o:FindFirstChildOfClass('UIScale') then return end
  s=T.make('UIScale',o,{Name='BuyPop',Scale=1})
 end
 tween(s,.07,{Scale=peak})
 later(.07,s,function() tween(s,.22,{Scale=1},Enum.EasingStyle.Back) end)
end
-- b: what the click saw {card (its copy), design, pos, size, well, wellSize}; find() -> the slot it
-- landed in and the shop list that clips it, looked up again as the copies fly (a redraw replaces
-- them); asset: its icon; color: its tier colour; n: copies. Positions are AbsolutePosition minus
-- the ScreenGui's own, so top-bar and safe-area insets cancel.
local function buyFX(screen,b,find,asset,color,n)
 local layer=T.make('Frame',screen,{Name='BuyFX',BackgroundTransparency=1,BorderSizePixel=0,Size=UDim2.fromScale(1,1),ZIndex=45,Active=false,Interactable=false})
 task.delay(1.2,function() layer:Destroy() end)
 local origin=screen.AbsolutePosition
 local c=b.well-origin;local base=math.max(b.wellSize,24)
 local function image(name,img,p,size,col,z)
  return T.make('ImageLabel',layer,{Name=name,BackgroundTransparency=1,Image=img,ImageColor3=col,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(p.X,p.Y),Size=UDim2.fromOffset(size,size),ZIndex=z})
 end
 -- The card: punch up 6%, settle, fade (the real one is already gone); its icon has left it.
 local g=b.card;local k=b.size.X/math.max(b.design,1);local gc=b.pos+b.size/2-origin
 for _,d in g:GetDescendants() do if d:IsA('GuiButton') then d.Active=false;d.Selectable=false;d.Interactable=false end end
 local well=g:FindFirstChild('IconWell')
 if well then for _,d in well:GetChildren() do if d:IsA('GuiObject') then d.Visible=false end end end
 g.AnchorPoint=Vector2.new(.5,.5);g.Position=UDim2.fromOffset(gc.X,gc.Y);g.ZIndex=1
 local sc=T.make('UIScale',g,{Scale=k});g.Parent=layer
 tween(sc,.07,{Scale=k*1.06})
 later(.07,sc,function() tween(sc,.2,{Scale=k},Enum.EasingStyle.Back) end)
 later(.2,g,function() fadeOut(g,.2) end)
 -- Soft glow and a sixth of a turn of rays behind the icon, growing as they fade.
 local glow=image('Glow',GLOW,c,base*1.4,color,2);glow.ImageTransparency=.15
 tween(glow,.4,{Size=UDim2.fromOffset(base*3.4,base*3.4)},Enum.EasingStyle.Quart)
 tween(glow,.45,{ImageTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
 local rays=image('Rays',RAYS,c,base*1.6,color,2);rays.ImageTransparency=.5
 tween(rays,.45,{Size=UDim2.fromOffset(base*3.2,base*3.2),Rotation=60},Enum.EasingStyle.Quart)
 tween(rays,.45,{ImageTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
 -- The copies fan up and out of the icon (0.16 s), then each swoops to the slot (0.32 s, 0.04 s
 -- apart): X eases in-out on a holder frame while Y backs in on the image inside, so they arc.
 local copies={}
 for i=1,n do
  local a=-math.pi/2+((i-.5)/n*2-1)*math.pi*.42+(math.random()*2-1)*.15;local dir=Vector2.new(math.cos(a),math.sin(a))
  local size=base*(.8+math.random()*.15);local p1=c+dir*base*(.9+math.random()*.4)
  local spin=(math.random()<.5 and -1 or 1)*(200+math.random()*160)
  local holder=T.make('Frame',layer,{Name='Copy',BackgroundTransparency=1,Position=UDim2.fromOffset(c.X,0),Size=UDim2.new(),ZIndex=3})
  local img=T.make('ImageLabel',holder,{Name='Icon',BackgroundTransparency=1,Image=asset,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(0,c.Y),Size=UDim2.fromOffset(size*.5,size*.5),Rotation=math.random(-20,20),ScaleType=Enum.ScaleType.Fit,ZIndex=3})
  tween(holder,.16,{Position=UDim2.fromOffset(p1.X,0)},Enum.EasingStyle.Quart)
  tween(img,.16,{Position=UDim2.fromOffset(0,p1.Y),Size=UDim2.fromOffset(size,size),Rotation=img.Rotation+spin*.3},Enum.EasingStyle.Quart)
  table.insert(copies,{holder=holder,img=img,p1=p1,spin=spin})
 end
 later(.16,layer,function()
  local target,clip=find()
  local goal,slot
  if target and target.Parent and target.AbsoluteSize.X>0 then
   goal=target.AbsolutePosition+target.AbsoluteSize/2-origin;slot=math.min(target.AbsoluteSize.X,target.AbsoluteSize.Y)
   -- Scrolled out of view (small screens): aim at the nearest edge of the shop list instead.
   if clip and clip.Parent then
    local lo=clip.AbsolutePosition-origin;local hi=lo+clip.AbsoluteSize
    goal=Vector2.new(math.clamp(goal.X,lo.X,hi.X),math.clamp(goal.Y,lo.Y,hi.Y))
   end
  end
  local landed=0
  for i,cp in copies do
   later((i-1)*.04,cp.holder,function()
    if not goal then
     -- Nowhere to land: drop a little and fade.
     tween(cp.img,.35,{Position=UDim2.fromOffset(0,cp.p1.Y+base*.8),ImageTransparency=1,Rotation=cp.img.Rotation+cp.spin*.5},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
     return
    end
    tween(cp.holder,.32,{Position=UDim2.fromOffset(goal.X,0)},Enum.EasingStyle.Sine,Enum.EasingDirection.InOut)
    tween(cp.img,.32,{Position=UDim2.fromOffset(0,goal.Y)},Enum.EasingStyle.Back,Enum.EasingDirection.In)
    tween(cp.img,.32,{Size=UDim2.fromOffset(slot*.6,slot*.6),Rotation=cp.img.Rotation+cp.spin},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
    later(.32,cp.holder,function()
     cp.holder:Destroy();landed+=1
     local now=find()
     bump(now,landed==1 and 1.22 or 1.1)
     if landed>1 then return end
     -- First one in: a quick glow on the slot.
     local flash=image('SlotGlow',GLOW,goal,slot*1.1,color,2);flash.ImageTransparency=.1
     tween(flash,.35,{Size=UDim2.fromOffset(slot*2.4,slot*2.4)},Enum.EasingStyle.Quart)
     tween(flash,.35,{ImageTransparency=1},Enum.EasingStyle.Quad,Enum.EasingDirection.In)
    end)
   end)
  end
 end)
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
  if player:GetAttribute('RunDown') or player:GetAttribute('RunReturning') or player:GetAttribute('RunResult')~=nil then return end
  local data=self:snapshot();if data then combat.ShopAction:FireServer(action,data.revision,arg,extra) end
 end
 -- BUY effect: what each Buy click saw (offer token -> the card copied, where its icon was), kept
 -- until a snapshot shows that offer sold; render() plays it then. A refused buy is dropped once
 -- its offer is gone (rerolled, next wave) or after 4 s.
 self.bought={}
 local function remember(card,well,i,o,data)
  local old=self.bought[o.token];if old then old.card:Destroy() end
  local unsold,copies,count=0,{},0
  for _,x in data.offers do if not x.sold and (x.token==o.token or not self.bought[x.token]) then unsold+=1 end end -- one already being bought counts as sold
  for _,w in data.weapons do copies[w.copy]=true end
  for _,it in data.items do if it.id==o.id then count=it.count end end
  self.bought[o.token]={index=i,id=o.id,wave=data.wave,t=os.clock(),last=unsold==1,copies=copies,count=count,card=card:Clone(),design=card.Size.X.Offset,
   pos=card.AbsolutePosition,size=card.AbsoluteSize,well=well.AbsolutePosition+well.AbsoluteSize/2,wellSize=well.AbsoluteSize.X}
 end
 -- Whether the bought thing is in the inventory now: one more of the item, or a weapon copy id the
 -- click didn't see. Buying the last offer refills the shop (its token goes), and so does a reroll
 -- after a refused buy; only this tells them apart.
 local function arrived(b,data)
  local entry=Catalog.ById[b.id]
  if entry and entry.weaponId then for _,w in data.weapons do if w.id==entry.weaponId and not b.copies[w.copy] then return true end end
  elseif entry then for _,it in data.items do if it.id==b.id and it.count>b.count then return true end end end
  return false
 end
 -- The confirmed buy's effect, from where its card was to the slot it landed in: the item's slot,
 -- or the weapon slot with a copy id the click didn't see (a new weapon, or the one it merged into).
 local function playBuy(b,data,parent)
  local entry=Catalog.ById[b.id];local screen=parent.Parent and parent:FindFirstAncestorOfClass('ScreenGui')
  if not (entry and screen and screen.Enabled) then b.card:Destroy();return end
  local region,slot=entry.weaponId and 'Weapons' or 'Items',nil
  if entry.weaponId then
   for k,w in data.weapons do if w.id==entry.weaponId and not b.copies[w.copy] then slot='WeaponSlot'..k;break end end
  else
   for k,it in data.items do if it.id==entry.id then slot='ItemSlot'..k;break end end
  end
  -- Looked up by name each time: a later redraw rebuilds the layout with the same names.
  local function find()
   local layout=parent:FindFirstChild('ShopLayout');local main=layout and layout:FindFirstChild('ShopMain')
   local r=main and main:FindFirstChild(region)
   return r and slot and r:FindFirstChild(slot),main
  end
  local asset=entry.weaponId and WeaponIcons[entry.weaponId] or T.Asset[entry.icon] or entry.icon
  buyFX(screen,b,find,asset,tiers[entry.tier] or white,math.clamp(2+entry.tier,3,5))
 end
 local refreshQueued=false
 local function queueRefresh()
  if refreshQueued then return end
  refreshQueued=true
  task.defer(function() refreshQueued=false;refresh() end)
 end
 state:GetAttributeChangedSignal('ShopSnapshot'):Connect(queueRefresh)
 local readyState=RS:FindFirstChild('RogueliteRunState')
 if readyState then readyState:GetAttributeChangedSignal('ShopPlayers'):Connect(queueRefresh) end
 for _,attribute in {'Shards','BaggedShards','RunLevel','PendingLevelUps'} do
  state:GetAttributeChangedSignal(attribute):Connect(queueRefresh)
 end
 player:GetAttributeChangedSignal('ProfileRerolls'):Connect(function() task.defer(refresh) end)
 for _,attribute in {'RunDown','RunReturning','RunResult'} do
  player:GetAttributeChangedSignal(attribute):Connect(function()
   if player:GetAttribute('RunDown') or player:GetAttribute('RunReturning') or player:GetAttribute('RunResult')~=nil then
    self.selected=nil
    if self.rerollConfirm then self.rerollConfirm.Close() end
    if self.leaveConfirm then self.leaveConfirm.Close() end
   end
  end)
 end
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
 -- The complete price (text + crystal) is centered as one measured group. icon: another image in
 -- place of the crystal (the crystal bag).
 local function price(parent,value,prefix,size,color,icon)
  size=math.floor(math.max(9,math.min(size,(parent.Size.X.Offset-20)/(#((prefix or '')..tostring(value))*.65+1.2))))
  local group=Instance.new('Frame');group.Name='PriceGroup';group.BackgroundTransparency=1;group.AutomaticSize=Enum.AutomaticSize.X;group.Size=UDim2.fromOffset(0,size+4);group.AnchorPoint=Vector2.new(.5,.5);group.Position=UDim2.fromScale(.5,.5);group.Parent=parent
  local layout=Instance.new('UIListLayout');layout.FillDirection=Enum.FillDirection.Horizontal;layout.VerticalAlignment=Enum.VerticalAlignment.Center;layout.Padding=UDim.new(0,6);layout.Parent=group
  local amount=text(group,'Price',(prefix or '')..tostring(value),0,0,0,size+4,size,color);amount.Font=Enum.Font.FredokaOne;amount.UITextSizeConstraint:Destroy();amount.TextScaled=false;amount.TextWrapped=false;amount.AutomaticSize=Enum.AutomaticSize.None;amount.Size=UDim2.fromOffset(math.ceil(game:GetService('TextService'):GetTextSize(amount.Text,size,Enum.Font.FredokaOne,Vector2.new(10000,1000)).X)+4,size+8);amount.TextStrokeTransparency=.4;amount.LayoutOrder=1
  local crystal=icon and T.icon(group,'BagIcon',0,0,size+2,icon) or shard(group,0,0,size+2);crystal.LayoutOrder=2
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
 -- Specialty, types and sets (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md;
 -- they replaced the class tag, the class-fit badge and its sentence). Every number comes from
 -- CharacterStats: S.specialty, S.setBonusText / S.setDamage / S.setBonus and S.typeLines.
 local TS=game:GetService('TextService')
 local function readableHeight(sentence,size,w,minimum)
  local visibleScale=math.min(1,9/minText)
  return math.max(minimum or 0,math.ceil(TS:GetTextSize(sentence,size,T.Body,Vector2.new(math.max(20,w*visibleScale*.9),1000)).Y/visibleScale)+8)
 end
 local function rich(color,s) return string.format('<font color="#%02X%02X%02X">%s</font>',math.round(color.R*255),math.round(color.G*255),math.round(color.B*255),s) end
 local function plain(s) return (s:gsub('<[^>]->','')) end
 -- Equipped copies by type now: S.typeCounts of the snapshot's weapon slots.
 local function equippedIds(data) local ids={};for _,w in data.weapons do if w.id~='' then table.insert(ids,w.id) end end;return ids end
 -- One bar under a weapon's name: lime '+10% DAMAGE · CHEF SPECIALTY' on your class's weapons, red
 -- '-15% RANGED DMG · BRAWLER DRAWBACK' when your class's own drawback hits it, else cream
 -- 'GUNNER WEAPON · NO PENALTY'. Named SpecBar, attribute Kind = specialty / drawback / neutral / godly.
 local function specBar(p,base,x,y,w,h)
  local class=state:GetAttribute('Class')
  local kind,text,icon,short -- short: the words for narrow cards
  if base.godly then kind,text='godly','GODLY · ANY CLASS'
  elseif Stats.specialty(base,class)>0 then kind,text,short,icon='specialty','+'..Stats.Specialty..'% DAMAGE · '..string.upper(class)..' SPECIALTY','+'..Stats.Specialty..'% DMG · SPECIALTY',WeaponIcons[Signature[class]]
  else
   local v,id=drawback(class,base)
   local what=v and string.upper(Stats.ById[id].label):gsub(' DAMAGE$',' DMG')
   if v then kind,text,short='drawback',v..'% '..what..' · '..string.upper(class)..' DRAWBACK',v..'% '..what..' · DRAWBACK'
   else kind,text,short,icon='neutral',string.upper(base.class)..' WEAPON · NO PENALTY',string.upper(base.class)..' · NO PENALTY',WeaponIcons[Signature[base.class]] end
  end
  local top,bottom,ink
  if kind=='specialty' then top,bottom,ink=Color3.fromRGB(63,125,16),Color3.fromRGB(36,77,8),Color3.fromRGB(234,255,208)
  elseif kind=='drawback' then top,bottom,ink=Color3.fromRGB(109,30,36),Color3.fromRGB(67,18,22),Color3.fromRGB(255,212,212)
  else top,bottom,ink=Color3.fromRGB(74,69,53),Color3.fromRGB(44,42,32),cream end
  local b=Instance.new('Frame');b.Name='SpecBar';b.Position=UDim2.fromOffset(x,y);b.Size=UDim2.fromOffset(w,h);b.BackgroundColor3=Color3.new(1,1,1);b.BorderSizePixel=0;b.Parent=p
  b:SetAttribute('Kind',kind);b:SetAttribute('WeaponId',base.id)
  T.make('UICorner',b,{CornerRadius=UDim.new(0,8)});T.make('UIStroke',b,{Color=Color3.fromRGB(8,10,11),Thickness=2})
  T.make('UIGradient',b,{Rotation=90,Color=ColorSequence.new(top,bottom)})
  local is=icon and h-6 or 0
  local size=math.max(math.floor(h*.6),minText)
  -- 25% slack: small shop scales draw the 9 px floor wider than the design-size measure.
  local tw=TS:GetTextSize(text,size,T.Font,Vector2.new(4000,100)).X*1.25
  if short and tw+(icon and is+6 or 0)>w-12 then text=short;tw=TS:GetTextSize(text,size,T.Font,Vector2.new(4000,100)).X*1.25 end
  local x0=math.max(6,(w-(tw+(icon and is+6 or 0)))/2)
  if icon and x0+is+6+tw<=w-4 then T.icon(b,'Icon',x0,3,is,icon) else is=0 end
  local l=T.label(b,'Text',text,is>0 and x0+is+6 or 6,0,is>0 and w-(x0+is+6)-4 or w-12,h,size,ink);l.TextStrokeTransparency=.5;l.TextWrapped=false
  if is==0 then l.TextXAlignment=Enum.TextXAlignment.Center end
  l.FitText.MinTextSize=math.min(size,9)
  return b
 end
 -- A type's line. after=true (offers): what you'd have after buying one more copy, with the old
 -- step muted: 'Blade 2 -> 3' and '+7% damage and +4% crit chance on Blade weapons (now +4% damage)'.
 -- after=false (the inventory popup): what you have now.
 local function typeLine(t,n,after)
  local strip=function(s) return (s:gsub('^'..t..' %d+: ','')) end
  if not after then
   return n>=2 and rich(green,strip(Stats.setBonusText(t,n))) or rich(cream,'No bonus yet. Sets start at 2.')
  end
  local a=n+1
  if n>=6 then return rich(T.Color.gold,'Set is full (6)') end
  if a<2 then return rich(cream,'1 more '..t..' weapon for: '..strip(Stats.setBonusText(t,2))) end
  return rich(green,strip(Stats.setBonusText(t,a)))..rich(T.Color.muted,n>=2 and ' (now +'..Stats.setDamage(n)..'% damage)' or ' (new)')
 end
 local function typeLineHeight(t,n,after,w) return readableHeight(plain(typeLine(t,n,after)),math.max(15,minText),w) end
 -- Six diamonds: filled for copies held, the outlined one is the copy this buy adds.
 local function pips(p,name,x,y,n,nextOne)
  for k=1,6 do
   local on=k<=n;local nx=nextOne==k
   local d=Instance.new('Frame');d.Name=name..k;d.AnchorPoint=Vector2.new(.5,.5);d.Position=UDim2.fromOffset(x+(k-1)*13+5,y);d.Size=UDim2.fromOffset(8,8);d.Rotation=45;d.BorderSizePixel=0
   d.BackgroundColor3=on and green or nx and Color3.fromRGB(26,32,36) or Color3.fromRGB(58,66,70);d.Parent=p
   T.make('UIStroke',d,{Color=nx and green or Color3.fromRGB(8,10,11),Thickness=nx and 2 or 1.5})
  end
 end
 -- One row per type of `base`: chip (literal icon), diamonds, 'n -> n+1' (or the count), then its
 -- line. Returns the height used.
 local function typeRows(p,base,x,y,w,counts,after)
  local y0=y;local ts=math.max(15,minText)
  for _,t in base.types or {} do
   local n=counts[t] or 0
   local _,cw=T.tag(p,'TypeChip_'..t,string.upper(t),x,y,{h=28,size=15,icon=WeaponIcons[TYPE_ICON[t]],maxW=w-90})
   local stepText=after and (n..' → '..math.min(n+1,6)) or tostring(n)
   local step=heading(p,'TypeStep_'..t,stepText,x+w-84,y,84,28,20,after and n<6 and green or white);step.TextXAlignment=Enum.TextXAlignment.Right
   if cw+8<=w-84-86 then pips(p,'TypePip_'..t..'_',x+w-84-86,y+14,n,after and n<6 and n+1 or nil) end
   local line=typeLine(t,n,after);local lh=typeLineHeight(t,n,after,w)
   local l=text(p,'TypeLine_'..t,line,x+2,y+31,w-2,lh,ts,white);l.RichText=true;l.TextYAlignment=Enum.TextYAlignment.Top
   y+=31+lh+4
  end
  return y-y0
 end
 local function typeRowsHeight(base,w,counts,after)
  local h=0;for _,t in base.types or {} do h+=31+typeLineHeight(t,counts[t] or 0,after,w)+4 end;return h
 end
 -- sets: S.typeCounts to show the stats with (an offer counts itself; nil = no type sets). The
 -- damage includes the specialty and the set damage; Critical includes the Blade set.
 local function weaponStats(p,base,tier,x,y,w,sets)
  local s=Stats.read(state);local d=Stats.weapon(base,s,state:GetAttribute('Class'),tier,sets);local ws=Stats.weaponStats(s,d)
  local rows={{'Damage',string.format('%.1f',d.damage),d.damage-base.damage},{'Cooldown',string.format('%.2f s',d.cooldown),base.cooldown-d.cooldown},{'Critical',string.format('x%.1f (%s)',s.CritDamage/100,Stats.format(Stats.ById.CritChance,ws.CritChance)),ws.CritChance-Stats.ById.CritChance.base},{'Range',string.format('%.1f',d.range),d.range-base.range}}
  for i,r in rows do
   local color=r[3]>0 and green or r[3]<0 and red or white
   local l=text(p,'WeaponStat'..i,string.format('<font color="#EADDA7">%s:</font> <font color="#%02X%02X%02X">%s</font>',r[1],math.round(color.R*255),math.round(color.G*255),math.round(color.B*255),r[2]),x,y+(i-1)*24,w,24,19)
   l.RichText=true
  end
  return #rows*24 -- the height used, so whatever comes next starts below it
 end
 -- The weapon's own traits in one line: 'Projectiles: 2 · Pierce: 1 · Ignites', '' when none. A
 -- slow shows its real numbers, as CombatEffectsService applies them (the weapon's own slow,
 -- WeaponCatalog.SlowById, or your slow stats, whichever is bigger): Medusa 'Slows 35% for 2 s'.
 local function traitLine(base,tier,sets)
  local s=Stats.read(state);local d=Stats.weapon(base,s,state:GetAttribute('Class'),tier,sets)
  d.projectileCount+=(d.typeBonus and d.typeBonus.ProjectileCount or 0) -- the Gun set's projectile
  -- The Duck's spray and the Washer's stream hit everything in their cone, so they never show
  -- Pierce or Bounce (2026-10-09; their old bounce / pierce traits did nothing).
  local cone=base.id=='17' or base.id=='29' or base.trait=='spray' or base.trait=='stream'
  local traits={};if d.projectileCount>1 then table.insert(traits,'Projectiles: '..d.projectileCount) end;if d.nativePierce>0 and not cone then table.insert(traits,'Pierce: '..d.nativePierce) end;if d.nativeBounce>0 and not cone then table.insert(traits,'Bounce: '..d.nativeBounce) end
  local slowText
  if d.slow>0 then
   local pct=math.min(70,math.max(s.SlowStrength,d.slowStrength or 0));local secs=math.max(s.SlowDuration,d.slowFor or 0)*Stats.mult(s.Duration)
   slowText=string.format('Slows %d%% for %s s',math.round(pct),(string.format('%.1f',secs):gsub('%.0$','')))
  end
  if d.burn>0 then table.insert(traits,'Ignites') elseif d.poison>0 then table.insert(traits,'Poisons') elseif slowText then table.insert(traits,slowText) elseif d.lightning then table.insert(traits,'Lightning') end
  return table.concat(traits,' · ')
 end
 -- "Works with" (user, 2026-10-03: which of my weapons does this item affect?) for items only some
 -- weapons use, from the server's own rule (ShopCatalog.worksWith -> CharacterStats.usesStat).
 -- Green 'Works with: Glock, Magic Staff', 'Works with all your weapons', or a red 'None of your
 -- weapons use this' (after selling the last one). nil for items that help every build.
 local function worksLine(entry,data)
  local ids,unique,n={},{},0
  for _,w in data.weapons do if w.id~='' then table.insert(ids,w.id);if not unique[w.id] then unique[w.id]=true;n+=1 end end end
  local works=Catalog.worksWith(entry,ids,Stats.read(state));if not works then return nil end
  if #works==0 then return 'None of your weapons use this',red end
  if n>1 and #works==n then return 'Works with all your weapons',green end
  local names={};for _,id in works do table.insert(names,Weapons.ById[id].name) end
  return 'Works with: '..table.concat(names,', '),green
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
   if height<450 then scale=math.max(.55,math.min(scale,(height-96)/277));tap=math.ceil(40/scale) end
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
  -- Under the stats: LEAVE RUN (between waves; tap twice) above GO.
  local startH=th(62);local leaveH=th(40);local statsH=math.max(90,ht-startH-leaveH-18)
  -- A party's headshots between LEAVE RUN and GO (ReadyRoster below), only while 2+ are counted.
  local partyState=RS:FindFirstChild('RogueliteRunState')
  local rosterH=data.phase=='Shop' and (partyState and partyState:GetAttribute('ShopPlayers') or 0)>1 and th(76) or 0
  if rosterH>0 then statsH=math.max(90,statsH-rosterH-8) end
  local stats=surface(root,'StatsColumn',leftW+gap+12,0,side,statsH)
  local secondary=self.statTab=='Secondary'
  local statTitle=heading(stats,'Title','Stats',12,10,side-24,34,28);statTitle.TextXAlignment=Enum.TextXAlignment.Center
  local tabH=th(32)
  -- SETS (2026-10-09): each equipped weapon type with its copies, current bonus and next step, most
  -- copies first. Pinned above the stats when it takes at most half the column (desktop); else a
  -- third tab, Sets, with one line per type (phones).
  local lines=Stats.typeLines(equippedIds(data))
  table.sort(lines,function(a,b) if a.count~=b.count then return a.count>b.count end return table.find(Weapons.Types,a.type)<table.find(Weapons.Types,b.type) end)
  local setsH=30+#lines*64+4
  local pinned=#lines>0 and tap==0 and setsH<=(statsH-52)*.5
  local function setRows(parent,y,w,compact)
   local y0=y
   for _,r in lines do
    local rh=compact and 78 or 64;local on=r.count>=2
    local f=Instance.new('Frame');f.Name='Set_'..r.type;f.Position=UDim2.fromOffset(0,y);f.Size=UDim2.fromOffset(w,rh-4);f.BorderSizePixel=0
    f.BackgroundColor3=on and Color3.fromRGB(26,32,36) or Color3.fromRGB(21,25,28);f.Parent=parent
    T.make('UICorner',f,{CornerRadius=UDim.new(0,8)});T.make('UIStroke',f,{Color=Color3.fromRGB(8,10,11),Thickness=2})
    f:SetAttribute('Count',r.count)
    local is=compact and 24 or 34;local nx=compact and 36 or 48
    T.icon(f,'Icon',6,compact and 4 or 6,is,WeaponIcons[TYPE_ICON[r.type]])
    heading(f,'Type',string.upper(r.type),nx,compact and 2 or 4,w-nx-50,24,compact and 16 or 18,on and white or T.Color.muted)
    local c=heading(f,'Count',tostring(r.count),w-46,2,38,28,compact and 20 or 24,on and green or T.Color.muted);c.TextXAlignment=Enum.TextXAlignment.Right
    local now=on and M.setShort(r.type,r.count) or (compact and ('1 more: '..M.setShort(r.type,2)) or 'No bonus yet. Sets start at 2.')
    text(f,'Bonus',now,compact and 8 or nx,compact and 25 or 29,w-(compact and 16 or nx+8),compact and 48 or 17,compact and math.max(13,minText) or 14,on and green or cream)
    if not compact and r.next then
     text(f,'Next',(on and 'Next at ' or 'At ')..r.next..': '..M.setShort(r.type,r.next),nx,45,w-nx-8,15,13,T.Color.muted)
    elseif not compact then text(f,'Next','Full set',nx,45,w-nx-8,15,13,T.Color.gold) end
    y+=rh
   end
   return y-y0
  end
  local tabsY=52
  if pinned then
   heading(stats,'SetsTitle','SETS',12,tabsY,60,26,18,green)
   text(stats,'SetsNote','equipped copies',72,tabsY+5,side-84,18,13,T.Color.muted)
   local box=T.frame(stats,'Sets',9,tabsY+30,side-18,#lines*64)
   setRows(box,0,side-18,false)
   tabsY+=setsH
  end
  local tabList=(pinned or #lines==0) and {'Primary','Secondary'} or {'Primary','Secondary','Sets'}
  local showSets=self.statTab=='Sets' and #tabList==3 -- kept when a resize pins the sets again
  local current=showSets and 'Sets' or secondary and 'Secondary' or 'Primary'
  local n=#tabList;local tw=(side-18-(n-1)*4)/n
  for i,tab in tabList do
   local short=side<180 or n==3
   local b=btn(stats,tab..'Tab',short and (tab=='Primary' and 'Main' or tab=='Secondary' and 'Extra' or 'Sets') or tab,9+(i-1)*(tw+4),tabsY,tw,tabH,function() self.statTab=tab;self.statPage=1;refresh() end,tab~=current)
   b.Caption.UITextSizeConstraint.MaxTextSize=side<180 and 12 or 18
  end
  local definitions={};if not showSets then for _,d in Stats.List do if (primary[d.id]==true)~=secondary then table.insert(definitions,d) end end end
  if showSets then
   local list=Instance.new('ScrollingFrame');list.Name='SetRows';list.Position=UDim2.fromOffset(9,tabsY+tabH+6);list.Size=UDim2.fromOffset(side-18,math.max(0,statsH-(tabsY+tabH+6)-8))
   list.BackgroundTransparency=1;list.BorderSizePixel=0;list.ScrollBarThickness=3;list.ScrollBarImageColor3=green;list.VerticalScrollBarInset=Enum.ScrollBarInset.None;list.Parent=stats
   list.CanvasSize=UDim2.fromOffset(0,setRows(list,0,side-24,true))
  end
  -- Rows fill the space between the tabs and the pager (never past the panel); each row at least
  -- 18 layout px and 13 px on screen.
  local rowsTop=tabsY+tabH+6;local rowMin=math.max(18,13/scale);local pagerH,pagerW=th(25),th(32)
  local available=statsH-rowsTop-8
  local perPage=math.max(1,math.floor(available/rowMin))
  local paged=#definitions>perPage
  if paged then available-=pagerH+5;perPage=math.max(1,math.floor(available/rowMin)) end
  if available<rowMin then perPage=math.max(1,#definitions);paged=false end -- too short for any row
  local pages=math.max(1,math.ceil(#definitions/perPage));local page=math.clamp(self.statPage or 1,1,pages)
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
  -- Past the win (RogueliteRunState.Won), the shop is Endless's.
  local runState=RS:FindFirstChild('RogueliteRunState');local won=runState~=nil and runState:GetAttribute('Won')==true
  heading(left,'ShopTitle',won and ('Endless (Wave '..data.wave..')') or ('Shop (Wave '..data.wave..')'),0,0,leftW*(narrow and .62 or .39),46,30,won and T.Color.gold or nil)
  -- Robux reroll sits beside the shard reroll (hidden where paid random items are restricted).
  local paid=not player:GetAttribute('PaidRandomRestricted')
  local oddsExtra=0
  local robuxW=paid and 118 or 0
  local rerollW=narrow and leftW-(paid and robuxW+8 or 0) or math.min(232,leftW*.30)
  local rerollH=th(46)
  local reroll=btn(left,'Reroll','',narrow and 0 or leftW-rerollW,narrow and 56 or 0,rerollW,rerollH,function() self:send('Reroll') end,true)
  local free=data.freeRerolls or 0
  if free>0 then reroll.Caption.Text='FREE REROLL ×'..free else price(reroll,data.rerollPrice,'REROLL - ',20,white) end
  reroll.Interactable=(free>0 or data.shards>=data.rerollPrice) and data.phase=='Shop'
  if paid then
   local stored=player:GetAttribute('ProfileRerolls') or 0
   local rb=btn(left,'RobuxReroll',stored>0 and ('TOKEN ×'..stored) or ('R$ '..Money.price('ShopReroll')),narrow and leftW-robuxW or leftW-rerollW-8-robuxW,narrow and 56 or 0,robuxW,rerollH,function()
    local screen=root:FindFirstAncestorOfClass('ScreenGui')
    if self.rerollConfirm or not screen then return end
    local using=(player:GetAttribute('ProfileRerolls') or 0)>0
    local win;local phaseConnection
    win=T.window(screen,'RerollConfirm','Shop Reroll',500,286,function()
     self.rerollConfirm=nil;if phaseConnection then phaseConnection:Disconnect() end
    end)
    self.rerollConfirm=win
    T.label(win.Body,'Question',using and 'Use 1 reroll token?' or 'Buy 1 shop reroll?',0,0,464,42,28)
    T.text(win.Body,'Details','Replaces every unlocked shop offer now. Locked offers stay. Use between waves while shopping.',8,52,448,72,21,cream)
    T.button(win.Body,'Cancel','CANCEL',0,152,224,58,function() win.Close() end,true)
    T.button(win.Body,'Confirm',using and 'USE 1 TOKEN' or ('BUY · R$ '..Money.price('ShopReroll')),240,152,224,58,function()
     local latest=self:snapshot();win.Close()
     if not latest or latest.phase~='Shop' or player:GetAttribute('RunDown') or player:GetAttribute('RunReturning') or player:GetAttribute('RunResult')~=nil then return end
     -- Never turn a token confirmation into a purchase if its balance changed while open.
     if using then
      if (player:GetAttribute('ProfileRerolls') or 0)>0 then combat.RunAction:FireServer('UseReroll','Shop') end
     else combat.PurchaseRequest:FireServer('ShopReroll') end
    end)
    if runState then phaseConnection=runState:GetAttributeChangedSignal('Phase'):Connect(function() if runState:GetAttribute('Phase')~='Shop' then win.Close() end end) end
   end)
   rb.Interactable=data.phase=='Shop'
   -- Odds note under the reroll buttons (in the gap above the cards): each new offer's tier chance at
   -- this wave and Luck. Wide: right-aligned in the 30 px under the buttons; narrow: the 22 px row.
   local luck=Stats.read(state).Luck
   local nw=narrow and leftW or math.min(leftW*.6,560)
   local oddsText=M.oddsLine('Reroll odds per offer',E.tierOdds(data.wave,luck))
   local oddsSize=math.max(narrow and 13 or 15,minText)
   local oldHeight=narrow and 18 or 20
   -- Font-size constraints apply at rendered size. Measure the available screen width,
   -- then convert height back into layout pixels; reserve slack for rich-text rounding.
   local oddsHeight=math.max(oldHeight,math.ceil(TS:GetTextSize(oddsText:gsub('<[^>]->',''),oddsSize,T.Body,Vector2.new(math.max(20,(nw-8)*math.min(1,scale)*.9),1000)).Y/math.min(1,scale))+6)
   oddsExtra=oddsHeight-oldHeight
   local note=text(left,'RerollOdds',oddsText,leftW-nw,narrow and 58+rerollH or rerollH+5,nw,oddsHeight,oddsSize,cream)
   note.RichText=true;note.TextScaled=false;note.TextSize=oddsSize;note.TextWrapped=true
   note.TextXAlignment=narrow and Enum.TextXAlignment.Left or Enum.TextXAlignment.Right
  end
  -- Crystals, and right beside them the crystal bag (Brotato's material bag, user 2026-10-03): what
  -- was left on the ground when the last wave ended. Shown only while it holds some (an empty bag
  -- hides), with a plain caption beside it. Example: '439 [crystal]  30 [bag]'. Between the title and
  -- the reroll buttons (or its own row, below); each amount sized by price()'s own fit rule.
  local bag=data.baggedShards or 0
  local bx0=leftW*(narrow and .65 or .40)
  local function shardsBox(name,x,width,value,size,color,icon)
   local f=Instance.new('Frame');f.Name=name;f.BackgroundTransparency=1;f.Position=UDim2.fromOffset(x,0);f.Size=UDim2.fromOffset(width,46);f.Parent=left
   price(f,value,'',size,color,icon);return f
  end
  local bagRow=0 -- extra layout px the bag row adds above the cards
  -- The caption sits right beside the bag, centred on it (play-test 2026-10-10: under the title, far
  -- left, it didn't read as the bag's). Wide screens with room keep the bag after the crystals in
  -- the header, the caption in the gap before the reroll buttons (two lines at most; 1920x1080 has
  -- about 290 px). Elsewhere the bag moves to its own row above the cards with the caption beside
  -- it: '[bag] 30  Missed crystals. ...' (1440x900 and smaller, phones).
  local caption="Missed crystals. Your next pickups pay double until it's empty."
  local fs=math.max(16,minText)
  local inline=false
  if bag>0 and not narrow then
   local bx1=math.max(bx0+leftW*.14,leftW-rerollW-(paid and robuxW+8 or 0)-8)
   local a,b=#tostring(data.shards)*.65+1.2,#tostring(bag)*.65+1.2
   local ss=math.max(12,math.min(32,math.floor((bx1-bx0-44)/(a+b))))
   local sw,bw=20+ss*a,20+ss*b
   local cx=bx0+sw+4+bw+2;local cw=bx1-cx
   if cw>=160 and TS:GetTextSize(caption,fs,T.Body,Vector2.new(cw-6,1000)).Y+4<=46 then
    inline=true
    shardsBox('Shards',bx0,sw,data.shards,ss,white)
    shardsBox('Bag',bx0+sw+4,bw,bag,ss,cream,T.Asset.shardBag)
    text(left,'BagNote',caption,cx,0,cw,46,fs,cream)
   end
  end
  if not inline then
   shardsBox('Shards',bx0,leftW*(narrow and .35 or .14),data.shards,narrow and 23 or 32,white)
   if bag>0 then
    -- price()'s fit rule sizes the box, so the amount keeps its size; the caption starts at its edge.
    local bs=narrow and 22 or 26
    local bw=20+bs*(#tostring(bag)*.65+1.2);local cw=leftW-bw-4
    local rh=math.max(bs+12,math.ceil(TS:GetTextSize(caption,fs,T.Body,Vector2.new(cw-6,1000)).Y)+4)
    local y=(narrow and 78+rerollH or math.max(76,rerollH+30))+oddsExtra
    local f=Instance.new('Frame');f.Name='Bag';f.BackgroundTransparency=1;f.Position=UDim2.fromOffset(0,y);f.Size=UDim2.fromOffset(bw,rh);f.Parent=left
    price(f,bag,'',bs,cream,T.Asset.shardBag)
    text(left,'BagNote',caption,bw+4,y,cw,rh,fs,cream)
    bagRow=rh+6
   end
  end
  -- Phones (tap>0) keep four columns only when each card is still 240 wide; else two rows of two.
  local top=(narrow and 78+rerollH or math.max(76,rerollH+30))+bagRow+oddsExtra;local cols=leftW>=(tap>0 and 1000 or 660) and 4 or leftW>=420 and 2 or 1;local cardW=(leftW-(cols-1)*12)/cols
  local buyH,lockH=th(43),th(34) -- a taller Buy makes the card taller by the same amount
  -- Weapon offers (2026-10-09): name, the attack line, the specialty bar, one row per type (the set
  -- step this buy reaches), then stat lines (with the specialty and those sets) and traits. Every
  -- card is as tall as the tallest one needs.
  local now=Stats.typeCounts(equippedIds(data))
  local function after(base) local c=table.clone(now);for _,t in base.types or {} do c[t]=(c[t] or 0)+1 end;return c end
  local ts=math.max(15,minText)
  local attackH,typesH,traitsH=38,0,22
  for _,offer in data.offers do
   local entry=Catalog.ById[offer.id];local base=entry and entry.weaponId and Weapons.ById[entry.weaponId]
   if base then
    attackH=math.max(attackH,readableHeight(M.attackLine(base),ts,cardW-98,38)-8)
    typesH=math.max(typesH,typeRowsHeight(base,cardW-28,now,true))
    traitsH=math.max(traitsH,readableHeight(traitLine(base,entry.tier,after(base)),16,cardW-28,22))
   end
  end
  local specY=44+attackH+4;local typesY=specY+26+8;local statsY=typesY+typesH+2
  local cardH=math.max(statsY+4*24+4+traitsH+12+buyH+16,math.min(L.CardHeight,ht-top-inventoryH-lockH-38))
  if not inventoryOnly then
   for i,o in data.offers do
    local entry=Catalog.ById[o.id];local x=((i-1)%cols)*(cardW+12);local y=top+math.floor((i-1)/cols)*(cardH+lockH+24)
    if not o.sold then
     local card=surface(left,'Offer'..i,x,y,cardW,cardH,entry.tier)
     local well=surface(card,'IconWell',12,12,64,64,nil,'inset')
     art(well,entry,4,4,56,56)
     heading(card,'Name',entry.name..(entry.weaponId and entry.tier>1 and (' '..({'I','II','III','IV'})[entry.tier]) or ''),86,12,cardW-98,entry.weaponId and 30 or 43,22,tiers[entry.tier])
     if not entry.weaponId then text(card,'Kind',entry.kind..(#entry.tags>0 and ' · '..entry.tags[1] or ''),86,56,cardW-98,26,17,cream) end
     if entry.weaponId then
      local base=Weapons.ById[entry.weaponId]
      local al=text(card,'Attack',M.attackLine(base),86,44,cardW-98,attackH,ts,cream);al.TextYAlignment=Enum.TextYAlignment.Top
      specBar(card,base,14,specY,cardW-28,26)
      typeRows(card,base,14,typesY,cardW-28,now,true)
      local used=weaponStats(card,base,entry.tier,14,statsY,cardW-28,after(base))
      text(card,'Traits',traitLine(base,entry.tier,after(base)),14,statsY+used+4,cardW-28,traitsH,16,tiers[entry.tier])
     else
      local used=effects(card,entry,14,98,cardW-28)
      -- Which of your weapons it works with, for items only some weapons use (worksLine).
      local works,wc=worksLine(entry,data)
      if works then text(card,'WorksWith',works,14,102+used,cardW-28,40,17,wc);used+=44 end
      text(card,'Description',entry.description,14,110+used,cardW-28,math.max(40,cardH-185-used-(buyH-43)),18)
     end
     local bw=math.min(136,cardW-32)
     local buy=btn(card,'Buy','', (cardW-bw)/2,cardH-16-buyH,bw,buyH,function() T.sound('ui_purchase');remember(card,well,i,o,data);self:send('Buy',i,o.token) end)
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
  -- LEAVE RUN ends the run for this player with what it has paid (RogueliteMeta), then the results.
  -- One tap opens the confirm popup shared with the pause menu and the death screen ("Leave the run?
  -- You keep 340 emeralds." STAY / LEAVE; UITheme.leaveConfirm, 2026-10-03). It sits on the HUD's
  -- ScreenGui, so shop refreshes keep it, and it closes itself when the next wave starts.
  local leave=btn(root,'LeaveRun','LEAVE RUN',leftW+gap+12,statsH+10,side,leaveH,function()
   local screen=root:FindFirstAncestorOfClass('ScreenGui')
   if self.leaveConfirm or not screen then return end
   local runState=RS:FindFirstChild('RogueliteRunState')
   self.leaveConfirm=T.leaveConfirm(screen,{keep=player:GetAttribute('RunEmeralds'),onClose=function() self.leaveConfirm=nil end,
    closeOn={runState and runState:GetAttributeChangedSignal('Phase')},closeIf=function() return runState==nil or runState:GetAttribute('Phase')~='Shop' end})
  end,true)
  leave.Caption.TextColor3=red;leave.Caption.UITextSizeConstraint.MaxTextSize=18
  leave.Interactable=data.phase=='Shop'
  local start=btn(root,'StartWave',data.ready and 'UNREADY' or 'GO (Wave '..data.wave..')',leftW+gap+12,statsH+18+leaveH+(rosterH>0 and rosterH+8 or 0),side,startH,function()
   local latest=self:snapshot();if latest then self:send(latest.ready and 'Unready' or 'Start') end
  end)
  start.Caption.UITextSizeConstraint.MaxTextSize=22
  if data.phase~='Shop' then start.Caption.Text='WAVE IN PROGRESS';start.Interactable=false end
  -- READY 2/4 under GO in multiplayer (user, 2026-10-03): living run members who pressed GO, out of
  -- all living ones (ShopService.publishReady: RogueliteRunState ShopReady / ShopPlayers). Kept live
  -- by the timer loop below; hidden solo, where the caption keeps the whole button.
  local readyLine=T.label(start,'ReadyCount','',8,0,0,0,16,cream);readyLine.Visible=false
  readyLine.Position=UDim2.new(0,8,.55,0);readyLine.Size=UDim2.new(1,-16,.45,-4);readyLine.TextStrokeTransparency=.3
  -- WHO is ready (user, 2026-10-03: "icon that shows whos ready"): each counted teammate's headshot
  -- above GO, from their ShopReady (ShopService.publishReady). Ready: full colour, a lime ring and a
  -- check (the pause menu's look); still shopping: dimmed, grey ring. Example: 4 in the party, 2
  -- pressed GO -> two lit heads with checks and two dim ones, with READY 2/4 on the button.
  local roster,shown
  if rosterH>0 then
   roster=Instance.new('Frame');roster.Name='ReadyRoster';roster.BackgroundTransparency=1
   roster.Position=start.Position-UDim2.fromOffset(0,rosterH+8);roster.Size=UDim2.fromOffset(side,rosterH);roster.Parent=root
  end
  local function drawRoster()
   if not roster then return end
   local list={}
   for _,p in game:GetService('Players'):GetPlayers() do local r=p:GetAttribute('ShopReady');if r~=nil then table.insert(list,{p=p,ready=r==true}) end end
   table.sort(list,function(a,b) return a.p.UserId<b.p.UserId end)
   local key='';for _,e in list do key..=e.p.UserId..(e.ready and '+' or '-') end
   if key==shown then return end -- redraw only when someone joins, leaves or readies
   roster:ClearAllChildren()
   local n=#list;if n==0 then return end
   local d=math.min(rosterH-28,math.floor((side-(n-1)*8)/n));local x=(side-(n*d+(n-1)*8))/2
   for i,e in list do
    local head=Instance.new('ImageLabel');head.Name='Head_'..e.p.UserId;head.BackgroundColor3=T.Color.well;head.BorderSizePixel=0
    head.Position=UDim2.fromOffset(x+(i-1)*(d+8),2);head.Size=UDim2.fromOffset(d,d);head.ImageTransparency=e.ready and 0 or .55;head.Parent=roster
    T.headshot(head,e.p.UserId)
    T.make('UICorner',head,{CornerRadius=UDim.new(1,0)})
    T.make('UIStroke',head,{Color=e.ready and T.Color.lime or T.Color.dim,Thickness=e.ready and 3 or 2})
    if e.ready then local s=math.floor(d*.42);T.check(head,d-s,d-s,s) end
    local name=text(roster,'Name_'..e.p.UserId,e.p==player and 'YOU' or e.p.DisplayName,x+(i-1)*(d+8)-3,d+4,d+6,20,12,e.ready and green or cream)
    name.TextXAlignment=Enum.TextXAlignment.Center;name.TextTruncate=Enum.TextTruncate.AtEnd
   end
   shown=key
  end
  local function showReady()
   local n,total=runState and runState:GetAttribute('ShopReady'),runState and runState:GetAttribute('ShopPlayers')
   local on=data.phase=='Shop' and type(n)=='number' and type(total)=='number' and total>1
   readyLine.Text=on and ('READY '..n..'/'..total) or '';readyLine.Visible=on
   start.Caption.Size=on and UDim2.new(1,-16,.55,-4) or UDim2.new(1,-16,1,-8)
   drawRoster()
  end
  showReady()
  -- The shop timer: the next wave starts on its own when it runs out, even if not everyone is ready.
  if data.phase=='Shop' then
   local label=start.Caption.Text
   task.spawn(function()
    while start.Parent do
     local left=M.shopSecondsLeft()
     start.Caption.Text=left and (label..'  ·  '..M.clock(left)) or label
     showReady()
     task.wait(.5)
    end
   end)
  end
  left.CanvasSize=UDim2.fromOffset(0,top+12)
  left.ScrollBarThickness=top+12>ht+1 and 3 or 0
  if self.selected and anchor then
   local sel=self.selected;local copy=sel.kind=='Weapon' and data.weapons[sel.slot];local entry=sel.kind=='Item' and Catalog.ById[sel.id];local base=copy and Weapons.ById[copy.id]
   if (base and copy.copy==sel.copy) or entry then
    local dim=Instance.new('TextButton');dim.Name='FocusBackdrop';dim.Text='';dim.AutoButtonColor=false;dim.BackgroundColor3=Color3.new(0,0,0);dim.BackgroundTransparency=.28;dim.BorderSizePixel=0;dim.Size=UDim2.fromScale(1,1);dim.ZIndex=10;dim.Parent=root
    dim.Activated:Connect(function() self.selected=nil;refresh() end)
    -- Combine/Sell (34) and Cancel (32) grow to touch size on phones; the panel grows with them.
    local b1,b2=th(34),th(32)
    local dw=math.min(324,w-20);local tier=copy and copy.tier or entry.tier
    -- Above the dimmed shop: a solid backing (sized below) under the panel, so nothing behind it
    -- shows through, then the panel.
    local backing=Instance.new('Frame');backing.Name='DetailsBacking';backing.BackgroundColor3=Color3.fromRGB(34,38,41);backing.BorderSizePixel=0;backing.ZIndex=11;backing.Parent=root
    T.make('UICorner',backing,{CornerRadius=UDim.new(0,14)})
    local outer=surface(root,'Details',0,0,dw,100,tier);outer.ZIndex=12;outer.Active=true
    local detail=Instance.new('ScrollingFrame');detail.Name='Body';detail.BackgroundTransparency=1;detail.BorderSizePixel=0;detail.Size=UDim2.fromScale(1,1);detail.ScrollBarThickness=3;detail.Parent=outer
    local well=surface(detail,'IconWell',14,14,72,72,nil,'inset')
    if base then thumbnail(well,combat.WeaponTemplates:FindFirstChild(copy.id),4,4,64,64) else art(well,entry,4,4,64,64) end
    heading(detail,'Title',(base or entry).name,98,14,dw-112,44,23,tiers[tier])
    text(detail,'Tier',E.TIER_NAMES[tier],98,60,dw-112,24,tap>0 and 16 or 14)
    -- The content stacks top-down and the buttons go under it, so stat lines, traits and the class
    -- row never overlap, whatever a weapon shows (2026-10-03: Range was hidden behind the class row).
    -- Example, Tier II Magic Staff: 4 stat lines end at 200, the class row sits at 208-232, the
    -- buttons start at 266. The panel grows (and scrolls on short screens) when content needs it.
    local y=104
    if base then
     local sets=Stats.typeCounts(equippedIds(data))
     y+=weaponStats(detail,base,copy.tier,16,y,dw-32,sets)
     local traits=traitLine(base,copy.tier,sets)
     if traits~='' then local th=readableHeight(traits,15,dw-32,22);text(detail,'Traits',traits,16,y+2,dw-32,th,15,tiers[tier]);y+=th+4 end
     y+=8
     -- Specialty bar and this weapon's sets now (2026-10-09; they replaced the class row).
     specBar(detail,base,16,y,dw-32,26);y+=34
     y+=typeRows(detail,base,16,y,dw-32,sets,false)+6
     local damage=math.max(0,math.floor(tonumber(copy.damage) or 0));local kills=math.max(0,math.floor(tonumber(copy.kills) or 0))
     text(detail,'RunPerformance',string.format('THIS RUN · %s damage · %s kills',damage,kills),16,y,dw-32,26,16,cream);y+=32
    else
     y+=effects(detail,entry,16,y,dw-32)
     local works,wc=worksLine(entry,data)
     if works then text(detail,'WorksWith',works,16,y+4,dw-32,40,15,wc);y+=46 end
     y+=14
    end
    local below=base and 2*(b1+7)+b2+12 or b2+12+16 -- the buttons under the content
    local dh=math.max(392+(base and 2*(b1-34) or 0)+(b2-32),y+below+(base and 0 or 40));local visibleH=math.min(dh,ht-16)
    local cancelY=dh-12-b2;local sellY=cancelY-7-b1;local combineY=sellY-7-b1
    if not base then text(detail,'Description',entry.description,16,y,dw-32,math.max(40,cancelY-16-y),15) end
    if base then
     local combine=btn(detail,'Combine',copy.tier==4 and 'Maximum tier' or copy.canCombine and 'Combine → '..E.TIER_NAMES[copy.tier+1] or 'Need matching weapon + tier',14,combineY,dw-28,b1,function() T.sound('ui_upgrade');self:send('Combine',sel.slot,sel.copy);self.selected=nil end,true)
     combine.Interactable=data.phase=='Shop' and copy.canCombine==true;combine.Caption.TextColor3=combine.Interactable and white or Color3.fromRGB(135,146,150)
     local sell=btn(detail,'Sell','',14,sellY,dw-28,b1,function() self:send('Sell',sel.slot,sel.copy);self.selected=nil end,true)
     price(sell,copy.sell or 0,'Recycle +',19,white);sell.Interactable=data.phase=='Shop'
    end
    btn(detail,'Cancel','Cancel',14,cancelY,dw-28,b2,function() self.selected=nil;refresh() end,true)
    local dx=math.clamp(anchor.X+6+slotSize/2-dw/2,8,w-dw-8)
    local ay=anchor.Y+6-(self[inventoryOnly and 'InventoryScroll' or 'ShopScroll'] or 0)
    local dy=math.clamp(ay-visibleH-12,8,math.max(8,ht-visibleH-8))
    outer.Position=UDim2.fromOffset(dx,dy);outer.Size=UDim2.fromOffset(dw,visibleH);detail.CanvasSize=UDim2.fromOffset(0,dh)
    -- 5 px in, with round corners, so the panel's cut corners still show.
    backing.Position=UDim2.fromOffset(dx+5,dy+5);backing.Size=UDim2.fromOffset(dw-10,visibleH-10)
   else self.selected=nil end
  end
  local key=inventoryOnly and 'InventoryScroll' or 'ShopScroll'
  task.defer(function() if left.Parent then left.CanvasPosition=Vector2.new(0,self[key] or 0);left:GetPropertyChangedSignal('CanvasPosition'):Connect(function() self[key]=left.CanvasPosition.Y end) end end)
  -- BUY effect: a buy the server took shows its offer sold (the last unsold one: the shop refilled,
  -- so its token is gone). Deferred after the scroll restore above, so the slot is where it shows.
  for token,b in self.bought do
   local o=data.offers[b.index];local gone=true
   for _,x in data.offers do if x.token==token then gone=false;break end end
   if os.clock()-b.t>4 or data.wave~=b.wave then self.bought[token]=nil;b.card:Destroy()
   elseif (o and o.token==token and o.sold) or (b.last and gone and arrived(b,data)) then self.bought[token]=nil;task.defer(playBuy,b,data,parent)
   elseif gone then self.bought[token]=nil;b.card:Destroy() end
  end
  return data
 end
 return self
end
return M
