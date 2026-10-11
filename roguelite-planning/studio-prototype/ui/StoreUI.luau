-- Store window (lobby): DAILY deals, BUNDLES, CHESTS and EMERALDS. The window, tabs and buttons
-- keep the green theme; every offer is a saturated colour card with big art that sticks out past
-- its top edge (StoreFX, plans/2026-10-01-H-store-and-quests.md). Presentation and requests only:
-- purchases go through PurchaseRequest / ProfileAction and are checked on the server.
local RS=game:GetService('ReplicatedStorage')
local T=require(RS:WaitForChild('UITheme'))
local FX=require(RS:WaitForChild('StoreFX'))
local combat=RS:WaitForChild('RogueliteCombat')
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local Stats=require(combat:WaitForChild('CharacterStats'))
local Chests=require(combat:WaitForChild('ChestConfig'))
local Money=require(combat:WaitForChild('MonetizationConfig'))
local Armor=require(combat:WaitForChild('ArmorCatalog'))
local WeaponArt=require(RS:WaitForChild('WeaponInventoryUI'))
local WeaponIcons=WeaponArt.Icons
-- The quests' CLAIM effect, for the DAILY tab's claims (user, 2026-10-03). QuestsUI doesn't require
-- this module, so there is no cycle.
local Quests=require(RS:WaitForChild('QuestsUI'))
-- A weapon's icon, or its uploaded art by name while it isn't in WeaponCatalog yet (from a
-- Studio edit to the old store, kept 2026-10-02).
local function iconFor(id,name) return (id and WeaponIcons[id]) or (WeaponArt.IconsByName and WeaponArt.IconsByName[name]) or 'armory' end
local C=T.Color
local S={}
-- One server result per awarded copy; never animate the displayed offer's guessed quantity.
-- The daily catalog bounds the effect (currently at most five copies per purchase).
function S.dailyReward(result)
 if type(result)~='table' or result.ok~=true or type(result.results)~='table' then return nil end
 local amount=#result.results;local maximum=0
 for _,range in Chests.DealAmount do maximum=math.max(maximum,range[2]) end
 if amount<1 or amount>maximum then return nil end
 local id
 for _,entry in result.results do
  if type(entry)~='table' or not Weapons.ById[entry.id] or id and id~=entry.id then return nil end
  id=entry.id
 end
 return {id=id,amount=amount}
end

S.Tabs={{'Daily','quests','DAILY'},{'Bundles','store','BUNDLES'},{'Chests','chest','CHESTS'},{'Emeralds','emerald','EMERALDS'}}
-- Class cards: class, signature weapon, Robux product, card colour.
-- Chef sells through the old ClassThrower product (2026-10-09: Thrower became Chef, same product id).
-- Each card shows the class's starting weapon: Chef the Frying Pan, Juggler the Rubber Duck (was the
-- Boxing Gloves, a Rare Brawler weapon since 2026-10-10). Brawler is free, so it has no card.
S.Classes={{'Chef','01','ClassThrower','red'},{'Juggler','17','ClassJuggler','purple'},{'Handyman','24','ClassHandyman','blue'}}
S.GemSizes={104,116,126,136,146,158}
S.ChestSashes={nil,'POPULAR','BEST VALUE'}
S.GemSashes={nil,'POPULAR',nil,nil,nil,'BEST VALUE'}
S.DealTheme={Common='steel',Rare='blue',Epic='purple',Legendary='gold',Godly='shadow'}
-- Godly bundles take their armor set's look.
S.BundleTheme={Phoenix='fire',DragonScale='shadow'}
local RED_SASH={Color3.fromRGB(255,96,110),Color3.fromRGB(196,24,44)}

-- Body layout: W wide; the offer list is SW wide (scroll bar inset); full-width cards are CW.
local W=1064;local SW=W-14;local CW=SW-4
local function comma(n)
 local s=tostring(math.floor(n or 0));local out=s:reverse():gsub('(%d%d%d)','%1,'):reverse()
 return (out:gsub('^,',''))
end
local function weaponId(name) for id,w in Weapons.ById do if w.name==name then return id end end end
local function godlyShort(name) for _,g in Money.GodlyWeapons do if g[1]==name then return g[2] end end;return name end
local function center(l) l.TextXAlignment=Enum.TextXAlignment.Center;return l end

-- ctx: profile() -> LobbyUI profile, need(rec), selection (kept between opens), open(name,arg),
-- cost(parent,amount,asset,size) (currency amount with its icon), fmt(n), setRedraw(fn).
function S.open(screen,ctx,focus)
 local w=T.window(screen,'StoreWindow','Store',1100,640,nil,{large=true});local b=w.Body
 local sel=ctx.selection
 sel.storeTab=focus or sel.storeTab or 'Daily'
 local profile=ctx.profile()
 local list,draw
 local function buy(key,arg) combat.PurchaseRequest:FireServer(key,arg) end
 -- The window's emerald pill icon, looked up each time (every redraw replaces it).
 local function gemIcon() local p=b:FindFirstChild('EmeraldsPill');return p and p:FindFirstChild('Icon') end
 -- parts: the art the CLAIM effect (QuestsUI) plays from once the server says yes: emeralds fly
 -- into the pill, a chest squashes, a weapon pops. Copied before asking, because the redraw on the
 -- result replaces them (user, 2026-10-03).
 local function act(action,a,parts)
  local shots=Quests.snapshot(parts or {})
  local completed,r=pcall(function() return combat.ProfileAction:InvokeServer(action,a) end)
  if not completed or type(r)~='table' then r={ok=false,message='Purchase could not be confirmed. Please try again.'} end
  if action=='BuyDeal' then
   local reward=S.dailyReward(r)
   for _,shot in shots do
    if shot.kind=='item' then
     -- A daily reset can replace the offer while the request is in flight: use the awarded ID.
     shot.kind='dealItem';shot.amount=reward and reward.amount or 0
     shot.name=reward and Weapons.ById[reward.id].name or nil
     local icon=shot.copy and shot.copy:FindFirstChild('Icon')
     if reward and icon then icon.Image=WeaponIcons[reward.id] or '' end
    end
   end
  end
  if r.ok then T.sound('ui_purchase') end
  if r.ok and w.Root.Parent then Quests.claimFX(screen,shots,gemIcon) else for _,s in shots do s.copy:Destroy() end end
  T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
 end
 -- GIFT (2026-10-04, user: "add gifting to the store"): opens the recipient picker for this product
 -- (S.giftPicker); the server checks everything again. You can gift a one-time pack or class you
 -- already own. Charcoal, so BUY stays the main button.
 local function giftButton(parent,name,x,y,bw,bh,key,arg)
  local gb=FX.button(parent,name,'GIFT',x,y,bw,bh,function() S.giftPicker(screen.Parent,key,{arg=arg,window=w.Root,signature=ctx.signature}) end,true)
  gb.Caption.TextSize=math.min(24,bh-22)
  return gb
 end
 -- Robux price button (breathes when `pulse`). owned: true = OWNED, a string = that label (e.g.
 -- COMING SOON); neither is buyable. arg goes with the purchase (the Godly Starter's pick).
 -- A giftable product's GIFT takes the right part of the space when it is 200+ px wide (BUY 169 +
 -- GIFT 83 on a 260 px hero card); class cards are narrower and put theirs in a corner. No GIFT on
 -- COMING SOON.
 local function priceButton(parent,name,x,y,bw,bh,key,owned,pulse,arg)
  local item=Money.Products[key] or Money.Passes[key]
  if bw>=200 and Money.giftable(key) and type(owned)~='string' then
   local gw=math.clamp(math.floor(bw*.32),64,100)
   giftButton(parent,name..'Gift',x+bw-gw,y,gw,bh,key,arg)
   bw-=gw+8
  end
  local pb=FX.button(parent,name,owned==true and 'OWNED' or owned or ('R$ '..comma(Money.price(key))),x,y,bw,bh,function() buy(key,arg) end,owned and true or false)
  pb.Caption.TextSize=math.min(34,bh-18)
  if owned then pb.Interactable=false elseif pulse then FX.pulse(pb,.04) end
  return pb
 end
 local function tiles(face,list_,x,y,size,gap)
  for i,it in list_ do FX.tile(face,'Item'..i,x+(i-1)*(size+gap),y,size,it[1],it[2],it[3],it[4]) end
 end
 -- SEE ODDS, on every card with chests in it (all of them hold Legendary Chests): the chest screen
 -- opens straight onto the Legendary Chest's odds, and closing them comes back to this tab.
 local function seeOdds()
  sel.chest='Legendary';local tab=sel.storeTab
  ctx.open('Chests',{chest='Legendary',odds=true,back=function() ctx.open('Store',tab) end})
 end
 local function oddsButton(parent,x,y,bw,bh)
  local ob=FX.button(parent,'Odds','SEE ODDS',x,y,bw,bh,seeOdds,true);ob.Caption.TextSize=math.min(20,bh-22)
  return ob
 end
 -- Wide card: title, line and item slots on the left; big art, sash and price on the right.
 -- tiles: {asset, label, rarity, amount}. opts: tag, sash, sashColors, pulse, shine, artSize, arg,
 -- odds (a SEE ODDS button left of the price, between the item slots and the art).
 local function hero(name,y,h,theme,title,sub,items,asset,key,owned,opts)
  opts=opts or {}
  local face,th=FX.card(list,name,2,y,CW,h,theme)
  -- The art sticks out above the card but always ends 96 px above its bottom (the price button).
  local size=math.min(opts.artSize or 240,h-96+44)
  FX.art(face,asset,CW-170,h-96-size/2,size,th,opts.raySize or 420)
  FX.title(face,'Title',title,28,22,CW-440,58,52,th.tint)
  FX.sub(face,'Sub',sub,30,82,CW-440,24,18)
  local size_=math.min(104,math.floor((CW-440-(#items-1)*12)/math.max(#items,1)))
  tiles(face,items,28,h-math.floor(size_*1.08)-24,size_,12)
  priceButton(face,'Buy',CW-300,h-90,260,66,key,owned,opts.pulse,opts.arg)
  -- Four 104 px slots end at x 480; this sits at 562-732, clear of them and of the price (746).
  if opts.odds then oddsButton(face,CW-484,h-84,170,54) end
  if opts.tag then FX.tag(face,opts.tag,th.tag,th.accent) end
  if opts.sash then FX.sash(face,opts.sash,opts.sashColors and opts.sashColors[1],opts.sashColors and opts.sashColors[2]) end
  if opts.shine then FX.shine(face) end
  return face,th
 end
 -- Half-width card with art on the right (VIP, Quick Open) or a quantity picker (Rerolls, Banishes).
 local HW=math.floor((SW-18)/2)
 local function half(name,x,y,h,theme,title,sub,asset)
  local face,th=FX.card(list,name,x,y,HW,h,theme)
  FX.art(face,asset,HW-104,48,170,th,320)
  FX.title(face,'Title',title,24,22,HW-230,50,42,th.tint)
  local s=FX.sub(face,'Sub',sub,26,76,HW-236,44,17);s.TextYAlignment=Enum.TextYAlignment.Top
  return face,th
 end

 local tabs={}
 function tabs.Daily()
  local y=10
  local timer=FX.header(list,'DAILY DEALS','',y,SW);y+=72+20
  local function tick()
   local sec=Money.secondsToReset()
   timer.Text=string.format('New deals in %02d:%02d:%02d',sec//3600,sec%3600//60,sec%60)
  end
  tick()
  task.spawn(function() while timer.Parent do task.wait(1);if timer.Parent then tick() end end end)
  local deals=profile.daily.deals or {}
  local n=math.max(1,#deals);local gap=14;local cw=math.floor((SW-(n-1)*gap)/n);local ch=330
  for i,deal in deals do
   local free=deal.kind=='Emeralds';local rarity=deal.rarity or 'Common'
   local face,th=FX.card(list,'Deal'..i,(i-1)*(cw+gap),y,cw,ch,free and 'emerald' or S.DealTheme[rarity] or 'steel')
   local art=FX.art(face,free and 'emerald' or WeaponIcons[deal.id],cw/2,50,116,th,220)
   Quests.tagReward(art,free and 'emerald' or 'item',free and deal.amount or nil,free and FX.Rarity.Emerald.top or (FX.Rarity[rarity] or FX.Rarity.Common).top)
   center(FX.title(face,'Amount',(free and '+' or '×')..comma(deal.amount),12,110,cw-24,42,38,th.tint))
   local name=free and 'Emeralds' or Weapons.ById[deal.id].name
   center(T.label(face,'Name',name,12,154,cw-24,26,20))
   if deal.kind=='Weapon' then
    center(FX.sub(face,'Rarity',string.upper(rarity)..'  ·  '..(deal.each or deal.price)..' each',12,182,cw-24,20,15))
    local rec=profile.weapons[deal.id]
    if rec then T.upgradeBar(face,'Bar',16,210,cw-32,20,rec.have,ctx.need(rec))
    else center(FX.title(face,'New','NEW WEAPON',12,208,cw-24,24,18,C.gold)) end
   end
   local label=deal.bought and 'CLAIMED' or deal.currency=='Free' and 'FREE' or ''
   local pb=FX.button(face,'Buy',label,14,ch-70,cw-28,56,function() act('BuyDeal',i,{art}) end,deal.bought)
   pb.Caption.TextSize=24
   if deal.bought then pb.Interactable=false
   elseif deal.currency=='Emeralds' then ctx.cost(pb,deal.price,'emerald',22) end
   if deal.currency=='Free' and not deal.bought then FX.tag(face,'FREE',th.tag,th.accent);FX.pulse(pb,.05) end
  end
  y+=ch+44
  local chest=Chests.ById[Money.VIPDailyChest]
  local face,th=FX.card(list,profile.vip and 'VipDaily' or 'VipPromo',2,y,CW,160,'purple')
  local art=FX.art(face,chest.icon,100,62,150,th,300)
  if profile.vip then
   local claimed=profile.daily.vipClaimed
   -- Where paid random items are restricted the chest comes as its emerald price instead.
   Quests.tagReward(art,profile.restricted and 'emerald' or 'chest',profile.restricted and chest.emeralds or 1,(FX.Rarity[FX.ChestRarity[chest.id]] or FX.Rarity.Common).top)
   FX.title(face,'Title','VIP DAILY CHEST',200,28,CW-480,50,44,th.tint)
   FX.sub(face,'Sub','A free '..chest.name..', every single day.',202,82,CW-480,24,18)
   local cb=FX.button(face,'Claim',claimed and 'CLAIMED' or 'CLAIM',CW-268,48,240,64,function() act('ClaimVipChest',nil,{art}) end,claimed)
   cb.Caption.TextSize=30;cb.Interactable=not claimed;if not claimed then FX.pulse(cb,.05) end
  else
   FX.title(face,'Title','FREE '..string.upper(chest.name)..' EVERY DAY',200,28,CW-480,50,40,th.tint)
   FX.sub(face,'Sub','Get VIP: +25% emeralds from every run, and open ×10 chests.',202,82,CW-480,24,18)
   local go=FX.button(face,'Go','GET VIP',CW-268,48,240,64,function() sel.storeTab='Bundles';draw() end)
   go.Caption.TextSize=30;FX.pulse(go,.05);FX.shine(face);FX.tag(face,'VIP',th.tag,th.accent)
  end
  return y+190
 end

 function tabs.Bundles()
  local y=44
  -- The Starter Pack holds chests (a paid random item): hidden where those are restricted.
  local sp=Money.Products.StarterPack
  if not profile.restricted then
   hero('Starter',y,290,'gold','STARTER PACK','One time only · the best deal in the game.',
    {{'emerald',comma(sp.emeralds),'Emerald'},{Chests.ById.Legendary.icon,'Legendary','Legendary','×'..sp.chests.Legendary},{'quests','Rerolls','Rare','×'..sp.rerolls}},
    Chests.ById.Legendary.icon,'StarterPack',profile.starter,{tag='ONE TIME OFFER',sash='BEST VALUE',sashColors=RED_SASH,pulse=true,shine=true,odds=true})
   y+=290+34
  end
  -- Godly bundles: a Godly weapon + a full armor set + emeralds, one time each. COMING SOON until
  -- the weapon is in WeaponCatalog (the server refuses it too).
  FX.header(list,'GODLY BUNDLES','The strongest weapons in the game, with a full armor set.',y,SW);y+=72+48
  for _,key in Money.GodlyBundles do
   local bd=Money.Products[key];local set=Armor.ById[bd.armorSet]
   local wid=weaponId(bd.godly)
   local items={{iconFor(wid,bd.godly),godlyShort(bd.godly),'Godly'}}
   for _,slot in Armor.Slots do table.insert(items,{Armor.Icons[Armor.pieceId(bd.armorSet,slot)],slot,set.rarity}) end
   table.insert(items,{'emerald',comma(bd.emeralds),'Emerald'})
   local state=profile.bundles[key] and true or not wid and 'COMING SOON' or false
   local title=string.upper((bd.name:gsub(' Bundle$','')))
   hero(key,y,290,S.BundleTheme[bd.armorSet] or 'shadow',title,bd.godly..' + the full '..set.name..' armor set + '..comma(bd.emeralds)..' emeralds.',items,
    Armor.Icons[Armor.pieceId(bd.armorSet,'Chest')],key,state,{tag=set.rarity=='Godly' and 'GODLY ARMOR' or 'BEST GODLY DEAL',sash='ONE TIME',pulse=state==false,shine=true})
   y+=290+48
  end
  -- Godly Starter: tap a Godly to choose it (it lifts, glows and gets a check; the big art and name
  -- switch to it), then buy (+3 Legendary Chests). Hidden where paid random items are restricted.
  if not profile.restricted then
   local gs=Money.Products.GodlyStarter
   local pick=sel.godlyPick or 1
   local ids={};for i,g in Money.GodlyWeapons do ids[i]=weaponId(g[1]) end
   local state=profile.bundles.GodlyStarter and true or not ids[pick] and 'COMING SOON' or false
   local h=340
   local face,th=FX.card(list,'GodlyStarter',2,y,CW,h,'obsidian')
   FX.tag(face,'PICK YOUR GODLY',th.tag,th.accent)
   FX.art(face,iconFor(ids[pick],Money.GodlyWeapons[pick][1]),CW-170,75,230,th,420)
   local nm=center(FX.title(face,'Picked',string.upper(Money.GodlyWeapons[pick][1]),CW-305,198,270,36,30,Color3.fromRGB(255,150,160)))
   nm.TextColor3=Color3.fromRGB(255,96,112)
   FX.title(face,'Title','GODLY STARTER',28,22,CW-440,58,52,th.tint)
   FX.sub(face,'Sub',Money.GodlyWeapons[pick][1]..' + '..gs.chests.Legendary..' Legendary Chests. One time only.',30,82,CW-440,24,18)
   local dot=T.make('Frame',face,{Name='StepDot',Position=UDim2.fromOffset(30,112),Size=UDim2.fromOffset(26,26),BackgroundColor3=th.accent,BorderSizePixel=0})
   T.make('UICorner',dot,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',dot,{Color=FX.INK,Thickness=2.5})
   local one=T.label(dot,'Number','1',0,0,0,0,16,FX.INK);one.Size=UDim2.fromScale(1,1);one.TextStrokeTransparency=1
   T.label(face,'Step','CHOOSE ONE',64,112,220,26,19,th.accent).TextXAlignment=Enum.TextXAlignment.Left
   local size,gap,ty=84,9,166
   for i,g in Money.GodlyWeapons do
    local x=28+(i-1)*(size+gap);local chosen=i==pick
    if chosen then
     T.make('ImageLabel',face,{Name='PickGlow',BackgroundTransparency=1,Image=FX.Asset.glow,ImageColor3=Color3.fromRGB(255,60,90),ImageTransparency=.05,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(x+size/2,ty+36),Size=UDim2.fromOffset(170,170)})
    end
    local t=FX.tile(face,'Item'..i,x,ty,size,iconFor(ids[i],g[1]),g[2],'Godly')
    if chosen then
     -- Lifted and 10% bigger around its centre, white rim, check badge.
     t.AnchorPoint=Vector2.new(.5,.5);t.Position=UDim2.fromOffset(x+size/2,ty+t.Size.Y.Offset/2-8)
     T.make('UIScale',t,{Scale=1.1})
     local stroke=t:FindFirstChildOfClass('UIStroke');stroke.Color=Color3.new(1,1,1);stroke.Thickness=3.5
     FX.check(t,-8,-8,26)
    else
     local dim=T.make('Frame',t,{Name='Dim',BackgroundColor3=FX.INK,BackgroundTransparency=.45,BorderSizePixel=0,Size=UDim2.fromScale(1,1)})
     T.make('UICorner',dim,{CornerRadius=UDim.new(0,12)})
     t.MouseEnter:Connect(function() dim.BackgroundTransparency=.8 end)
     t.MouseLeave:Connect(function() dim.BackgroundTransparency=.45 end)
    end
    local hit=T.make('TextButton',t,{Name='Pick',Text='',BackgroundTransparency=1,Size=UDim2.fromScale(1,1),Selectable=true})
    hit.Activated:Connect(function() if sel.godlyPick~=i then sel.godlyPick=i;T.sound('ui_equip');draw() end end)
   end
   -- The chests that come with it, as a tilted sticker after a plus.
   local sx=28+#Money.GodlyWeapons*(size+gap)+4
   local plus=center(FX.title(face,'Plus','+',sx,ty+22,26,44,40,th.tint))
   plus.TextColor3=th.accent
   FX.tile(face,'Chests',sx+30,ty-6,88,Chests.ById.Legendary.icon,'Legendary','Legendary','×'..gs.chests.Legendary).Rotation=-8
   -- Under the chest sticker (it ends near y 262), never reaching the price button (x 746).
   oddsButton(face,math.min(sx+4,CW-300-12-140),h-62,140,46)
   priceButton(face,'Buy',CW-300,h-90,260,66,'GodlyStarter',state,state==false,pick)
   FX.shine(face)
   y+=h+48
  end
  FX.header(list,'MORE DEALS','Upgrades, passes and boosts.',y,SW);y+=72+40
  local ab=Money.Products.ArsenalBundle
  local items={}
  for _,cl in Stats.ClassOrder do table.insert(items,{WeaponIcons[(ctx.signature or {})[cl] or ''] or 'armory','+'..ab.signatureUpgrades,'Rare'}) end
  table.insert(items,{'emerald',comma(ab.emeralds),'Emerald'})
  hero('Arsenal',y,290,'teal','ARSENAL BUNDLE','+'..ab.signatureUpgrades..' upgrades to every class starter weapon.',items,WeaponIcons['00'],'ArsenalBundle',false,{pulse=true,shine=true,artSize=210})
  y+=290+48
  -- VIP + Quick Open.
  local vh=320
  local face=half('VIP',0,y,vh,'purple','VIP PASS','Permanent. Yours on every visit.','profile')
  FX.tag(face,'FOREVER',FX.Themes.purple.tag,FX.Themes.purple.accent)
  tiles(face,{{'emerald','+25%','Emerald'},{Chests.ById[Money.VIPDailyChest].icon,'Daily','Legendary'},{'chest','Open ×10','Epic'},{'profile','VIP Tag','Rare'}},24,138,84,10)
  priceButton(face,'Buy',24,vh-84,HW-48,62,'VIP',profile.vip,true)
  FX.shine(face)
  face=half('QuickOpen',HW+18,y,vh,'wood','QUICK OPEN','Open 10 chests or eggs in one click.','chest')
  tiles(face,{{'chest','×10','Common'}},24,138,84,10)
  priceButton(face,'Buy',24,vh-84,HW-48,62,'QuickOpen',profile.quickOpen,false)
  y+=vh+48
  -- Saved rerolls and banishes, with a quantity picker. Hidden where paid random items are restricted.
  if not profile.restricted then
   local ph=320
   for i,spec in {{'Rerolls','Reroll level-up and shop choices.',Money.RerollPacks,'quests',profile.rerolls,'blue'},{'Banishes','Remove unwanted level-ups for the run.',Money.BanishPacks,'armory',profile.banishes,'red'}} do
    local x=(i-1)*(HW+18)
    local f,th=FX.card(list,spec[1],x,y,HW,ph,spec[6])
    FX.art(f,spec[4],96,60,150,th,280)
    FX.title(f,'Title',string.upper(spec[1]),186,24,HW-210,48,42,th.tint)
    local s=FX.sub(f,'Sub',spec[2],188,76,HW-212,40,17);s.TextYAlignment=Enum.TextYAlignment.Top
    FX.sub(f,'Have','You have '..spec[5],188,120,HW-212,22,17,th.tint)
    local key='pack'..spec[1];sel[key]=sel[key] or 1
    local idx=sel[key];local packKey=spec[3][idx];local pack=Money.Products[packKey]
    -- Quantity row: [-] [×5] [+], 14 px under the art and the "You have" line.
    local qy=160;local bw=72;local qw=HW-48-2*bw-20
    FX.button(f,'Less','-',24,qy,bw,54,function() sel[key]=math.max(1,idx-1);draw() end,true).Caption.TextSize=34
    local q=T.make('Frame',f,{Name='Qty',Position=UDim2.fromOffset(24+bw+10,qy),Size=UDim2.fromOffset(qw,54),BackgroundColor3=FX.INK,BackgroundTransparency=.35,BorderSizePixel=0})
    T.make('UICorner',q,{CornerRadius=UDim.new(0,12)});T.make('UIStroke',q,{Color=FX.INK,Thickness=3})
    center(FX.title(q,'Text','×'..(pack.rerolls or pack.banishes),8,4,qw-16,46,32))
    FX.button(f,'More','+',HW-24-bw,qy,bw,54,function() sel[key]=math.min(#spec[3],idx+1);draw() end,true).Caption.TextSize=34
    priceButton(f,'Buy',24,ph-84,HW-48,62,packKey,false,true)
   end
   y+=ph+48
  end
  FX.header(list,'CLASSES','Play them right now.',y,SW);y+=72+40
  local tw=math.floor((SW-2*16)/3);local th_=340
  for i,cl in S.Classes do
   local owned=profile.classes[cl[1]]==true
   local f,th=FX.card(list,'Class_'..cl[1],(i-1)*(tw+16),y,tw,th_,cl[4])
   FX.art(f,WeaponIcons[cl[2]],tw/2,44,140,th,260)
   center(FX.title(f,'Name',string.upper(cl[1]),12,124,tw-24,44,38,th.tint))
   local d=center(FX.sub(f,'Desc',Stats.Classes[cl[1]].description,18,172,tw-36,44,16));d.TextYAlignment=Enum.TextYAlignment.Top
   local hw=math.floor((tw-36-10)/2)
   priceButton(f,'Buy',18,th_-80,hw,58,cl[3],owned)
   giftButton(f,'Gift',tw-96,16,82,46,cl[3]) -- top right, clear of the art and the OWNED tag
   local eb=FX.button(f,'BuyEmeralds','',28+hw,th_-80,hw,58,function()
    local r=combat.ProfileAction:InvokeServer('BuyClass',cl[1]);T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
   end,true)
   eb.Caption.Visible=false;if owned then eb.Interactable=false end
   ctx.cost(eb,owned and 'OWNED' or Money.ClassEmeraldPrice,not owned and 'emerald' or nil,20)
   if owned then FX.tag(f,'OWNED',th.tag,th.accent) end
  end
  return y+th_+30
 end

 function tabs.Chests()
  local y=10
  if profile.restricted then
   T.text(list,'Restricted','Chest packs are not available in your region. Open chests with emeralds earned in runs in the Chests menu.',4,8,SW-8,50,18,C.muted)
   return 70
  end
  local sub=FX.header(list,'LEGENDARY CHESTS',Chests.itemsText('Legendary')..' in every chest, one a guaranteed Legendary.',y,SW)
  sub.Position=UDim2.fromOffset(200,y+42);sub.Size=UDim2.fromOffset(SW-400,24)
  oddsButton(list,SW-178,y+36,174,40).Caption.TextSize=16
  y+=72+46
  local cw=math.floor((SW-2*16)/3);local ch=380;local base=Money.Products[Money.ChestPacks[1]]
  for i,key in Money.ChestPacks do
   local pack=Money.Products[key];local n=pack.chests.Legendary
   local face,th=FX.card(list,key,(i-1)*(cw+16),y,cw,ch,'gold')
   FX.art(face,Chests.ById.Legendary.icon,cw/2,80,168+(i-1)*18,th,340)
   center(FX.title(face,'Count','×'..n,12,162,cw-24,54,52,th.tint))
   center(T.label(face,'Name',n==1 and 'LEGENDARY CHEST' or 'LEGENDARY CHESTS',12,214,cw-24,26,21))
   local each=math.floor(pack.robux/n+.5)
   local save=n>1 and math.floor((1-each/base.robux)*100+.5) or 0
   center(FX.sub(face,'Drops',(n*(Chests.itemRange('Legendary')))..' items'..(save>0 and ('  ·  SAVE '..save..'%') or ''),12,244,cw-24,22,17,save>0 and Color3.fromRGB(220,255,170) or nil))
   priceButton(face,'Buy',16,ch-80,cw-32,62,key,false,i==3)
   if S.ChestSashes[i] then FX.sash(face,S.ChestSashes[i],RED_SASH[1],RED_SASH[2]) end
   if i==3 then FX.shine(face) end
  end
  y+=ch+48
  local mb=Money.Products.MegaBundle
  hero('Mega',y,290,'purple','MEGA BUNDLE','The biggest pile of chests in the game.',
   {{Chests.ById.Legendary.icon,'Legendary','Legendary','×'..mb.chests.Legendary},{'emerald',comma(mb.emeralds),'Emerald'},{'quests','Rerolls','Rare','×'..mb.rerolls},{'armory','Banishes','Epic','×'..mb.banishes}},
   'chest','MegaBundle',false,{tag='INSANE DEAL',pulse=true,shine=true,odds=true})
  y+=290+48
  local ub=Money.Products.UltimateBundle
  local each=math.floor(ub.robux/ub.chests.Legendary+.5)
  local save=math.floor((1-each/base.robux)*100+.5)
  hero('Ultimate',y,300,'obsidian','ULTIMATE BUNDLE','×'..ub.chests.Legendary..' Legendary Chests: '..each..' R$ each, save '..save..'%.',
   {{Chests.ById.Legendary.icon,'Legendary','Legendary','×'..ub.chests.Legendary},{'emerald',ctx.fmt(ub.emeralds),'Emerald'},{'quests','Rerolls','Rare','×'..ub.rerolls},{'armory','Banishes','Epic','×'..ub.banishes}},
   Chests.ById.Legendary.icon,'UltimateBundle',false,{tag='ULTIMATE',sash='SAVE '..save..'%',sashColors=RED_SASH,pulse=true,shine=true,artSize=250,odds=true})
  y+=300+40
  local owned=profile.chests.Legendary or 0
  if owned>0 then
   local ob=FX.button(list,'OpenOwned','OPEN YOUR '..owned..' LEGENDARY CHEST'..(owned>1 and 'S' or ''),2,y,SW-4,60,function() sel.chest='Legendary';ctx.open('Chests','Legendary') end)
   ob.Caption.TextSize=26;FX.pulse(ob,.03);y+=72
  end
  return y
 end

 function tabs.Emeralds()
  local y=10
  FX.header(list,'EMERALDS','Open chests, buy skills and unlock classes. You also earn them in every run.',y,SW);y+=72+44
  -- Two rows of three; art grows with the pack, the biggest one breathes and shines.
  local per=3;local gw=math.floor((SW-(per-1)*16)/per);local gh=330;local top=#Money.EmeraldPacks
  for i,key in Money.EmeraldPacks do
   local pack=Money.Products[key]
   local x=((i-1)%per)*(gw+16);local cy=y+(i-1)//per*(gh+52)
   local face,th=FX.card(list,'Emeralds_'..pack.name,x,cy,gw,gh,'emerald')
   -- Bigger packs show a bigger pile: pack i has i gems fanned behind the main one.
   local size=S.GemSizes[i] or 120;local cx,cy=gw/2,size/2-26
   for k=1,i-1 do
    local side=k%2==1 and -1 or 1;local row=(k-1)//2
    local g=T.icon(face,'Gem'..k,cx+side*(size*.3+row*size*.22)-size*.36,cy+size*.12+row*8-size*.36,size*.72,'emerald')
    g.Rotation=side*(14+row*10)
   end
   local gem=FX.art(face,'emerald',cx,cy,size,th,280);gem.ZIndex=2
   center(FX.title(face,'Amount',comma(pack.emeralds),12,144,gw-24,52,48,th.tint))
   local bonus=Money.bonusPercent(key)
   local nm=center(FX.sub(face,'Name',bonus>0 and (pack.name..'  ·  +'..bonus..'% MORE') or pack.name,12,198,gw-24,24,19))
   if bonus>0 then nm.TextColor3=Color3.fromRGB(230,255,170) end
   priceButton(face,'Buy',16,gh-80,gw-32,62,key,false,i==top)
   if S.GemSashes[i] then FX.sash(face,S.GemSashes[i],RED_SASH[1],RED_SASH[2]) end
   if i>=top-1 then FX.shine(face) end
  end
  y+=math.ceil(top/per)*(gh+52)
  FX.header(list,'CODES','Enter a code for free rewards.',y,SW);y+=72+10
  local row=T.panel(list,'Codes',2,y,SW-4,84,'panel')
  local field=T.panel(row,'Field',16,14,SW-4-264,56,'inset')
  local box=T.make('TextBox',field,{Name='Input',BackgroundTransparency=1,Position=UDim2.fromOffset(16,0),Size=UDim2.new(1,-32,1,0),Font=T.Font,TextSize=24,TextColor3=C.white,PlaceholderText='Enter code',PlaceholderColor3=C.dim,Text='',ClearTextOnFocus=false,TextXAlignment=Enum.TextXAlignment.Left})
  FX.button(row,'Claim','CLAIM',SW-4-234,14,218,56,function() if box.Text~='' then act('Redeem',box.Text);box.Text='' end end).Caption.TextSize=28
  return y+100
 end

 draw=function()
  local keep=list and list.Parent and sel.storeTabDrawn==sel.storeTab and list.CanvasPosition
  for _,c in b:GetChildren() do c:Destroy() end
  profile=ctx.profile()
  local active=sel.storeTab
  -- Emerald pill on the right; tabs share the rest of the width equally (never overlap).
  local pillW,gap=160,8
  local pillsX=W-pillW
  local tw=math.floor((pillsX-16-3*gap)/4)
  for i,t in S.Tabs do
   local tb=FX.button(b,'Tab_'..t[1],'',(i-1)*(tw+gap),0,tw,64,function() sel.storeTab=t[1];draw() end,t[1]~=active)
   tb.Caption.Visible=false
   local ic=T.icon(tb,'Icon',10,10,44,t[2])
   local l=T.label(tb,'Label',t[3],58,0,tw-68,64,18);l.TextXAlignment=Enum.TextXAlignment.Left;l.TextWrapped=false
   FX.popIcon(tb,ic)
  end
  local pl=T.panel(b,'EmeraldsPill',pillsX,8,pillW,48,'inset');T.icon(pl,'Icon',8,6,36,'emerald')
  local v=T.label(pl,'Value',ctx.fmt(profile.gems),48,4,pillW-94,40,22,C.emerald);v.TextXAlignment=Enum.TextXAlignment.Left
  -- + drawn with two bars (no text), so it stays crisp and inside the button at every scale.
  local plus=FX.button(pl,'Plus','',pillW-42,6,36,36,function() sel.storeTab='Emeralds';draw() end);plus.Caption.Visible=false
  for _,sz in {{18,5},{5,18}} do
   local bar=T.make('Frame',plus,{Name='Bar',AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromOffset(sz[1],sz[2]),BackgroundColor3=C.white,BorderSizePixel=0})
   T.make('UICorner',bar,{CornerRadius=UDim.new(1,0)});T.make('UIStroke',bar,{Color=FX.INK,Thickness=1.5})
  end
  list=T.scroll(b,'Offers',0,78,W,500)
  local h=tabs[active] and tabs[active]() or 0
  list.CanvasSize=UDim2.fromOffset(0,h)
  if keep then list.CanvasPosition=keep end
  sel.storeTabDrawn=active
 end
 -- Deals roll over at UTC midnight; ask the server for today's set if ours is stale.
 if profile.daily.deals and (profile.daily.resetIn or 0)>0 and Money.secondsToReset()>(profile.daily.resetIn or 0) then
  task.spawn(function() combat.ProfileAction:InvokeServer('Refresh') end)
 end
 draw()
 if ctx.setRedraw then ctx.setRedraw(draw) end
 return w
end

-- Purchase reveal (user, 2026-10-03: "not any cool animation when buying bundles like starter
-- bundle") -----------------------------------------------------------------------------------------
-- Once the server says a store product arrived as itself (PurchaseResult, LobbyUI), its contents pop
-- out of its art one by one onto a row of reward slots: each lands with a flash and a chime that
-- climbs (a Legendary sting for Legendary and Godly ones), and the emerald amount counts up from 0.
-- COLLECT (or a tap anywhere once all are out, or 8 s later) plays the quests' CLAIM effect on the
-- slots (QuestsUI.claimFX): the emeralds fly into the emerald counter, chests squash. Its own
-- ScreenGui above the lobby's full screens (the chest screen and run setup sell things too).
-- Presentation only: the server granted everything before saying so.
local TweenService=game:GetService('TweenService')
local ChestFX=require(RS:WaitForChild('ChestFX')) -- the chest screen's sounds
local function tween(o,t,props,style,dir,delay)
 local tw=TweenService:Create(o,TweenInfo.new(t,style or Enum.EasingStyle.Quad,dir or Enum.EasingDirection.Out,0,false,delay or 0),props);tw:Play();return tw
end
S.Rank={Common=1,Emerald=1,Rare=2,Epic=3,Legendary=4,Godly=5}
-- The big art over the slots: the store card's art where the first slot isn't it.
S.RevealArt={ArsenalBundle=WeaponIcons['00'],MegaBundle='chest',VIP='profile',QuickOpen='chest'}
-- What a product or pass gives, as reward slots {asset, label, rarity, amount, kind, count} (the
-- store cards' art; kind and count for the CLAIM effect). Empty for in-run products (revives,
-- rerolls, banish), which show no reveal. opts: signature (class -> weapon id), pick (the Godly
-- Starter's pick, an index into Money.GodlyWeapons).
function S.contents(key,opts)
 opts=opts or {}
 local p=Money.Products[key];local out={}
 if not p then
  if key=='VIP' then return {{'emerald','+25%','Emerald'},{Chests.ById[Money.VIPDailyChest].icon,'Daily','Legendary'},{'chest','Open ×10','Epic'},{'profile','VIP Tag','Rare'}} end
  if key=='QuickOpen' then return {{'chest','Open ×10','Common'}} end
  return out
 end
 if p.revive or key=='ShopReroll' or key=='UpgradeReroll' or key=='Banish' then return out end
 local pick=p.godlyPick and Money.GodlyWeapons[opts.pick or 1]
 local godly=p.godly or pick and pick[1]
 if godly then table.insert(out,{iconFor(weaponId(godly),godly),godlyShort(godly),'Godly'}) end
 if p.armorSet then
  local set=Armor.ById[p.armorSet]
  for _,slot in Armor.Slots do table.insert(out,{Armor.Icons[Armor.pieceId(p.armorSet,slot)],slot,set and set.rarity or 'Epic'}) end
 end
 local sig=opts.signature or {}
 if p.class then table.insert(out,{WeaponIcons[sig[p.class] or ''] or 'profile',p.class,'Rare'}) end
 if p.signatureUpgrades then
  for _,cl in Stats.ClassOrder do table.insert(out,{WeaponIcons[sig[cl] or ''] or 'armory','+'..p.signatureUpgrades,'Rare'}) end
 end
 if (p.emeralds or 0)>0 then table.insert(out,{'emerald',comma(p.emeralds),'Emerald',nil,'emerald',p.emeralds}) end
 for _,kind in {'Wooden','Silver','Gold','Magical','Legendary'} do
  local n=p.chests and p.chests[kind]
  if n and n>0 then table.insert(out,{Chests.ById[kind].icon,kind,FX.ChestRarity[kind],'×'..n,'chest',n}) end
 end
 if (p.rerolls or 0)>0 then table.insert(out,{'quests','Rerolls','Rare','×'..p.rerolls}) end
 if (p.banishes or 0)>0 then table.insert(out,{'armory','Banishes','Epic','×'..p.banishes}) end
 return out
end
-- Where the emeralds fly: the Store window's pill while it is open, else the lobby HUD's counter.
local function counterIn(hud)
 return function()
  if not (hud and hud.Parent and hud.Enabled) then return nil end
  local win=hud:FindFirstChild('StoreWindow');local pill=win and win:FindFirstChild('EmeraldsPill',true)
  local icon=pill and pill:FindFirstChild('Icon')
  if icon and icon.AbsoluteSize.X>0 then return icon end
  local h=hud:FindFirstChild('HUD');local side=h and h.Visible and h:FindFirstChild('Left');local row=side and side:FindFirstChild('Gems')
  icon=row and row:FindFirstChild('Icon')
  return icon and icon.AbsoluteSize.X>0 and icon or nil
 end
end
-- opts: signature, pick (S.contents), hud (the lobby HUD's ScreenGui, for the emerald counter),
-- note (a small line under the title, e.g. Studio's "not saved"), from (a gift's sender: the header
-- says GIFT FROM BEN, 2026-10-04), emeralds (a gift paid as emeralds, e.g. a second Starter Pack:
-- just those). Returns the reveal's ScreenGui, or nil when the product has nothing to show.
function S.reveal(playerGui,key,opts)
 opts=opts or {}
 local items=opts.emeralds and {{'emerald',comma(opts.emeralds),'Emerald',nil,'emerald',opts.emeralds}} or S.contents(key,opts)
 if #items==0 or not playerGui then return nil end
 local old=playerGui:FindFirstChild('PurchaseReveal');if old then old:Destroy() end
 local product=Money.Products[key] or Money.Passes[key]
 local gui=T.make('ScreenGui',playerGui,{Name='PurchaseReveal',ResetOnSpawn=false,DisplayOrder=88,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets})
 -- Laid out at 960 x 600 and scaled to fit: 1920x1080 draws it at 1.25, an 844x390 phone at about .6.
 local DW,DH=960,600
 local back=T.make('TextButton',gui,{Name='Backdrop',Text='',AutoButtonColor=false,Active=true,Modal=true,Selectable=false,Position=UDim2.fromOffset(0,-120),Size=UDim2.new(1,0,1,120),BackgroundColor3=C.shade,BackgroundTransparency=1,BorderSizePixel=0})
 back:SetAttribute('NoClickSound',true)
 tween(back,.25,{BackgroundTransparency=.22})
 local stage=T.frame(back,'Stage',0,0,DW,DH);stage.AnchorPoint=Vector2.new(.5,.5);stage.Position=UDim2.new(.5,0,.5,60)
 local scale=T.make('UIScale',stage,{Scale=1})
 local function fit() local v=gui.AbsoluteSize;if v.X>0 then scale.Scale=math.clamp(math.min((v.X-24)/DW,(v.Y-16)/DH),.3,1.25) end end
 gui:GetPropertyChangedSignal('AbsoluteSize'):Connect(fit);fit()
 -- Colours from the best thing in it: Godly red-black, Legendary gold, anything else emerald.
 local best=1;for _,it in items do best=math.max(best,S.Rank[it[3]] or 1) end
 local th=best>=5 and FX.Themes.shadow or best>=4 and FX.Themes.gold or FX.Themes.emerald
 -- 1. YOU GOT and the product's name pop in.
 local head=T.frame(stage,'Head',0,14,DW,136);head.ZIndex=3
 local hs=T.make('UIScale',head,{Scale=.4});tween(hs,.4,{Scale=1},Enum.EasingStyle.Back)
 center(T.label(head,'You',opts.from and ('GIFT FROM '..string.upper(opts.from)) or 'YOU GOT',0,0,DW,32,26,opts.from and C.gold or C.cream))
 -- Emerald packs say the amount ('1,700 EMERALDS', not 'STACK'), classes 'CHEF CLASS'.
 local name=product and product.name or tostring(key)
 if #items==1 and items[1][5]=='emerald' then name=comma(items[1][6])..' emeralds' elseif product and product.class then name=product.class..' class' end
 center(FX.title(head,'Title',string.upper(name),30,32,DW-60,76,62,th.tint))
 if opts.note then center(T.text(head,'Note',opts.note,30,110,DW-60,22,16,C.muted)) end
 -- 2. Its art bursts in over spinning rays, with a white flash.
 local ax,ay=DW/2,266
 local burst,rays=FX.burst(stage,ax,ay,60,th.rays,40);burst.ZIndex=1
 burst.Glow.ImageColor3=th.glow;burst.Glow.ImageTransparency=.15;rays.ImageTransparency=.25
 tween(burst,.55,{Size=UDim2.fromOffset(500,500)},Enum.EasingStyle.Back)
 local godlyArt=items[1][3]=='Godly' and items[1][1]
 local chestArt;for _,it in items do if it[5]=='chest' then chestArt=chestArt or it[1] end end
 local art=T.icon(stage,'Art',ax-100,ay-100,200,S.RevealArt[key] or godlyArt or chestArt or items[1][1]);art.ZIndex=2
 local as=T.make('UIScale',art,{Scale=0});tween(as,.45,{Scale=1},Enum.EasingStyle.Back,nil,.08)
 local flash=T.make('ImageLabel',stage,{Name='Flash',BackgroundTransparency=1,Image=FX.Asset.glow,ImageColor3=Color3.new(1,1,1),AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromOffset(ax,ay),Size=UDim2.fromOffset(120,120),ZIndex=4})
 tween(flash,.5,{Size=UDim2.fromOffset(560,560),ImageTransparency=1})
 ChestFX.play(ChestFX.Sounds.Burst,.4,1)
 -- 3. Each reward flies out of the art to its slot, one by one (0.32 s apart; 0.24 s past 5).
 local n=#items;local gap=14
 local size=math.min(112,math.floor((DW-48-(n-1)*gap)/n));local h=math.floor(size*1.08)
 local x0=(DW-(n*size+(n-1)*gap))/2;local ty=404
 local step=n>5 and .24 or .32
 local slots={}
 for i,it in items do
  task.delay(.5+(i-1)*step,function()
   if not stage.Parent then return end
   local rank=S.Rank[it[3]] or 1
   local color=(FX.Rarity[it[3]] or FX.Rarity.Common).top
   local cx,cy=x0+(i-1)*(size+gap)+size/2,ty+h/2
   local t=Quests.tagReward(FX.tile(stage,'Reward'..i,0,0,size,it[1],it[2],it[3],it[4]),it[5] or 'item',it[6],color)
   t.AnchorPoint=Vector2.new(.5,.5);t.Position=UDim2.fromOffset(ax,ay);t.ZIndex=3
   local ts=T.make('UIScale',t,{Scale=.2})
   tween(t,.36,{Position=UDim2.fromOffset(cx,cy)},Enum.EasingStyle.Back)
   tween(ts,.36,{Scale=1},Enum.EasingStyle.Back)
   table.insert(slots,t)
   task.delay(.3,function()
    if not stage.Parent then return end
    -- Lands: a flash under it and a chime that climbs with each slot.
    local lb,lr=FX.burst(stage,cx,cy,size*.7,color,90);lb.ZIndex=1;lb.Glow.ImageTransparency=.1
    tween(lb,.45,{Size=UDim2.fromOffset(size*2.6,size*2.6)},Enum.EasingStyle.Quart)
    tween(lb.Glow,.6,{ImageTransparency=1},nil,Enum.EasingDirection.In)
    tween(lr,.55,{ImageTransparency=1},nil,Enum.EasingDirection.In)
    task.delay(.7,function() lb:Destroy() end)
    if rank>=4 then ChestFX.play(ChestFX.Sounds.Legendary,.4,rank>=5 and .85 or 1)
    else ChestFX.play(ChestFX.Sounds.Chime,.35,1.05+i*.07) end
    if it[5]=='emerald' and it[6] then
     -- The amount counts up from 0 while a few emeralds spray off the slot.
     local strip=t:FindFirstChild('Strip');local label=strip and strip:FindFirstChild('Label')
     if label then
      label.Text='0'
      local v=Instance.new('NumberValue');v.Value=0
      v.Changed:Connect(function(x) if label.Parent then label.Text=comma(x) end end)
      tween(v,.9,{Value=it[6]},Enum.EasingStyle.Quad)
      task.delay(.95,function() v:Destroy();if label.Parent then label.Text=comma(it[6]) end end)
     end
     for _=1,10 do
      local a=-math.pi/2+(math.random()*2-1)*1.1;local d=Vector2.new(math.cos(a),math.sin(a))
      local to=Vector2.new(cx,cy)+d*size*(.8+math.random()*.6)
      local g=T.icon(stage,'Gem',cx-10,cy-10,20,'emerald');g.ZIndex=4;g.Rotation=math.random(-40,40)
      tween(g,.6,{Position=UDim2.fromOffset(to.X-10,to.Y+10),Rotation=g.Rotation+math.random(-120,120),ImageTransparency=1})
      task.delay(.65,function() g:Destroy() end)
     end
    end
   end)
  end)
 end
 -- 4. COLLECT once everything is out; the CLAIM effect sends it to the counter.
 local doneAt=.5+(n-1)*step+.7
 local t0=os.clock()
 local finished=false
 local function finish()
  if finished or not gui.Parent then return end
  finished=true
  local shots=Quests.snapshot(slots)
  stage.Visible=false;back.Active=false
  tween(back,.25,{BackgroundTransparency=1})
  task.delay(.25,function() back.Visible=false end)
  Quests.claimFX(gui,shots,counterIn(opts.hud))
  task.delay(2,function() gui:Destroy() end)
 end
 back.Activated:Connect(function() if os.clock()-t0>=doneAt then finish() end end)
 task.delay(doneAt,function()
  if finished or not stage.Parent then return end
  local cb=FX.button(stage,'Collect','COLLECT',DW/2-150,DH-72,300,66,finish);cb.Caption.TextSize=32;cb.ZIndex=5
  local cs=T.make('UIScale',cb,{Scale=.5});tween(cs,.3,{Scale=1},Enum.EasingStyle.Back)
  task.delay(.32,function() if cb.Parent then cs:Destroy();FX.pulse(cb,.05) end end)
  T.gamepadSelect(stage)
 end)
 task.delay(doneAt+8,finish)
 return gui
end

-- Gift picker (2026-10-04, user: "add gifting to the store, like be able to buy stuff for other
-- people") -----------------------------------------------------------------------------------------
-- GIFT on a store card opens this: who gets it, then a confirm ("Gift Starter Pack to Ana?" with
-- what they get and the price). Players in this server first, then your Roblox friends (online
-- first, then the rest, A-Z), each with a headshot, and a search box. Someone here who already owns
-- that one-time pack, Godly bundle or class is greyed out; offline friends can't be checked (theirs
-- pays emeralds instead). Studio lists you too, so one test player can try the whole flow. GIFT sends
-- PurchaseRequest('GiftRequest', key, userId, pick); the server checks everything again, then opens
-- the normal Robux prompt. Its own ScreenGui above the lobby HUD (below the reveal), laid out at
-- 600 x 460 and scaled to fit: an 844x390 phone draws it at about .65 (60 px rows -> 39). opts: arg (the Godly Starter's
-- pick), window (the Store: closing it closes this), signature (class -> weapon id, for the tiles).
local Players=game:GetService('Players')
local friendsCache -- {at=os.clock(), list}: at most one friends fetch a minute
local function csvSet(text) local out={};for v in string.gmatch(text or '','[^,]+') do out[v]=true end;return out end
-- What a player here owns, from their Profile* attributes, in a profile's shape (Money.giftBlocked).
local function ownedBy(q)
 if q:GetAttribute('ProfileLoaded')~=true then return nil end
 return {starterPack=q:GetAttribute('ProfileStarterPack')==true,classes=csvSet(q:GetAttribute('ProfileClasses')),bundles=csvSet(q:GetAttribute('ProfileBundles'))}
end
-- Your friends: {id, name, user, online}, then done(list, ok). Up to Roblox's 200.
local function loadFriends(done)
 if friendsCache and os.clock()-friendsCache.at<60 then done(friendsCache.list,true);return end
 task.spawn(function()
  local me=Players.LocalPlayer;local online={};local out={}
  local okO,list=pcall(function() return me:GetFriendsOnline(200) end)
  if okO and type(list)=='table' then for _,f in list do if type(f.VisitorId)=='number' then online[f.VisitorId]=true end end end
  local okF,pages=pcall(function() return Players:GetFriendsAsync(me.UserId) end)
  if okF and pages then
   for _=1,10 do
    local okP,page=pcall(function() return pages:GetCurrentPage() end)
    if not okP or type(page)~='table' then break end
    for _,f in page do
     if type(f.Id)=='number' then table.insert(out,{id=f.Id,name=f.DisplayName or f.Username or '?',user=f.Username or '',online=online[f.Id]==true or f.IsOnline==true}) end
    end
    if pages.IsFinished or not pcall(function() pages:AdvanceToNextPageAsync() end) then break end
   end
   friendsCache={at=os.clock(),list=out}
  end
  done(out,okF and pages~=nil)
 end)
end
function S.giftPicker(playerGui,key,opts)
 opts=opts or {}
 local product=Money.Products[key]
 if not product or not playerGui or not Money.giftable(key) then return nil end
 local old=playerGui:FindFirstChild('GiftPicker');if old then old:Destroy() end
 local me=Players.LocalPlayer
 local studio=game:GetService('RunService'):IsStudio()
 local pick=product.godlyPick and Money.GodlyWeapons[opts.arg or 1]
 local title=product.name..(pick and (' ('..pick[2]..')') or '')
 local price='R$ '..comma(Money.price(key))
 local items=S.contents(key,{pick=opts.arg,signature=opts.signature})
 local art=S.RevealArt[key] or items[1] and items[1][1] or 'store'
 local gui=T.make('ScreenGui',playerGui,{Name='GiftPicker',ResetOnSpawn=false,DisplayOrder=87,ZIndexBehavior=Enum.ZIndexBehavior.Sibling,ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets})
 local function close() if gui.Parent then gui:Destroy() end end
 if opts.window then opts.window.Destroying:Connect(close) end
 local DW,DH=600,460;local BW,BH=DW-44,DH-62
 local back=T.make('TextButton',gui,{Name='Backdrop',Text='',AutoButtonColor=false,Active=true,Modal=true,Selectable=false,Position=UDim2.fromOffset(0,-120),Size=UDim2.new(1,0,1,120),BackgroundColor3=C.shade,BackgroundTransparency=.35,BorderSizePixel=0})
 back:SetAttribute('NoClickSound',true);back.Activated:Connect(close)
 -- Centred like a large window (the backdrop starts 120 px above the screen; the title plate pokes 30 up).
 local stage=T.frame(back,'Stage',0,0,DW,DH);stage.AnchorPoint=Vector2.new(.5,.5);stage.Position=UDim2.new(.5,0,.5,76)
 local scale=T.make('UIScale',stage,{Scale=1})
 local function fit() local v=gui.AbsoluteSize;if v.X>0 then scale.Scale=math.clamp(math.min((v.X-24)/DW,(v.Y-24)/(DH+40)),.3,1.25) end end
 gui:GetPropertyChangedSignal('AbsoluteSize'):Connect(fit);fit()
 local frame=T.panel(stage,'Frame',0,0,DW,DH,'panel');frame.Active=true
 local plate=T.panel(stage,'TitlePlate',18,-30,0,56,'panel');plate.Active=true
 plate.Size=UDim2.fromOffset(game:GetService('TextService'):GetTextSize('Gift',32,T.Font,Vector2.new(2000,100)).X+76,56);T.caps(plate,40)
 T.label(plate,'Title','Gift',0,0,0,0,32).Size=UDim2.fromScale(1,1)
 local x=T.button(stage,'Close','X',DW-62,-22,58,58,close,true);T.setTier(x,4);x.Caption.TextColor3=C.negative;x.Caption.TextSize=34
 local body=T.frame(stage,'Body',22,40,BW,BH)
 local view,chosen,query,sent='pick',nil,'',false
 local friends,friendsState={},'loading'
 local draw,refill
 -- Everyone here (you too in Studio, last), then friends not here: online first, then A-Z.
 local function candidates()
  local here,seen={},{}
  for _,q in Players:GetPlayers() do
   if q~=me or studio then
    seen[q.UserId]=true
    local owned=ownedBy(q)
    table.insert(here,{id=q.UserId,display=q.DisplayName,name=q.DisplayName..(q==me and ' (you)' or ''),user=q.Name,where='server',me=q==me,blocked=owned and Money.giftBlocked(key,owned)})
   end
  end
  table.sort(here,function(a,b) if a.me~=b.me then return b.me end;return a.name:lower()<b.name:lower() end)
  local fl={}
  for _,f in friends do if not seen[f.id] then table.insert(fl,{id=f.id,display=f.name,name=f.name,user=f.user,where=f.online and 'online' or 'offline'}) end end
  table.sort(fl,function(a,b) if a.where~=b.where then return a.where=='online' end;return a.name:lower()<b.name:lower() end)
  return here,fl
 end
 local function matches(c) local q=query:lower();return q=='' or c.name:lower():find(q,1,true)~=nil or c.user:lower():find(q,1,true)~=nil end
 local CHIP={server={'HERE',C.limeDark,C.white},online={'ONLINE',Color3.fromRGB(16,90,52),C.emerald},offline={'OFFLINE',C.well,C.muted}}
 local function row(parent,c,y,w)
  local b=T.button(parent,'Player_'..c.id,'',0,y,w,60,function() chosen=c;view='confirm';T.sound('ui_equip');draw() end,true)
  b.Caption.Visible=false
  local img=T.make('ImageLabel',b,{Name='Headshot',BackgroundTransparency=1,Position=UDim2.fromOffset(10,8),Size=UDim2.fromOffset(44,44),Image=''})
  T.make('UICorner',img,{CornerRadius=UDim.new(0,8)});T.headshot(img,c.id)
  local n=T.label(b,'Name',c.name,64,6,w-210,28,19);n.TextXAlignment=Enum.TextXAlignment.Left;n.TextTruncate=Enum.TextTruncate.AtEnd;n.TextWrapped=false
  T.text(b,'User','@'..c.user,64,32,w-210,20,14,C.muted)
  local chip=c.blocked and {string.upper(c.blocked),Color3.fromRGB(70,20,24),C.negative} or CHIP[c.where]
  local ch=T.chip(b,'Status',chip[1],0,19,chip[2],chip[3]);ch.AnchorPoint=Vector2.new(1,0);ch.Position=UDim2.fromOffset(w-14,19)
  if c.blocked then b.Interactable=false end
 end
 local function drawPick()
  T.icon(body,'Art',0,0,64,art)
  local t=T.label(body,'Product','GIFT '..string.upper(title),76,2,BW-76,34,26,C.lime);t.TextXAlignment=Enum.TextXAlignment.Left;t.TextWrapped=false
  T.text(body,'Price',price..'  ·  you pay, they get it',76,38,BW-76,22,16,C.muted)
  local field=T.panel(body,'Search',0,74,BW,48,'inset')
  local box=T.make('TextBox',field,{Name='Input',BackgroundTransparency=1,Position=UDim2.fromOffset(14,0),Size=UDim2.new(1,-28,1,0),Font=T.Font,TextSize=20,TextColor3=C.white,PlaceholderText='Search players and friends',PlaceholderColor3=C.dim,Text=query,ClearTextOnFocus=false,TextXAlignment=Enum.TextXAlignment.Left})
  local list=T.scroll(body,'List',0,132,BW,BH-132)
  local function fill()
   if not list.Parent then return end
   for _,c in list:GetChildren() do if c:IsA('GuiObject') then c:Destroy() end end
   local here,fl=candidates()
   local y,w=0,BW-14
   local function line(name,text,color) T.text(list,name,text,6,y,w,24,15,color or C.dim);y+=32 end
   local function section(text) local l=T.label(list,'Section_'..text,text,4,y,w,26,16,C.muted);l.TextXAlignment=Enum.TextXAlignment.Left;y+=30 end
   section('IN THIS SERVER')
   local any=false
   for _,c in here do if matches(c) then row(list,c,y,w);y+=68;any=true end end
   if not any then line('NoneHere',query=='' and 'Nobody else is here right now.' or 'No match here.') end
   section('FRIENDS')
   if friendsState=='loading' then line('Loading','Loading your friends...')
   elseif friendsState=='failed' then line('Failed',"Couldn't load your friends. Close and try again.",C.negative)
   else
    local shown=0
    for _,c in fl do
     if matches(c) then
      if shown>=60 then line('More','Search to find more friends.');break end -- 60 rows, not 200 headshots
      row(list,c,y,w);y+=68;shown+=1
     end
    end
    if shown==0 then line('NoneFriends',query=='' and 'No friends to show.' or 'No friend matches.') end
   end
   list.CanvasSize=UDim2.fromOffset(0,y)
  end
  box:GetPropertyChangedSignal('Text'):Connect(function() query=box.Text;fill() end)
  fill()
  return fill
 end
 local WHERE={server='In this server: they get it right away.',online='Online: it reaches them in the lobby.',offline='Offline: it waits for their next visit.'}
 local function drawConfirm()
  local c=chosen
  local img=T.make('ImageLabel',body,{Name='Headshot',BackgroundTransparency=1,Position=UDim2.fromOffset(BW/2-58,0),Size=UDim2.fromOffset(116,116),Image=''})
  T.make('UICorner',img,{CornerRadius=UDim.new(0,16)});T.make('UIStroke',img,{Color=C.lime,Thickness=3});T.headshot(img,c.id)
  center(T.label(body,'Question','Gift '..title..' to '..c.display..'?',10,126,BW-20,64,32))
  center(T.text(body,'Where',price..'  ·  '..WHERE[c.where],10,194,BW-20,24,17,C.muted))
  -- What they get: the store card's slots.
  local n=math.max(#items,1);local gap=10
  local size=math.min(76,math.floor((BW-(n-1)*gap)/n));local x0=(BW-(#items*size+(#items-1)*gap))/2
  for i,it in items do FX.tile(body,'Item'..i,x0+(i-1)*(size+gap),232,size,it[1],it[2],it[3],it[4]) end
  local half=(BW-16)/2
  FX.button(body,'Back','BACK',0,BH-66,half,62,function() view='pick';draw() end,true).Caption.TextSize=26
  local go=FX.button(body,'Send','GIFT  ·  '..price,half+16,BH-66,half,62,function()
   if sent then return end;sent=true
   combat.PurchaseRequest:FireServer('GiftRequest',key,c.id,opts.arg)
   T.sound('ui_equip');close()
  end)
  go.Caption.TextSize=26;FX.pulse(go,.04)
 end
 draw=function()
  if not gui.Parent then return end
  for _,c in body:GetChildren() do c:Destroy() end
  refill=nil
  if view=='confirm' and chosen then drawConfirm() else refill=drawPick() end
  T.gamepadSelect(body)
 end
 draw()
 loadFriends(function(list,ok)
  friends=list;friendsState=(not ok and #list==0) and 'failed' or 'ready'
  if gui.Parent and refill then refill() end
 end)
 return gui
end
return S
