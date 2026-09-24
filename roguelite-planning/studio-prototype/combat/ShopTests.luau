-- Run as a temporary normal server Script in Studio Play, never ship this test.
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
 near(E.refund(30),15,'30 refund');near(E.refund(47),23,'odd refund');near(E.reroll(1,0),1,'wave1 reroll');near(E.reroll(8,3),18,'wave8 reroll4')
 near(E.rarityChance(2,1,0),0,'tier2 locked on wave1');near(E.rarityChance(2,2,0),.06,'tier2 wave2')
 near(E.rarityChance(3,4,0),.02,'tier3 wave4');near(E.rarityChance(4,8,0),.0023,'tier4 wave8')
 near(E.rarityChance(4,1000,100),.08,'tier4 luck cap')
 near(E.rarityChance(2,10,0)-E.rarityChance(3,10,0),.40,'wave10 tier2 share')
 near(E.rarityChance(3,10,0)-E.rarityChance(4,10,0),.1331,'wave10 tier3 share')
 for _,case in {{.005,4},{.10,3},{.30,2},{.90,1}} do
  local draw={NextNumber=function() return case[1] end}
  near(E.rollTier(10,0,draw),case[2],'ordered rarity draw')
 end
 check(E.weaponSlot(1,1,Random.new(1)) and E.weaponSlot(1,2,Random.new(1)),'early weapons')
 check(not E.weaponSlot(1,3,Random.new(1)) and not E.weaponSlot(1,4,Random.new(1)),'early items')
 check(E.weaponSlot(5,1,Random.new(1)),'wave5 weapon guarantee')
 for _,entry in Catalog.List do
  check(entry.basePrice>0 and entry.basePrice%1==0,'catalog price '..entry.id)
  for id in entry.modifiers do check(Stats.ById[id]~=nil,'valid item stat '..id) end
  for id in entry.percent or {} do check(Stats.ById[id]~=nil,'valid percent '..id) end
  if entry.weaponId then
   local band=E.TIER_PRICE_BANDS[entry.tier];check(entry.basePrice>=band[1] and entry.basePrice<=band[2],'weapon tier band')
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
 check(request('Lock',1,token),'lock');local shards=Shop.states[p].shards;local price=E.reroll(1,0)
 check(request('Reroll'),'reroll');near(Shop.states[p].shards,shards-price,'reroll charge');near(Shop.states[p].rerolls,1,'reroll count');check(Shop.states[p].offers[1]==o and o.price==47,'locked price and identity')
 for _,offerNow in Shop.states[p].offers do check(not seen[offerNow.id] or offerNow==o,'reroll repeated old offer') end
 cs.overrides.ShopPricePercent=15;Characters.refresh(p);check(o.price==47,'locked unaffected by stat');near(E.modifier(cs.stats),1.15,'positive price modifier')
 cs.overrides.ShopPricePercent=-10;Characters.refresh(p);near(E.modifier(cs.stats),.9,'negative price modifier')
 cs.overrides={};Characters.refresh(p)
 check(request('Buy',1,token),'buy locked weapon');local slot=cs.folder.Slot2;check(slot:GetAttribute('WeaponId')=='00','equipped immediately');near(slot:GetAttribute('FinalPurchasePrice'),47,'actual paid saved')
 local copy=slot:GetAttribute('CopyId');local rev=Shop.states[p].revision;shards=Shop.states[p].shards
 check(not request('Buy',1,token),'reject replay sold');near(Shop.states[p].shards,shards,'no repeat charge')
 Shop.wave=20;check(request('Sell',2,copy),'sell later wave');near(Shop.states[p].shards,shards+23,'sale ignores inflation');check(slot:GetAttribute('WeaponId')=='','sale removed');check(not request('Sell',2,copy),'reject sell replay')
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
 check(buy('mask',70),'buy burial mask');near(cs.stats.ContactReduction,25,'mask adds contact defense')
 check(buy('potato',20),'buy support potato');check(cs.stats.PickupRadius>8,'potato aids shard pickup')
end,debug.traceback)
pcall(reset)
script:SetAttribute('Result',game.HttpService:JSONEncode({passed=ok,assertions=checked,error=ok and '' or err}))
