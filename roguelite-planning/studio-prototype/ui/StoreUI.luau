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
-- A weapon's icon, or its uploaded art by name while it isn't in WeaponCatalog yet (from a
-- Studio edit to the old store, kept 2026-10-02).
local function iconFor(id,name) return (id and WeaponIcons[id]) or (WeaponArt.IconsByName and WeaponArt.IconsByName[name]) or 'armory' end
local C=T.Color
local S={}

S.Tabs={{'Daily','quests','DAILY'},{'Bundles','store','BUNDLES'},{'Chests','chest','CHESTS'},{'Emeralds','emerald','EMERALDS'}}
-- Class cards: class, signature weapon, Robux product, card colour.
S.Classes={{'Thrower','12','ClassThrower','red'},{'Juggler','19','ClassJuggler','purple'},{'Handyman','24','ClassHandyman','blue'}}
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
 local function act(action,a)
  local r=combat.ProfileAction:InvokeServer(action,a)
  if r.ok then T.sound('ui_purchase') end
  T.toast(screen,r.message or '',r.ok and C.lime or C.negative)
 end
 -- Robux price button (breathes when `pulse`). owned: true = OWNED, a string = that label (e.g.
 -- COMING SOON); neither is buyable. arg goes with the purchase (the Godly Starter's pick).
 local function priceButton(parent,name,x,y,bw,bh,key,owned,pulse,arg)
  local item=Money.Products[key] or Money.Passes[key]
  local pb=FX.button(parent,name,owned==true and 'OWNED' or owned or ('R$ '..comma(item.robux)),x,y,bw,bh,function() buy(key,arg) end,owned and true or false)
  pb.Caption.TextSize=math.min(34,bh-18)
  if owned then pb.Interactable=false elseif pulse then FX.pulse(pb,.04) end
  return pb
 end
 local function tiles(face,list_,x,y,size,gap)
  for i,it in list_ do FX.tile(face,'Item'..i,x+(i-1)*(size+gap),y,size,it[1],it[2],it[3],it[4]) end
 end
 -- Wide card: title, line and item slots on the left; big art, sash and price on the right.
 -- tiles: {asset, label, rarity, amount}. opts: tag, sash, sashColors, pulse, shine, artSize, arg.
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
   FX.art(face,free and 'emerald' or WeaponIcons[deal.id],cw/2,50,116,th,220)
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
   local pb=FX.button(face,'Buy',label,14,ch-70,cw-28,56,function() act('BuyDeal',i) end,deal.bought)
   pb.Caption.TextSize=24
   if deal.bought then pb.Interactable=false
   elseif deal.currency=='Emeralds' then ctx.cost(pb,deal.price,'emerald',22) end
   if deal.currency=='Free' and not deal.bought then FX.tag(face,'FREE',th.tag,th.accent);FX.pulse(pb,.05) end
  end
  y+=ch+44
  local chest=Chests.ById[Money.VIPDailyChest]
  local face,th=FX.card(list,profile.vip and 'VipDaily' or 'VipPromo',2,y,CW,160,'purple')
  FX.art(face,chest.icon,100,62,150,th,300)
  if profile.vip then
   local claimed=profile.daily.vipClaimed
   FX.title(face,'Title','VIP DAILY CHEST',200,28,CW-480,50,44,th.tint)
   FX.sub(face,'Sub','A free '..chest.name..', every single day.',202,82,CW-480,24,18)
   local cb=FX.button(face,'Claim',claimed and 'CLAIMED' or 'CLAIM',CW-268,48,240,64,function() act('ClaimVipChest') end,claimed)
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
    Chests.ById.Legendary.icon,'StarterPack',profile.starter,{tag='ONE TIME OFFER',sash='BEST VALUE',sashColors=RED_SASH,pulse=true,shine=true})
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
  face=half('QuickOpen',HW+18,y,vh,'wood','QUICK OPEN','Open 10 chests in one click.','chest')
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
  local sub=FX.header(list,'LEGENDARY CHESTS',Chests.ById.Legendary.copies..' items and a guaranteed Legendary in every chest.',y,SW)
  sub.Position=UDim2.fromOffset(200,y+42);sub.Size=UDim2.fromOffset(SW-400,24)
  local odds=FX.button(list,'Odds','SEE ODDS',SW-178,y+36,174,40,function() sel.chest='Legendary';ctx.open('Chests','Legendary') end,true);odds.Caption.TextSize=16
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
   center(FX.sub(face,'Drops',(n*Chests.ById.Legendary.copies)..' items'..(save>0 and ('  ·  SAVE '..save..'%') or ''),12,244,cw-24,22,17,save>0 and Color3.fromRGB(220,255,170) or nil))
   priceButton(face,'Buy',16,ch-80,cw-32,62,key,false,i==3)
   if S.ChestSashes[i] then FX.sash(face,S.ChestSashes[i],RED_SASH[1],RED_SASH[2]) end
   if i==3 then FX.shine(face) end
  end
  y+=ch+48
  local mb=Money.Products.MegaBundle
  hero('Mega',y,290,'purple','MEGA BUNDLE','The biggest pile of chests in the game.',
   {{Chests.ById.Legendary.icon,'Legendary','Legendary','×'..mb.chests.Legendary},{'emerald',comma(mb.emeralds),'Emerald'},{'quests','Rerolls','Rare','×'..mb.rerolls},{'armory','Banishes','Epic','×'..mb.banishes}},
   'chest','MegaBundle',false,{tag='INSANE DEAL',pulse=true,shine=true})
  y+=290+48
  local ub=Money.Products.UltimateBundle
  local each=math.floor(ub.robux/ub.chests.Legendary+.5)
  local save=math.floor((1-each/base.robux)*100+.5)
  hero('Ultimate',y,300,'obsidian','ULTIMATE BUNDLE','×'..ub.chests.Legendary..' Legendary Chests: '..each..' R$ each, save '..save..'%.',
   {{Chests.ById.Legendary.icon,'Legendary','Legendary','×'..ub.chests.Legendary},{'emerald',ctx.fmt(ub.emeralds),'Emerald'},{'quests','Rerolls','Rare','×'..ub.rerolls},{'armory','Banishes','Epic','×'..ub.banishes}},
   Chests.ById.Legendary.icon,'UltimateBundle',false,{tag='ULTIMATE',sash='SAVE '..save..'%',sashColors=RED_SASH,pulse=true,shine=true,artSize=250})
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
return S
