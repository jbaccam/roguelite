-- Saved account progression: emeralds, classes, weapon tiers/duplicates, chests, skills,
-- pity, map records and processed purchase receipts. Server-only authority.
-- Emeralds are the only currency: earned from runs/daily/codes and bought with Robux.
-- `bought` counts Robux emeralds not yet spent; where paid random items are restricted,
-- only the earned part (emeralds - bought) can open chests.
-- Studio always uses an in-memory profile: practice and simulated purchases never touch
-- production saves, even when an old place still carries EnableStudioDataStores=true.
-- Saves hold a session lock (ProfileLock): only the server that loaded a profile writes it.
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
local Pets=require(combat:WaitForChild('PetConfig')) -- sandboxed data
local Eggs=require(combat:WaitForChild('EggConfig')) -- pet eggs; unsandboxed data like ChestConfig
local Admin=require(combat:WaitForChild('AdminConfig')) -- sandboxed; this module is unsandboxed
local Journal=require(combat:WaitForChild('WeaponJournal'))
local Lock=require(game:GetService('ServerScriptService'):WaitForChild('ProfileLock')) -- unsandboxed, like this module
-- Daily quests, streak and achievements (plans/2026-10-01-H-store-and-quests.md). Optional and
-- protected: until QuestService is installed, or if it ever errors, quests do nothing and payouts,
-- chest opens and upgrades carry on. quest('event',...) returns QuestService.event's results or nil.
local questModule=game:GetService('ServerScriptService'):FindFirstChild('QuestService')
local questsOk,Quests=pcall(function() return questModule and require(questModule) end)
if not questsOk then warn('ProfileService: QuestService failed to load:',Quests);Quests=nil end
local function quest(fn,...)
 if not Quests then return nil end
 local r=table.pack(pcall(Quests[fn],...))
 if not r[1] then warn('ProfileService: quest '..fn..' failed:',r[2]);return nil end
 return table.unpack(r,2,r.n)
end
-- Redeemable codes (server-only so they cannot be read from the client). One use per account.
local CODES={
 RELEASE={emeralds=300},
 CHESTS={chests={Gold=1}},
 REROLL={rerolls=3},
}
local P={profiles={},loaded={}}
local STORE_NAME='RogueliteProfile_v1'
local useStore=not RunService:IsStudio()
local store=useStore and DataStores:GetDataStore(STORE_NAME)
-- This server's lock id. Studio has no JobId.
local JOB=game.JobId~='' and game.JobId or Http:GenerateGUID(false)
local function key(player) return 'u_'..player.UserId end
-- TutorialConfig, looked up when needed: nil until it is in the place (then the tutorial is off).
local function tutorialConfig()
 local module=combat:FindFirstChild('TutorialConfig')
 local ok,T=pcall(function() return module and require(module) end)
 return ok and T or nil
end
local SIGNATURE={Brawler='06',Gunner='00',Chef='01',Juggler='17',Handyman='24',Mage='30'} -- a copy of CharacterStats.Signature
-- Classes that were renamed: an old save, receipt or grant naming the left one means the right one.
-- Thrower became Chef 1:1 (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md).
local RENAMED={Thrower='Chef'}
local MAX_RECEIPTS=200

local function fresh()
 local d={version=1,emeralds=0,bought=0,classes={Brawler=true,Gunner=true,Mage=true},weapons={},pity={},picks={},chests={},
  receipts={},receiptOrder={},bestWaves={},mapWins={},starterPack=false,vip=false,
  rerolls=0,banishes=0,quickOpen=false,codes={},daily={day=0,bought={}},vipClaimDay=0,skills={},
  armor={},wearing={}, -- armor: 'DragonScale.Helmet' -> {tier,have}; wearing: slot -> set id
  pets={},pet=nil, -- pets: PetConfig id -> {tier,have}; pet: the equipped pet id (nil = none)
  loadout={}, -- the class and starter last picked in a lobby: {class=,weapon=} (P.setLoadout); {} = none yet
  bundles={}, -- one-time Godly bundles bought: product key -> true
  godlyPick='', -- the Godly weapon name chosen for a pending Godly Starter purchase
  tutorial={step='Run'}, -- first-join tutorial (TutorialConfig.Steps); old saves count as done (P.load)
  freeChestDay=0, -- Money.day() of the last free daily chest (the Wooden Chest)
  journal=Journal.clean(nil), -- lifetime weapon damage/kills and passive purchases, bounded to known IDs
  quests={}} -- daily quests, streak, lifetime stats, achievements (QuestService.state fills it in)
 for class in d.classes do d.weapons[SIGNATURE[class]]={tier=1,have=0} end
 return d
end
local function csv(t,fmt) local out={};for k,v in t do table.insert(out,fmt(k,v)) end;table.sort(out);return table.concat(out,',') end
local journalDirty={}
local questDirty={} -- player -> true: quest progress changed since ProfileQuests was last written

function P.publish(player)
 local d=P.profiles[player];if not d then return end
 questDirty[player]=nil -- written below, with everything else
 player:SetAttribute('ProfileGems',d.emeralds)
 player:SetAttribute('ProfileGemsEarned',d.emeralds-d.bought) -- what restricted regions may spend on chests
 player:SetAttribute('ProfileClasses',csv(d.classes,function(k) return k end))
 player:SetAttribute('ProfileWeapons',csv(d.weapons,function(k,v) return k..':'..v.tier..':'..v.have end))
 player:SetAttribute('ProfileArmor',csv(d.armor,function(k,v) return k..':'..v.tier..':'..v.have end))
 -- ArmorService puts the worn pieces on the character from this attribute.
 player:SetAttribute('ProfileWearing',csv(d.wearing,function(k,v) return k..':'..v end))
 -- Pets: CharacterService (stat bonus) and PetService (abilities, the follower) read these.
 player:SetAttribute('ProfilePets',csv(d.pets,function(k,v) return k..':'..v.tier..':'..v.have end))
 player:SetAttribute('ProfilePet',d.pet or '')
 player:SetAttribute('ProfileFreeChestDay',d.freeChestDay) -- = Money.day(): today's free chest is claimed
 player:SetAttribute('ProfilePity',csv(d.pity,function(k,v) return k..':'..v end))
 player:SetAttribute('ProfilePicks',csv(d.picks,function(k,v) return k..':'..v end))
 player:SetAttribute('ProfileChests',csv(d.chests,function(k,v) return k..':'..v end))
 player:SetAttribute('ProfileEggs',d.eggs or 0) -- unhatched pet eggs (EggConfig)
 player:SetAttribute('ProfileBestWaves',csv(d.bestWaves,function(k,v) return k..':'..v end))
 player:SetAttribute('ProfileMapWins',csv(d.mapWins,function(k) return k end))
 player:SetAttribute('ProfileStarterPack',d.starterPack);player:SetAttribute('ProfileVIP',d.vip)
 player:SetAttribute('ProfileBundles',csv(d.bundles,function(k) return k end))
 player:SetAttribute('ProfileRerolls',d.rerolls);player:SetAttribute('ProfileBanishes',d.banishes)
 player:SetAttribute('ProfileQuickOpen',d.quickOpen)
 player:SetAttribute('ProfileTutorial',type(d.tutorial)=='table' and d.tutorial.step or 'Done') -- TutorialDirector, TutorialGuide
 -- CharacterService reads this server-set attribute to apply the permanent skill bonuses.
 player:SetAttribute('ProfileSkills',Skills.serialize(d.skills))
 player:SetAttribute('ProfileDaily',Http:JSONEncode(P.dailyView(player)))
 player:SetAttribute('ProfileQuests',Http:JSONEncode(P.questView(player)))
 player:SetAttribute('ProfileJournal',Http:JSONEncode(Journal.view(d.journal)));journalDirty[player]=nil
 player:SetAttribute('ProfileLoaded',true)
end

-- Settings (launch audit U1): HUD size, screen shake, damage numbers, music and SFX volume, saved
-- with the profile so they follow the player lobby -> match -> lobby. They're set once at load as
-- the Setting_* attributes the client already reads (never by later publishes, which would undo a
-- change still on its way here). P.saveSettings keeps what the client sends, checked and clamped.
local SETTINGS={VisualQuality='quality',HudScale='scale',ScreenShake='bool',DamageNumbers='bool',MusicVolume='volume',SfxVolume='volume'}
local function cleanSetting(kind,v)
 if kind=='quality' then return (v=='Auto' or v=='Low' or v=='Full') and v or nil end
 if kind=='bool' then if type(v)=='boolean' then return v end;return nil end -- (not `and v or nil`: false must survive)
 if type(v)~='number' or v~=v then return nil end
 if kind=='volume' then return math.round(math.clamp(v,0,1)*20)/20 end -- the slider's 5% steps
 return math.clamp(v,.85,1.15) -- HUD size: Small .85, Normal 1, Large 1.15
end
function P.saveSettings(player,t)
 local d=P.profiles[player];if not d or type(t)~='table' then return false,'Profile loading' end
 if type(d.settings)~='table' then d.settings={} end
 for name,kind in SETTINGS do local v=cleanSetting(kind,t[name]);if v~=nil then d.settings[name]=v end end
 return true,'' -- saved by the autosave, a hand-off or leaving, like everything else
end
-- The class and starter weapon last picked in a lobby (RogueliteLobbyPreview saves them once
-- RunSetupRules.validLoadout accepts them), so the next lobby, after a run or a rejoin, starts
-- with them instead of Brawler and its default starter (user, 2026-10-03). RunClass/RunWeapon only
-- live on one server. Saved by the autosave, a hand-off or leaving, like the settings.
-- The same rule as validLoadout (2026-10-09): an owned weapon whose starter class is this class,
-- or an owned Godly with any class. Example: Brawler + Baseball Bat yes, Brawler + Frying Pan no.
function P.setLoadout(player,class,weapon)
 local d=P.profiles[player]
 if not d or not P.loaded[player] then return false,'Your save is still loading' end
 local w=type(weapon)=='string' and Weapons.ById[weapon]
 if type(class)~='string' or not d.classes[class] then return false,'Class locked' end
 if not w or not d.weapons[weapon] then return false,'Weapon not owned' end
 if not w.godly and w.class~=class then return false,'Choose a weapon for your class' end
 d.loadout={class=class,weapon=weapon}
 return true
end
function P.loadout(player)
 local d=P.profiles[player];local l=d and d.loadout
 if type(l)=='table' and type(l.class)=='string' and type(l.weapon)=='string' then return l.class,l.weapon end
 return nil
end
local function applySettings(player,d)
 if type(d.settings)~='table' then return end
 for name,kind in SETTINGS do local v=cleanSetting(kind,d.settings[name]);if v~=nil then player:SetAttribute('Setting_'..name,v) end end
end
-- Saves have no version number: every load runs these fix-ups, in place, and returns data. Each
-- one changes an old save once and leaves a fixed one alone (running it twice = once). Tables
-- only, no Instances or attributes, so ProfileMigrationTests runs it on old-save fixtures.
function P.migrate(data)
 local base=fresh();for k,v in base do if data[k]==nil then data[k]=v end end
 -- Chest tiers replaced class chests and the Royal Chest (2026-09-28): convert unopened ones,
 -- and the old every-10th-chest picks became the Legendary pity counter.
 local chests={}
 for kind,n in data.chests do local k=Chests.Legacy[kind] or kind;if Chests.ById[k] then chests[k]=(chests[k] or 0)+n end end
 data.chests=chests
 if data.pity.Legendary==nil then data.pity={Legendary=0} end
 if data.pity.Godly==nil then data.pity.Godly=0 end -- Godly pity (2026-09-28); old saves start at 0
 data.picks={}
 for id in data.pets do if not Pets.valid(id) then data.pets[id]=nil end end
 if data.pet~=nil and not data.pets[data.pet] then data.pet=nil end
 -- Keys were dropped: old saves convert them to earned emeralds once.
 if type(data.keys)=='number' then data.emeralds+=math.max(0,data.keys)*Money.EmeraldsPerOldKey;data.keys=nil end
 -- Renamed classes (2026-10-09): an owned Thrower is an owned Chef, a saved Thrower pick is a Chef
 -- pick, and a map won as a Thrower counts as won as a Chef. Claimed unlocks stay claimed (Wave
 -- Rider's reward is now Chef).
 for old,new in RENAMED do
  if data.classes[old]~=nil then if data.classes[old] then data.classes[new]=true end;data.classes[old]=nil end
  if type(data.loadout)=='table' and data.loadout.class==old then data.loadout.class=new end
  local wins=type(data.quests)=='table' and type(data.quests.classWins)=='table' and data.quests.classWins
  if wins and wins[old]~=nil then if wins[old]==true then wins[new]=true end;wins[old]=nil end
 end
 -- One starter class per weapon (2026-10-09): a saved starter that no longer fits its class goes
 -- back to that class's default. Example: Brawler + Frying Pan (Chef's now) -> Brawler + Baseball
 -- Bat (2026-10-10; it was the Gloves for a day). A saved Brawler + Boxing Gloves still fits (they
 -- are a Brawler weapon) and stays. An owned Godly still fits any class. A pick for a class that
 -- isn't owned is dropped.
 local l=data.loadout
 if type(l)~='table' or (l.class~=nil and not (type(l.class)=='string' and SIGNATURE[l.class] and data.classes[l.class])) then data.loadout={}
 elseif l.class~=nil then
  local w=type(l.weapon)=='string' and Weapons.ById[l.weapon]
  if not (w and data.weapons[l.weapon] and (w.godly or w.class==l.class)) then l.weapon=SIGNATURE[l.class] end
 end
 -- Every owned class owns its starting weapon. Juggler's changed from Boxing Gloves to Rubber Duck
 -- (2026-10-03), so Juggler owners get the duck; on 2026-10-09 Brawler's became Boxing Gloves and
 -- Chef's the Frying Pan; on 2026-10-10 Brawler's became the Baseball Bat, so Brawler owners get the
 -- Bat. Nothing owned is ever taken away: no weapon, copy or tier.
 for class in data.classes do local id=SIGNATURE[class];if id and not data.weapons[id] then data.weapons[id]={tier=1,have=0} end end
 data.journal=Journal.clean(data.journal)
 return data
end
function P.load(player)
 local data
 if store then
  -- Waits (up to ProfileLock.WAIT) while another server still holds this save, e.g. its
  -- leaving save after a quick rejoin, then takes over as if that server crashed. A DataStore
  -- outage is retried for about a minute (ProfileLock.ERROR_SECONDS). ProfileLoadState tells the
  -- player (SaveStatus): 'loading' shows "Loading your save..." if it takes a moment.
  local reason
  player:SetAttribute('ProfileLoadState','loading')
  data,reason=Lock.claim(store,key(player),JOB,{fresh=fresh,stillWanted=function() return player.Parent==Players end})
  if reason=='takeover' then warn('ProfileService: took over another server\'s session lock',player.UserId) end
  if not data then
   -- Never play on a blank profile or save over unknown data: say so, then send them to rejoin.
   if reason=='error' and player.Parent==Players then
    player:SetAttribute('ProfileLoadFailed',true);player:SetAttribute('ProfileLoadState','failed')
    task.delay(4,function()
     if player.Parent==Players and not P.profiles[player] then player:Kick("We couldn't load your save. Your progress is safe: please rejoin in a minute.") end
    end)
   end
   return
  end
  player:SetAttribute('ProfileLoadState',nil)
  -- Left while loading: hand the lock straight back and keep nothing, so no later autosave can
  -- write this copy over the newer save of the server they moved to.
  if player.Parent~=Players then Lock.write(store,key(player),JOB,data,true);return end
 else data=fresh() end
 -- Tutorial: a save from before it existed has no `tutorial` and counts as done. Studio profiles
 -- (in memory) play it only with Workspace.StudioTutorial=true, so normal Studio play skips it.
 if type(data.tutorial)~='table' or (not store and workspace:GetAttribute('StudioTutorial')~=true) then data.tutorial={step='Done'} end
 -- Armor has no chests yet: Studio test profiles (in memory, never saved, always fresh() here)
 -- own the sample sets.
 if not store then
  for _,setId in Armor.StudioGrant do
   for _,slot in Armor.Slots do local id=Armor.pieceId(setId,slot);data.armor[id]=data.armor[id] or {tier=1,have=0} end
  end
  -- No Pet Chest yet either: Studio test profiles own every pet at Tier I.
  for _,id in Pets.StudioGrant do data.pets[id]=data.pets[id] or {tier=1,have=0} end
 end
 P.migrate(data)
 P.profiles[player]=data;P.loaded[player]=true
 applySettings(player,data) -- before ProfileLoaded, so music never starts at the wrong volume
 P.publish(player)
end
-- Saves under this server's lock and returns true once the write is durable (Studio's in-memory
-- profile counts as saved). release=true clears the lock (leaving). One write per profile at a
-- time: receipts, autosave and leaving can ask together.
local saving={}
function P.save(player,release)
 local d=P.profiles[player];if not d or not P.loaded[player] then return false end
 if not store then return true end
 while saving[player] do task.wait() end
 if not P.loaded[player] then return false end -- the lock was lost while waiting
 saving[player]=true
 local ok,lost,err=Lock.write(store,key(player),JOB,d,release)
 saving[player]=nil
 if lost then
  -- Another server owns this save now. Never write this out-of-date copy again.
  P.loaded[player]=nil
  warn('ProfileService: session lock lost, stopped saving',player.UserId)
  if player.Parent==Players then player:Kick('Your progress was opened on another server. Please rejoin.') end
 elseif not ok then warn('ProfileService: save failed',player.UserId,err) end
 return ok
end
function P.get(player) return P.profiles[player] end
-- Teleporting to another server: the last save releases the lock, and this server drops the
-- profile so nothing here can change or save it again (receipts wait for the next server).
-- Returns false if the save failed; the player should not be teleported then.
function P.handOff(player)
 if not P.save(player,true) then return false end
 P.profiles[player]=nil;P.loaded[player]=nil;player:SetAttribute('ProfileLoaded',false)
 return true
end
-- The teleport failed: load the save again (it was just released, so this is immediate).
function P.reclaim(player)
 if player.Parent==Players and not P.profiles[player] then P.load(player) end
 return P.profiles[player]~=nil
end
-- WeaponCatalog id for a weapon name ('Vampire Blade' -> its id), nil while it isn't in the game.
function P.weaponIdByName(name)
 for id,w in Weapons.ById do if w.name==name then return id end end
end

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
 -- A class and its starting weapon. One still named Thrower (a server on older code) gives Chef.
 local class=g.class and (RENAMED[g.class] or g.class)
 if class then d.classes[class]=true;if SIGNATURE[class] and not d.weapons[SIGNATURE[class]] then d.weapons[SIGNATURE[class]]={tier=1,have=0} end end
 for kind,n in g.chests or {} do kind=Chests.Legacy[kind] or kind;if Chests.ById[kind] then d.chests[kind]=(d.chests[kind] or 0)+n end end
 if g.starterPack then d.starterPack=true end
 if g.vip then d.vip=true end
 if g.quickOpen then d.quickOpen=true end
 d.rerolls+=g.rerolls or 0;d.banishes+=g.banishes or 0
 -- Godly bundles: one copy of the weapon and of every piece of the armor set.
 if g.weapon then P.addCopies(d,g.weapon,1) end
 if g.armorSet then for _,slot in Armor.Slots do P.addCopies(d,Armor.pieceId(g.armorSet,slot),1) end end
 if g.bundle then d.bundles[g.bundle]=true end
 -- Arsenal bundle: +N toward the upgrade bar of every class's signature weapon.
 if g.signatureUpgrades then
  for _,id in SIGNATURE do
   for _=1,g.signatureUpgrades do P.addDrop(d,id) end
  end
 end
 P.publish(player);return true
end

-- Copies of one item (a weapon, an armor piece like 'Iron.Helmet', or a pet like 'Fox'): the first copy unlocks it
-- at Tier I; the rest fill the upgrade bar; past Tier IV each copy turns into (earned) emeralds
-- by rarity.
function P.addCopies(d,id,count)
 local book=Chests.isArmor(id) and d.armor or Pets.valid(id) and d.pets or d.weapons
 local rec=book[id];local new=false
 if not rec then rec={tier=1,have=0};book[id]=rec;new=true;count-=1 end
 local emeralds=0
 if rec.tier>=4 then emeralds=count*Chests.overflow(id);d.emeralds+=emeralds
 else rec.have+=count end
 return {id=id,new=new,tier=rec.tier,have=rec.have,emeralds=emeralds,overflow=emeralds>0}
end
function P.addDrop(d,id) return P.addCopies(d,id,1) end

-- Wear the owned piece of `setId` in `slot`, or take it off (setId nil). slot 'All' does every
-- slot: all owned pieces of the set, or takes everything off.
function P.wear(player,slot,setId)
 if player:GetAttribute('LobbyLockedIn')==true then return false,'Unready before changing your armor' end
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
-- Equip an owned pet (PetConfig id), or put the pet away (id nil). One pet slot.
function P.equipPet(player,id)
 if player:GetAttribute('LobbyLockedIn')==true then return false,'Unready before changing your pet' end
 local d=P.profiles[player];if not d then return false,'Profile still loading' end
 if id==nil then
  if d.pet==nil then return false,'No pet equipped' end
  d.pet=nil;P.publish(player);return true,'Pet put away'
 end
 if not Pets.valid(id) then return false,'Unknown pet' end
 if not d.pets[id] then return false,"You don't own that pet yet" end
 if d.pet==id then return false,'Already equipped' end
 d.pet=id;P.publish(player)
 return true,Pets.ById[id].name..' equipped'
end

local rng=Random.new()
local RANK={Common=1,Rare=2,Epic=3,Legendary=4,Godly=5}
-- Buy chests into the inventory. Where paid random items are restricted, only emeralds earned
-- in play can pay for chests.
function P.buyChest(player,kind,count,restricted)
 local d=P.profiles[player];local chest=Chests.ById[kind]
 if not d or not chest then return false,'Unknown chest' end
 -- The free daily chest: one per day, never sold (count is ignored).
 if chest.daily then
  if d.freeChestDay==Money.day() then
   local s=Money.secondsToReset()
   return false,string.format('Next free %s in %dh %dm',chest.name,s//3600,(s%3600)//60)
  end
  d.freeChestDay=Money.day();d.chests[kind]=(d.chests[kind] or 0)+1
  P.publish(player)
  return true,'Free '..chest.name..' claimed'
 end
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
-- by item (weapon or armor piece): {id, count, rarity, new, tier, have, emeralds}, rarest first.
function P.openChest(player,kind,count)
 local d=P.profiles[player];local chest=Chests.ById[kind]
 if not d or not chest then return false,'Unknown chest' end
 if not Chests.validAmount(count) then return false,'Invalid amount' end
 -- Opening 10 or 100 at once is the Quick Open pass (VIP includes it); everyone else opens one.
 if count>1 and not (d.quickOpen or d.vip) then return false,'Get Quick Open to open 10 at once' end
 local n=math.min(count,d.chests[kind] or 0)
 if n<=0 then return false,'No '..chest.name..' to open' end
 d.chests[kind]-=n;if d.chests[kind]<=0 then d.chests[kind]=nil end
 local tally={}
 -- The tutorial's first Silver Chest (P.tutorialReward) holds its seeded copies instead of a roll.
 local seed
 if type(d.tutorial)=='table' and d.tutorial.seed then
  local T=tutorialConfig()
  if T and kind==T.SeedChest then d.tutorial.seed=nil;seed=T.SeedCopies end
 end
 for i=1,n do
  if i==1 and seed then for id,c in seed do tally[id]=(tally[id] or 0)+c end
  else Chests.fill(kind,Chests.open(kind,rng,d.pity),rng,tally) end -- rolls with both pity counters and updates them
 end
 quest('event',d,Money.day(),player.UserId,'chests',n)
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
-- First-join tutorial (plans/2026-10-03-tutorial-design.md; numbers in TutorialConfig). Its run
-- pays once, when the boss wave is cleared: 3 Silver Chests and 100 emeralds. The next Silver
-- Chest opened is 2 copies of the tutorial weapon (Baseball Bat since 2026-10-10) and an Iron
-- helmet instead of a roll (openChest), so the lobby steps can upgrade it and equip the helmet.
-- The lobby steps then only move forward: Chests -> Armory -> Equip -> Offer -> Play -> Done
-- (TutorialConfig.canStep).
function P.tutorialReward(player)
 local d=P.profiles[player];local T=tutorialConfig()
 if not d or not T or type(d.tutorial)~='table' or d.tutorial.rewarded then return false end
 d.tutorial.rewarded=true;d.tutorial.seed=true;d.tutorial.step=T.Steps[2]
 d.emeralds+=T.Reward.emeralds or 0
 for kind,n in T.Reward.chests or {} do if Chests.ById[kind] then d.chests[kind]=(d.chests[kind] or 0)+n end end
 P.publish(player)
 return true
end
function P.tutorialStep(player,step)
 local d=P.profiles[player];local T=tutorialConfig()
 if not d or not T or type(d.tutorial)~='table' then return false,'Profile loading' end
 if not T.canStep(d.tutorial.step,step) then return false,'' end
 d.tutorial.step=step;P.publish(player)
 return true,''
end
-- Studio only (the admin panel's Tutorial buttons, through TutorialDirector), and only on an
-- in-memory profile: set tutorial progress directly. 'Run' starts over with the reward unpaid,
-- 'Chests' pays the reward now (the lobby part), anything else just sets the step ('Done').
function P.tutorialAdmin(player,step)
 local d=P.profiles[player];local T=tutorialConfig()
 if store or not RunService:IsStudio() or not d or not T or not T.stepIndex(step) then return false end
 if step=='Run' or step=='Chests' then d.tutorial={step='Run'} else d.tutorial.step=step end
 if step=='Chests' then return P.tutorialReward(player) end
 P.publish(player)
 return true
end
-- Pet eggs (EggConfig, the egg merchant): bought into the inventory, then hatched. Like chests,
-- where paid random items are restricted only emeralds earned in play can buy them.
function P.buyEgg(player,count,restricted)
 local d=P.profiles[player]
 if not d then return false,'Profile still loading' end
 if not Eggs.validAmount(count) then return false,'Invalid amount' end
 local price=Eggs.price(count)
 if not canSpend(d,price,restricted) then
  if restricted and d.emeralds>=price then return false,'Only emeralds earned in runs can buy eggs in your region' end
  return false,'Need '..(price-(restricted and d.emeralds-d.bought or d.emeralds))..' more emeralds'
 end
 spend(d,price,restricted)
 d.eggs=(d.eggs or 0)+count
 P.publish(player)
 return true,count>1 and ('Bought '..count..'× '..Eggs.Name) or ('Bought a '..Eggs.Name)
end
-- Hatch owned eggs (up to count): one pet per egg, rolled here. The reply has one entry per pet,
-- {id, count, rarity, new, tier, have, emeralds}, rarest first (the same shape as openChest).
function P.openEgg(player,count)
 local d=P.profiles[player]
 if not d then return false,'Profile still loading' end
 if not Eggs.validAmount(count) then return false,'Invalid amount' end
 -- Hatching ×3 or ×10 at once is the Quick Open pass (VIP includes it), like openChest; without
 -- it every egg hatches one at a time (it used to be free for eggs, 2026-10-10 play-test).
 if count>1 and not (d.quickOpen or d.vip) then return false,'Get Quick Open to hatch '..count..' at once' end
 local n=math.min(count,d.eggs or 0)
 if n<=0 then return false,'No '..Eggs.Name..' to hatch' end
 d.eggs-=n
 quest('event',d,Money.day(),player.UserId,'eggs',n) -- Hatch an Egg, Hatcher (plan K)
 local tally={}
 for _=1,n do local id=Eggs.roll(rng);tally[id]=(tally[id] or 0)+1 end
 local results={}
 for id,c in tally do
  local r=P.addCopies(d,id,c);r.count=c;r.rarity=Pets.ById[id].rarity
  table.insert(results,r)
 end
 table.sort(results,function(a,b)
  if RANK[a.rarity]~=RANK[b.rarity] then return RANK[a.rarity]>RANK[b.rarity] end
  if a.count~=b.count then return a.count>b.count end
  return a.id<b.id
 end)
 P.publish(player)
 return true,n>1 and ('Hatched '..n..' eggs') or 'Hatched an egg',results
end
-- One tier up for a weapon, an armor piece or a pet: spends its copies AND emeralds (both tables
-- in ChestConfig, by the item's rarity; the emerald cost triples each tier).
function P.upgrade(player,id)
 local d=P.profiles[player];local armor=Chests.isArmor(id);local pet=Pets.valid(id)
 local rec=d and (armor and d.armor or pet and d.pets or d.weapons)[id]
 if not rec then return false,armor and 'You do not own that piece' or pet and 'You do not own that pet' or 'You do not own that weapon' end
 if rec.tier>=4 then return false,'Already Tier IV' end
 local cost,gems=Chests.upgradeCost(id,rec.tier),Chests.upgradeEmeralds(id,rec.tier)
 if rec.have<cost then return false,'Need '..cost..' copies to upgrade' end
 if not spend(d,gems) then return false,'Need '..(gems-d.emeralds)..' more emeralds' end
 rec.have-=cost;rec.tier+=1;quest('event',d,Money.day(),player.UserId,'upgrades',1);P.publish(player)
 local name=armor and Armor.pieceName(id) or pet and Pets.ById[id].name or Weapons.ById[id].name
 return true,name..' is now Tier '..({'I','II','III','IV'})[rec.tier]
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

-- Run emeralds, settled once per run (LOBBY_AND_MATCH_SERVERS.md §5). `stint` names one player's
-- time in one run; the profile remembers what that stint already paid, so wave clears, giving up,
-- leaving and shutdown can all settle it and only the difference ever pays. `owed` is the stint's
-- total so far, before the VIP bonus. Returns the emeralds paid now.
-- A test run (the admin panel was used) grants nothing.
function P.settleRun(player,stint,map,wavesPassed,owed)
 local d=P.profiles[player]
 if not d or Admin.isTestRun() or type(stint)~='string' or type(owed)~='number' then return 0 end
 if type(d.run)~='table' or d.run.id~=stint then d.run={id=stint,paid=0} end
 if d.vip then owed=math.floor(owed*(1+Money.VIPRunBonus)+.5) end
 local pay=math.max(0,math.floor(owed)-d.run.paid)
 d.run.paid+=pay;d.emeralds+=pay
 quest('event',d,Money.day(),player.UserId,'earn',pay)
 if wavesPassed>(d.bestWaves[map] or 0) then d.bestWaves[map]=wavesPassed end
 P.publish(player)
 return pay
end

-- What a stint has paid in run emeralds so far (VIP bonus included), for the results screen.
function P.stintPaid(player,stint)
 local d=P.profiles[player]
 return d and type(d.run)=='table' and d.run.id==stint and d.run.paid or 0
end
-- The saved best wave for a run key (the map, or map/difficulty).
function P.bestWave(player,map)
 local d=P.profiles[player];return d and d.bestWaves[map] or 0
end
-- Run counts for analytics (RunAnalytics): runsStarted, and when the last run ended (os.time), so
-- "started another run soon after" spans servers. markRunStart returns the seconds since that end
-- (nil for a first run). Missing in older saves means 0.
function P.markRunStart(player)
 local d=P.profiles[player];if not d then return nil end
 d.runsStarted=(d.runsStarted or 0)+1
 return d.lastRunEnd and os.time()-d.lastRunEnd or nil
end
function P.markRunEnd(player)
 local d=P.profiles[player];if d then d.lastRunEnd=os.time() end
end

-- Live progress as each wave clears (RogueliteMeta): best wave, and the win at wave 20 with its
-- one-time first-win bonus. A test run (the admin panel was used) saves nothing. Returns the
-- first-win bonus paid now (0 when there is none), for the results screen.
function P.recordProgress(player,map,wavesPassed,firstWinBonus)
 local d=P.profiles[player];if not d or Admin.isTestRun() then return 0 end
 local changed,bonus=false,0
 if wavesPassed>(d.bestWaves[map] or 0) then d.bestWaves[map]=wavesPassed;changed=true end
 if wavesPassed>=20 and not d.mapWins[map] then
  bonus=math.max(0,math.floor(firstWinBonus or 0))
  d.mapWins[map]=true;d.emeralds+=bonus;changed=true
 end
 if changed then P.publish(player) end
 return bonus
end

-- Stored rerolls/banishes spent during a run.
function P.spend(player,field)
 local d=P.profiles[player]
 if not d or (field~='rerolls' and field~='banishes') or d[field]<=0 then return false end
 d[field]-=1;P.publish(player);return true
end

-- Quests (QuestService) -----------------------------------------------------------------------
function P.questView(player)
 local d=P.profiles[player];if not d then return {} end
 local day=Money.day()
 local view=quest('view',d,day,player.UserId,Money.secondsToReset())
 if not view then return {} end
 view.claimable=quest('claimable',d,day,player.UserId) or 0
 return view
end
-- Kills come many per second: an event only marks the profile, and marked profiles publish
-- ProfileQuests at most once a second. A test run (the admin panel was used) counts nothing.
-- In a run (RunMember) they wait instead (launch audit P11): only the lobby shows quests, and a
-- multi-KB JSON every second goes to every client. Each wave clear's settleRun publishes them
-- (P.publish), and leaving the run lets this loop catch up.
local function publishQuests(player)
 questDirty[player]=nil
 if P.profiles[player] then player:SetAttribute('ProfileQuests',Http:JSONEncode(P.questView(player))) end
end
-- Called by server-confirmed combat/shop hooks. Numeric changes only: safe inside their sandbox.
function P.recordWeaponHit(player,id,damage,lethal)
 local d=P.profiles[player]
 if not d or not P.loaded[player] or Admin.isTestRun() or player:GetAttribute('RunMember')~=true then return false end
 if Journal.hit(d.journal,id,damage,lethal) then journalDirty[player]=true;return true end
 return false
end
function P.recordItemBuy(player,id)
 local d=P.profiles[player]
 if not d or not P.loaded[player] or Admin.isTestRun() or player:GetAttribute('RunMember')~=true then return false end
 if Journal.bought(d.journal,id) then journalDirty[player]=true;return true end
 return false
end
-- No per-hit replication. Wave settlement publishes; returning to the lobby catches up within 2s.
task.spawn(function() while true do task.wait(2);for p in journalDirty do
 if p:GetAttribute('RunMember')~=true then
  local d=P.profiles[p];journalDirty[p]=nil
  if d then p:SetAttribute('ProfileJournal',Http:JSONEncode(Journal.view(d.journal))) end
 end
end end end)
function P.questEvent(player,stat,n)
 local d=P.profiles[player];if not d or Admin.isTestRun() then return end
 if quest('event',d,Money.day(),player.UserId,stat,n) then questDirty[player]=true end
end
-- A run (one player's stint) counts once, at its first cleared wave.
function P.questRun(player,stint)
 local d=P.profiles[player];if not d or Admin.isTestRun() then return end
 if quest('runStarted',d,Money.day(),player.UserId,stint) then questDirty[player]=true end
end
task.spawn(function() while true do task.wait(1);for p in questDirty do if p:GetAttribute('RunMember')~=true then publishQuests(p) end end end end)
-- Claims: QuestService checks and marks; the grant goes through P.grant (earned emeralds).
local function questGrant(player,ok,message,g)
 if ok==nil then return false,'Quests are not available right now' end
 if ok then P.grant(player,g) end -- publishes, ProfileQuests included
 return ok,message
end
function P.claimQuest(player,index)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 return questGrant(player,quest('claimQuest',d,Money.day(),player.UserId,index))
end
function P.claimStreak(player,milestone)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 return questGrant(player,quest('claimStreak',d,Money.day(),player.UserId,milestone))
end
function P.claimRoad(player,roadId)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 return questGrant(player,quest('claimRoad',d,Money.day(),player.UserId,roadId))
end
function P.claimUnlock(player,id)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 -- A weapon reward needs that weapon in the game; until then the claim waits.
 local config=quest('config');local u=config and type(id)=='string' and config.UnlockById[id]
 if u and u.reward.weapon and not P.weaponIdByName(u.reward.weapon) then return false,'Coming soon' end
 local ok,message,g=quest('claimUnlock',d,Money.day(),player.UserId,id,function(class) return d.classes[class]==true end)
 if ok and g.weapon then g.weapon=P.weaponIdByName(g.weapon) end
 return questGrant(player,ok,message,g)
end

-- Plan M: a map win's record (difficulty, solo, no-down, class) for feats and weekly quests,
-- and their claims. A test run counts nothing, like questEvent.
function P.questWin(player,info)
 local d=P.profiles[player];if not d or Admin.isTestRun() then return end
 if quest('win',d,Money.day(),player.UserId,info) then questDirty[player]=true end
end
function P.claimWeekly(player,index)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 return questGrant(player,quest('claimWeekly',d,Money.day(),player.UserId,index))
end
function P.claimFeat(player,id)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 return questGrant(player,quest('claimFeat',d,Money.day(),player.UserId,id))
end
-- CLAIM ALL on one Quests tab (2026-10-03): QuestService re-checks each reward with its own claim.
-- The emeralds and chests go out as one grant (one publish); each unlocked class, weapon or armor
-- set as its own. An unlock whose weapon isn't in the game yet waits, like P.claimUnlock. Returns
-- ok, message, total ({emeralds, chests, count}) for the client's one combined burst.
function P.claimAll(player,group)
 local d=P.profiles[player];if not d then return false,'Profile loading' end
 local ok,message,grants,total=quest('claimAll',d,Money.day(),player.UserId,group,
  function(class) return d.classes[class]==true end,
  function(u) return not (u.reward.weapon and not P.weaponIdByName(u.reward.weapon)) end)
 if ok==nil then return false,'Quests are not available right now' end
 if not ok then return false,message end
 local sum={emeralds=total.emeralds,chests=total.chests}
 for _,g in grants do
  if g.class or g.weapon or g.armorSet then P.grant(player,{class=g.class,weapon=g.weapon and P.weaponIdByName(g.weapon),armorSet=g.armorSet}) end
 end
 P.grant(player,sum) -- publishes, ProfileQuests included
 return true,message,total
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
function P.claimVipChest(player,restricted)
 local d=P.profiles[player]
 if not d or not d.vip then return false,'VIP only' end
 if d.vipClaimDay==Money.day() then return false,'Come back tomorrow' end
 d.vipClaimDay=Money.day()
 local chest=Chests.ById[Money.VIPDailyChest]
 -- VIP is bought with Robux, so its chest is a paid random item: where those are restricted the
 -- chest's emerald price comes instead, as Robux emeralds (they can't buy chests there either).
 if restricted then
  P.grant(player,{emeralds=chest.emeralds,paid=true})
  return true,chest.emeralds..' VIP emeralds added'
 end
 P.grant(player,{chests={[Money.VIPDailyChest]=1}})
 return true,'Free '..chest.name..' added'
end
-- Hidden codes (user, 2026-10-04: "a hidden code for my friends ... gives them a starter pack"). The
-- repo is public, so these live only in the place: ServerScriptService.SecretCodes, a Folder of
-- StringValues named by the code (upper case), each Value a MonetizationConfig product key whose
-- contents it grants for free (not counted as bought). Example: SecretCodes.<CODE>.Value =
-- 'StarterPack' gives 1,500 emeralds, 2 Legendary chests, 5 rerolls and marks the pack owned.
-- ServerScriptService never reaches clients. One use per account, like the codes above.
local function secretReward(code)
 local folder=game:GetService('ServerScriptService'):FindFirstChild('SecretCodes')
 local entry=folder and folder:FindFirstChild(code)
 local product=entry and entry:IsA('StringValue') and Money.Products[entry.Value]
 if not product then return nil end
 return {emeralds=product.emeralds,chests=product.chests,rerolls=product.rerolls,banishes=product.banishes,starterPack=product.oneTime=='starterPack'}
end
function P.redeem(player,code)
 local d=P.profiles[player]
 if not d or type(code)~='string' or #code>30 then return false,'Invalid code' end
 code=string.upper(code:gsub('%s',''))
 local reward=CODES[code] or secretReward(code)
 if not reward then return false,'Invalid code' end
 if d.codes[code] then return false,'Code already used' end
 d.codes[code]=true;P.grant(player,reward)
 return true,'Code redeemed!'
end

-- Last save, which also hands back the lock. Leaving and shutdown can both ask; one is enough.
-- A failed write is tried again 3 more times, 1, 2 and 3 s apart, keeping the profile until it's
-- saved (launch audit S3): one DataStore hiccup no longer loses everything since the last autosave.
-- A lost lock stops at once (another server owns the save). releaseCount: saves still running.
local releasing,releaseCount={},0
local function release(p)
 if releasing[p] then return end
 releasing[p]=true;releaseCount+=1
 local ok=P.save(p,true)
 for pause=1,3 do
  if ok or not P.loaded[p] then break end
  task.wait(pause);ok=P.save(p,true)
 end
 if not ok and P.loaded[p] then warn('ProfileService: last save failed after 4 tries',p.UserId) end
 P.profiles[p]=nil;P.loaded[p]=nil;releasing[p]=nil;questDirty[p]=nil;journalDirty[p]=nil
 releaseCount-=1
end

Players.PlayerAdded:Connect(P.load)
for _,p in Players:GetPlayers() do task.spawn(P.load,p) end
Players.PlayerRemoving:Connect(release)
-- Shutdown: every player at once, inside Roblox's 30 s window, and the leave-saves already running
-- (a player who left just before) are waited for too.
game:BindToClose(function()
 for p in P.profiles do task.spawn(release,p) end
 local started=os.clock()
 while releaseCount>0 and os.clock()-started<27 do task.wait(.1) end
end)
task.spawn(function() while true do task.wait(120);for p in P.profiles do P.save(p) end end end)
return P
