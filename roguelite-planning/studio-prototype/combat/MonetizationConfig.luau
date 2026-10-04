-- Robux catalog shared by server and UI. Prices here are display values; Roblox charges
-- whatever the developer product / game pass is set to in the Creator Dashboard.
-- productId / gamePassId 0 = not created yet: live servers refuse the purchase, Studio
-- simulates the grant into the in-memory profile so every flow can be tested.
-- random=true marks paid random items (hidden where PolicyService restricts them).
-- noGift=true marks in-run products, which can't be gifted (Gifting, at the end).
local M={}

M.Products={
 -- In-run, used immediately. Revives (LOBBY_AND_MATCH_SERVERS.md §4): as many as you like, and the
 -- price doubles each time in the same run. The nth revive uses Revive<n>, and from the 5th on it
 -- stays Revive5. Five products because a developer product's price is fixed in the dashboard.
 Revive1={productId=3716085560,robux=65,name='Revive',revive=1,noGift=true},
 Revive2={productId=3716085638,robux=130,name='Revive',revive=2,noGift=true},
 Revive3={productId=3716085708,robux=260,name='Revive',revive=3,noGift=true},
 Revive4={productId=3716085762,robux=520,name='Revive',revive=4,noGift=true},
 Revive5={productId=3716085809,robux=1040,name='Revive',revive=5,noGift=true},
 ShopReroll={productId=3716085846,robux=15,name='Reroll',random=true,noGift=true},
 UpgradeReroll={productId=3716085906,robux=15,name='Reroll',random=true,noGift=true},
 Banish={productId=3716085963,robux=19,name='Banish',random=true,noGift=true},
 -- Packs saved to your profile, used during runs
 Rerolls5={productId=3716086015,robux=59,rerolls=5,name='5 Rerolls',random=true},
 Rerolls15={productId=3716086057,robux=149,rerolls=15,name='15 Rerolls',random=true},
 Banishes5={productId=3716086107,robux=79,banishes=5,name='5 Banishes',random=true},
 Banishes15={productId=3716086145,robux=199,banishes=15,name='15 Banishes',random=true},
 -- Price ladder (2026-10-01, the owner: "too expensive"): modelled on a successful Roblox shop.
 -- Cheap entry (39-49 R$), mid tiers 150-800, nothing above ~3,750 R$. Emeralds are worth about
 -- 10 per Robux, so a Gold Chest (300) costs about what a Legendary Chest does (~30-49 R$).
 -- Emeralds: the bonus climbs 0 -> 11% -> 21% -> 28% -> 30% -> 35% (bonusPercent).
 Emeralds1={productId=3716086201,robux=39,emeralds=400,name='Pouch'},
 Emeralds2={productId=3716086239,robux=149,emeralds=1700,name='Stack'},
 Emeralds3={productId=3716086267,robux=339,emeralds=4200,name='Crate'},
 Emeralds4={productId=3716086307,robux=799,emeralds=10500,name='Vault'},
 Emeralds5={productId=3716086334,robux=1649,emeralds=22000,name='Hoard'},
 Emeralds6={productId=3716086358,robux=3749,emeralds=52000,name='Treasury'},
 -- Chests (Legendary Chest: one Legendary guaranteed): 49 / 40 / 33 R$ each. Keys keep their old
 -- Royal names so existing developer products stay mapped.
 Royal1={productId=3716086379,robux=49,chests={Legendary=1},name='1 Legendary Chest',random=true},
 Royal5={productId=3716086403,robux=199,chests={Legendary=5},name='5 Legendary Chests',random=true},
 Royal12={productId=3716086431,robux=399,chests={Legendary=12},name='12 Legendary Chests',random=true},
 -- Bundles
 StarterPack={productId=3716086468,robux=49,emeralds=1500,chests={Legendary=2},rerolls=5,name='Starter Pack',oneTime='starterPack',random=true},
 ArsenalBundle={productId=3716086491,robux=299,emeralds=1500,signatureUpgrades=3,name='Arsenal Bundle'},
 MegaBundle={productId=3716086523,robux=999,emeralds=3000,chests={Legendary=30},rerolls=25,banishes=10,name='Mega Chest Bundle',random=true},
 -- 100 Legendary Chests at 30 R$ each (the best chest price in the store).
 UltimateBundle={productId=3716086557,robux=2999,emeralds=5000,chests={Legendary=100},rerolls=50,banishes=25,name='Ultimate Chest Bundle',random=true},
 -- Godly bundles (2026-10-01): one Godly weapon + a full armor set + emeralds, one time each.
 -- godly = the weapon's WeaponCatalog name. Until that weapon exists the store shows COMING SOON
 -- and the server refuses the purchase. Phoenix (Godly armor) is the premium line, Dragon Scale
 -- (Legendary armor) the cheaper one.
 BloodPhoenixBundle={productId=3716086596,robux=1799,emeralds=3000,godly='Vampire Blade',armorSet='Phoenix',name='Blood Phoenix Bundle'},
 ShadowDragonBundle={productId=3716086616,robux=1199,emeralds=1500,godly='Shadow Daggers',armorSet='DragonScale',name='Shadow Dragon Bundle'},
 -- Godly Starter: the buyer picks one Godly weapon (an index into GodlyWeapons) + 3 Legendary
 -- Chests, one time. The pick is saved to the profile before the prompt (ProfileService godlyPick).
 GodlyStarter={productId=3716086636,robux=799,chests={Legendary=3},godlyPick=true,name='Godly Starter',random=true},
 -- Class unlocks (400 emeralds is ~39 R$ of emeralds, so Robux stays close to that).
 ClassThrower={productId=3716086758,robux=49,class='Thrower',name='Thrower'},
 ClassJuggler={productId=3716086815,robux=49,class='Juggler',name='Juggler'},
 ClassHandyman={productId=3716086840,robux=49,class='Handyman',name='Handyman'},
}
M.EmeraldPacks={'Emeralds1','Emeralds2','Emeralds3','Emeralds4','Emeralds5','Emeralds6'}
M.ChestPacks={'Royal1','Royal5','Royal12'}
M.RerollPacks={'Rerolls5','Rerolls15'}
M.BanishPacks={'Banishes5','Banishes15'}
M.GodlyBundles={'BloodPhoenixBundle','ShadowDragonBundle'}
-- The Godly weapons (WeaponCatalog names) and short labels for small store tiles.
M.GodlyWeapons={{"Reaper's Scythe",'Scythe'},{"Poseidon's Trident",'Trident'},{'Storm Bow','Storm Bow'},
 {'Shadow Daggers','Daggers'},{'Vampire Blade','Vampire'},{'Ray Gun','Ray Gun'}}
M.Passes={
 VIP={gamePassId=2005940558,robux=499,name='VIP Pass'},
 QuickOpen={gamePassId=2006606580,robux=149,name='Quick Open'},
}
-- VIP perks (applied on the server).
M.VIPRunBonus=.25 -- +25% emeralds from runs
M.VIPDailyChest='Gold' -- one free Gold Chest per day
-- Class unlocks can also be bought with emeralds.
M.ClassEmeraldPrice=400
-- Quick Open: open up to this many chests at once.
M.QuickOpenCount=10

-- Revive: death-screen continue for the current run. No limit per run; the count resets each run.
-- Example: a first revive costs 65 R$, a second in the same run 130, a sixth 1040.
M.ReviveSteps=5
function M.reviveKey(n) return 'Revive'..math.clamp(math.floor(tonumber(n) or 1),1,M.ReviveSteps) end
function M.isRevive(key) local p=type(key)=='string' and M.Products[key];return p and p.revive~=nil or false end
M.ReviveHealth=.5
M.ReviveInvulnerableSeconds=3
M.RevivePushRadius=22
M.RevivePushDistance=14

-- Daily deals: 5 slots, new every UTC day. Slot 1 is always free.
M.DailyDealSlots=5
M.DailyFreeEmeralds=200
-- Emeralds are the only account currency (keys were dropped 2026-09-27). Old saves convert
-- each key at this rate, the same rate the old key swap used.
M.EmeraldsPerOldKey=20

-- Bonus shown on bigger emerald packs, measured against the smallest pack.
function M.bonusPercent(key)
 local base=M.Products.Emeralds1;local p=M.Products[key]
 local rate=(p.emeralds/p.robux)/(base.emeralds/base.robux)
 return math.max(0,math.floor((rate-1)*100+.5))
end
-- What a Robux price is worth in emeralds at the smallest pack's rate (39 R$ = 400). Used when a
-- paid product can't be delivered as itself (already owned, region rules): 49 R$ -> 502 emeralds.
function M.fairEmeralds(robux)
 local base=M.Products.Emeralds1
 return math.floor((tonumber(robux) or 0)*base.emeralds/base.robux)
end
-- What this player is charged for a product or pass. Managed pricing (regional prices, price
-- tests) can change it, so on the client RoguelitePrices asks Roblox and stores the answer as
-- Price_<key> on the local player; until it answers (and on the server) it is the list price.
function M.price(key)
 local player=game:GetService('Players').LocalPlayer
 local v=player and player:GetAttribute('Price_'..key)
 if type(v)=='number' then return v end
 local p=M.Products[key] or M.Passes[key]
 return p and p.robux or 0
end
function M.byProductId(id)
 for key,p in M.Products do if p.productId==id and id~=0 then return key,p end end
end
function M.day() return math.floor(os.time()/86400) end
function M.secondsToReset() return 86400-os.time()%86400 end

-- Gifting (2026-10-04, user: "add gifting to the store, like be able to buy stuff for other people").
-- Developer products only (Roblox game passes can't be gifted), never the in-run ones (noGift). The
-- buyer pays; RogueliteMeta saves a gift intent before the prompt, the receipt puts the gift in the
-- recipient's inbox, and their server (or their next join) delivers it. Pure helpers below, shared
-- by the server, the store and GiftTests. Example: Ben gifts Ana a Starter Pack for 49 R$: Ana gets
-- 1,500 emeralds, 2 Legendary Chests and 5 rerolls, or 502 emeralds if she already had one.
M.GiftIntentSeconds=600 -- a GIFT prompt has 10 minutes to be paid, else the purchase is the buyer's
M.GiftBoundSeconds=30*86400 -- a paid gift's intent waits this long for its receipt to finish
M.GiftInboxMax=100 -- gifts waiting for one player; one more waits in the buyer's receipt retries
function M.giftable(key)
 local p=type(key)=='string' and M.Products[key]
 return (p and not p.noGift) and true or false
end
-- Who may receive a gift: anyone in the buyer's server or any Roblox friend, never the buyer
-- (Studio allows yourself and negative test ids, so one test player can try the whole flow).
-- o: buyer, to (user ids), inServer, friends, studio. Returns ok, and why not.
function M.giftRecipientOk(o)
 local to=o.to
 if type(to)~='number' or to~=to or to%1~=0 or to==0 or (to<0 and not o.studio) then return false,'Pick someone to gift' end
 if to==o.buyer and not o.studio then return false,"You can't gift to yourself" end
 if not (o.inServer or o.friends) then return false,'You can gift to players here or your friends' end
 return true
end
-- Why a player can't receive `key` as itself (nil: they can), from what they own: a profile, or the
-- same fields read from their Profile* attributes: {starterPack=bool, classes={Thrower=true},
-- bundles={GodlyStarter=true}}. Example: Ana owns the Starter Pack -> 'already has it'.
function M.giftBlocked(key,owned)
 local p=M.Products[key];if not p or type(owned)~='table' then return nil end
 if p.oneTime and owned[p.oneTime]==true then return 'already has it' end
 if p.class and type(owned.classes)=='table' and owned.classes[p.class] then return 'already unlocked it' end
 if (p.godly or p.godlyPick) and type(owned.bundles)=='table' and owned.bundles[key] then return 'already has it' end
 return nil
end
-- Gift intents, one DataStore key per buyer: {[productKey]={pending=intent, bound={[purchaseId]=intent}}},
-- intent = {id, to, toName, at, pick}. A new GIFT replaces `pending`; the receipt moves it to `bound`
-- under its PurchaseId, so a retried receipt (failed inbox write, crash, another server) still finds
-- its gift however late. Example: Ben taps GIFT at 12:00 and pays at 12:03: Ana's gift. A receipt at
-- 12:11 finds nothing fresh: a normal purchase for Ben.
local function intentEntry(record,key) return type(record)=='table' and type(record[key])=='table' and record[key] or nil end
function M.giftIntentPut(record,key,intent,now)
 record=type(record)=='table' and record or {}
 -- Tidy while here: forgotten prompts and long-finished bindings go.
 for k,e in record do
  if type(e)~='table' then record[k]=nil;continue end
  if type(e.pending)=='table' and not (now-(tonumber(e.pending.at) or -math.huge)<=M.GiftIntentSeconds) then e.pending=nil end
  if type(e.bound)=='table' then
   for r,b in e.bound do if type(b)~='table' or not (now-(tonumber(b.at) or -math.huge)<=M.GiftBoundSeconds) then e.bound[r]=nil end end
   if next(e.bound)==nil then e.bound=nil end
  end
  if e.pending==nil and e.bound==nil then record[k]=nil end
 end
 local e=record[key] or {};record[key]=e
 e.pending=intent
 return record
end
-- The intent this receipt pays for, bound to it. Returns the intent (nil: a normal purchase) and
-- whether the record changed (and must be written).
function M.giftIntentBind(record,key,receipt,now)
 local e=intentEntry(record,key)
 if not e or type(receipt)~='string' then return nil,false end
 local b=type(e.bound)=='table' and e.bound[receipt]
 if type(b)=='table' then return b,false end
 local p=e.pending
 if type(p)~='table' or type(p.to)~='number' or not (now-(tonumber(p.at) or -math.huge)<=M.GiftIntentSeconds) then return nil,false end
 e.pending=nil;e.bound=type(e.bound)=='table' and e.bound or {};e.bound[receipt]=p
 return p,true
end
-- The receipt is finished: its binding goes. Returns whether the record changed.
function M.giftIntentDone(record,key,receipt)
 local e=intentEntry(record,key)
 if not e or type(e.bound)~='table' or e.bound[receipt]==nil then return false end
 e.bound[receipt]=nil
 if next(e.bound)==nil then e.bound=nil end
 if e.pending==nil and e.bound==nil then record[key]=nil end
 return true
end
-- A GIFT prompt closed unpaid (or a normal BUY of the same product): its pending intent goes, but
-- only that one (by id), never a newer GIFT or a bound one. Returns whether the record changed.
function M.giftIntentCancel(record,key,id)
 local e=intentEntry(record,key)
 if not e or type(e.pending)~='table' or e.pending.id~=id then return false end
 e.pending=nil
 if e.bound==nil or next(e.bound)==nil then record[key]=nil end
 return true
end
-- A gift in a recipient's inbox (one DataStore key per recipient: {gifts={...}}): {from=buyer id,
-- fromName, key=product, receipt=the buyer's PurchaseId, at=os.time(), pick? (Godly Starter),
-- spent? (Robux paid)}. Shape only: a product no longer sold still arrives (as emeralds).
function M.giftValid(g)
 return type(g)=='table' and type(g.from)=='number' and type(g.key)=='string' and #g.key<=40
  and type(g.receipt)=='string' and #g.receipt>0 and #g.receipt<=100 and type(g.at)=='number'
  and (g.pick==nil or type(g.pick)=='number') and (g.spent==nil or type(g.spent)=='number')
  and (g.fromName==nil or type(g.fromName)=='string')
end
-- Adds one gift, once per receipt. Returns the inbox and 'added', 'duplicate' or 'full'.
function M.giftInboxAdd(inbox,gift,max)
 inbox=type(inbox)=='table' and inbox or {}
 if type(inbox.gifts)~='table' then inbox.gifts={} end
 for _,g in inbox.gifts do if type(g)=='table' and g.receipt==gift.receipt then return inbox,'duplicate' end end
 if #inbox.gifts>=(max or M.GiftInboxMax) then return inbox,'full' end
 table.insert(inbox.gifts,gift)
 return inbox,'added'
end
-- The inbox's gifts, oldest first, and how many entries are malformed (logged, then dropped).
function M.giftList(inbox)
 local list,bad={},0
 local gifts=type(inbox)=='table' and type(inbox.gifts)=='table' and inbox.gifts or {}
 for _,g in gifts do if M.giftValid(g) then table.insert(list,g) else bad+=1 end end
 table.sort(list,function(a,b) if a.at~=b.at then return a.at<b.at end;return a.receipt<b.receipt end)
 return list,bad
end
-- Takes out delivered gifts (done: receipt -> true) and malformed entries; gifts that arrived
-- meanwhile stay. Returns the inbox and how many went.
function M.giftInboxRemove(inbox,done)
 if type(inbox)~='table' or type(inbox.gifts)~='table' then return {gifts={}},0 end
 local keep,n={},0
 for _,g in inbox.gifts do
  if M.giftValid(g) and not done[g.receipt] then table.insert(keep,g) else n+=1 end
 end
 inbox.gifts=keep
 return inbox,n
end
return M
