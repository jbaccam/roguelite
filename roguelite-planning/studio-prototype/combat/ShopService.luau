-- In-memory run economy. No DataStores, client prices or client-owned inventory.
-- Robux rerolls arrive only through RogueliteMeta's validated receipts (S.paidReroll).
local RS=game:GetService('ReplicatedStorage')
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Http=game:GetService('HttpService')
local combat=RS:WaitForChild('RogueliteCombat')
local E=require(combat.EconomyConfig)
local Catalog=require(combat.ShopCatalog)
local Weapons=require(combat.WeaponCatalog)
local Characters=require(script.Parent.CharacterService)
local Shards=require(script.Parent.ShardDropService)
local Hearts=require(script.Parent.HeartDropService)
local XP=require(combat.RunXP)
local Upgrades=require(combat.LevelUpCatalog)
local StatSchema=require(combat.CharacterStats)
local Maps=require(combat.MapConfig) -- sandboxed, like this module
local S={states={},wave=1,phase='Shop'}
-- The first-join tutorial (plans/2026-10-03-tutorial-design.md): TutorialDirector sets S.tutorial
-- while a tutorial run is on, nil otherwise. Plain data from TutorialConfig: startShards, waves
-- ([wave]={count,roster}), offers ([shop wave][slot]=ShopCatalog id), waveSeconds (the director
-- ends each wave when its enemies are dead) and noShopTimer. Clearing its last wave goes to phase
-- 'Victory' instead of a shop: no shop or level-up cards before the results screen, until
-- RogueliteMeta ends the run.
-- Hooks other scripts listen to: `S.onWaveCleared=fn` adds a listener and never replaces one, so
-- load order between listeners doesn't matter. Listeners run inside this sandboxed module's
-- thread, so they should only record (RunAnalytics queues its events and sends them itself).
--   onWaveCleared(wavesPassed)      onBuy(p,offerId,price)     onReroll(p,kind,how,cost)
--   onLevelPick(p,upgradeId)        onLevelUp(p,gained)        onShards(p,collected)
-- kind is 'Shop' or 'Upgrade'; how is 'Shards', 'Free' (a saved reroll) or 'Bought' (Robux/stored).
local listeners={onWaveCleared={},onBuy={},onReroll={},onLevelPick={},onLevelUp={},onShards={}}
setmetatable(S,{__newindex=function(t,k,v) if listeners[k] then table.insert(listeners[k],v) else rawset(t,k,v) end end})
local function fire(name,...)
 for _,fn in listeners[name] do local ok,err=pcall(fn,...);if not ok then warn('ShopService.'..name..' listener failed:',err) end end
end
local rng=Random.new()
local serial=0
local function token() serial+=1;return tostring(serial) end
-- Run membership: who is in this run, apart from who is connected. A player joins by being alive
-- in the arena (a pad launch, Studio's arena start, admin travel) and leaves by returning to the
-- lobby, giving up or disconnecting. Each stay is a stint with its own id, so run emeralds settle
-- once per stint (ProfileService.settleRun). The RunMember attribute mirrors it for other scripts
-- (boss health scaling, leaderboards).
S.members={}
local stints=0
local function newRunId() return string.format('%x-%x',os.time(),rng:NextInteger(0,2^30)) end
S.runId=newRunId()
function S.isMember(p) return S.members[p]~=nil end
function S.memberCount() local n=0;for _ in S.members do n+=1 end;return n end
function S.join(p)
 if S.members[p] or not S.states[p] then return end
 stints+=1;S.members[p]={stint=S.runId..'/'..stints,joined=S.wave}
 p:SetAttribute('RunMember',true)
end
function S.leave(p)
 if not S.members[p] then return end
 S.members[p]=nil;p:SetAttribute('RunMember',nil)
end
local run=RS:FindFirstChild('RogueliteRunState') or Instance.new('Folder')
run.Name='RogueliteRunState';run.Parent=RS
run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',1);run:SetAttribute('AdminTestRun',nil);run:SetAttribute('RunId',S.runId)
combat:SetAttribute('ZombiesEnabled',false)
local remote=combat:WaitForChild('ShopAction')
local function alive(p) local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid');return h~=nil and h.Health>0 end
-- Only run members count: players standing in the lobby are not part of the arena run.
local function living(p) return S.members[p]~=nil and alive(p) end
local function slots(p) return Characters.states[p].folder end
-- What selling the weapon in slot folder f pays now (EconomyConfig.sellValue). Godly weapons are
-- never in the run shop, so they are valued at the top of their tier's price band.
local function sellValue(p,f)
 local tier=math.clamp(f:GetAttribute('Tier') or 1,1,4)
 local entry=Catalog.ById['weapon_'..(f:GetAttribute('WeaponId') or '')..'_'..tier]
 local cs=Characters.states[p]
 return E.sellValue(entry and entry.basePrice or E.TIER_PRICE_BANDS[tier][2],S.wave,E.modifier(cs and cs.stats or {}))
end
local function owned(p)
 local result={}
 for i=1,6 do local f=slots(p)['Slot'..i]
  result[i]={slot=i,id=f:GetAttribute('WeaponId') or '',copy=f:GetAttribute('CopyId') or '',tier=f:GetAttribute('Tier') or 1,paid=f:GetAttribute('FinalPurchasePrice') or 0,basePrice=f:GetAttribute('BasePrice') or 0,wave=f:GetAttribute('WavePurchased') or 0,sell=f:GetAttribute('WeaponId')~='' and sellValue(p,f) or 0}
 end
 for _,weapon in result do
  for _,other in result do
   if weapon.id~='' and weapon.tier<4 and weapon.slot~=other.slot and weapon.id==other.id and weapon.tier==other.tier then weapon.canCombine=true;weapon.combineSlot=other.slot;break end
  end
 end
 return result
end
local function clearWeapon(f)
 f:SetAttribute('WeaponId','');f:SetAttribute('CopyId',token());f:SetAttribute('FinalPurchasePrice',0);f:SetAttribute('PurchasePrice',0);f:SetAttribute('BasePrice',0);f:SetAttribute('Tier',1);f:SetAttribute('WavePurchased',0)
end
local function upgradeWeapon(f,paid)
 local tier=(f:GetAttribute('Tier') or 1)+1
 f:SetAttribute('FinalPurchasePrice',(f:GetAttribute('FinalPurchasePrice') or 0)+paid)
 f:SetAttribute('PurchasePrice',f:GetAttribute('FinalPurchasePrice'))
 f:SetAttribute('BasePrice',Catalog.ById['weapon_'..f:GetAttribute('WeaponId')..'_'..tier].basePrice)
 f:SetAttribute('CopyId',token());f:SetAttribute('Tier',tier)
end
function S.prepareUpgrades(p)
 local s=S.states[p];local cs=Characters.states[p]
 if not s or not cs or S.phase~='Shop' or s.pendingLevels<=0 or #s.upgradeOffers>0 then return end
 s.upgradeOffers=Upgrades.roll(cs.stats,s.banished,s.level-s.pendingLevels+1,rng)
 for _,offer in s.upgradeOffers do offer.token=token();offer.new=(s.upgradeBonuses[offer.id] or 0)==0 end
 s.upgradeToken=token();s.upgradeRerolls=0
end
-- The combat HUD reads these attributes directly. Pickups do not change shop
-- offers, passives or equipped weapons, so they must not rebuild the full snapshot.
function S.publishProgress(p)
 local s=S.states[p];if not s or not Characters.states[p] then return end
 local state=slots(p)
 state:SetAttribute('Shards',s.shards);state:SetAttribute('BaggedShards',s.baggedShards)
 state:SetAttribute('RunLevel',s.level);state:SetAttribute('RunXP',s.xp)
 state:SetAttribute('RunXPRequired',XP.required(s.level))
 state:SetAttribute('PendingLevelUps',s.pendingLevels)
end
-- A weapon slot's attributes, as a rejoin keeps them (stash, below); nil when the slots are gone.
local SLOT_KEYS={'WeaponId','Tier','CopyId','BasePrice','FinalPurchasePrice','PurchasePrice','WavePurchased'}
local function slotRows(p)
 local cs=Characters.states[p];local folder=cs and cs.folder;if not folder or not folder.Parent then return nil end
 local rows={}
 for i=1,6 do
  local f=folder:FindFirstChild('Slot'..i);if not f then return nil end
  local row={};for _,k in SLOT_KEYS do row[k]=f:GetAttribute(k) end;rows[i]=row
 end
 return rows
end
function S.publish(p,message)
 local s=S.states[p];if not s or not Characters.states[p] then return end
 s.slotRows=slotRows(p) or s.slotRows -- every slot change publishes, so this copy stays current
 local data={pendingLevels=s.pendingLevels,upgradeOffers=s.upgradeOffers,upgradeToken=s.upgradeToken,upgradeRerolls=s.upgradeRerolls,upgradeRerollPrice=E.reroll(S.wave,s.upgradeRerolls),freeRerolls=s.freeRerolls,freeUpgradeRerolls=s.freeUpgradeRerolls,baggedShards=s.baggedShards,level=s.level,shards=s.shards,wave=S.wave,phase=S.phase,rerolls=s.rerolls,rerollPrice=E.reroll(S.wave,s.rerolls),offers=s.offers,items=s.items,weapons=owned(p),ready=s.ready,revision=s.revision,message=message or s.message or '',modifier=E.modifier(Characters.states[p].stats),debug=RunService:IsStudio() and E.DEBUG_CURRENCY_ENABLED}
 data.upgrades=s.upgradeBonuses -- plan L: the pause screen's level-up picks (id -> picks)
 s.message=data.message;S.publishProgress(p)
 slots(p):SetAttribute('ShopSnapshot',Http:JSONEncode(data))
end
local function reprice(p)
 local s=S.states[p];local modifier=E.modifier(Characters.states[p].stats)
 for _,o in s.offers do if not o.locked and not o.sold then o.price=E.price(Catalog.ById[o.id].basePrice,S.wave,modifier) end end
end
local wanted={
 Brawler={Health=true,Armor=true,Melee=true},Gunner={Projectile=true,Pierce=true,Crit=true,AttackSpeed=true},
 Thrower={Projectile=true,Bounce=true,Pierce=true},Juggler={Mobility=true,Bounce=true,Crit=true},
 Handyman={Explosion=true,Economy=true,Armor=true},Mage={Burn=true,Slow=true,Poison=true,Lightning=true},
}
local function choose(pool,p,wantWeapon)
 local cs=Characters.states[p]
 if wantWeapon then
  local ownedIds,ownedHomes={},{}
  for i=1,6 do
   local id=slots(p)['Slot'..i]:GetAttribute('WeaponId')
   local weapon=Weapons.ById[id]
   if weapon then ownedIds[id]=true;ownedHomes[weapon.home]=true end
  end
  local n=rng:NextNumber()
  local same,sameClass={},{}
  for _,entry in pool do
   if ownedIds[entry.weaponId] then table.insert(same,entry) end
   if ownedHomes[Weapons.ById[entry.weaponId].home] then table.insert(sameClass,entry) end
  end
  -- 10% an owned weapon (duplicates merge up a tier), 15% one from an owned weapon's class.
  if n<.10 and #same>0 then pool=same
  elseif n<.25+E.classBonus(S.wave) and #sameClass>0 then pool=sameClass end
 elseif rng:NextNumber()<.05 then
  local tags=wanted[cs.class] or {}
  local matched={}
  for _,entry in pool do
   for _,tag in entry.tags or {} do if tags[tag] then table.insert(matched,entry);break end end
  end
  if #matched>0 then pool=matched end
 end
 -- Weapons are picked by rarity weight (EconomyConfig.rarityWeight): rarer ones show up less,
 -- less so as waves go on and with Luck. Items stay equally likely.
 if pool[1] and pool[1].kind=='Weapon' and E.rarityWeight then
  local total,weights=0,{}
  for i,entry in pool do
   local w=Weapons.ById[entry.weaponId];weights[i]=E.rarityWeight(w and w.rarity or 'Common',S.wave,cs.stats.Luck);total+=weights[i]
  end
  if total>0 then
   local x=rng:NextNumber()*total
   for i,w in weights do x-=w;if x<=0 then return pool[i] end end
   return pool[#pool]
  end
 end
 return pool[rng:NextInteger(1,#pool)]
end
-- Weapons the run shop may offer this player: the ones they own (ProfileWeapons, "id:tier:have"
-- from ProfileService) plus whatever they carry now (the user, 2026-10-02; audit G6). New weapons
-- unlock from chests and the lobby's daily shop. Example: a new player owns the Glock, Frying Pan
-- and Magic Staff, so their shop offers those three (any tier) and items.
local function offerable(p)
 local set={}
 for id in string.gmatch(p:GetAttribute('ProfileWeapons') or '','([^,:]+):%d+:%d+') do set[id]=true end
 for i=1,6 do local id=slots(p)['Slot'..i]:GetAttribute('WeaponId');if id and id~='' then set[id]=true end end
 return set
end
local function roll(p,slot,excluded)
 local s=S.states[p];local cs=Characters.states[p]
 -- The tutorial's guided offer (S.tutorial.offers), tagged forced=<wave>. Once this wave's is
 -- on show (or sold), a reroll or refill rolls the slot normally. The previous shop's offers don't
 -- count, even when they held the same item.
 local forced=S.tutorial and S.tutorial.offers and S.tutorial.offers[S.wave] and S.tutorial.offers[S.wave][slot]
 local forcedEntry=forced and Catalog.ById[forced]
 local forcedShown=false
 if forcedEntry then for _,o in s.offers do if o.forced==S.wave then forcedShown=true;break end end end
 if forcedEntry and not forcedShown then
  excluded[forcedEntry.id]=true
  return {id=forcedEntry.id,token=token(),price=E.price(forcedEntry.basePrice,S.wave,E.modifier(cs.stats)),locked=false,sold=false,forced=S.wave}
 end
 local wantWeapon=E.weaponSlot(S.wave,slot,rng)
 local tier=E.rollTier(S.wave,cs.stats.Luck,rng)
 local owned=offerable(p)
 local function fill(weapons)
  local pool={}
  for try=tier,1,-1 do
   for _,entry in Catalog.List do
    if (entry.kind=='Weapon')==weapons and entry.tier==try and not excluded[entry.id] and (not weapons or owned[entry.weaponId]) then
     local count=0
     for _,it in s.items do if it.id==entry.id then count=it.count;break end end
     if entry.kind=='Weapon' or count<entry.cap then table.insert(pool,entry) end
    end
   end
   if #pool>0 then break end
  end
  return pool
 end
 -- An owned weapon, else an item; with the item pool exhausted too, any owned weapon of any tier.
 local pool=fill(wantWeapon)
 if #pool==0 and wantWeapon then pool=fill(false) end
 if #pool==0 then
  for _,entry in Catalog.List do if entry.kind=='Weapon' and owned[entry.weaponId] and not excluded[entry.id] then table.insert(pool,entry) end end
 end
 -- Last resort (nothing owned is known yet): any weapon, rather than a dead offer.
 if #pool==0 then
  for _,entry in Catalog.List do if entry.kind=='Weapon' and not excluded[entry.id] then table.insert(pool,entry) end end
 end
 local entry=choose(pool,p,wantWeapon and #pool>0 and pool[1].kind=='Weapon')
 excluded[entry.id]=true
 return {id=entry.id,token=token(),price=E.price(entry.basePrice,S.wave,E.modifier(cs.stats)),locked=false,sold=false}
end
function S.bonuses(p)
 local s=S.states[p];local cs=Characters.states[p];if not s or not cs then return end
 cs.itemBonuses=table.clone(s.upgradeBonuses);cs.itemPercent={}
 for _,item in s.items do local entry=Catalog.ById[item.id]
  for id,value in entry.modifiers do cs.itemBonuses[id]=(cs.itemBonuses[id] or 0)+value*item.count end
  for id,value in entry.percent do cs.itemPercent[id]=(cs.itemPercent[id] or 0)+value*item.count end
 end
 Characters.refresh(p)
end
S.startingWeapons={}
-- The loadout starter enters a run at the tier the player owns it at (ProfileWeapons, written by
-- ProfileService): a Tier II Frying Pan starts the run in slot 1 at Tier II.
local function starterTier(p)
 local f=slots(p).Slot1;local start=S.startingWeapons[p]
 local id=f:GetAttribute('WeaponId')
 if not start or id=='' or id~=start[1] then return end
 f:SetAttribute('Tier',StatSchema.ownedTier(p:GetAttribute('ProfileWeapons'),id) or 1)
end
local function newState(p)
 -- A tutorial run starts with no crystals (S.tutorial.startShards).
 local s={shards=S.tutorial and S.tutorial.startShards or E.STARTING_SHARDS,level=1,xp=0,pendingLevels=0,upgradeOffers={},upgradeBonuses={},banished={},baggedShards=0,upgradeRerolls=0,upgradeToken=token(),rerolls=0,offers={},items={},ready=false,revision=1,lastRequest=-1e6,freeRerolls=0,freeUpgradeRerolls=0}
 S.states[p]=s
 for i=1,6 do local f=slots(p)['Slot'..i];f:SetAttribute('Tier',1);f:SetAttribute('FinalPurchasePrice',0);f:SetAttribute('BasePrice',0);f:SetAttribute('WavePurchased',0);f:SetAttribute('CopyId',token()) end
 starterTier(p)
 local excluded={}
 for i=1,E.OFFER_COUNT do s.offers[i]=roll(p,i,excluded) end
 return s
end
-- Rejoin (plan J item 9): a run member who disconnects mid-run on a match server leaves their build
-- here (weapons, items, level, shards, the shop) for REJOIN_SECONDS. Coming back into the same run
-- puts it back (S.attach); MatchService offers the way back from the lobby. A new run drops them.
S.REJOIN_SECONDS=600
S.stashes={} -- userId -> {runId,at,state,slots}
local function stash(p)
 local s=S.states[p]
 if not s or not S.members[p] or RS:GetAttribute('ServerRole')~='Match' then return end
 if S.wave==1 and S.phase~='Combat' then return end -- the run hasn't started: nothing to keep
 -- The live slots if they're still here, else the copy S.publish keeps: CharacterService and the
 -- combat script tear the slots down in their own PlayerRemoving, in no fixed order.
 local rows=slotRows(p) or s.slotRows;if not rows then return end
 S.stashes[p.UserId]={runId=S.runId,at=os.clock(),state=s,slots=rows}
end
-- The build a player left in this run, while it is kept (nil once it expired or the run reset).
function S.stashFor(userId)
 local st=S.stashes[userId]
 if st and (st.runId~=S.runId or os.clock()-st.at>S.REJOIN_SECONDS) then S.stashes[userId]=nil;st=nil end
 return st
end
local function restore(p)
 local st=S.stashFor(p.UserId);if not st then return false end
 S.stashes[p.UserId]=nil
 local s=st.state
 s.ready=false;s.revision+=1;s.lastRequest=-1e6
 S.states[p]=s
 local count=0
 for i=1,6 do
  local f=slots(p)['Slot'..i]
  for k,v in st.slots[i] do f:SetAttribute(k,v) end
  if (f:GetAttribute('WeaponId') or '')~='' then count+=1 end
 end
 slots(p):SetAttribute('EquippedCount',count)
 S.bonuses(p)
 return true
end
function S.attach(p)
 -- Remember the run's starting weapons so a give-up can restore them.
 local start={};for i=1,6 do start[i]=slots(p)['Slot'..i]:GetAttribute('WeaponId') or '' end
 S.startingWeapons[p]=start
 newState(p)
 if restore(p) then S.publish(p,'Welcome back! Your build is where you left it') else S.publish(p) end
 p.CharacterAdded:Connect(function() task.defer(function() local s=S.states[p];if s then s.ready=false;S.publish(p) end end) end)
 -- An Armory upgrade (or a save loading on a match server) shows on the starter right away, while
 -- the starter can still change (S.setStarter's rule); a run under way keeps its tiers.
 p:GetAttributeChangedSignal('ProfileWeapons'):Connect(function()
  if S.states[p] and Characters.states[p] and S.canSwapStarter(p) then starterTier(p);S.publish(p) end
 end)
end
-- Fresh run state for one player: starting weapons, shards, level and shop.
function S.resetPlayer(p)
 if not S.states[p] or not Characters.states[p] then return end
 local start=S.startingWeapons[p] or {}
 for i=1,6 do local f=slots(p)['Slot'..i];clearWeapon(f);f:SetAttribute('WeaponId',start[i] or '') end
 newState(p);S.bonuses(p);S.publish(p,'New run')
end
-- Whole run back to wave 1 (nobody left alive after a give-up).
-- A new loadout starter: every later run begins with it. A player standing in the lobby sees it
-- on their ring right away, and so does a match member before wave 1 (MatchService sets it as
-- they arrive); run weapons are never swapped mid-run.
function S.canSwapStarter(p)
 local beforeFirstWave=RS:GetAttribute('ServerRole')=='Match' and S.wave==1 and S.phase=='Shop'
 return p:GetAttribute('LobbyPreviewActive')==true or beforeFirstWave
end
function S.setStarter(p,id)
 if not S.states[p] or not Characters.states[p] then return end
 S.startingWeapons[p]={id,'','','','',''}
 if not S.canSwapStarter(p) then return end
 for i=1,6 do local f=slots(p)['Slot'..i];clearWeapon(f);f:SetAttribute('WeaponId',S.startingWeapons[p][i]) end
 starterTier(p)
 slots(p):SetAttribute('EquippedCount',1)
end
function S.resetRun()
 S.wave=1;S.phase='Shop';S.paused=nil
 -- A new run: everyone still here starts a new stint of it at wave 1.
 S.runId=newRunId();run:SetAttribute('RunId',S.runId)
 table.clear(S.stashes) -- builds kept for rejoining belonged to the run that just ended
 for _,m in S.members do stints+=1;m.stint=S.runId..'/'..stints;m.joined=1 end
 run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',1);run:SetAttribute('WaveEndsAt',nil);run:SetAttribute('Paused',nil);run:SetAttribute('ShopEndsAt',nil)
 -- A new run starts clean: not a test run, no admin pause, freeze or Keep N alive, and the map's
 -- own enemy mix (ADMIN_PANEL.md). Normal play already has these, so nothing fires.
 run:SetAttribute('AdminTestRun',nil);run:SetAttribute('AdminPaused',nil)
 local map=Maps.get(combat:GetAttribute('RunMap'))
 combat:SetAttribute('AdminFreeze',nil);combat:SetAttribute('TestZombieCountOverride',nil);combat:SetAttribute('EnemyRoster',map and map.roster)
 combat:SetAttribute('ZombiesEnabled',false);Shards.clear(false)
 for p in S.states do Characters.clearAdmin(p);S.resetPlayer(p) end
end
-- Solo death pauses the wave clock; revive resumes it with the same time left.
function S.pause()
 if S.phase~='Combat' or S.paused then return end
 local ends=run:GetAttribute('WaveEndsAt')
 S.paused=ends and math.max(0,ends-workspace:GetServerTimeNow()) or 0
 run:SetAttribute('WaveEndsAt',nil);run:SetAttribute('Paused',true)
end
-- An admin Pause holds the clock until adminPause(false), which clears AdminPaused first: a revive
-- during it must not restart the clock while the spawner stays paused.
function S.resume()
 -- Plan L: a paused run (RunPaused) keeps the clock held too; RogueliteMeta resumes it on unfreeze.
 if not S.paused or run:GetAttribute('AdminPaused') or combat:GetAttribute('RunPaused')==true then return end
 if S.phase=='Combat' then run:SetAttribute('WaveEndsAt',workspace:GetServerTimeNow()+S.paused) end
 S.paused=nil;run:SetAttribute('Paused',nil)
end
-- Banish (stored or bought): remove one offered stat for the rest of the run and replace
-- only that card. Validated here: shop phase, pending level-up, valid card index.
function S.canBanish(p,index)
 local s=S.states[p]
 return s~=nil and S.phase=='Shop' and s.pendingLevels>0 and type(index)=='number' and s.upgradeOffers[index]~=nil
end
function S.banish(p,index)
 if not S.canBanish(p,index) then return false end
 local s=S.states[p];local cs=Characters.states[p]
 local offer=s.upgradeOffers[index]
 s.banished[offer.id]=true
 local skip=table.clone(s.banished)
 for _,o in s.upgradeOffers do skip[o.id]=true end
 local replacement=Upgrades.roll(cs.stats,skip,s.level-s.pendingLevels+1,rng)[1]
 if replacement then replacement.token=token();replacement.new=(s.upgradeBonuses[replacement.id] or 0)==0;s.upgradeOffers[index]=replacement
 else table.remove(s.upgradeOffers,index) end
 s.upgradeToken=token();s.revision+=1
 S.publish(p,'Banished '..Upgrades.ById[offer.id].name..' for this run')
 return true
end
local function rerollOffers(p)
 local s=S.states[p];local excluded={}
 for _,o in s.offers do excluded[o.id]=true end
 for i,o in s.offers do if not o.locked or o.sold then s.offers[i]=roll(p,i,excluded) end end
end
local function rerollUpgrades(p)
 local s=S.states[p];local cs=Characters.states[p]
 s.upgradeOffers=Upgrades.roll(cs.stats,s.banished,s.level-s.pendingLevels+1,rng)
 s.upgradeToken=token()
 for _,o in s.upgradeOffers do o.token=token();o.new=(s.upgradeBonuses[o.id] or 0)==0 end
end
-- Robux reroll (validated receipt). Applies now during the shop; otherwise banks a free
-- reroll that the next Reroll uses before shards.
function S.paidReroll(p,kind)
 local s=S.states[p];if not s then return false end
 local now=S.phase=='Shop' and (kind=='Shop' or s.pendingLevels>0)
 if now and kind=='Shop' then rerollOffers(p);s.ready=false
 elseif now then rerollUpgrades(p)
 elseif kind=='Shop' then s.freeRerolls+=1 else s.freeUpgradeRerolls+=1 end
 if now then fire('onReroll',p,kind,'Bought',0) end
 s.revision+=1;reprice(p);S.publish(p,now and 'Rerolled' or 'Free reroll saved for the next shop')
 return true
end
-- The wave's normal enemy count (Keep N alive overrides it through TestZombieCountOverride).
function S.waveEnemyCount() return math.min(100,8+(S.wave-1)*3) end
-- Every wave starts at full health (Brotato rule): damage never carries between waves.
local function refillHealth()
 for p in S.states do
  local h=p.Character and p.Character:FindFirstChildOfClass('Humanoid')
  if h and h.Health>0 then h.Health=h.MaxHealth end
 end
end
local function startWave()
 refillHealth()
 -- A tutorial wave has its own count and enemies, and no clock: TutorialDirector ends it.
 local tutorialWave=S.tutorial and S.tutorial.waves and S.tutorial.waves[S.wave]
 S.phase='Combat';run:SetAttribute('Phase','Combat');run:SetAttribute('WaveEndsAt',workspace:GetServerTimeNow()+(S.tutorial and S.tutorial.waveSeconds or E.WAVE_SECONDS))
 run:SetAttribute('ShopEndsAt',nil)
 if tutorialWave then combat:SetAttribute('EnemyRoster',tutorialWave.roster) end
 combat:SetAttribute('ZombieCount',combat:GetAttribute('TestZombieCountOverride') or tutorialWave and tutorialWave.count or S.waveEnemyCount());combat:SetAttribute('ZombiesEnabled',true)
 for p in S.states do local cs=Characters.states[p];cs.blocks=1;cs.folder:SetAttribute('BlocksRemaining',cs.stats.FirstHitBlock);S.publish(p,'Wave started') end
end
local function beginWave()
 if S.phase~='Shop' then return end
 local count=0
 for p,s in S.states do if living(p) then count+=1;if not s.ready or s.pendingLevels>0 then return end end end
 if count==0 then return end
 startWave()
end
-- Shop timer (SHOP_SECONDS from the wave clear): when it runs out, anyone still choosing gets
-- their level-ups picked for them (the first card each time; a capped stat is skipped) and is
-- marked ready, so one idle player can't hold the party. Shards stay unspent.
local function autoPick(p,s)
 local cs=Characters.states[p];if not cs then return end
 for _=1,200 do
  if s.pendingLevels<=0 then break end
  if #s.upgradeOffers==0 then S.prepareUpgrades(p) end
  local offer=s.upgradeOffers[1];local schema=offer and StatSchema.ById[offer.id]
  local amount=schema and math.min(offer.amount,schema.max-cs.stats[offer.id]) or 0
  if amount>0 then s.upgradeBonuses[offer.id]=(s.upgradeBonuses[offer.id] or 0)+amount end
  s.pendingLevels-=1;s.upgradeOffers={}
  if amount>0 then S.bonuses(p) end
 end
 S.prepareUpgrades(p);S.publishProgress(p)
end
local function shopTimeUp()
 if S.phase~='Shop' or run:GetAttribute('AdminPaused') then return end
 run:SetAttribute('ShopEndsAt',nil)
 local any=false
 for p,s in S.states do
  if living(p) then
   any=true
   if s.pendingLevels>0 then autoPick(p,s) end
   s.ready=true;s.revision+=1
  end
 end
 if any then startWave() end
end
-- A group launched from a lobby pad goes straight into wave 1; the first shop comes after it.
-- Only from a fresh run (resetRun), so it can never skip a later shop.
function S.startFirstWave()
 if S.phase~='Shop' or S.wave~=1 then return false end
 startWave();return true
end
function S.stopWave()
 -- Abort a Studio test, not a wave clear: no reward, advancement or reroll.
 if not RunService:IsStudio() or S.phase~='Combat' then return false end
 S.phase='Shop';run:SetAttribute('Phase','Shop');run:SetAttribute('WaveEndsAt',nil)
 combat:SetAttribute('ZombiesEnabled',false)
 -- A stopped wave can't stay paused (solo death or admin Pause), like endWave.
 S.paused=nil;run:SetAttribute('Paused',nil);run:SetAttribute('AdminPaused',nil)
 Shards.clear(false)
 for p,s in S.states do
  s.ready=false;s.revision+=1
  S.prepareUpgrades(p)
  S.publish(p,'Wave stopped · restart this wave when ready')
 end
 return true
end
function S.finishWave()
 if S.phase~='Combat' then return false end
 -- Leftover crystals fly to the players and count as pickups (XP and shards) while it's still
 -- Combat; any that nobody alive can take are bagged as before (2026-10-03).
 if Shards.sweep then Shards.sweep() end
 Shards.clear(true)
 local won=S.tutorial~=nil and S.tutorial.waves~=nil and S.wave>=#S.tutorial.waves -- the tutorial's last wave
 local phase=won and 'Victory' or 'Shop'
 combat:SetAttribute('ZombiesEnabled',false);S.phase=phase;S.wave+=1
 run:SetAttribute('Phase',phase);run:SetAttribute('Wave',S.wave);run:SetAttribute('WaveEndsAt',nil)
 -- The tutorial's shops wait for the player (no countdown).
 run:SetAttribute('ShopEndsAt',not won and not (S.tutorial and S.tutorial.noShopTimer) and workspace:GetServerTimeNow()+E.SHOP_SECONDS or nil)
 for p,s in S.states do
  if living(p) then s.shards=math.min(E.MAX_SHARDS,s.shards+E.WAVE_REWARD_BASE+(S.wave-1)*E.WAVE_REWARD_SCALE) end
  s.rerolls=0;s.ready=false;s.revision+=1
  local excluded={}
  for _,o in s.offers do excluded[o.id]=true end
  for i,o in s.offers do if not o.locked or o.sold then s.offers[i]=roll(p,i,excluded) end end
  S.prepareUpgrades(p)
  S.publish(p,'Next shop · reroll cost reset')
 end
 refillHealth()
 fire('onWaveCleared',S.wave-1)
 return true
end
-- Admin panel run modes (ADMIN_PANEL.md "Waves"). AdminService checks the developer first.
-- Enemies turn off for one frame so the spawner and BossEncounter see the old wave end
-- (signals are deferred in this place).
local function endEnemies()
 combat:SetAttribute('ZombiesEnabled',false);Shards.clear(false)
 S.paused=nil;run:SetAttribute('Paused',nil);run:SetAttribute('AdminPaused',nil);run:SetAttribute('WaveEndsAt',nil);run:SetAttribute('ShopEndsAt',nil)
 for _,s in S.states do s.ready=false;s.revision+=1 end
 task.wait()
end
-- Sandbox: phase Practice at wave 1, no clock and no shop. Enemies stay on (weapons need them),
-- but only Keep N alive (TestZombieCountOverride) and Mobs spawns fill the arena.
function S.setPractice()
 endEnemies()
 S.phase='Practice';S.wave=1;run:SetAttribute('Phase','Practice');run:SetAttribute('Wave',1)
 combat:SetAttribute('ZombieCount',combat:GetAttribute('TestZombieCountOverride') or 0);combat:SetAttribute('ZombiesEnabled',true)
 for p in S.states do S.publish(p,'Sandbox · no waves') end
 return true
end
-- Waves from the sandbox: the normal wave-1 shop, then the normal beginWave/finishWave loop.
-- The build stays: it's the same test run.
function S.setWaves()
 if S.phase~='Practice' then return false end
 endEnemies()
 S.phase='Shop';S.wave=1;run:SetAttribute('Phase','Shop');run:SetAttribute('Wave',1)
 for p in S.states do S.prepareUpgrades(p);S.publish(p,'Waves · press Start when ready') end
 return true
end
-- Start wave n (1-20) now from any phase, skipping the shop's ready check.
function S.jumpToWave(n)
 if type(n)~='number' or n~=n or n%1~=0 or n<1 or n>20 then return false end
 endEnemies()
 S.wave=n;run:SetAttribute('Wave',n)
 startWave();return true
end
-- End this wave as if the timer ran out (wave reward, next shop). A boss can't hold it open.
function S.endWave()
 if S.phase~='Combat' then return false end
 S.paused=nil;run:SetAttribute('Paused',nil);run:SetAttribute('AdminPaused',nil)
 return S.finishWave()
end
-- Pause/Resume: the wave clock (pause/resume above) and, through AdminPaused, the spawner.
-- S.pause alone (a solo death) keeps spawning as before.
function S.adminPause(on)
 if on then
  if S.phase~='Combat' or S.paused then return false end
  S.pause();run:SetAttribute('AdminPaused',true)
 else
  if not run:GetAttribute('AdminPaused') then return false end
  run:SetAttribute('AdminPaused',nil);S.resume()
 end
 return true
end
-- Admin grants (Player tab). AdminConfig.check already validated mode and number.
function S.adminShards(p,mode,value)
 local s=S.states[p];if not s then return false,'No run state' end
 local total=mode=='Set' and value or s.shards+value
 if not E.integer(total,0,E.MAX_SHARDS) then return false,'Shards must be between 0 and '..E.MAX_SHARDS end
 s.shards=total;s.revision+=1;S.publish(p,'Shards: '..total)
 return true,'Shards: '..total
end
-- New levels arrive as earned level-ups (chosen in the shop); lowering the level drops unspent ones.
function S.adminLevel(p,mode,value)
 local s=S.states[p];if not s then return false,'No run state' end
 local level=math.clamp(mode=='Set' and value or s.level+value,1,XP.MAX_LEVEL)
 s.pendingLevels=math.max(0,s.pendingLevels+level-s.level);s.level=level;s.xp=0
 s.upgradeOffers={};s.revision+=1;S.prepareUpgrades(p);S.publish(p,'Level '..level)
 return true,'Level '..level
end
function S.adminItem(p,id)
 local s=S.states[p];local entry=Catalog.ById[id]
 if not s or not entry or entry.kind=='Weapon' then return false,'Unknown item' end
 local existing;for _,it in s.items do if it.id==id then existing=it end end
 if existing and existing.count>=entry.cap then return false,'Item copy limit reached' end
 if not existing and #s.items>=E.ITEM_CAPACITY then return false,'Item inventory full' end
 if existing then existing.count+=1 else table.insert(s.items,{id=id,count=1}) end
 s.revision+=1;S.bonuses(p);S.publish(p,entry.name..' added')
 return true,entry.name..' added'
end
function S.request(p,action,revision,arg,extra)
 local s=S.states[p];local cs=Characters.states[p]
 if not s or not cs or not living(p) or type(action)~='string' then return false end
 if os.clock()-s.lastRequest<.12 then return false end;s.lastRequest=os.clock()
 local function fail(msg) S.publish(p,msg);return false end
 if revision~=s.revision then return fail('Shop changed. Please try again.') end
 if action=='Shards' then
  if not RunService:IsStudio() or not E.DEBUG_CURRENCY_ENABLED then return fail('Developer control unavailable') end
  if not E.integer(extra,-E.MAX_SHARDS,E.MAX_SHARDS) or (arg~='Set' and arg~='Add') then return fail('Enter a whole shards amount') end
  local value=arg=='Set' and extra or s.shards+extra
  if not E.integer(value,0,E.MAX_SHARDS) then return fail('Shards must be between 0 and '..E.MAX_SHARDS) end
  s.shards=value
 elseif S.phase~='Shop' then return fail('Shop actions are available between waves')
 elseif action=='Upgrade' or action=='UpgradeReroll'  or action=='UpgradeSkip' then
  if s.pendingLevels<=0 then return fail('No earned upgrades available') end
  if extra~=s.upgradeToken then return fail('Upgrade offers changed') end
  if action=='UpgradeSkip' then
   if #Upgrades.pool(cs.stats,s.banished)>0 then return fail('Choose an available upgrade') end
   s.pendingLevels-=1;s.upgradeOffers={};S.prepareUpgrades(p)
  elseif action=='UpgradeReroll' then
   -- Level-up rerolls are Robux (or saved) only; shards cannot buy them.
   if s.freeUpgradeRerolls<=0 then return fail('Level-up rerolls use REROLL') end
   s.freeUpgradeRerolls-=1
   rerollUpgrades(p);fire('onReroll',p,'Upgrade','Free',0)
  else
   if not E.integer(arg,1,Upgrades.OFFER_COUNT) then return fail('Invalid upgrade') end
   local offer=s.upgradeOffers[arg];if not offer then return fail('Upgrade unavailable') end
    local definition=Upgrades.ById[offer.id]
    if not definition then return fail('Invalid stat upgrade') end
    local amount=math.min(offer.amount,StatSchema.ById[offer.id].max-cs.stats[offer.id])
    if amount<=0 then return fail('This stat is already capped; choose another offer or reroll') end
    s.upgradeBonuses[offer.id]=(s.upgradeBonuses[offer.id] or 0)+amount
    fire('onLevelPick',p,offer.id)
    s.pendingLevels-=1;s.upgradeOffers={}
    S.bonuses(p);S.prepareUpgrades(p)
  end
 elseif action=='Buy' or action=='Lock' then
  if not E.integer(arg,1,E.OFFER_COUNT) then return fail('Invalid offer') end
  local o=s.offers[arg];if not o or o.token~=extra or o.sold then return fail('Offer is no longer available') end
  if action=='Lock' then o.locked=not o.locked
  else
   local entry=Catalog.ById[o.id]
   if s.shards<o.price then return fail('Not enough shards') end
   if entry.kind=='Weapon' then
    if not combat.WeaponTemplates:FindFirstChild(entry.weaponId) then return fail('Weapon asset unavailable') end
    local free
    for i=1,6 do if slots(p)['Slot'..i]:GetAttribute('WeaponId')=='' then free=slots(p)['Slot'..i];break end end
    local merge
    if not free and entry.tier<4 then
     for i=1,6 do local f=slots(p)['Slot'..i]
      if f:GetAttribute('WeaponId')==entry.weaponId and f:GetAttribute('Tier')==entry.tier then merge=f;break end
     end
    end
    if not free and not merge then return fail('Six weapons equipped. Combine a matching pair or recycle one first.') end
    if merge then upgradeWeapon(merge,o.price) else
    free:SetAttribute('BasePrice',entry.basePrice);free:SetAttribute('FinalPurchasePrice',o.price);free:SetAttribute('PurchasePrice',o.price)
    free:SetAttribute('Tier',entry.tier);free:SetAttribute('WavePurchased',S.wave);free:SetAttribute('CopyId',token());free:SetAttribute('WeaponId',entry.weaponId)
    end
   else
    local existing
    for _,it in s.items do if it.id==entry.id then existing=it end end
    if existing and existing.count>=entry.cap then return fail('Item copy limit reached') end
    if not existing and #s.items>=E.ITEM_CAPACITY then return fail('Item inventory full') end
    if existing then existing.count+=1 else table.insert(s.items,{id=entry.id,count=1}) end
   end
   s.shards-=o.price;o.sold=true;o.locked=false
   fire('onBuy',p,o.id,o.price)
   S.bonuses(p)
   local soldOut=true
   for _,offerNow in s.offers do if not offerNow.sold then soldOut=false;break end end
   if soldOut then
    local excluded={}
    for _,offerNow in s.offers do excluded[offerNow.id]=true end
    for i=1,E.OFFER_COUNT do s.offers[i]=roll(p,i,excluded) end
   end
  end
 elseif action=='Reroll' then
  local available=false;for _,o in s.offers do if not o.locked or o.sold then available=true end end
  if not available then return fail('Unlock an offer before rerolling') end
  local how,cost='Free',0
  if s.freeRerolls>0 then s.freeRerolls-=1
  else
   local price=E.reroll(S.wave,s.rerolls);if s.shards<price then return fail('Not enough shards to reroll') end
   s.shards-=price;s.rerolls+=1;how,cost='Shards',price
  end
  rerollOffers(p);fire('onReroll',p,'Shop',how,cost)
 elseif action=='Combine' then
  if not E.integer(arg,1,6) then return fail('Invalid weapon slot') end
  local f=slots(p)['Slot'..arg];local id=f:GetAttribute('WeaponId');local tier=f:GetAttribute('Tier') or 1
  if id=='' or f:GetAttribute('CopyId')~=extra then return fail('Weapon changed; select it again') end
  if tier>=4 then return fail('Tier IV is the highest tier') end
  local partner
  for i=1,6 do local other=slots(p)['Slot'..i]
   if i~=arg and other:GetAttribute('WeaponId')==id and other:GetAttribute('Tier')==tier then partner=other;break end
  end
  if not partner then return fail('Combine needs two identical weapons of the same tier') end
  upgradeWeapon(f,partner:GetAttribute('FinalPurchasePrice') or 0)
  clearWeapon(partner);S.bonuses(p)
 elseif action=='Sell' then
  if not E.integer(arg,1,6) then return fail('Invalid weapon slot') end
  local f=slots(p)['Slot'..arg]
  if f:GetAttribute('WeaponId')=='' or f:GetAttribute('CopyId')~=extra then return fail('Weapon changed; select it again') end
  s.shards=math.min(E.MAX_SHARDS,s.shards+sellValue(p,f))
  clearWeapon(f)
 elseif action=='Start' then
  if s.pendingLevels>0 then return fail('Choose your earned level-up upgrades first') end
  s.ready=true
 else return fail('Unknown shop action') end
 if action~='Start' then s.ready=false end
 local count=0;for i=1,6 do if slots(p)['Slot'..i]:GetAttribute('WeaponId')~='' then count+=1 end end;slots(p):SetAttribute('EquippedCount',count)
 s.revision+=1;reprice(p);S.publish(p,action=='Start' and 'Ready · waiting for other living players' or '')
 if action=='Start' then beginWave() end
 return true
end
remote.OnServerEvent:Connect(S.request)
Characters.onStatsChanged=function(p) if S.states[p] then reprice(p);S.states[p].revision+=1;S.publish(p) end end
-- Collected units consume stored units one-for-one. Leftovers grant nothing until picked up.
function S.creditShards(p,amount,pickedUp)
 local s=S.states[p]
 if not s or not E.integer(amount,1,E.MAX_SHARDS) or (pickedUp and not living(p)) then return false end
 if not pickedUp then
  s.baggedShards=math.min(E.MAX_SHARDS,s.baggedShards+amount)
 else
  if S.phase~='Combat' then return false end
  local bonus=math.min(s.baggedShards,amount)
  s.baggedShards-=bonus
  local total=amount+bonus
  s.shards=math.min(E.MAX_SHARDS,s.shards+total)
  local level,xp,gained=XP.add(s.level,s.xp,math.min(1000000,total*XP.XP_PER_SHARD))
  s.level=level;s.xp=xp;s.pendingLevels+=gained
  fire('onShards',p,total)
  if gained>0 then fire('onLevelUp',p,gained) end
 end
 S.publishProgress(p);return true
end
Shards.configure(Characters,function() return S.phase=='Combat' end,S.creditShards)
Hearts.configure(Characters)
require(combat.ZombieDeath).onDeath=function(npc,position)
 Shards.spawn(npc,position)
 Hearts.roll(npc,position)
end
-- The last player leaving resets the run, so no wave, phase or test-run flag outlives an empty server.
Players.PlayerRemoving:Connect(function(p) stash(p);S.leave(p);S.states[p]=nil;S.startingWeapons[p]=nil;if next(S.states)==nil then S.resetRun() end;task.defer(beginWave) end)
-- Any boss (IsBoss: the Hammer boss today, later map bosses; scheduled or admin-spawned) holds
-- the wave open until it is gone, then a short grace lets players sweep up its crystal shower.
-- Only the admin panel's End wave / Jump to wave skip this.
local BOSS_LOOT_GRACE=5
local bossSeenAt=-math.huge
local function bossHolding(now)
 local mobs=workspace:FindFirstChild('RogueliteEnemies')
 if mobs then for _,npc in mobs:GetChildren() do if npc:GetAttribute('IsBoss') or npc:GetAttribute('IsHammerBoss') then bossSeenAt=now;return true end end end
 return run:GetAttribute('BossAlive')==true or now-bossSeenAt<BOSS_LOOT_GRACE
end
local elapsed=0
RunService.Heartbeat:Connect(function(dt)
 elapsed+=dt;if elapsed<.2 then return end;elapsed=0
 local now=workspace:GetServerTimeNow()
 -- Membership follows where players are: alive in the arena joins, back in the lobby leaves.
 -- Downed players stay members (they are still in the run). Lobby servers have no run.
 if RS:GetAttribute('ServerRole')~='Lobby' then
  for p in S.states do
   local inLobby=p:GetAttribute('LobbyPreviewActive')==true
   if S.members[p] then if inLobby then S.leave(p) end
   elseif not inLobby and alive(p) then S.join(p) end
  end
 end
 if S.phase=='Shop' then beginWave() end
 local shopEnds=run:GetAttribute('ShopEndsAt')
 if S.phase=='Shop' and type(shopEnds)=='number' and now>=shopEnds then shopTimeUp() end
 local holding=S.phase=='Combat' and bossHolding(now)
 if run:GetAttribute('BossHolding')~=holding then run:SetAttribute('BossHolding',holding) end
 if S.phase=='Combat' and not holding and now>=(run:GetAttribute('WaveEndsAt') or math.huge) then S.finishWave() end
end)
return S
