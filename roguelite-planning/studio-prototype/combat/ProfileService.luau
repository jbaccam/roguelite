-- Saved account progression: emeralds, classes, weapon tiers/duplicates, chests, skills,
-- pity, map records and processed purchase receipts. Server-only authority.
-- Emeralds are the only currency: earned from runs/daily/codes and bought with Robux.
-- `bought` counts Robux emeralds not yet spent; where paid random items are restricted,
-- only the earned part (emeralds - bought) can open chests.
-- Studio uses an in-memory profile unless Workspace attribute EnableStudioDataStores=true,
-- so Studio play and simulated purchases never persist.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Http=game:GetService('HttpService')
local DataStores=game:GetService('DataStoreService')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Chests=require(combat:WaitForChild('ChestConfig'))
local Weapons=require(combat:WaitForChild('WeaponCatalog'))
local Money=require(combat:WaitForChild('MonetizationConfig'))
local Skills=require(combat:WaitForChild('SkillTreeConfig'))
local Armor=require(combat:WaitForChild('ArmorCatalog'))
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed; this module is unsandboxed
-- Redeemable codes (server-only so they cannot be read from the client). One use per account.
local CODES={
 RELEASE={emeralds=300},
 CHESTS={chests={Gold=1}},
 REROLL={rerolls=3},
}
local P={profiles={},loaded={}}
local STORE_NAME='RogueliteProfile_v1'
local useStore=not RunService:IsStudio() or workspace:GetAttribute('EnableStudioDataStores')==true
local store=useStore and DataStores:GetDataStore(STORE_NAME)
local SIGNATURE={Brawler='01',Gunner='00',Thrower='12',Juggler='19',Handyman='24',Mage='30'}
local MAX_RECEIPTS=200

local function fresh()
 local d={version=1,emeralds=0,bought=0,classes={Brawler=true,Gunner=true,Mage=true},weapons={},pity={},picks={},chests={},
  receipts={},receiptOrder={},bestWaves={},mapWins={},starterPack=false,vip=false,
  rerolls=0,banishes=0,quickOpen=false,codes={},daily={day=0,bought={}},vipClaimDay=0,skills={},
  armor={},wearing={}} -- armor: 'DragonScale.Helmet' -> {tier,have}; wearing: slot -> set id
 for class in d.classes do d.weapons[SIGNATURE[class]]={tier=1,have=0} end
 return d
end
local function csv(t,fmt) local out={};for k,v in t do table.insert(out,fmt(k,v)) end;table.sort(out);return table.concat(out,',') end

function P.publish(player)
 local d=P.profiles[player];if not d then return end
 player:SetAttribute('ProfileGems',d.emeralds)
 player:SetAttribute('ProfileGemsEarned',d.emeralds-d.bought) -- what restricted regions may spend on chests
 player:SetAttribute('ProfileClasses',csv(d.classes,function(k) return k end))
 player:SetAttribute('ProfileWeapons',csv(d.weapons,function(k,v) return k..':'..v.tier..':'..v.have end))
 player:SetAttribute('ProfileArmor',csv(d.armor,function(k,v) return k..':'..v.tier..':'..v.have end))
 -- ArmorService puts the worn pieces on the character from this attribute.
 player:SetAttribute('ProfileWearing',csv(d.wearing,function(k,v) return k..':'..v end))
 player:SetAttribute('ProfilePity',csv(d.pity,function(k,v) return k..':'..v end))
 player:SetAttribute('ProfilePicks',csv(d.picks,function(k,v) return k..':'..v end))
 player:SetAttribute('ProfileChests',csv(d.chests,function(k,v) return k..':'..v end))
 player:SetAttribute('ProfileBestWaves',csv(d.bestWaves,function(k,v) return k..':'..v end))
 player:SetAttribute('ProfileMapWins',csv(d.mapWins,function(k) return k end))
 player:SetAttribute('ProfileStarterPack',d.starterPack);player:SetAttribute('ProfileVIP',d.vip)
 player:SetAttribute('ProfileRerolls',d.rerolls);player:SetAttribute('ProfileBanishes',d.banishes)
 player:SetAttribute('ProfileQuickOpen',d.quickOpen)
 -- CharacterService reads this server-set attribute to apply the permanent skill bonuses.
 player:SetAttribute('ProfileSkills',Skills.serialize(d.skills))
 player:SetAttribute('ProfileDaily',Http:JSONEncode(P.dailyView(player)))
 player:SetAttribute('ProfileLoaded',true)
end

function P.load(player)
 local data
 if store then
  for attempt=1,3 do
   local ok,result=pcall(store.GetAsync,store,'u_'..player.UserId)
   if ok then data=result or fresh();break end
   warn('ProfileService: load failed',player.UserId,result);task.wait(attempt)
  end
  if not data then player:SetAttribute('ProfileLoadFailed',true);return end -- never save over unknown data
 else data=fresh() end
 local base=fresh();for k,v in base do if data[k]==nil then data[k]=v end end
 -- Chest tiers replaced class chests and the Royal Chest (2026-09-28): convert unopened ones,
 -- and the old every-10th-chest picks became the Legendary pity counter.
 local chests={}
 for kind,n in data.chests do local k=Chests.Legacy[kind] or kind;if Chests.ById[k] then chests[k]=(chests[k] or 0)+n end end
 data.chests=chests
 if data.pity.Legendary==nil then data.pity={Legendary=0} end
 if data.pity.Godly==nil then data.pity.Godly=0 end -- Godly pity (2026-09-28); old saves start at 0
 data.picks={}
 -- Armor has no chests yet: Studio test profiles (in memory, never saved) own the sample sets.
 if not store then
  for _,setId in Armor.StudioGrant do
   for _,slot in Armor.Slots do local id=Armor.pieceId(setId,slot);data.armor[id]=data.armor[id] or {tier=1,have=0} end
  end
 end
 -- Keys were dropped: old saves convert them to earned emeralds once.
 if type(data.keys)=='number' then data.emeralds+=math.max(0,data.keys)*Money.EmeraldsPerOldKey;data.keys=nil end
 P.profiles[player]=data;P.loaded[player]=true
 P.publish(player)
end
function P.save(player)
 local d=P.profiles[player];if not d or not store or not P.loaded[player] then return end
 local ok,err=pcall(store.UpdateAsync,store,'u_'..player.UserId,function() return d end)
 if not ok then warn('ProfileService: save failed',player.UserId,err) end
end
function P.get(player) return P.profiles[player] end

-- Receipts: remember processed PurchaseIds so a retried receipt never grants twice.
function P.hasReceipt(player,id) local d=P.profiles[player];return d and d.receipts[id]==true end
function P.addReceipt(player,id)
 local d=P.profiles[player];if not d then return end
 d.receipts[id]=true;table.insert(d.receiptOrder,id)
 while #d.receiptOrder>MAX_RECEIPTS do d.receipts[table.remove(d.receiptOrder,1)]=nil end
end

-- Spend emeralds. Robux emeralds are used up first, so earned emeralds last longest for
-- restricted-region chests; `earnedOnly` (restricted chest opens) may not touch Robux emeralds.
local function canSpend(d,amount,earnedOnly) return (earnedOnly and d.emeralds-d.bought or d.emeralds)>=amount end
local function spend(d,amount,earnedOnly)
 if not canSpend(d,amount,earnedOnly) then return false end
 d.emeralds-=amount
 if not earnedOnly then d.bought=math.max(0,d.bought-amount) end
 return true
end
-- g.paid marks emeralds bought with Robux (receipts and Robux refunds).
function P.grant(player,g)
 local d=P.profiles[player];if not d then return false end
 d.emeralds+=g.emeralds or 0
 if g.paid then d.bought+=g.emeralds or 0 end
 if g.class then d.classes[g.class]=true;if SIGNATURE[g.class] and not d.weapons[SIGNATURE[g.class]] then d.weapons[SIGNATURE[g.class]]={tier=1,have=0} end end
 for kind,n in g.chests or {} do kind=Chests.Legacy[kind] or kind;if Chests.ById[kind] then d.chests[kind]=(d.chests[kind] or 0)+n end end
 if g.starterPack then d.starterPack=true end
 if g.vip then d.vip=true end
 if g.quickOpen then d.quickOpen=true end
 d.rerolls+=g.rerolls or 0;d.banishes+=g.banishes or 0
 -- Arsenal bundle: +N toward the upgrade bar of every class's signature weapon.
 if g.signatureUpgrades then
  for _,id in SIGNATURE do
   for _=1,g.signatureUpgrades do P.addDrop(d,id) end
  end
 end
 P.publish(player);return true
end

-- Copies of one weapon: the first copy of a new weapon unlocks it at Tier I; the rest fill the
-- upgrade bar; past Tier IV each copy turns into (earned) emeralds by rarity.
function P.addCopies(d,id,count)
 local rec=d.weapons[id];local new=false
 if not rec then rec={tier=1,have=0};d.weapons[id]=rec;new=true;count-=1 end
 local emeralds=0
 if rec.tier>=4 then emeralds=count*Chests.overflow(id);d.emeralds+=emeralds
 else rec.have+=count end
 return {id=id,new=new,tier=rec.tier,have=rec.have,emeralds=emeralds,overflow=emeralds>0}
end
function P.addDrop(d,id) return P.addCopies(d,id,1) end

-- Wear the owned piece of `setId` in `slot`, or take it off (setId nil). slot 'All' does every
-- slot: all owned pieces of the set, or takes everything off.
function P.wear(player,slot,setId)
 local d=P.profiles[player];if not d then return false,'Profile still loading' end
 local set=setId~=nil and Armor.ById[setId]
 if setId~=nil and not set then return false,'Unknown armor' end
 local slots=slot=='All' and Armor.Slots or {slot}
 if not Armor.isSlot(slots[1]) then return false,'Unknown slot' end
 local changed=0
 for _,s in slots do
  if not set then
   if d.wearing[s] then d.wearing[s]=nil;changed+=1 end
  elseif d.armor[Armor.pieceId(setId,s)] then d.wearing[s]=setId;changed+=1
  elseif slot~='All' then return false,"You don't own that piece yet" end
 end
 if changed==0 then return false,set and "You don't own any of that set" or 'Nothing to take off' end
 P.publish(player)
 if not set then return true,slot=='All' and 'Armor off' or 'Took off the '..string.lower(slot) end
 return true,slot=='All' and (set.name..' set equipped') or (set.name..' '..string.lower(slot)..' equipped')
end

local rng=Random.new()
local RANK={Common=1,Rare=2,Epic=3,Legendary=4,Godly=5}
-- Buy chests into the inventory. Where paid random items are restricted, only emeralds earned
-- in play can pay for chests.
function P.buyChest(player,kind,count,restricted)
 local d=P.profiles[player];local chest=Chests.ById[kind]
 if not d or not chest then return false,'Unknown chest' end
 if not Chests.validAmount(count) then return false,'Invalid amount' end
 if not chest.emeralds then return false,chest.name..'s come from Robux packs and rewards' end
 local price=chest.emeralds*count
 if not canSpend(d,price,restricted) then
  if restricted and d.emeralds>=price then return false,'Only emeralds earned in runs can buy chests in your region' end
  return false,'Need '..(price-(restricted and d.emeralds-d.bought or d.emeralds))..' more emeralds'
 end
 spend(d,price,restricted)
 d.chests[kind]=(d.chests[kind] or 0)+count
 P.publish(player)
 return true,count>1 and ('Bought '..count..'× '..chest.name) or ('Bought '..chest.name)
end
-- Open owned chests (up to count). Every chest rolls on the server; the reply groups all copies
-- by weapon: {id, count, rarity, new, tier, have, emeralds}, rarest first.
function P.openChest(player,kind,count)
 local d=P.profiles[player];local chest=Chests.ById[kind]
 if not d or not chest then return false,'Unknown chest' end
 if not Chests.validAmount(count) then return false,'Invalid amount' end
 local n=math.min(count,d.chests[kind] or 0)
 if n<=0 then return false,'No '..chest.name..' to open' end
 d.chests[kind]-=n;if d.chests[kind]<=0 then d.chests[kind]=nil end
 local tally={}
 for _=1,n do
  local counts=Chests.open(kind,rng,d.pity) -- rolls with both pity counters and updates them
  for _,r in Chests.Rarities do Chests.group(r,counts[r],rng,tally) end
 end
 local results={}
 for id,c in tally do
  local r=P.addCopies(d,id,c);r.count=c;r.rarity=Chests.RarityOf[id]
  table.insert(results,r)
 end
 table.sort(results,function(a,b)
  if RANK[a.rarity]~=RANK[b.rarity] then return RANK[a.rarity]>RANK[b.rarity] end
  if a.count~=b.count then return a.count>b.count end
  return a.id<b.id
 end)
 P.publish(player)
 return true,n>1 and ('Opened '..n..'× '..chest.name) or ('Opened '..chest.name),results
end
function P.upgrade(player,id)
 local d=P.profiles[player];local rec=d and d.weapons[id]
 if not rec then return false,'You do not own that weapon' end
 if rec.tier>=4 then return false,'Already Tier IV' end
 local cost=Chests.upgradeCost(id,rec.tier)
 if rec.have<cost then return false,'Need '..cost..' to upgrade' end
 rec.have-=cost;rec.tier+=1;P.publish(player)
 return true,Weapons.ById[id].name..' is now Tier '..({'I','II','III','IV'})[rec.tier]
end
function P.buyClass(player,class,price)
 local d=P.profiles[player]
 if not d or not SIGNATURE[class] then return false,'Unknown class' end
 if d.classes[class] then return false,'Already unlocked' end
 if not spend(d,price) then return false,'Not enough emeralds' end
 P.grant(player,{class=class})
 return true,class..' unlocked'
end
-- Skill tree: one node per call, parent must be owned, paid in emeralds (SkillTreeConfig).
function P.buySkill(player,id)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 local owned=Skills.parse(Skills.serialize(d.skills))
 local ok,why=Skills.canBuy(owned,id,d.emeralds)
 if not ok then return false,why end
 local node=Skills.ById[id]
 spend(d,node.cost);d.skills[id]=true;P.publish(player)
 return true,node.name..' unlocked'
end
-- Refunds every bought node. Only reachable through the Studio test action in RogueliteMeta.
function P.resetSkills(player)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 local refund=0
 for id in d.skills do local node=Skills.ById[id];if node then refund+=node.cost end end
 d.skills={};d.emeralds+=refund;P.publish(player)
 return true,'Skills reset (+'..refund..' emeralds)'
end

-- Run result: emeralds for the waves passed, best wave per map.
-- A test run (the admin panel was used) grants nothing: no emeralds, wins or best waves.
function P.recordRun(player,map,wavesPassed,emeralds)
 local d=P.profiles[player];if not d or Admin.isTestRun() then return end
 if d.vip then emeralds=math.floor(emeralds*(1+Money.VIPRunBonus)+.5) end
 d.emeralds+=emeralds
 if wavesPassed>(d.bestWaves[map] or 0) then d.bestWaves[map]=wavesPassed end
 if wavesPassed>=20 then d.mapWins[map]=true end
 P.publish(player)
end

-- Live progress as each wave clears (RogueliteMeta): best wave, and the win at wave 20 with its
-- one-time first-win bonus. Wave emeralds still pay at the run's end (recordRun). A test run
-- (the admin panel was used) saves nothing.
function P.recordProgress(player,map,wavesPassed,firstWinBonus)
 local d=P.profiles[player];if not d or Admin.isTestRun() then return end
 local changed=false
 if wavesPassed>(d.bestWaves[map] or 0) then d.bestWaves[map]=wavesPassed;changed=true end
 if wavesPassed>=20 and not d.mapWins[map] then
  d.mapWins[map]=true;d.emeralds+=math.max(0,math.floor(firstWinBonus or 0));changed=true
 end
 if changed then P.publish(player) end
end

-- Stored rerolls/banishes spent during a run.
function P.spend(player,field)
 local d=P.profiles[player]
 if not d or (field~='rerolls' and field~='banishes') or d[field]<=0 then return false end
 d[field]-=1;P.publish(player);return true
end

-- Daily deals: same 5 deals for a player all day, new ones at UTC midnight. Never Godly.
local function dealList(userId)
 local day=Money.day();local r=Random.new(day*100003+userId%100003)
 local list={{kind='Emeralds',amount=Money.DailyFreeEmeralds,currency='Free',price=0}}
 -- Each paid slot: a rarity, then a weapon of it, priced per copy by rarity (ChestConfig.rollDeal).
 for _=2,Money.DailyDealSlots do table.insert(list,Chests.rollDeal(r)) end
 return list,day
end
local function dailyState(d)
 local day=Money.day()
 if d.daily.day~=day then d.daily={day=day,bought={}} end
 return d.daily
end
function P.dailyView(player)
 local d=P.profiles[player];if not d then return {} end
 local list=dealList(player.UserId);local st=dailyState(d)
 for i,deal in list do deal.bought=st.bought[tostring(i)]==true end
 return {deals=list,vipClaimed=d.vipClaimDay==Money.day(),resetIn=Money.secondsToReset()}
end
function P.buyDeal(player,index)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 local list=dealList(player.UserId);local deal=type(index)=='number' and list[index]
 if not deal then return false,'Unknown deal' end
 local st=dailyState(d)
 if st.bought[tostring(index)] then return false,'Already claimed today' end
 if deal.currency=='Emeralds' and not spend(d,deal.price) then return false,'Not enough emeralds' end
 st.bought[tostring(index)]=true
 local results={}
 if deal.kind=='Emeralds' then d.emeralds+=deal.amount
 else for _=1,deal.amount do table.insert(results,P.addDrop(d,deal.id)) end end
 P.publish(player)
 return true,deal.kind=='Emeralds' and ('+'..deal.amount..' emeralds') or ('+'..deal.amount..' '..Weapons.ById[deal.id].name),results
end
function P.claimVipChest(player)
 local d=P.profiles[player]
 if not d or not d.vip then return false,'VIP only' end
 if d.vipClaimDay==Money.day() then return false,'Come back tomorrow' end
 d.vipClaimDay=Money.day();P.grant(player,{chests={[Money.VIPDailyChest]=1}})
 return true,'Free '..Chests.ById[Money.VIPDailyChest].name..' added'
end
function P.redeem(player,code)
 local d=P.profiles[player]
 if not d or type(code)~='string' or #code>30 then return false,'Invalid code' end
 code=string.upper(code:gsub('%s',''))
 local reward=CODES[code]
 if not reward then return false,'Invalid code' end
 if d.codes[code] then return false,'Code already used' end
 d.codes[code]=true;P.grant(player,reward)
 return true,'Code redeemed!'
end

Players.PlayerAdded:Connect(P.load)
for _,p in Players:GetPlayers() do task.spawn(P.load,p) end
Players.PlayerRemoving:Connect(function(p) P.save(p);P.profiles[p]=nil;P.loaded[p]=nil end)
game:BindToClose(function() for p in P.profiles do P.save(p) end end)
task.spawn(function() while true do task.wait(120);for p in P.profiles do P.save(p) end end end)
return P
