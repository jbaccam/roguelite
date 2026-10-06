-- Run as a temporary normal server Script in Studio Play, never ship this test.
-- Fixture prerequisite: the player is alive in the arena and Shop.join(player) has completed.
local RS=game.ReplicatedStorage
local C=RS.RogueliteCombat
local E=require(C.EconomyConfig)
local Catalog=require(C.ShopCatalog)
local Stats=require(C.CharacterStats)
local Weapons=require(C.WeaponCatalog)
local Shop=require(game.ServerScriptService.ShopService)
local Characters=require(game.ServerScriptService.CharacterService)
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
while not (Characters.states[p] and Shop.states[p]) do task.wait() end
local cs=assert(Characters.states[p],'Player state ready')
local checked=0
local function check(ok,msg) checked+=1;assert(ok,msg) end
local function near(a,b,msg) check(math.abs(a-b)<.001,msg..': '..a..' / '..b) end
local function request(action,arg,extra,revision)
 Shop.states[p].lastRequest=-1e6
 return Shop.request(p,action,revision or Shop.states[p].revision,arg,extra)
end
local serial=0
local function offer(id,index,price)
 serial+=1;local o={id=id,token='test_'..serial,price=price or E.price(Catalog.ById[id].basePrice,Shop.wave,E.modifier(cs.stats)),locked=false,sold=false}
 Shop.states[p].offers[index or 1]=o;Shop.publish(p);return o
end
local function buy(id,price) local o=offer(id,1,price);return request('Buy',1,o.token) end
local originalOverrides=table.clone(cs.overrides)
local originalClass=cs.class
local function reset()
 Shop.phase='Shop';Shop.wave=1;RS.RogueliteRunState:SetAttribute('Phase','Shop');RS.RogueliteRunState:SetAttribute('Wave',1);RS.RogueliteRunState:SetAttribute('WaveEndsAt',nil);C:SetAttribute('ZombiesEnabled',false)
 for i=1,6 do cs.folder['Slot'..i]:SetAttribute('WeaponId',i==1 and '03' or '') end
 cs.class=originalClass;cs.overrides=table.clone(originalOverrides);cs.itemBonuses={};cs.itemPercent={};Characters.refresh(p)
 Shop.attach(p);Shop.bonuses(p);cs.folder:SetAttribute('EquippedCount',1)
 local character=p.Character or p.CharacterAdded:Wait()
 local humanoid=character:WaitForChild('Humanoid')
 if humanoid.Health<=0 then
  p:LoadCharacter()
  character=p.Character or p.CharacterAdded:Wait()
  humanoid=character:WaitForChild('Humanoid')
 end
 humanoid.Health=humanoid.MaxHealth
end
local ok,err=xpcall(function()
 for _,wave in {1,5,10,20} do for _,base in {8,20,55,160} do near(E.price(base,wave,1),math.floor(base+wave+base*wave*.10+1e-8),'inflation') end end
 near(E.price(20,1,1),23,'example wave1');near(E.price(20,5,1),35,'example wave5');near(E.price(20,10,1),50,'example wave10');near(E.price(20,20,1),80,'example wave20')
 near(E.sellValue(20,1,1),5,'sell wave1');near(E.sellValue(20,10,1),12,'sell wave10');near(E.sellValue(1,1,.2),1,'sell at least 1');near(E.reroll(1,0),1,'wave1 reroll');near(E.reroll(8,3),18,'wave8 reroll4')
 near(E.rarityChance(2,1,0),0,'tier2 locked on wave1');near(E.rarityChance(2,2,0),.06,'tier2 wave2')
 near(E.rarityChance(3,5,0),0,'tier3 locked before wave6');near(E.rarityChance(3,6,0),.015,'tier3 wave6')
 near(E.rarityChance(4,11,0),0,'tier4 locked before wave12');near(E.rarityChance(4,12,0),.0015,'tier4 wave12')
 near(E.rarityChance(4,1000,100),.05,'tier4 luck cap')
 near(E.rarityChance(2,10,0)-E.rarityChance(3,10,0),.465,'wave10 tier2 share')
 near(E.rarityChance(3,10,0)-E.rarityChance(4,10,0),.075,'wave10 tier3 share')
 for _,case in {{.005,4},{.10,3},{.30,2},{.90,1}} do
  local draw={NextNumber=function() return case[1] end}
  near(E.rollTier(15,0,draw),case[2],'ordered rarity draw')
 end
 check(E.weaponSlot(1,1,Random.new(1)) and E.weaponSlot(1,2,Random.new(1)),'early weapons')
 check(not E.weaponSlot(1,3,Random.new(1)) and not E.weaponSlot(1,4,Random.new(1)),'early items')
 check(E.weaponSlot(5,1,Random.new(1)),'wave5 weapon guarantee')
 for _,entry in Catalog.List do
  check(entry.basePrice>0 and entry.basePrice%1==0,'catalog price '..entry.id)
  for id in entry.modifiers do check(Stats.ById[id]~=nil,'valid item stat '..id) end
  for id in entry.percent or {} do check(Stats.ById[id]~=nil,'valid percent '..id) end
  if entry.weaponId then
   -- The tier's band, times the rarity premium (EconomyConfig.RARITY_PRICE: a Legendary x1.5).
   local f=E.RARITY_PRICE[Weapons.ById[entry.weaponId].rarity] or 1
   local band=E.TIER_PRICE_BANDS[entry.tier];check(entry.basePrice>=math.floor(band[1]*f) and entry.basePrice<=math.ceil(band[2]*f),'weapon tier band')
   local base=Weapons.ById[entry.weaponId];local s=Stats.resolve('Brawler',1)
   near(Stats.weapon(base,s,'Brawler',entry.tier).damage,Stats.weapon(base,s,'Brawler',1).damage*base.tierDamage[entry.tier]/base.tierDamage[1],'tier applied')
  end
 end
 reset()
 local seen={}
 for i,o in Shop.states[p].offers do
  local entry=Catalog.ById[o.id]
  check((entry.kind=='Weapon')==(i<=2),'first shop split')
  check(not seen[o.id],'duplicate first offer');seen[o.id]=true
 end
 check(request('Shards','Set',10000),'set shards');check(request('Shards','Add',100),'add shards');check(request('Shards','Add',-100),'subtract shards');near(Shop.states[p].shards,10000,'currency controls')
 for _,bad in {0/0,math.huge,-1,1.5,'100',{}} do check(not request('Shards','Set',bad),'reject invalid shards') end
 check(not request('Shards','Set',100,0),'reject stale revision')
 local old=E.DEBUG_CURRENCY_ENABLED;E.DEBUG_CURRENCY_ENABLED=false;check(not request('Shards','Set',100),'disabled production control');E.DEBUG_CURRENCY_ENABLED=old
 local o=offer('weapon_00_1',1,47);local token=o.token
 -- A reroll excludes what's on display now; offer() above swapped slot 1's first roll out, so that one may return.
 local shown={};for _,x in Shop.states[p].offers do shown[x.id]=true end
 check(request('Lock',1,token),'lock');local shards=Shop.states[p].shards;local price=E.reroll(1,0)
 check(request('Reroll'),'reroll');near(Shop.states[p].shards,shards-price,'reroll charge');near(Shop.states[p].rerolls,1,'reroll count');check(Shop.states[p].offers[1]==o and o.price==47,'locked price and identity')
 for _,offerNow in Shop.states[p].offers do check(not shown[offerNow.id] or offerNow==o,'reroll repeated old offer') end
 cs.overrides.ShopPricePercent=15;Characters.refresh(p);check(o.price==47,'locked unaffected by stat');near(E.modifier(cs.stats),1.15,'positive price modifier')
 cs.overrides.ShopPricePercent=-10;Characters.refresh(p);near(E.modifier(cs.stats),.9,'negative price modifier')
 cs.overrides={};Characters.refresh(p)
 check(request('Buy',1,token),'buy locked weapon');local slot=cs.folder.Slot2;check(slot:GetAttribute('WeaponId')=='00','equipped immediately');near(slot:GetAttribute('FinalPurchasePrice'),47,'actual paid saved')
 local copy=slot:GetAttribute('CopyId');local rev=Shop.states[p].revision;shards=Shop.states[p].shards
 check(not request('Buy',1,token),'reject replay sold');near(Shop.states[p].shards,shards,'no repeat charge')
 Shop.wave=20;check(request('Sell',2,copy),'sell later wave');near(Shop.states[p].shards,shards+E.sellValue(Catalog.ById['weapon_00_1'].basePrice,20,1),'sale pays 25% of the current price');check(slot:GetAttribute('WeaponId')=='','sale removed');check(not request('Sell',2,copy),'reject sell replay')
 local snap=game:GetService('HttpService'):JSONDecode(cs.folder:GetAttribute('ShopSnapshot'))
 if cs.folder.Slot1:GetAttribute('WeaponId')~='' then check(snap.weapons[1].sell>=1,'free starter still sells') end
 Shop.wave=1
 for _=2,6 do check(buy('weapon_03_2',30),'fill slots') end
 shards=Shop.states[p].shards;check(not buy('weapon_11_4',130),'full slots reject');near(Shop.states[p].shards,shards,'full slots no charge');check(cs.folder.Slot6:GetAttribute('WeaponId')=='03','no deletion on full')
 -- A full purchase merges into one exact-tier copy; no slot or price is trusted from the client.
 local mergeSlot=cs.folder.Slot2;local staleCopy=mergeSlot:GetAttribute('CopyId')
 check(buy('weapon_03_2',31),'full matching purchase auto-combines')
 near(mergeSlot:GetAttribute('Tier'),3,'automatic next tier');near(mergeSlot:GetAttribute('FinalPurchasePrice'),61,'combined paid basis')
 near(cs.folder:GetAttribute('EquippedCount'),6,'auto-combine preserves six equipped')
 check(not request('Combine',2,staleCopy),'old copy token rejected after merge')
 local manual=cs.folder.Slot3;local manualCopy=manual:GetAttribute('CopyId');shards=Shop.states[p].shards
 check(request('Combine',3,manualCopy),'manual same tier combination')
 near(manual:GetAttribute('Tier'),3,'manual next tier');near(cs.folder:GetAttribute('EquippedCount'),5,'manual frees slot')
 near(Shop.states[p].shards,shards,'combine is free');near(manual:GetAttribute('FinalPurchasePrice'),60,'manual paid basis')
 check(not request('Combine',3,manualCopy),'manual replay rejected')
 check(request('Combine',2,mergeSlot:GetAttribute('CopyId')),'combine rare pair to legendary')
 near(mergeSlot:GetAttribute('Tier'),4,'legendary cap');near(mergeSlot:GetAttribute('FinalPurchasePrice'),121,'all constituent purchase prices retained')
 check(not request('Combine',2,mergeSlot:GetAttribute('CopyId')),'no tier five')
 check(not request('Combine',1,cs.folder.Slot1:GetAttribute('CopyId')),'different tiers do not combine')
 for _,bad in {0,7,1.5,0/0,'2',{}} do check(not request('Combine',bad,'forged'),'invalid combine slot') end
 check(not request('Combine',5,'forged'),'forged ownership token')
 local before=cs.stats.Damage;check(buy('protein',14),'buy passive');near(cs.stats.Damage,before+8,'passive damage');near(p.Character:GetAttribute('Stat_Damage'),cs.stats.Damage,'avatar bonus mirror')
 before=p.Character.Humanoid.WalkSpeed;check(buy('shoes',18),'buy utility');near(p.Character.Humanoid.WalkSpeed,before*1.06,'utility applied movement')
 check(buy('energy',31),'buy penalty item');check(cs.itemBonuses.MaxHP==-3,'negative passive stored')
 for _=1,4 do check(buy('protein',14),'stack item') end
 shards=Shop.states[p].shards;check(not buy('protein',14),'copy cap');near(Shop.states[p].shards,shards,'cap no charge')
 check(request('Shards','Set',0),'zero shards');check(not buy('cheese',9),'unaffordable purchase');check(not request('Reroll'),'unaffordable reroll');near(Shop.states[p].shards,0,'no negative shards')
 check(request('Shards','Set',1000),'reset shards');o=offer('weapon_00_1',1,22);check(request('Lock',1,o.token),'wave lock');check(request('Reroll'),'visit reroll')
 check(request('Start'),'start wave');check(Shop.phase=='Combat' and C:GetAttribute('ZombiesEnabled'),'combat active')
 check(not request('Combine',2,cs.folder.Slot2:GetAttribute('CopyId')),'combat combining denied');check(not request('Buy',1,o.token),'combat purchase denied');check(not request('Sell',1,cs.folder.Slot1:GetAttribute('CopyId')),'combat selling denied')
 check(Shop.finishWave(),'finish');check(Shop.phase=='Shop' and Shop.wave==2 and not C:GetAttribute('ZombiesEnabled'),'next shop');near(Shop.states[p].rerolls,0,'rerolls reset');near(E.reroll(Shop.wave,0),2,'new wave base');check(Shop.states[p].offers[1]==o and o.price==22,'lock survives wave inflation')
 for i=1,4 do Shop.states[p].offers[i].locked=true;Shop.states[p].offers[i].sold=false end
 shards=Shop.states[p].shards;check(not request('Reroll'),'all locked reject');near(Shop.states[p].shards,shards,'all locked free rejection')
 reset();check(request('Shards','Set',1000),'fund sold-out refill')
 local bought={}
 for i=1,4 do bought[i]=offer('cheese',i,1).token end
 for i=1,4 do check(request('Buy',i,bought[i]),'buy all offer '..i) end
 near(Shop.states[p].rerolls,0,'sold-out refill is free')
 for _,nextOffer in Shop.states[p].offers do check(not nextOffer.sold and nextOffer.id~='cheese','sold-out refill renewed offers') end
 reset();check(request('Shards','Set',1000),'fund build items')
 check(buy('antlers',68),'buy antlers');near(cs.stats.ChainBonus,1,'antlers boost chains')
 near(cs.stats.ChainCount,0,'antlers do not create lightning')
 check(buy('battery',72),'buy battery');near(cs.stats.ChainCount,1,'battery creates lightning')
 check(buy('alien',38),'buy alien battery');near(cs.stats.ChainDamage,15,'alien battery boosts chains')
 local contactBefore=cs.stats.ContactReduction -- the class/armor base varies (no class has +15 since the 2026-10-03 class rebalance)
 check(buy('mask',70),'buy burial mask');near(cs.stats.ContactReduction,contactBefore+10,'mask adds contact defense')
 check(buy('potato',20),'buy support potato');check(cs.stats.PickupRadius>8,'potato aids shard pickup')
 -- 2026-10-03: every non-Godly weapon can be offered, not just owned ones. A fresh profile that owns
 -- only the Glock, Frying Pan and Magic Staff can see Medusa's Head and Crystal Ball, never a Godly.
 reset();local savedProfile=p:GetAttribute('ProfileWeapons');p:SetAttribute('ProfileWeapons','00:1:1,01:1:1,30:1:1')
 local set=Shop.offerableWeapons(p)
 check(set['34'] and set['35'] and set['31'],'unowned weapons offerable (Medusa, Crystal Ball, Mjolnir)')
 for _,w in Weapons.List do if w.godly then check(not set[w.id] and Catalog.ById['weapon_'..w.id..'_1']==nil,'godly never offered '..w.id) end end
 check(request('Shards','Set',100000),'fund offer rolls')
 local unowned=false
 for _=1,30 do
  check(request('Reroll'),'roll offers')
  for _,o in Shop.states[p].offers do
   local entry=Catalog.ById[o.id]
   if entry.weaponId then
    check(not Weapons.ById[entry.weaponId].godly,'no godly offer')
    if entry.weaponId~='00' and entry.weaponId~='01' and entry.weaponId~='30' and entry.weaponId~='03' then unowned=true end
   end
  end
 end
 check(unowned,'an unowned weapon was offered in 30 rerolls');p:SetAttribute('ProfileWeapons',savedProfile)
 -- Works with (CharacterStats.usesStat, the rule the server's launchers use too).
 local function W(id) return Weapons.ById[id] end
 check(Stats.usesStat(W('00'),'ProjectileCount') and Stats.usesStat(W('00'),'Pierce') and not Stats.usesStat(W('00'),'Bounce'),'Glock bullets use extra shots and pierce, never bounce')
 for id in Stats.StraightGuns do check(not Stats.usesStat({id=id},'Bounce'),'guns never advertise bounce: '..id) end
 check(not Stats.usesStat(W('01'),'ProjectileCount') and not Stats.usesStat(W('01'),'Pierce'),'Frying Pan swings use none')
 check(not Stats.usesStat(W('12'),'ProjectileCount') and Stats.usesStat(W('12'),'Bounce'),'Boomerang returns: bounce, no extra copies')
 check(Stats.usesStat(W('14'),'ProjectileCount') and not Stats.usesStat(W('14'),'Pierce'),'Molotov: extra throws, no pierce')
 check(Stats.usesStat(W('11'),'ProjectileCount') and not Stats.usesStat(W('11'),'Bounce') and Stats.usesStat(W('11'),'ExplosionDamage'),'Rocket: extra rockets, explosion damage')
 check(not Stats.usesStat(W('29'),'ProjectileCount') and not Stats.usesStat(W('17'),'Pierce'),'streams and spray use none')
 check(Stats.usesStat(W('38'),'ProjectileCount') and not Stats.usesStat(W('38'),'Pierce'),'Storm Bow: more arrows only')
 check(not Stats.usesStat(W('31'),'ProjectileCount') and Stats.usesStat(W('31'),'Pierce'),'Mjolnir throw: pierce, no copies')
 check(not Stats.usesStat(W('00'),'ChainBonus') and Stats.usesStat(W('00'),'ChainBonus',{ChainCount=1}) and Stats.usesStat(W('35'),'ChainBonus'),'lightning needs a source')
 local works=Catalog.worksWith(Catalog.ById.straws,{'01','00','30','00'});check(#works==2 and works[1]=='00' and works[2]=='30','Two Straws works with Glock and Magic Staff')
 check(#Catalog.worksWith(Catalog.ById.straws,{'01','12'})==0,'Two Straws: none for Frying Pan + Boomerang')
 check(Catalog.worksWith(Catalog.ById.protein,{'01'})==nil and Catalog.weaponStats(Catalog.ById.alien)==nil,'general items work with everything')
 -- No dead items: each weapon-only item has some non-Godly weapon that uses it.
 for _,entry in Catalog.List do
  if Catalog.weaponStats(entry) then
   local ids={};for _,w in Weapons.List do if not w.godly then table.insert(ids,w.id) end end
   check(#Catalog.worksWith(entry,ids,Stats.resolve('Brawler',0))>0,'item usable by some weapon '..entry.id)
  end
 end
 -- Offers skip items none of the carried weapons use: a lone Frying Pan never sees Two Straws.
 reset();for i=1,6 do cs.folder['Slot'..i]:SetAttribute('WeaponId',i==1 and '01' or '') end
 check(not Shop.usableItem(Catalog.ById.straws,{'01'},cs.stats) and not Shop.usableItem(Catalog.ById.ketchup,{'01'},cs.stats),'pan: no shot or explosion items')
 check(Shop.usableItem(Catalog.ById.straws,{'00'},cs.stats) and Shop.usableItem(Catalog.ById.protein,{'01'},cs.stats),'glock: straws; pan: protein')
 check(request('Shards','Set',100000),'fund gated rolls');Shop.wave=20
 for _=1,40 do
  check(request('Reroll'),'gated roll')
  for _,o in Shop.states[p].offers do local entry=Catalog.ById[o.id];if not entry.weaponId then check(Shop.usableItem(entry,{'01'},cs.stats),'offered item works with the pan: '..o.id) end end
 end
 Shop.wave=1
 -- Reworked and new items (2026-10-03).
 reset();check(request('Shards','Set',100000),'fund new items')
 local before=table.clone(cs.stats)
 check(buy('marshmallow',20),'buy marshmallow');near(cs.stats.BurnChance,before.BurnChance+5,'marshmallow lights fires');near(cs.stats.BurnDamage,before.BurnDamage+20,'marshmallow burn damage')
 check(buy('crown',44),'buy crown');near(cs.stats.Damage,before.Damage+5,'crown general damage');near(cs.stats.BossDamage,before.BossDamage+20,'crown boss damage')
 check(buy('banana',18),'buy banana peel');near(cs.stats.Dodge,before.Dodge+5,'banana dodge')
 check(buy('soup',34),'buy chicken soup');near(cs.stats.Recovery,before.Recovery+15,'soup recovery')
 check(buy('gummies',66),'buy gummies');near(cs.stats.Regeneration,before.Regeneration+2,'gummies regeneration')
 -- Same-class weighting (2026-10-04): a weapon offer joins choose()'s "same class" pool when it shares
 -- any class with a carried weapon. Carrying a Kusarigama (Juggler, Thrower): Kunai (Thrower), Yo-Yo
 -- (Juggler) and Boomerang (Thrower, Juggler) match; Magic Staff (Mage) and Glock (Gunner) don't.
 local function has(list,wid) for _,e in list do if e.weaponId==wid then return true end end;return false end
 local pool={Catalog.ById.weapon_13_1,Catalog.ById.weapon_21_1,Catalog.ById.weapon_12_1,Catalog.ById.weapon_30_1,Catalog.ById.weapon_00_1}
 local sc=Shop.sameClassPool(pool,{'04'})
 check(has(sc,'13') and has(sc,'21') and has(sc,'12') and not has(sc,'30') and not has(sc,'00'),'same class by any shared class')
 -- A second class counts too: a Nail Gun (Handyman, Gunner) pulls in the Glock, not the Staff.
 sc=Shop.sameClassPool(pool,{'24'});check(has(sc,'00') and not has(sc,'30') and not has(sc,'13'),'Nail Gun shares Gunner')
 check(#Shop.sameClassPool(pool,{'36'})==0 and #Shop.sameClassPool(pool,{})==0,'a Godly or nothing carried shares no class')
 -- READY x/y (RogueliteRunState ShopReady / ShopPlayers): living run members who pressed GO.
 reset();Shop.join(p);Shop.states[p].ready=false;Shop.publishReady()
 near(RS.RogueliteRunState:GetAttribute('ShopPlayers'),1,'ready total');near(RS.RogueliteRunState:GetAttribute('ShopReady'),0,'none ready')
 check(p:GetAttribute('ShopReady')==false,'counted and not ready: the player shows false')
 Shop.states[p].ready=true;Shop.publishReady();near(RS.RogueliteRunState:GetAttribute('ShopReady'),1,'one ready')
 check(p:GetAttribute('ShopReady')==true,'counted and ready: the player shows true')
 -- Withdrawing ready is safe even when GO just ran or an unrelated snapshot made the UI stale.
 -- Replays must not republish, change revisions or renew the normal action cooldown.
 local readiness=Shop.states[p]
 readiness.lastRequest=os.clock();readiness.lastUnready=nil
 local readyRevision=readiness.revision
 check(Shop.request(p,'Unready',readyRevision),'immediate withdrawal bypasses the GO cooldown')
 check(not readiness.ready and p:GetAttribute('ShopReady')==false,'withdrawal updates player and roster')
 near(readiness.revision,readyRevision+1,'withdrawal increments revision once')
 local withdrawnRevision=readiness.revision
 local withdrawnSnapshot=cs.folder:GetAttribute('ShopSnapshot')
 local withdrawnMessage=readiness.message
 local withdrawnRequest,withdrawnAt=readiness.lastRequest,readiness.lastUnready
 for _=1,20 do check(not Shop.request(p,'Unready',readyRevision),'stale no-op withdrawal rejected quietly') end
 near(readiness.revision,withdrawnRevision,'no-op withdrawal keeps revision')
 check(cs.folder:GetAttribute('ShopSnapshot')==withdrawnSnapshot and readiness.message==withdrawnMessage,'no-op withdrawal does not republish')
 check(readiness.lastRequest==withdrawnRequest and readiness.lastUnready==withdrawnAt,'no-op withdrawal does not renew cooldowns')
 readiness.ready=true;readiness.lastUnready=-1e6;readiness.lastRequest=os.clock()
 local staleRevision=readiness.revision
 check(Shop.request(p,'Unready',staleRevision-10),'stale revision can safely withdraw readiness')
 near(readiness.revision,staleRevision+1,'stale withdrawal advances current server revision')
 -- A second distinct withdrawal still has its own throttle, independent of stale revision checks.
 readiness.ready=true;readiness.lastUnready=os.clock()
 local repeatedRevision=readiness.revision;local repeatedSnapshot=cs.folder:GetAttribute('ShopSnapshot')
 check(not Shop.request(p,'Unready',repeatedRevision-10),'repeated stale withdrawal uses separate throttle')
 check(readiness.ready and readiness.revision==repeatedRevision and cs.folder:GetAttribute('ShopSnapshot')==repeatedSnapshot,'throttled withdrawal does not mutate')
 Shop.phase='Combat';readiness.lastUnready=-1e6
 check(not Shop.request(p,'Unready',readiness.revision),'cannot withdraw outside shop phase')
 check(readiness.ready and readiness.revision==repeatedRevision and cs.folder:GetAttribute('ShopSnapshot')==repeatedSnapshot,'combat withdrawal does not mutate')
 Shop.phase='Combat';Shop.publishReady();check(RS.RogueliteRunState:GetAttribute('ShopReady')==nil,'no ready count outside the shop')
 check(p:GetAttribute('ShopReady')==nil,'no player ready mark outside the shop')
 Shop.phase='Shop';Shop.states[p].ready=false
 -- Turret items (2026-10-04, HANDYMAN_TURRET.md): the free Nail Turret follows the class until the
 -- run starts; offered, priced, 20% off for a Handyman, capped at 10; UPGRADE TURRET ignored.
 local Turret=require(C.HandymanTurret)
 local nail,twin,quad=Catalog.ById.turret_nail,Catalog.ById.turret_twin,Catalog.ById.turret_quad
 check(nail and twin and quad and nail.turret==1 and nail.structure,'turret items in the catalog')
 reset();cs.class='Gunner';Characters.refresh(p)
 check(Turret.owned(Shop.states[p].items)==0,'a Gunner starts with no turret')
 cs.class='Handyman';Characters.refresh(p)
 check(Turret.count(Shop.states[p].items,'turret_nail')==1,'picking Handyman before the run adds his free Nail Turret')
 cs.class='Gunner';Characters.refresh(p)
 check(Turret.count(Shop.states[p].items,'turret_nail')==0,'another class before the run takes it back')
 cs.class='Handyman';Characters.refresh(p);Shop.resetPlayer(p)
 local s=Shop.states[p]
 check(Turret.count(s.items,'turret_nail')==1 and Turret.owned(s.items)==1,'a new Handyman run starts with one')
 Shop.wave=2;cs.class='Gunner';Characters.refresh(p)
 check(Turret.count(s.items,'turret_nail')==1,'once the run is under way a class change keeps it')
 cs.class='Handyman';Characters.refresh(p)
 check(Turret.count(s.items,'turret_nail')==1,'and never adds a second')
 -- Prices: EconomyConfig.price, and 20% off structure items for a Handyman only.
 Shop.wave=5
 near(Shop.offerPrice(p,nail),32,'Handyman: a wave-5 Nail Turret is 32 (41 less 20%)')
 near(Shop.offerPrice(p,Catalog.ById.toolbelt),E.price(18,5,.8),'Handyman: Toolbelt 20% off')
 near(Shop.offerPrice(p,Catalog.ById.protein),E.price(14,5,1),'Handyman: other items full price')
 cs.class='Gunner';Characters.refresh(p)
 near(Shop.offerPrice(p,nail),41,'Gunner: a wave-5 Nail Turret is 41')
 cs.class='Handyman';Characters.refresh(p)
 check(request('Shards','Set',100000),'fund turret rolls')
 -- Offered, at the server's price.
 local seenTurret=false
 for _=1,60 do
  check(request('Reroll'),'turret roll')
  for _,o in s.offers do
   local entry=Catalog.ById[o.id]
   if entry.turret then seenTurret=true;near(o.price,Shop.offerPrice(p,entry),'offered turret price '..o.id) end
  end
 end
 check(seenTurret,'a Handyman was offered a turret item in 60 rerolls')
 local o=offer('turret_quad',1);check(request('Buy',1,o.token),'buy a Quad Nailer')
 check(Turret.count(s.items,'turret_quad')==1 and Turret.owned(s.items)==2,'two turrets owned')
 -- Capped at 10: the admin grant, a buy and the offers all stop.
 for _=1,8 do check(Shop.adminItem(p,'turret_nail'),'give a Nail Turret') end
 check(Turret.owned(s.items)==10,'10 turrets')
 check(not Shop.adminItem(p,'turret_twin'),'an 11th from the admin panel is refused')
 local shards=s.shards
 o=offer('turret_twin',1);check(not request('Buy',1,o.token),'buying an 11th is refused');near(s.shards,shards,'no charge for the refused 11th')
 for _=1,40 do
  check(request('Reroll'),'capped roll')
  for _,x in s.offers do check(not Catalog.ById[x.id].turret,'no turret offers at 10: '..x.id) end
 end
 -- UPGRADE TURRET is gone: an old client's request does nothing and says nothing.
 local rev=s.revision;local message=s.message
 check(not request('UpgradeTurret',1),'UpgradeTurret refused')
 check(s.revision==rev and s.message==message,'quietly: no change, no message')
 check(game:GetService('HttpService'):JSONDecode(cs.folder:GetAttribute('ShopSnapshot')).turret==nil,'no turret row in the snapshot')
 Shop.wave=1
end,debug.traceback)
pcall(reset)
script:SetAttribute('Result',game.HttpService:JSONEncode({passed=ok,assertions=checked,error=ok and '' or err}))
