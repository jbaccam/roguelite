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
for _,id in {'MaxHP','Damage','MeleeDamage','RangedDamage','ElementalDamage','UtilityPower','AttackSpeed','CritChance','CritDamage','Armor','Dodge','Regeneration','LifeSteal','Recovery','MoveSpeed','AttackRange','Luck','PickupRadius','XPGain','ShopDiscount','ShopPricePercent','ExplosionDamage','ContactReduction','LifeStealCap'} do primary[id]=true end
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
function M.attackWord(w) return w.kind=='Melee' and 'Melee' or w.kind=='Blast' and 'Explosive' or table.find(w.types or {},'Thrown') and 'Thrown' or 'Ranged' end
function M.attackLine(w)
 local word=M.attackWord(w)
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
 -- One confirm popup at a time (UITheme.confirm, 2026-10-10): every Robux reroll, saved reroll and
 -- Banish asks first, every time, whatever the count. It sits on the HUD's ScreenGui, so shop
 -- refreshes keep it, and it closes when the shop ends.
 local function blocked() return player:GetAttribute('RunDown') or player:GetAttribute('RunReturning') or player:GetAttribute('RunResult')~=nil end
 function self:ask(screen,opts)
  if self.confirmWin or not screen or blocked() then return end
  local runState=RS:FindFirstChild('RogueliteRunState')
  opts.onClose=function() self.confirmWin=nil end
  opts.closeOn={runState and runState:GetAttributeChangedSignal('Phase')}
  opts.closeIf=function() return runState==nil or runState:GetAttribute('Phase')~='Shop' end
  self.confirmWin=T.confirm(screen,opts)
 end
 -- Shop Banish (2026-10-10): BANISH, then a click on an offer, opens this. A saved Banish is used
 -- (RunAction UseBanish); with none saved, the 19 R$ Banish is bought for that offer (the server
 -- spends it on the offer when the receipt lands, or keeps it saved if the offer is gone).
 local function askBanish(screen,i,o)
  local entry=Catalog.ById[o.id];if not entry then return end
  local saved=player:GetAttribute('ProfileBanishes') or 0;local using=saved>0
  local name=entry.name..(entry.weaponId and entry.tier>1 and (' '..T.Roman[entry.tier]) or '')
  local robux=Money.price('Banish')
  self:ask(screen,{name='BanishConfirm',title='Banish',danger=true,
   question=using and ('Banish '..name..' for the rest of this run?') or ('Banish '..name..' for R$ '..robux..'?'),
   detail=(using and ('Uses 1 saved Banish (you have '..saved..', '..(saved-1)..' after). ') or '')..(entry.weaponId and 'No tier of it shows again this run.' or 'It never shows again this run.')..' A new offer takes its place.',
   confirm=using and 'USE 1 BANISH' or ('BUY · R$ '..robux),
   onConfirm=function()
    self.banishMode=false;refresh()
    local latest=self:snapshot();local now=latest and latest.offers and latest.offers[i]
    if blocked() or not latest or latest.phase~='Shop' or not now or now.token~=o.token or now.sold or now.locked then return end
    local target={kind='Shop',index=i,token=o.token}
    -- Never turn a saved-Banish confirmation into a purchase if the count changed while open.
    if using then
     if (player:GetAttribute('ProfileBanishes') or 0)>0 then self.banishing={t=os.clock(),revision=latest.revision};combat.RunAction:FireServer('UseBanish',target) end
    else combat.PurchaseRequest:FireServer('Banish',target) end
   end})
 end
 -- Shop rerolls that cost Robux or a saved one. kind: 'robux' (the R$ button: a saved reroll when
 -- there is one, else buy one) or 'bought' (one bought earlier in this run, from before 2026-10-10).
 local function askReroll(screen,kind)
  local saved=player:GetAttribute('ProfileRerolls') or 0;local using=kind=='robux' and saved>0
  local bought=kind=='bought' and ((self:snapshot() or {}).freeRerolls or 0) or 0
  local robux=Money.price('ShopReroll')
  self:ask(screen,{name='RerollConfirm',title='Shop Reroll',
   question=kind=='bought' and 'Use 1 bought reroll?' or using and 'Use 1 saved reroll?' or ('Reroll for R$ '..robux..'?'),
   detail=(kind=='bought' and ('You have '..bought..' from this run, '..(bought-1)..' after. ') or using and ('You have '..saved..' saved, '..(saved-1)..' after. ') or '')..'Replaces every unlocked offer now. Locked offers stay.',
   confirm=(kind=='bought' or using) and 'USE 1 REROLL' or ('BUY · R$ '..robux),
   onConfirm=function()
    local latest=self:snapshot()
    if blocked() or not latest or latest.phase~='Shop' then return end
    if kind=='bought' then
     if (latest.freeRerolls or 0)>0 then self:send('Reroll') end
    elseif using then
     if (player:GetAttribute('ProfileRerolls') or 0)>0 then combat.RunAction:FireServer('UseReroll','Shop') end
    else combat.PurchaseRequest:FireServer('ShopReroll') end
   end})
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
  -- On phones Items / Weapons are sideways-scrolling rows; they clip the landing spot instead.
  local function find()
   local layout=parent:FindFirstChild('ShopLayout');local main=layout and layout:FindFirstChild('ShopMain')
   local r=main and main:FindFirstChild(region)
   return r and slot and r:FindFirstChild(slot),r and r:IsA('ScrollingFrame') and r or main
  end
  local asset=entry.weaponId and WeaponIcons[entry.weaponId] or T.Asset[entry.icon] or entry.icon
  buyFX(screen,b,find,asset,tiers[entry.tier] or white,math.clamp(2+entry.tier,3,5))
 end
 -- Each shop opens clean (user, 2026-10-16: "next time the shop opens the item is already clicked
 -- on"): the open item / weapon popup, banish mode and the scroll belong to one shop, and go when
 -- the phase leaves Shop or the wave changes (GO, the timer, auto-ready). render() checks too: the
 -- HUD draws the new shop before the deferred listener below runs. The first look keeps them.
 local shopKey
 local function newShop(data)
  if not data then return end
  local key=data.phase=='Shop' and data.wave or false
  if shopKey==nil then shopKey=key;return end
  if key==shopKey then return end
  shopKey=key;self.selected=nil;self.banishMode=false;self.ShopScroll=nil;self.InventoryScroll=nil
  self.OffersScroll=nil;self.ItemsScroll=nil;self.WeaponsScroll=nil -- the phone rows' sideways scroll
 end
 local refreshQueued=false
 local function queueRefresh()
  if refreshQueued then return end
  refreshQueued=true
  task.defer(function() refreshQueued=false;newShop(self:snapshot());refresh() end)
 end
 state:GetAttributeChangedSignal('ShopSnapshot'):Connect(queueRefresh)
 local readyState=RS:FindFirstChild('RogueliteRunState')
 if readyState then readyState:GetAttributeChangedSignal('ShopPlayers'):Connect(queueRefresh) end
 for _,attribute in {'Shards','BaggedShards','RunLevel','PendingLevelUps'} do
  state:GetAttributeChangedSignal(attribute):Connect(queueRefresh)
 end
 player:GetAttributeChangedSignal('ProfileRerolls'):Connect(function() task.defer(refresh) end)
 player:GetAttributeChangedSignal('ProfileBanishes'):Connect(function() task.defer(refresh) end)
 for _,attribute in {'RunDown','RunReturning','RunResult'} do
  player:GetAttributeChangedSignal(attribute):Connect(function()
   if player:GetAttribute('RunDown') or player:GetAttribute('RunReturning') or player:GetAttribute('RunResult')~=nil then
    self.selected=nil;self.banishMode=false
    if self.confirmWin then self.confirmWin.Close() end
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
 -- owned: the item is already in your build (the inventory detail), so its Armor is in your stat.
 -- rowH/size: the phone card's smaller lines (26 / 18 elsewhere).
 local function effects(p,entry,x,y,w,owned,rowH,size)
  local row=0;rowH=rowH or 26
  for _,d in Stats.List do
   local v=entry.modifiers[d.id];local percent=(entry.percent or {})[d.id]
   if v or percent then
    local value=v or percent
    -- Flat Armor also says what it does from your live Armor (2026-10-10): 'Armor: +2 (25% → 32%
    -- less damage)'; an owned copy goes from your Armor without it to your Armor now.
    local change=''
    if d.id=='Armor' and v and not percent then local now=Stats.read(state).Armor;change=' ('..Stats.armorChange(owned and now-v or now,v)..')' end
    text(p,'Effect_'..d.id,d.label..': '..(value>0 and '+' or '')..value..(percent and '%' or d.unit)..change,x,y+row*rowH,w,rowH,size or 18,M.statColor(d.id,value,0));row+=1
   end
  end
  return row*rowH
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
 -- compact (phone cards, 2026-10-16): when even the short words don't fit at a readable size, the
 -- tiny ones: '+10% DMG', '-15% RANGED DMG', 'NO PENALTY'.
 local function specBar(p,base,x,y,w,h,compact)
  local class=state:GetAttribute('Class')
  local kind,text,icon,short,tiny -- short: the words for narrow cards
  if base.godly then kind,text='godly','GODLY · ANY CLASS'
  elseif Stats.specialty(base,class)>0 then kind,text,short,tiny,icon='specialty','+'..Stats.Specialty..'% DAMAGE · '..string.upper(class)..' SPECIALTY','+'..Stats.Specialty..'% DMG · SPECIALTY','+'..Stats.Specialty..'% DMG',WeaponIcons[Signature[class]]
  else
   local v,id=drawback(class,base)
   local what=v and string.upper(Stats.ById[id].label):gsub(' DAMAGE$',' DMG')
   if v then kind,text,short,tiny='drawback',v..'% '..what..' · '..string.upper(class)..' DRAWBACK',v..'% '..what..' · DRAWBACK',v..'% '..what
   else kind,text,short,tiny,icon='neutral',string.upper(base.class)..' WEAPON · NO PENALTY',string.upper(base.class)..' · NO PENALTY','NO PENALTY',WeaponIcons[Signature[base.class]] end
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
  local size=type(compact)=='table' and compact.size or math.max(math.floor(h*.6),minText)
  -- 25% slack: small shop scales draw the 9 px floor wider than the design-size measure.
  local tw=TS:GetTextSize(text,size,T.Font,Vector2.new(4000,100)).X*1.25
  if short and tw+(icon and is+6 or 0)>w-12 then text=short;tw=TS:GetTextSize(text,size,T.Font,Vector2.new(4000,100)).X*1.25 end
  if compact and tiny and tw+(icon and is+6 or 0)>w-12 then text=tiny;tw=TS:GetTextSize(text,size,T.Font,Vector2.new(4000,100)).X*1.25 end
  local x0=math.max(6,(w-(tw+(icon and is+6 or 0)))/2)
  if icon and x0+is+6+tw<=w-4 then T.icon(b,'Icon',x0,3,is,icon) else is=0 end
  local l=T.label(b,'Text',text,is>0 and x0+is+6 or 6,0,is>0 and w-(x0+is+6)-4 or w-12,h,size,ink);l.TextStrokeTransparency=.5;l.TextWrapped=false
  if is==0 then l.TextXAlignment=Enum.TextXAlignment.Center end
  l.FitText.MinTextSize=compact and math.min(size,minText) or math.min(size,9)
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
 local function statRows(base,tier,sets)
  local s=Stats.read(state);local d=Stats.weapon(base,s,state:GetAttribute('Class'),tier,sets);local ws=Stats.weaponStats(s,d)
  return {{'Damage',string.format('%.1f',d.damage),d.damage-base.damage},{'Cooldown',string.format('%.2f s',d.cooldown),base.cooldown-d.cooldown},{'Critical',string.format('x%.1f (%s)',s.CritDamage/100,Stats.format(Stats.ById.CritChance,ws.CritChance)),ws.CritChance-Stats.ById.CritChance.base},{'Range',string.format('%.1f',d.range),d.range-base.range}}
 end
 -- Phone cards (2026-10-16): the four lines two to a row when both fit at `size` in half the width
 -- ('Critical' says 'Crit'), else one to a row. Returns {[i]={x, row, width}} and the row count.
 -- Example, 194 px wide at 11: 'Damage: 6.9' | 'Cooldown: 0.74 s', then 'Crit: x1.5 (5%)' | 'Range: 22.0'.
 local function statWords(r,short) return (short and r[1]=='Critical' and 'Crit' or r[1])..': '..r[2] end
 local function statGrid(rows,w,size,slack)
  local half=math.floor((w-8)/2);local fits={}
  for i,r in rows do fits[i]=TS:GetTextSize(statWords(r,true),size,T.Body,Vector2.new(4000,100)).X*(slack or 1.15)<=half end
  local cells,line,i={},0,1
  while i<=#rows do
   if i<#rows and fits[i] and fits[i+1] then cells[i]={0,line,half};cells[i+1]={half+8,line,half};i+=2
   else cells[i]={0,line,w};i+=1 end
   line+=1
  end
  return cells,line
 end
 -- compact: {size=, rowH=} for the phone card's grid (statGrid); nil keeps one 24 px line each.
 local function weaponStats(p,base,tier,x,y,w,sets,compact)
  local rows=statRows(base,tier,sets)
  local cells,lines
  if compact then cells,lines=statGrid(rows,w,compact.size,1.02) end
  for i,r in rows do
   local color=r[3]>0 and green or r[3]<0 and red or white
   local words=string.format('<font color="#EADDA7">%s:</font> <font color="#%02X%02X%02X">%s</font>',compact and r[1]=='Critical' and 'Crit' or r[1],math.round(color.R*255),math.round(color.G*255),math.round(color.B*255),r[2])
   local l
   if compact then local c=cells[i];l=text(p,'WeaponStat'..i,words,x+c[1],y+c[2]*compact.rowH,c[3],compact.rowH,compact.size)
   else l=text(p,'WeaponStat'..i,words,x,y+(i-1)*24,w,24,19) end
   l.RichText=true
  end
  return compact and lines*compact.rowH or #rows*24 -- the height used, so whatever comes next starts below it
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
  newShop(data)
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
  local function th(v) return math.max(v,tap) end
  -- PHONES AND TABLETS (2026-10-16, user: "its a 2x2 grid and tons of scrolling. it should have all
  -- the cards in 1 row ... its way too large"): `compact` lays the offers in one row that scrolls
  -- sideways (Offers, 2.2-2.5 cards in view) with Buy and Lock side by side at each card's foot,
  -- then Items and Weapons as one sideways row each. A card keeps the icon, the name with the
  -- specialty bar (weapons) or kind (items) beside it, one row of type chips ('GUN 1→2'; the Sets tab
  -- has the bonuses), the four stats two to a row and the attack line ('Ranged · Poisons'), or an
  -- item's effects and description; every card is as tall as the tallest needs.
  -- Compact sizes are SCREEN px through K.px(): UITextSizeConstraint caps screen px, so the 9/scale
  -- floor used elsewhere drew phone text at 14-15 px. Here text is 11 px (names 14, at least 9 like
  -- the other screens) and buttons 40 px. Phones take the biggest scale, down to T.READABLE_SCALE,
  -- at which everything fits without scrolling: 844x390's 714x275 shop gets .5, 218 x 156 px cards
  -- and no scroll; 812x375 (688x260) scrolls about 12 px, up to 22 with a crystal bag line.
  -- Tablets and narrow windows (1024x768: four 174 px cards on desktop) get the row with bigger text.
  local K={} -- the compact layout's helpers and sizes (one table: render is near Luau's 200-local limit)
  local now=Stats.typeCounts(equippedIds(data))
  local function after(base) local c=table.clone(now);for _,t in base.types or {} do c[t]=(c[t] or 0)+1 end;return c end
  local paid=not player:GetAttribute('PaidRandomRestricted')
  local banishOn=paid and combat:GetAttribute('TutorialRun')~=true
  local compact=false
  K.s=scale -- the scale K.px() converts at (the phone loop below tries several)
  function K.px(v) return v/K.s end
  K.k=1 -- text size factor: 1 on phones; tablets pick the biggest that fits (below)
  function K.cR(v) return math.floor(v*K.k) end -- a compact text size, screen px
  function K.hR(v) return math.floor(v*math.min(K.k,1.25)) end -- the header's: it shares its row with the buttons
  function K.hSize(r) return K.px(K.hR(r)) end
  function K.hLine(r) return math.ceil(K.px(K.hR(r)*1.1+2)) end
  function K.cSize(r) return K.px(K.cR(r)) end -- that size in layout px
  function K.cLine(r) return math.ceil(K.px(K.cR(r)*1.1+2)) end -- one line's box
  function K.cTextH(sentence,r,w) return math.ceil(TS:GetTextSize(plain(sentence),K.cSize(r),T.Body,Vector2.new(w*.95,10000)).Y*1.05+K.px(3)) end
  function K.leftAt(s) local lw=(width-12)/s;return lw-math.clamp(lw*.23,tap>0 and 200 or 148,math.max(L.StatsWidth,tap>0 and 200 or 148))-28 end
  function K.compactW(lw) return math.floor(math.clamp((lw+12)/2.4-12,K.px(K.cR(tap>0 and 200 or 150)),K.px(K.cR(230)))) end -- phones 200-230 px: 2.2-2.5 in view
  function K.cName(entry) return entry.name..(entry.weaponId and entry.tier>1 and (' '..T.Roman[entry.tier]) or '') end
  function K.cPad() return math.ceil(K.px(4)) end -- text inset from a card's edge beyond its 12 px border
  -- The icon well, then the name (one line at 14 px, two at 12 when it won't fit at 12) and the kind
  -- line or specialty bar under it.
  function K.cWell() return K.cLine(14)+K.cLine(11)+2 end
  function K.cNameH(entry,cw)
   local one=TS:GetTextSize(K.cName(entry),K.cSize(12),Enum.Font.FredokaOne,Vector2.new(4000,100)).X*1.1
   return one<=cw-12-K.cWell()-8-12-K.cPad() and K.cLine(14) or 2*K.cLine(12)
  end
  function K.cTop(entry,cw) return 12+math.max(K.cWell(),K.cNameH(entry,cw)+K.cLine(11)+2)+math.ceil(K.px(4)) end
  -- A weapon's attack line: 'Ranged', then its traits: 'Ranged · Projectiles: 2 · Poisons'.
  function K.cAttack(base,tier) local tr=traitLine(base,tier,after(base));return M.attackWord(base)..(tr~='' and ' · '..tr or ''),tr end
  -- A compact label's text capped at r screen px (9 at least): TextScaled would otherwise grow it
  -- to fill its box.
  function K.cCap(l,r,exact) -- exact: r is already the screen size (hR)
   local c=l:FindFirstChild('UITextSizeConstraint') or l:FindFirstChild('FitText')
   local z=exact and r or K.cR(r)
   if c then c.MaxTextSize=z;c.MinTextSize=math.min(9,z) end
  end
  -- The type chips ('[gun] GUN 1→2' at 10 px, lime when this buy reaches a bonus) in one row `iw`
  -- wide, the first way that fits: with icons; without; two long ones at half the row each (text
  -- down to 9 px); icon and step only ('[crystal ball] 0→1', the Sets tab names them). Returns the
  -- height; p=nil only measures (T.tag's own width rule). Three types (none yet) wrap.
  function K.cChips(p,base,x,y,iw)
   local h=K.cLine(11);local gap=math.ceil(K.px(4));local list={}
   for _,t in base.types or {} do local n=now[t] or 0;local a=math.min(n+1,6);table.insert(list,{t=t,n=n,a=a,words=string.upper(t)..' '..n..'→'..a,step=n..'→'..a}) end
   local function width(c,icon,short,size) return math.min(iw,math.ceil(TS:GetTextSize(short and c.step or c.words,size or K.cSize(10),T.Font,Vector2.new(1000,100)).X*1.12)+(icon and h-6+14 or 20)) end
   local function total(icon,short) local sum=0;for _,c in list do sum+=width(c,icon,short)+gap end;return sum-gap end
   local half=math.floor((iw-gap)/2)
   local icons,short,halves=true,false,false
   if total(true)>iw then
    if total(false)<=iw then icons=false
    elseif #list==2 and width(list[1],false,false,K.px(9))<=half and width(list[2],false,false,K.px(9))<=half then icons,halves=false,true
    elseif #list<=2 then short=true end
   end
   local cx,rows=0,1
   for _,c in list do
    local cw=halves and half or width(c,icons,short)
    if cx>0 and cx+cw>iw then rows+=1;cx=0 end
    if p then
     local chip=T.tag(p,'TypeChip_'..c.t,short and c.step or c.words,x+cx,y+(rows-1)*(h+gap),{h=h,size=K.cSize(10),icon=icons and WeaponIcons[TYPE_ICON[c.t]] or nil,maxW=cw,textColor=c.n<6 and c.a>=2 and green or cream})
     K.cCap(chip.Text,10)
    end
    cx+=cw+gap
   end
   return rows*(h+gap)
  end
  function K.compactCardH(cw)
   local iw=cw-24-2*K.cPad();local need=0;local gap=math.ceil(K.px(3))
   for _,o in data.offers do
    local entry=Catalog.ById[o.id];local base=entry and entry.weaponId and Weapons.ById[entry.weaponId]
    if base then
     local _,lines=statGrid(statRows(base,entry.tier,after(base)),iw,K.cSize(11),1.02)
     need=math.max(need,K.cTop(entry,cw)+K.cChips(nil,base,0,0,iw)+lines*K.cLine(11)+K.cTextH(K.cAttack(base,entry.tier),11,iw))
    elseif entry then
     local rows=0;for _,d in Stats.List do if entry.modifiers[d.id] or (entry.percent or {})[d.id] then rows+=1 end end
     local works=worksLine(entry,data)
     need=math.max(need,K.cTop(entry,cw)+rows*K.cLine(11)+(works and K.cTextH(works,11,iw) or 0)+K.cTextH(entry.description,11,iw))
    end
   end
   return need+gap+th(43)+12 -- the Buy / Lock row, clear of the card's 12 px border
  end
  -- The compact header: 'Shop (Wave 6)' and the crystals, the odds line under them (10 px), the
  -- buttons on the right at full height. One row: 844x390's is the buttons' 40 px.
  function K.cButtons() return math.ceil(K.px(K.hR(100))),math.ceil(K.px(K.hR(62))) end
  function K.oddsText(label) return M.oddsLine(label,data.tierOdds or E.tierOdds(data.wave,Stats.read(state).Luck)) end -- tierOdds: admin odds (ShopService)
  function K.oddsHeightFor(label,nw,size,s,old)
   return math.max(old,math.ceil(TS:GetTextSize(K.oddsText(label):gsub('<[^>]->',''),size,T.Body,Vector2.new(math.max(20,(nw-8)*math.min(1,s)*.9),1000)).Y/math.min(1,s))+6)
  end
  function K.compactHeader(lw)
   local rw,pw=K.cButtons()
   local nw=lw-rw-(paid and pw+8 or 0)-(banishOn and pw+8 or 0)-12
   local oddsH=paid and math.ceil(TS:GetTextSize(plain(K.oddsText('Odds')),K.hSize(10),T.Body,Vector2.new(nw-8,10000)).Y+K.px(4)) or 0
   -- A crystal bag takes a third line there: '[bag] 30  Missed crystals: next pickups pay double'.
   return math.max(th(46),K.hLine(16)+oddsH+((data.baggedShards or 0)>0 and K.hLine(11) or 0)),nw,oddsH
  end
  local bag=data.baggedShards or 0
  local bagCaption="Missed crystals. Your next pickups pay double until it's empty."
  function K.bagRowH(lw,narrow)
   local bs=narrow and 22 or 26;local bw=20+bs*(#tostring(bag)*.65+1.2)
   return math.max(bs+12,math.ceil(TS:GetTextSize(bagCaption,math.max(16,minText),T.Body,Vector2.new(lw-bw-10,1000)).Y)+4)
  end
  -- Everything left of the stats column, top to bottom (ShopMain's 6 px pads included), at K.s.
  function K.compactNeed()
   local lw=K.leftAt(K.s);local narrow=lw<500;local cell=th(64)
   local head=narrow and 78+th(46)+20+(banishOn and th(46)+8 or 0) or K.compactHeader(lw)
   local row=cell+math.ceil(K.px(5))
   return head+math.ceil(K.px(4))+(bag>0 and narrow and K.bagRowH(lw,narrow)+6 or 0)+K.compactCardH(K.compactW(lw))+math.ceil(K.px(5))+math.ceil(K.px(4))+(lw<560 and 2*row+math.ceil(K.px(4)) or row)+12
  end
  if not inventoryOnly then
   compact=tap>0 or (K.leftAt(scale)-36)/4<200
   if tap>0 then
    local s=math.min(1,(width-12)/480)
    while true do
     K.s=s;tap=math.ceil(40/s);minText=9
     if s<=T.READABLE_SCALE or K.compactNeed()<=(height-12)/s then break end
     s=math.max(T.READABLE_SCALE,s-.025)
    end
    scale=s
   elseif compact then
    -- Tablets and narrow windows: the biggest text, x1.8 down to x1.2, whose row and inventory fit.
    -- Example, 1024x768: x1.8 (body 19 px, cards 290 px, 2.4 in view).
    K.s=scale;K.k=1.8
    while K.k>1.2 and K.compactNeed()>(height-12)/scale do K.k-=.1 end
   end
  end
  K.s=scale
  minText=compact and tap>0 and 9 or math.max(9,9/scale) -- compact phones: the 9 px floor, as above
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
  -- copies first. Desktop pins them above the stats; phones get a third tab, Sets.
  -- SET BONUSES (2026-10-16, user: "equipped copies" wasn't clear; rows overlapped each other and the
  -- tabs, and their last line clipped on the row edge): a plain title and hint, then one row per type
  -- as tall as its wrapped lines (measured like readableHeight), 8 px under the last line. Pinned,
  -- they take at most half the column and scroll past that. Example, 310 wide: BLADE 2 is 34 + 20 +
  -- 18 + 8 = 80 px, so three types take 46 + 248.
  local lines=Stats.typeLines(equippedIds(data))
  table.sort(lines,function(a,b) if a.count~=b.count then return a.count>b.count end return table.find(Weapons.Types,a.type)<table.find(Weapons.Types,b.type) end)
  local bonusSize,nextSize,tabSize=math.max(14,minText),math.max(13,minText),math.max(13,minText)
  local function lineH(s,size,w) return readableHeight(s,size,w)-6 end
  -- The row's words: now (the bonus you have, or 'No bonus yet') and, full rows only, the next step.
  -- Compact (the Sets tab) has one line: the bonus, or 'At 2: +4% dmg' when there is none yet.
  local function setText(r,compact)
   local on=r.count>=2;local step=r.next and M.setShort(r.type,r.next)
   if compact then return on and M.setShort(r.type,r.count) or step and ('At '..r.next..': '..step) or '' end
   return on and M.setShort(r.type,r.count) or 'No bonus yet',step and ((on and 'Next at ' or 'At ')..r.next..': '..step) or 'Full set'
  end
  local function setRowH(r,w,compact)
   local now,nxt=setText(r,compact)
   if compact then return 32+lineH(now,tabSize,w-20)+8 end
   return 34+lineH(now,bonusSize,w-56)+lineH(nxt,nextSize,w-56)+8
  end
  local function rowsHeight(w,compact) local h=0;for _,r in lines do h+=setRowH(r,w,compact)+4 end;return math.max(0,h-4) end
  -- Rows from y=2, x=2 (their 2 px outlines stay inside a clipping list); returns the canvas height.
  local function setRows(parent,w,compact)
   local y=2;w-=4
   for _,r in lines do
    local rh=setRowH(r,w,compact);local on=r.count>=2;local now,nxt=setText(r,compact)
    local f=Instance.new('Frame');f.Name='Set_'..r.type;f.Position=UDim2.fromOffset(2,y);f.Size=UDim2.fromOffset(w,rh);f.BorderSizePixel=0
    f.BackgroundColor3=on and Color3.fromRGB(26,32,36) or Color3.fromRGB(21,25,28);f.Parent=parent
    T.make('UICorner',f,{CornerRadius=UDim.new(0,8)});T.make('UIStroke',f,{Color=Color3.fromRGB(8,10,11),Thickness=2})
    f:SetAttribute('Count',r.count)
    local is=compact and 24 or 30;local nx=compact and 40 or 46
    T.icon(f,'Icon',8,compact and 6 or 8,is,WeaponIcons[TYPE_ICON[r.type]])
    heading(f,'Type',string.upper(r.type),nx,compact and 4 or 7,w-nx-52,24,compact and 16 or 18,on and white or T.Color.muted)
    local c=heading(f,'Count',tostring(r.count),w-48,compact and 2 or 5,40,28,compact and 20 or 24,on and green or T.Color.muted);c.TextXAlignment=Enum.TextXAlignment.Right
    if compact then
     local l=text(f,'Bonus',now,10,32,w-20,lineH(now,tabSize,w-20),tabSize,on and green or cream);l.TextYAlignment=Enum.TextYAlignment.Top
    else
     local bh=lineH(now,bonusSize,w-56)
     local l=text(f,'Bonus',now,nx,34,w-nx-10,bh,bonusSize,on and green or cream);l.TextYAlignment=Enum.TextYAlignment.Top
     local n=text(f,'Next',nxt,nx,34+bh,w-nx-10,lineH(nxt,nextSize,w-56),nextSize,r.next and T.Color.muted or T.Color.gold);n.TextYAlignment=Enum.TextYAlignment.Top
    end
    y+=rh+4
   end
   return y-4+2
  end
  local tabsY=52
  local cap=math.floor((statsH-52)*.5)
  local pinned=#lines>0 and tap==0 and 46+setRowH(lines[1],side-24,false)+4<=cap
  if pinned then
   heading(stats,'SetsTitle','SET BONUSES',14,tabsY,side-28,24,18,green)
   text(stats,'SetsNote','2+ weapons of one type give a bonus',14,tabsY+24,side-28,18,13,T.Color.muted)
   local listW=side-24;local rowsH=rowsHeight(listW-4,false)+4
   local scrolls=46+rowsH>cap
   if scrolls then listW-=6;rowsH=rowsHeight(listW-4,false)+4 end
   local boxH=math.min(rowsH,cap-46)
   local box=Instance.new('ScrollingFrame');box.Name='Sets';box.Position=UDim2.fromOffset(12,tabsY+46);box.Size=UDim2.fromOffset(side-24,boxH);box.CanvasSize=UDim2.fromOffset(0,rowsH)
   box.BackgroundTransparency=1;box.BorderSizePixel=0;box.ScrollBarThickness=scrolls and 3 or 0;box.ScrollBarImageColor3=green;box.VerticalScrollBarInset=Enum.ScrollBarInset.None;box.Parent=stats
   setRows(box,listW,false)
   tabsY+=46+boxH+8
  end
  local tabList=(pinned or #lines==0) and {'Primary','Secondary'} or {'Primary','Secondary','Sets'}
  local showSets=self.statTab=='Sets' and #tabList==3 -- kept when a resize pins the sets again
  local current=showSets and 'Sets' or secondary and 'Secondary' or 'Primary'
  local n=#tabList;local tw=(side-18-(n-1)*4)/n
  for i,tab in tabList do
   local short=side<180 or n==3
   local b=btn(stats,tab..'Tab',short and (tab=='Primary' and 'Main' or tab=='Secondary' and 'Extra' or 'Sets') or tab,9+(i-1)*(tw+4),tabsY,tw,tabH,function() self.statTab=tab;self.statPage=1;refresh() end,tab~=current)
   b.Caption.UITextSizeConstraint.MaxTextSize=compact and tap>0 and 13 or side<180 and 12 or 18 -- 13: inside the tab on .5-scale phones
  end
  local definitions={};if not showSets then for _,d in Stats.List do if (primary[d.id]==true)~=secondary then table.insert(definitions,d) end end end
  if showSets then
   local list=Instance.new('ScrollingFrame');list.Name='SetRows';list.Position=UDim2.fromOffset(12,tabsY+tabH+6);list.Size=UDim2.fromOffset(side-24,math.max(0,statsH-(tabsY+tabH+6)-12))
   list.BackgroundTransparency=1;list.BorderSizePixel=0;list.ScrollBarThickness=3;list.ScrollBarImageColor3=green;list.VerticalScrollBarInset=Enum.ScrollBarInset.None;list.Parent=stats
   list.CanvasSize=UDim2.fromOffset(0,setRows(list,side-30,true))
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
  -- 12 px in, so names and values clear the panel's 12 px border by 4 and 8 (2026-10-16).
  local scroll=Instance.new('Frame');scroll.Name='StatRows';scroll.Position=UDim2.fromOffset(12,rowsTop);scroll.Size=UDim2.fromOffset(side-24,math.max(0,available));scroll.BackgroundTransparency=1;scroll.ClipsDescendants=true;scroll.Parent=stats
  local values=Stats.read(state)
  for i=1,shown do
   local d=definitions[(page-1)*perPage+i]
   local row=Instance.new('Frame');row.Name=d.id;row.Size=UDim2.new(1,-4,0,rowH-1);row.Position=UDim2.fromOffset(0,(i-1)*rowH);row.BorderSizePixel=0;row.BackgroundColor3=Color3.fromRGB(18,22,23);row.BackgroundTransparency=1;row.Parent=scroll
   local font=side<180 and 10 or math.clamp(rowH*.86,11,19)
   text(row,'Name',Stats.statLabel(d,values[d.id]),4,0,side*.58-12,rowH-1,font) -- 'Armor · you take 35% less damage' (2026-10-10)
   local value=d.id=='ShopPricePercent' and string.format('×%.2f',data.modifier) or Stats.format(d,values[d.id])
   local v=text(row,'Value',value,side*.58-8,0,side*.42-24,rowH-1,font,M.statColor(d.id,d.id=='ShopPricePercent' and (data.modifier-1)*100 or values[d.id],d.base));v.TextXAlignment=Enum.TextXAlignment.Right
  end
  if paged then
   local py=statsH-8-pagerH
   btn(stats,'PreviousStats','‹',10,py,pagerW,pagerH,function() self.statPage=page>1 and page-1 or pages;refresh() end,true)
   text(stats,'StatPage',page..' / '..pages,16+pagerW,py,side-32-pagerW*2,pagerH,tap>0 and 16 or 12)
   btn(stats,'NextStats','›',side-10-pagerW,py,pagerW,pagerH,function() self.statPage=page<pages and page+1 or 1;refresh() end,true)
  end
  local narrow=leftW<500
  -- Compact header (phones, tablets): 'Shop (Wave 4)' and the crystals on one line, the odds under
  -- them, the three buttons at full height on the right; one row in all. Example, 844x390: 40 px.
  local cHead=compact and not narrow
  local headH,noteW,cOddsH;if cHead then headH,noteW,cOddsH=K.compactHeader(leftW) end
  -- Past the win (RogueliteRunState.Won), the shop is Endless's.
  local runState=RS:FindFirstChild('RogueliteRunState');local won=runState~=nil and runState:GetAttribute('Won')==true
  local titleText=won and ('Endless (Wave '..data.wave..')') or ('Shop (Wave '..data.wave..')')
  local titleSize=cHead and K.hSize(16) or 30
  local shardsSize=K.cSize(14);local shardsW=math.ceil(20+shardsSize*(#tostring(data.shards)*.65+1.2))
  local titleW=cHead and math.min(math.ceil(TS:GetTextSize(titleText,titleSize,Enum.Font.FredokaOne,Vector2.new(4000,100)).X*1.1)+8,noteW-shardsW-4) or leftW*(narrow and .62 or .39)
  local shopTitle=heading(left,'ShopTitle',titleText,0,0,titleW,cHead and K.hLine(16) or 46,titleSize,won and T.Color.gold or nil)
  if cHead then K.cCap(shopTitle,K.hR(16),true) end
  -- The paid buttons sit beside the crystal reroll (hidden where paid random items are restricted):
  -- R$ REROLL, and BANISH (2026-10-10; not in the tutorial, whose offers are guided). Each button
  -- says what its next click uses: REROLL - 12 [crystal] (crystals, no question); REROLL with
  -- '4 SAVED' or 'R$ 15'; BANISH with '3 SAVED' or 'R$ 19'. The paid ones always ask first.
  if not banishOn or data.phase~='Shop' then self.banishMode=false end
  local banishing=self.banishMode==true
  local screenGui=function() return root:FindFirstAncestorOfClass('ScreenGui') end
  local oddsExtra=0
  local cRerollW,cPaidW=K.cButtons()
  local robuxW=paid and (cHead and cPaidW or 118) or 0
  local banishW=banishOn and (cHead and cPaidW or 118) or 0
  local rerollW=cHead and cRerollW or narrow and leftW-(paid and robuxW+8 or 0) or math.min(232,leftW*.30)
  local rerollH=th(46)
  -- Wide: BANISH | R$ REROLL | REROLL in the title row, right of the crystals (they end at 54% of
  -- the width). When the three don't fit there, the paid two narrow to 96 and REROLL to no less than
  -- 150; when even that doesn't fit (and on narrow layouts), BANISH takes its own row under the
  -- reroll buttons, at the right, and everything below moves down by that row (banishDrop).
  -- Example: 1920x1080 fits all three at full size, 1280x720 narrowed, 1024x768 drops BANISH a row.
  local banishDrop=0
  if banishOn and not cHead then
   local room=leftW*.46
   if not narrow and rerollW+robuxW+banishW+16>room then
    local tight=math.max(150,math.min(rerollW,room-2*(96+8)))
    if tight+2*(96+8)<=room then rerollW,robuxW,banishW=tight,96,96 end
   end
   if narrow or rerollW+robuxW+banishW+16>room then banishDrop=rerollH+8 end
  end
  -- Caption on top, what the click uses under it (the level-up screen's BANISH / REROLL look).
  local function twoLine(b,sub,color)
   local bw,bh=b.Size.X.Offset,b.Size.Y.Offset;local capH=math.floor(bh*(compact and not cHead and .5 or .58)) -- .5: room for the price line on narrow compact layouts
   -- Compact: 7 screen px in from the sides and the bottom, clear of the button's border.
   local side=cHead and math.ceil(K.px(7)) or 6;local foot=cHead and math.ceil(K.px(5)) or 3
   b.Caption.Size=UDim2.new(1,-2*side,0,capH);b.Caption.Position=UDim2.fromOffset(side,3)
   local sl=text(b,'Price',sub,side,capH,bw-2*side,bh-capH-foot,math.max(15,minText),color or white);sl.TextXAlignment=Enum.TextXAlignment.Center;sl.Font=T.Font
   return sl
  end
  -- The crystal reroll asks nothing. A reroll bought earlier in this run (only servers from before
  -- 2026-10-10 bank them) is a paid one: it says so and asks first.
  local free=data.freeRerolls or 0
  local reroll=btn(left,'Reroll','',narrow and 0 or leftW-rerollW,narrow and 56 or 0,rerollW,rerollH,function()
   local latest=self:snapshot()
   if latest and (latest.freeRerolls or 0)>0 then askReroll(screenGui(),'bought') else self:send('Reroll') end
  end,true)
  if free>0 then reroll.Caption.Text='BOUGHT REROLL ×'..free else price(reroll,data.rerollPrice,'REROLL - ',20,white) end
  reroll.Interactable=(free>0 or data.shards>=data.rerollPrice) and data.phase=='Shop'
  if paid then
   local stored=player:GetAttribute('ProfileRerolls') or 0
   local rb=btn(left,'RobuxReroll','REROLL',narrow and leftW-robuxW or leftW-rerollW-8-robuxW,narrow and 56 or 0,robuxW,rerollH,function() askReroll(screenGui(),'robux') end)
   twoLine(rb,stored>0 and (stored..' SAVED') or ('R$ '..Money.price('ShopReroll')),white)
   rb.Interactable=data.phase=='Shop'
   if banishOn then
    local saved=player:GetAttribute('ProfileBanishes') or 0
    local bx=banishDrop>0 and leftW-banishW or leftW-rerollW-8-robuxW-8-banishW
    local by=banishDrop>0 and (narrow and 56 or 0)+rerollH+8 or 0
    if banishing then
     local cancel=btn(left,'CancelBanish','CANCEL',bx,by,banishW,rerollH,function() self.banishMode=false;refresh() end,true)
     cancel.Caption.TextColor3=red
    else
     local bb=btn(left,'Banish','BANISH',bx,by,banishW,rerollH,function()
      if blocked() then return end
      self.banishMode=true;self.selected=nil;refresh()
     end,true)
     T.setTier(bb,4);bb.Caption.TextColor3=T.Color.negative
     twoLine(bb,saved>0 and (saved..' SAVED') or ('R$ '..Money.price('Banish')),Color3.fromRGB(255,190,190))
     bb.Interactable=data.phase=='Shop'
    end
   end
   -- Odds note under the reroll buttons (in the gap above the cards): each new offer's tier chance at
   -- this wave and Luck. Wide: right-aligned in the 30 px under the buttons; narrow: the 22 px row.
   -- Compact: 'Odds: Tier I 46% · ...' under the title, left of the buttons (compactHeader).
   local nw=cHead and noteW or narrow and leftW or math.min(leftW*.6,560)
   local label=cHead and 'Odds' or 'Reroll odds per offer'
   local oddsSize=cHead and K.hSize(10) or math.max(narrow and 13 or 15,minText)
   local oldHeight=narrow and 18 or 20
   -- Font-size constraints apply at rendered size. Measure the available screen width,
   -- then convert height back into layout pixels; reserve slack for rich-text rounding.
   local oddsHeight=cHead and cOddsH or K.oddsHeightFor(label,nw,oddsSize,scale,oldHeight)
   oddsExtra=oddsHeight-oldHeight
   local note=text(left,'RerollOdds',K.oddsText(label),cHead and 0 or leftW-nw,cHead and K.hLine(16) or (narrow and 58+rerollH or rerollH+5)+banishDrop,nw,oddsHeight,oddsSize,cream)
   note.RichText=true;note.TextScaled=false;note.TextSize=oddsSize;note.TextWrapped=true
   note.TextXAlignment=(narrow or cHead) and Enum.TextXAlignment.Left or Enum.TextXAlignment.Right
   -- Banish mode: the hint takes the odds line's place.
   if banishing then note.Name='BanishHint';note.RichText=false;note.Text='Click the offer you want to banish';note.TextColor3=red;note.Font=T.Font end
  end
  -- Crystals, and right beside them the crystal bag (Brotato's material bag, user 2026-10-03): what
  -- was left on the ground when the last wave ended. Shown only while it holds some (an empty bag
  -- hides), with a plain caption beside it. Example: '439 [crystal]  30 [bag]'. Between the title and
  -- the reroll buttons (or its own row, below); each amount sized by price()'s own fit rule.
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
  local caption=bagCaption
  local fs=math.max(16,minText)
  local inline=false
  if cHead then
   -- Compact: the crystals right after the title; a bag takes the header's third line (below).
   local f=Instance.new('Frame');f.Name='Shards';f.BackgroundTransparency=1;f.Position=UDim2.fromOffset(titleW+4,0);f.Size=UDim2.fromOffset(shardsW,K.hLine(16));f.Parent=left
   price(f,data.shards,'',shardsSize,white)
  elseif bag>0 and not narrow then
   local bx1=math.max(bx0+leftW*.14,leftW-rerollW-(paid and robuxW+8 or 0)-(banishW>0 and banishDrop==0 and banishW+8 or 0)-8)
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
   if not cHead then shardsBox('Shards',bx0,leftW*(narrow and .35 or .14),data.shards,narrow and 23 or 32,white) end
   if bag>0 and cHead then
    -- Compact: the header's third line, under the odds; a short caption so it stays one line.
    local bs=K.hSize(11);local bw=math.ceil(20+bs*(#tostring(bag)*.65+1.2));local y=K.hLine(16)+cOddsH;local rh=K.hLine(11)
    local f=Instance.new('Frame');f.Name='Bag';f.BackgroundTransparency=1;f.Position=UDim2.fromOffset(0,y);f.Size=UDim2.fromOffset(bw,rh);f.Parent=left
    price(f,bag,'',bs,cream,T.Asset.shardBag)
    local words='Missed crystals: next pickups pay double'
    for _,w in {words,'Next pickups pay double','Pickups pay double'} do words=w;if TS:GetTextSize(w,K.hSize(10),T.Body,Vector2.new(4000,100)).X*1.1<=noteW-bw-4 then break end end
    K.cCap(text(left,'BagNote',words,bw+4,y,noteW-bw-4,rh,K.hSize(10),cream),K.hR(10),true)
   elseif bag>0 then
    -- price()'s fit rule sizes the box, so the amount keeps its size; the caption starts at its edge.
    local bs=narrow and 22 or 26
    local bw=20+bs*(#tostring(bag)*.65+1.2);local cw=leftW-bw-4
    local rh=math.max(bs+12,math.ceil(TS:GetTextSize(caption,fs,T.Body,Vector2.new(cw-6,1000)).Y)+4)
    local y=(narrow and 78+rerollH or math.max(76,rerollH+30))+oddsExtra+banishDrop
    local f=Instance.new('Frame');f.Name='Bag';f.BackgroundTransparency=1;f.Position=UDim2.fromOffset(0,y);f.Size=UDim2.fromOffset(bw,rh);f.Parent=left
    price(f,bag,'',bs,cream,T.Asset.shardBag)
    text(left,'BagNote',caption,bw+4,y,cw,rh,fs,cream)
    bagRow=rh+6
   end
  end
  -- Desktop: four columns from 660 wide, else two rows of two (compact layouts use the Offers row).
  local top=cHead and headH+math.ceil(K.px(4))+bagRow or (narrow and 78+rerollH or math.max(76,rerollH+30))+bagRow+oddsExtra+banishDrop;local cols=leftW>=(tap>0 and 1000 or 660) and 4 or leftW>=420 and 2 or 1;local cardW=compact and K.compactW(leftW) or (leftW-(cols-1)*12)/cols
  local buyH,lockH=th(43),th(34) -- a taller Buy makes the card taller by the same amount
  -- Weapon offers (2026-10-09): name, the attack line, the specialty bar, one row per type (the set
  -- step this buy reaches), then stat lines (with the specialty and those sets) and traits. Every
  -- card is as tall as the tallest one needs.
  local ts=math.max(15,minText)
  local attackH,typesH,traitsH=38,0,22
  for _,offer in data.offers do
   local entry=Catalog.ById[offer.id];local base=entry and entry.weaponId and Weapons.ById[entry.weaponId]
   if base then
    attackH=math.max(attackH,readableHeight(M.attackLine(base),ts,cardW-104,38)-8)
    typesH=math.max(typesH,typeRowsHeight(base,cardW-36,now,true))
    traitsH=math.max(traitsH,readableHeight(traitLine(base,entry.tier,after(base)),16,cardW-36,22))
   end
  end
  local specY=44+attackH+4;local typesY=specY+26+8;local statsY=typesY+typesH+2
  local cardH=compact and K.compactCardH(cardW) or math.max(statsY+4*24+4+traitsH+12+buyH+16,math.min(L.CardHeight,ht-top-inventoryH-lockH-38))
  -- The compact card (see `compact`): icon well, the name with the specialty bar (weapons) or kind
  -- (items) beside it, then a weapon's type chips, stats two to a row and attack line, or an item's
  -- effects, 'Works with' and description. Buy and Lock share the foot (the caller). Same names as
  -- the desktop card's pieces. Example, 844x390: 218 x 156 px, text 11 px, names 14.
  local function compactCard(card,entry,cw)
   local pad=12+K.cPad();local iw=cw-2*pad;local ws=K.cWell()
   local well=surface(card,'IconWell',12,12,ws,ws,nil,'inset')
   local rim=math.max(4,math.floor(ws*.12));art(well,entry,rim,rim,ws-2*rim,ws-2*rim)
   local nx=12+ws+8;local nw=cw-nx-pad
   local nameH=K.cNameH(entry,cw)
   heading(card,'Name',K.cName(entry),nx,12,nw,nameH,K.cSize(14),tiers[entry.tier])
   local y=K.cTop(entry,cw)
   if entry.weaponId then
    local base=Weapons.ById[entry.weaponId]
    specBar(card,base,nx,12+nameH+1,nw,K.cLine(11),{size=K.cSize(11)})
    y+=K.cChips(card,base,pad,y,iw)
    y+=weaponStats(card,base,entry.tier,pad,y,iw,after(base),{size=K.cSize(11),rowH=K.cLine(11)})
    local words,tr=K.cAttack(base,entry.tier)
    local l=text(card,'Attack',rich(cream,M.attackWord(base))..(tr~='' and rich(tiers[entry.tier],' · '..tr) or ''),pad,y,iw,K.cTextH(words,11,iw),K.cSize(11),cream)
    l.RichText=true;l.TextYAlignment=Enum.TextYAlignment.Top
   else
    text(card,'Kind',entry.kind..(#entry.tags>0 and ' · '..entry.tags[1] or ''),nx,12+nameH+1,nw,K.cLine(11),K.cSize(11),cream)
    y+=effects(card,entry,pad,y,iw,false,K.cLine(11),K.cSize(11))
    local works,wc=worksLine(entry,data)
    if works then local wh=K.cTextH(works,11,iw);local l=text(card,'WorksWith',works,pad,y,iw,wh,K.cSize(11),wc);l.TextYAlignment=Enum.TextYAlignment.Top;y+=wh end
    local d=text(card,'Description',entry.description,pad,y,iw,K.cTextH(entry.description,11,iw),K.cSize(11));d.TextYAlignment=Enum.TextYAlignment.Top
   end
   for _,d in card:GetDescendants() do if d:IsA('TextLabel') and not d.Parent.Name:match('^TypeChip_') then K.cCap(d,d.Name=='Name' and 14 or 11) end end
   return well
  end
  local offersStrip
  if not inventoryOnly then
   -- Compact: one row, scrolled sideways (touch drag, wheel or the 4 px bar under the cards).
   local shownCards=0
   if compact then
    offersStrip=T.make('ScrollingFrame',left,{Name='Offers',Position=UDim2.fromOffset(0,top),Size=UDim2.fromOffset(leftW,cardH+math.ceil(K.px(5))),BackgroundTransparency=1,BorderSizePixel=0,
     ScrollingDirection=Enum.ScrollingDirection.X,ScrollBarThickness=0,ScrollBarImageColor3=green,HorizontalScrollBarInset=Enum.ScrollBarInset.None,VerticalScrollBarInset=Enum.ScrollBarInset.None,CanvasSize=UDim2.new()})
   end
   for i,o in data.offers do
    local entry=Catalog.ById[o.id];local x=((i-1)%cols)*(cardW+12);local y=top+math.floor((i-1)/cols)*(cardH+lockH+24)
    if compact then x=2+shownCards*(cardW+12);y=0 end
    if not o.sold then
     shownCards+=1
     local holder=offersStrip or left
     local card=surface(holder,'Offer'..i,x,y,cardW,cardH,entry.tier)
     local well,buy
     local function buyIt() T.sound('ui_purchase');remember(card,well,i,o,data);self:send('Buy',i,o.token) end
     if compact then
      -- Buy (58%) and Lock side by side, 12 px in from the card's foot. Lock is the row's, drawn over
      -- the card (ZIndex 2), so it still unlocks in banish mode.
      well=compactCard(card,entry,cardW)
      local rowW=cardW-24;local bw=math.floor((rowW-8)*.58);local by=cardH-12-buyH
      buy=btn(card,'Buy','',12,by,bw,buyH,buyIt)
      local lock=btn(holder,'Lock'..i,o.locked and 'Locked' or 'Lock',x+12+bw+8,by,rowW-bw-8,buyH,function() self:send('Lock',i,o.token) end,not o.locked);lock.ZIndex=2
      K.cCap(lock.Caption,14)
     else
     well=surface(card,'IconWell',12,12,64,64,nil,'inset')
     art(well,entry,7,7,50,50) -- clear of the well's 8 px rim
     heading(card,'Name',entry.name..(entry.weaponId and entry.tier>1 and (' '..({'I','II','III','IV'})[entry.tier]) or ''),86,12,cardW-104,entry.weaponId and 30 or 43,22,tiers[entry.tier])
     if not entry.weaponId then text(card,'Kind',entry.kind..(#entry.tags>0 and ' · '..entry.tags[1] or ''),86,56,cardW-104,26,17,cream) end
     if entry.weaponId then
      local base=Weapons.ById[entry.weaponId]
      local al=text(card,'Attack',M.attackLine(base),86,44,cardW-104,attackH,ts,cream);al.TextYAlignment=Enum.TextYAlignment.Top
      specBar(card,base,18,specY,cardW-36,26)
      typeRows(card,base,18,typesY,cardW-36,now,true)
      local used=weaponStats(card,base,entry.tier,18,statsY,cardW-36,after(base))
      text(card,'Traits',traitLine(base,entry.tier,after(base)),18,statsY+used+4,cardW-36,traitsH,16,tiers[entry.tier])
     else
      local used=effects(card,entry,18,98,cardW-36)
      -- Which of your weapons it works with, for items only some weapons use (worksLine).
      local works,wc=worksLine(entry,data)
      if works then text(card,'WorksWith',works,18,102+used,cardW-36,40,17,wc);used+=44 end
      text(card,'Description',entry.description,18,110+used,cardW-36,math.max(40,cardH-185-used-(buyH-43)),18)
     end
     local bw=math.min(136,cardW-32)
     buy=btn(card,'Buy','', (cardW-bw)/2,cardH-16-buyH,bw,buyH,buyIt)
     btn(left,'Lock'..i,o.locked and 'Locked' or 'Lock',x+8,y+cardH+10,cardW-16,lockH,function() self:send('Lock',i,o.token) end,not o.locked)
     end
     price(buy,o.price,'',compact and math.min(K.cSize(15),buyH*.42) or 30,data.shards>=o.price and white or red);buy.Interactable=data.shards>=o.price and data.phase=='Shop'
     if banishing then
      -- Banish mode (the level-up screen's look): red corners and a full-card BANISH on each offer
      -- that can go. A locked offer can't: it says so, and its Lock button below still unlocks it.
      local can=not o.locked
      if can then T.setTier(card,4) end
      buy.Selectable=false
      local pick=T.make('TextButton',card,{Name=can and 'BanishPick' or 'BanishLocked',Text='',AutoButtonColor=false,Selectable=can,BackgroundColor3=can and Color3.fromRGB(120,10,20) or Color3.fromRGB(8,10,12),BackgroundTransparency=can and .72 or .4,Size=UDim2.fromScale(1,1),ZIndex=5})
      T.make('UICorner',pick,{CornerRadius=UDim.new(0,10)})
      local tag=heading(pick,'Tag',can and 'BANISH' or 'LOCKED · UNLOCK TO BANISH',12,0,cardW-24,cardH,can and 34 or 22,can and white or cream)
      tag.TextXAlignment=Enum.TextXAlignment.Center;tag.ZIndex=6;tag.TextStrokeTransparency=0
      if can then pick.Activated:Connect(function() askBanish(screenGui(),i,o) end) end
     end
    end
   end
   if offersStrip then
    local cw=shownCards*(cardW+12)-8
    offersStrip.CanvasSize=UDim2.fromOffset(cw,0);offersStrip.ScrollBarThickness=cw>leftW+1 and math.ceil(K.px(4)) or 0
    top+=offersStrip.Size.Y.Offset+math.ceil(K.px(4))
   else top+=math.ceil(4/cols)*(cardH+lockH+24) end
  end
  -- Owned tiles (2026-10-16, user: icons didn't fit their boxes): a thinner frame (8 px, not the
  -- button's 11), each icon centred in it with an even gap (Fit keeps its shape: 64 px -> 46 px icon,
  -- 9 px each side), and the count on a dark pill 5 px in from the corner, off the frame's edge.
  local function slotFrame(b) b.SliceScale=.36 end
  local function slotPad(size) return math.max(8,math.floor(size*.15)) end
  local function countPill(b,s,size,cs)
   local pw=math.ceil(TS:GetTextSize(s,cs,T.Body,Vector2.new(200,50)).X)+10;local ph=cs+4
   local c=text(b,'Count',s,size-5-pw,size-5-ph,pw,ph,cs);c.TextXAlignment=Enum.TextXAlignment.Center;c.ZIndex=4
   c.BackgroundColor3=Color3.fromRGB(8,10,11);c.BackgroundTransparency=.3
   T.make('UICorner',c,{CornerRadius=UDim.new(0,6)})
   return c
  end
  local split=leftW>=660
  local weaponW=split and math.min(300,leftW*.32) or leftW
  local itemW=split and leftW-weaponW-24 or leftW
  if split and not compact then top=math.max(top,ht-inventoryH-12) end
  -- Turret combining (2026-10-12, user: "it shouldnt automatically combine and it should be clear
  -- that the user can combine them"). data.combinable (ShopService, HandymanTurret.combinable): the
  -- turret ids that can combine now -> the next id. Each gets a lime up-arrow badge on its tile, a
  -- hint sits beside the Items title, and its popup has Combine. Example: 3 Nail Turrets -> the
  -- Nail tile shows the arrow; Combine 2 -> Twin Nailer leaves 1 Nail + 1 Twin.
  local combinable=type(data.combinable)=='table' and data.combinable or {}
  local anyCombine=next(combinable)~=nil
  local count=0;for _,copy in data.weapons do if copy.id~='' then count+=1 end end
  -- Weapons get the same arrow (2026-10-18, user: "players have reported not knowing they could
  -- combine weapons"): a weapon with a matching copy at its tier (ShopService canCombine). The hint
  -- shows when anything can combine. Example: two Tier I Bats -> both tiles show the arrow.
  local weaponCombine=false;for _,copy in data.weapons do if copy.canCombine then weaponCombine=true end end
  anyCombine=anyCombine or weaponCombine
  -- The lime up-arrow badge, top-right of a tile `cell` wide.
  local function combineBadge(b,cell)
   local s=math.clamp(math.floor(cell*.34),16,24)
   local mark=T.make('Frame',b,{Name='CombineBadge',AnchorPoint=Vector2.new(1,0),Position=UDim2.fromOffset(cell-4,4),Size=UDim2.fromOffset(s,s),BackgroundColor3=T.Color.lime,BorderSizePixel=0,ZIndex=4})
   T.make('UICorner',mark,{CornerRadius=UDim.new(1,0)})
   T.make('UIStroke',mark,{Color=T.Color.ink,Thickness=2})
   -- An up arrow in ink: a stem and two strokes leaning in (T.check's way of drawing marks).
   for _,a in {{.5,.6,.17,.46,0},{.385,.4,.17,.38,45},{.615,.4,.17,.38,-45}} do
    local line=T.make('Frame',mark,{Name='Arrow',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(a[1],a[2]),Size=UDim2.fromScale(a[3],a[4]),Rotation=a[5],BackgroundColor3=T.Color.ink,BorderSizePixel=0,ZIndex=5})
    T.make('UICorner',line,{CornerRadius=UDim.new(1,0)})
   end
  end
  -- Compact: Items and Weapons are one sideways row each, the title first and then the tiles (the
  -- combine hint after the last one). Side by side, Weapons as wide as its tiles (at least 42% while
  -- Items needs the room); stacked when the shop is under 560 wide. Example, 844x390: one 43 px row.
  local hint='Lime arrow: tap to combine 2 into the next tier'
  local cCell=th(64);local rowH=cCell+math.ceil(K.px(5));local stack=leftW<560
  local headSize,hintSize=K.cSize(14),K.cSize(11)
  local itemsTW,weaponsTW,hintW=0,0,0
  if compact then
   local function wide(s,size,font) return math.ceil(TS:GetTextSize(s,size,font,Vector2.new(4000,100)).X*1.1)+8 end
   itemsTW,weaponsTW=wide('Items',headSize,Enum.Font.FredokaOne),wide('Weapons ('..count..'/6)',headSize,Enum.Font.FredokaOne)
   hintW=anyCombine and wide(hint,hintSize,T.Body) or 0
   local itemsNeed=itemsTW+8+#data.items*(cCell+8)+hintW
   local weaponsNeed=weaponsTW+8+count*(cCell+8)-8
   if stack then itemW,weaponW=leftW,leftW
   else weaponW=math.min(weaponsNeed,math.max(math.floor(leftW*.42),leftW-16-itemsNeed));itemW=leftW-16-weaponW end
  end
  local function inventoryRegion(name,x,y,width)
   if compact then
    return T.make('ScrollingFrame',left,{Name=name,Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(width,rowH),BackgroundTransparency=1,BorderSizePixel=0,ScrollingDirection=Enum.ScrollingDirection.X,
     ScrollBarThickness=0,ScrollBarImageColor3=green,HorizontalScrollBarInset=Enum.ScrollBarInset.None,VerticalScrollBarInset=Enum.ScrollBarInset.None,CanvasSize=UDim2.new()})
   end
   local f=Instance.new('Frame');f.Name=name;f.BackgroundTransparency=1;f.Position=UDim2.fromOffset(x,y);f.Size=UDim2.fromOffset(width,inventoryH);f.Parent=left;return f
  end
  -- A compact row's canvas: as wide as what's in it, with the bar only when it scrolls.
  local function fitRow(f,cw) f.CanvasSize=UDim2.fromOffset(cw,0);f.ScrollBarThickness=cw>f.Size.X.Offset+1 and math.ceil(K.px(4)) or 0 end
  local items=inventoryRegion('Items',0,top,itemW)
  local itemX=compact and itemsTW+8 or 0
  if compact then
   K.cCap(heading(items,'Title','Items',0,0,itemsTW,cCell,headSize),14)
   if anyCombine then K.cCap(text(items,'CombineHint',hint,itemX+#data.items*(cCell+8),0,hintW,cCell,hintSize,green),11) end
   fitRow(items,itemX+#data.items*(cCell+8)-8+hintW)
  else
   heading(items,'Title','Items',0,0,anyCombine and 88 or itemW,32,28)
   if anyCombine then text(items,'CombineHint',hint,96,0,itemW-96,32,15,green) end
  end
  local itemCols=compact and math.max(1,#data.items) or math.max(1,math.min(8,math.floor((itemW+8)/(th(52)+8))));local cell=compact and cCell or math.min(th(64),(itemW-(itemCols-1)*8)/itemCols)
  local anchor
  for i,it in data.items do
   local entry=Catalog.ById[it.id];local x=((i-1)%itemCols)*(cell+8);local y=40+math.floor((i-1)/itemCols)*(cell+8)
   if compact then x=itemX+(i-1)*(cell+8);y=0 end
   local b=btn(items,'ItemSlot'..i,'',x,y,cell,cell,function() self.selected={kind='Item',id=it.id};refresh() end,true)
   slotFrame(b);T.setTier(b,entry.tier)
   local pad=slotPad(cell);art(b,entry,pad,pad,cell-2*pad,cell-2*pad)
   if it.count>1 then countPill(b,'×'..it.count,cell,tap>0 and 16 or 14) end
   -- Turret tiles: a small tier badge top-left (I-IV, like weapon slots), and the combine arrow
   -- top-right, 4 px in. Cells are at least 52 px: badge 4..30 (III), arrow 31..48, count from 29 down.
   if entry.turret then local tb=T.tierBadge(b,entry.turret,4,4);tb.Size=UDim2.fromOffset(8+#T.Roman[entry.turret]*6,16) end
   if combinable[it.id] then combineBadge(b,cell) end
   -- The popup anchors where the tile shows: a scrolled compact row moves it left.
   if self.selected and self.selected.kind=='Item' and self.selected.id==it.id then anchor=Vector2.new(x-(compact and self.ItemsScroll or 0),top+y) end
  end
  local itemBottom=math.max(inventoryH,40+math.ceil(#data.items/itemCols)*(cell+8))
  if compact then if stack then top+=rowH+math.ceil(K.px(4)) end
  elseif not split then top+=itemBottom+18 end
  local wx=compact and (stack and 0 or itemW+16) or split and leftW-weaponW or 0
  local owned=inventoryRegion('Weapons',wx,top,weaponW)
  local weaponX=compact and weaponsTW+8 or 0
  if compact then K.cCap(heading(owned,'Title','Weapons ('..count..'/6)',0,0,weaponsTW,cCell,headSize),14);fitRow(owned,weaponX+count*(cCell+8)-8)
  else heading(owned,'Title','Weapons ('..count..'/6)',0,0,weaponW,32,27) end
  local slotSize=compact and cCell or math.min(th(66),(weaponW-16)/3);local shown=0
  for i,copy in data.weapons do
   local base=Weapons.ById[copy.id]
   if base then
    local x=(shown%3)*(slotSize+8);local y=40+math.floor(shown/3)*(slotSize+8)
    if compact then x=weaponX+shown*(slotSize+8);y=0 end
    shown+=1
    local b=btn(owned,'WeaponSlot'..i,'',x,y,slotSize,slotSize,function() self.selected={kind='Weapon',slot=i,copy=copy.copy};refresh() end,true)
    slotFrame(b);T.setTier(b,copy.tier)
    local pad=slotPad(slotSize);thumbnail(b,combat.WeaponTemplates:FindFirstChild(copy.id),pad,pad,slotSize-2*pad,slotSize-2*pad)
    T.tierBadge(b,copy.tier,slotSize-5,slotSize-5,Vector2.new(1,1))
    if copy.canCombine then combineBadge(b,slotSize) end
    if self.selected and self.selected.kind=='Weapon' and self.selected.copy==copy.copy then anchor=Vector2.new(wx+x-(compact and self.WeaponsScroll or 0),top+y) end
   end
  end
  top+=compact and rowH or math.max(inventoryH,40+math.ceil(shown/3)*(slotSize+8))
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
    -- The dim reaches the screen edges (2026-10-16, user: a grey frame showed round the screen with
    -- a popup open). This layout sits in the HUD's scroller, which clips it, so the dim above only
    -- covered the shop and the margins and bands around it stayed the lighter backdrop. A second
    -- shade on the scroller's parent (the full-screen Menus backdrop), just under the scroller,
    -- darkens those too; it goes with this layout.
    local clip;local up=parent
    while up and not up:IsA('LayerCollector') do if up:IsA('ScrollingFrame') then clip=up end;up=up.Parent end
    if clip and clip.Parent and clip.Parent:IsA('GuiObject') then
     local edge=Instance.new('TextButton');edge.Name='FocusEdge';edge.Text='';edge.AutoButtonColor=false;edge.Selectable=false;edge.BackgroundColor3=Color3.new(0,0,0);edge.BackgroundTransparency=dim.BackgroundTransparency;edge.BorderSizePixel=0
     edge.Size=UDim2.fromScale(1,1);edge.ZIndex=math.max(0,clip.ZIndex-1);edge.Parent=clip.Parent
     edge.Activated:Connect(function() self.selected=nil;refresh() end)
     root.Destroying:Connect(function() edge:Destroy() end)
    end
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
    if base then thumbnail(well,combat.WeaponTemplates:FindFirstChild(copy.id),8,8,56,56) else art(well,entry,8,8,56,56) end
    heading(detail,'Title',(base or entry).name,98,14,dw-116,44,23,tiers[tier])
    text(detail,'Tier',E.TIER_NAMES[tier],98,60,dw-116,24,tap>0 and 16 or 14)
    -- The content stacks top-down and the buttons go under it, so stat lines, traits and the class
    -- row never overlap, whatever a weapon shows (2026-10-03: Range was hidden behind the class row).
    -- Example, Tier II Magic Staff: 4 stat lines end at 200, the class row sits at 208-232, the
    -- buttons start at 266. The panel grows (and scrolls on short screens) when content needs it.
    local y=104
    if base then
     local sets=Stats.typeCounts(equippedIds(data))
     y+=weaponStats(detail,base,copy.tier,18,y,dw-36,sets)
     local traits=traitLine(base,copy.tier,sets)
     if traits~='' then local th=readableHeight(traits,15,dw-36,22);text(detail,'Traits',traits,18,y+2,dw-36,th,15,tiers[tier]);y+=th+4 end
     y+=8
     -- Specialty bar and this weapon's sets now (2026-10-09; they replaced the class row).
     specBar(detail,base,18,y,dw-36,26);y+=34
     y+=typeRows(detail,base,18,y,dw-36,sets,false)+6
     local damage=math.max(0,math.floor(tonumber(copy.damage) or 0));local kills=math.max(0,math.floor(tonumber(copy.kills) or 0))
     text(detail,'RunPerformance',string.format('THIS RUN · %s damage · %s kills',damage,kills),18,y,dw-36,26,16,cream);y+=32
    else
     y+=effects(detail,entry,18,y,dw-36,true)
     local works,wc=worksLine(entry,data)
     if works then text(detail,'WorksWith',works,18,y+4,dw-36,40,15,wc);y+=46 end
     y+=14
    end
    -- Turret items (2026-10-12) get one Combine button over Cancel, where a weapon's Recycle sits.
    local turret=entry and entry.turret
    local below=base and 2*(b1+7)+b2+12 or b2+12+16+(turret and b1+7 or 0) -- the buttons under the content
    local dh=math.max(392+(base and 2*(b1-34) or 0)+(b2-32),y+below+(base and 0 or 40));local visibleH=math.min(dh,ht-16)
    local cancelY=dh-12-b2;local sellY=cancelY-7-b1;local combineY=sellY-7-b1
    if not base then text(detail,'Description',entry.description,18,y,dw-36,math.max(40,(turret and sellY or cancelY)-16-y),15) end
    if turret then
     -- Lime when it can combine now (ShopService's data.combinable); greyed with the reason otherwise.
     -- Example: 3 Nail Turrets -> "Combine 2 → Twin Nailer"; 1 -> "Need 2 to combine".
     local nextEntry=combinable[entry.id] and Catalog.ById[combinable[entry.id]]
     local have=0;for _,it in data.items do if it.id==entry.id then have=it.count end end
     local caption=nextEntry and 'Combine 2 → '..nextEntry.name or turret>=4 and 'Maximum tier' or have<2 and 'Need 2 to combine' or 'No room: item inventory full'
     local combine=btn(detail,'Combine',caption,14,sellY,dw-28,b1,function()
      T.sound('ui_upgrade');self.combining={t=os.clock(),revision=(self:snapshot() or data).revision};self:send('CombineItem',entry.id);self.selected=nil
     end,nextEntry==nil)
     combine.Interactable=data.phase=='Shop' and nextEntry~=nil;combine.Caption.TextColor3=combine.Interactable and white or Color3.fromRGB(135,146,150)
    end
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
  -- The compact rows keep their sideways scroll across redraws (a buy, a lock) until the shop ends.
  if compact then
   for rowKey,f in {OffersScroll=offersStrip,ItemsScroll=items,WeaponsScroll=owned} do
    task.defer(function() if f.Parent then f.CanvasPosition=Vector2.new(self[rowKey] or 0,0);f:GetPropertyChangedSignal('CanvasPosition'):Connect(function() self[rowKey]=f.CanvasPosition.X end) end end)
   end
  end
  -- BUY effect: a buy the server took shows its offer sold (the last unsold one: the shop refilled,
  -- so its token is gone). Deferred after the scroll restore above, so the slot is where it shows.
  for token,b in self.bought do
   local o=data.offers[b.index];local gone=true
   for _,x in data.offers do if x.token==token then gone=false;break end end
   if os.clock()-b.t>4 or data.wave~=b.wave then self.bought[token]=nil;b.card:Destroy()
   elseif (o and o.token==token and o.sold) or (b.last and gone and arrived(b,data)) then self.bought[token]=nil;task.defer(playBuy,b,data,parent)
   elseif gone then self.bought[token]=nil;b.card:Destroy() end
  end
  -- A saved Banish's result as a short toast, "Banished Two Straws for this run", once the server's
  -- answer is in (a newer revision). A bought one's comes as the purchase reply's toast (RogueliteUI).
  local sent=self.banishing
  if sent and (data.revision or 0)>sent.revision and type(data.message)=='string' and data.message:find('^Banished ') then
   self.banishing=nil
   local screen=screenGui();if screen then T.toast(screen,data.message,T.Color.lime) end
  elseif sent and os.clock()-sent.t>5 then self.banishing=nil end
  -- A turret combine's result, "2 Nail Turrets → Twin Nailer", the same way (2026-10-12).
  local combined=self.combining
  if combined and (data.revision or 0)>combined.revision and type(data.message)=='string' and data.message:find(' → ',1,true) then
   self.combining=nil
   local screen=screenGui();if screen then T.toast(screen,data.message,T.Color.lime) end
  elseif combined and os.clock()-combined.t>5 then self.combining=nil end
  -- A controller in banish mode starts on the first offer's BANISH (after the HUD's own selection
  -- restore, which is deferred).
  if banishing then task.delay(.05,function() pcall(function()
   if not left.Parent or not game:GetService('UserInputService'):GetLastInputType().Name:find('^Gamepad') then return end
   local GS=game:GetService('GuiService');local sel=GS.SelectedObject
   if sel and sel.Name=='BanishPick' and sel:IsDescendantOf(left) then return end
   for i=1,4 do local c=left:FindFirstChild('Offer'..i,true);local pick=c and c:FindFirstChild('BanishPick');if pick then GS.SelectedObject=pick;return end end
  end) end) end
  return data
 end
 return self
end
return M
