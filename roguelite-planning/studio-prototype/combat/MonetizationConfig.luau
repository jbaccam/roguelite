-- Robux catalog shared by server and UI. Prices here are display values; Roblox charges
-- whatever the developer product / game pass is set to in the Creator Dashboard.
-- productId / gamePassId 0 = not created yet: live servers refuse the purchase, Studio
-- simulates the grant into the in-memory profile so every flow can be tested.
-- random=true marks paid random items (hidden where PolicyService restricts them).
local M={}

M.Products={
 -- In-run, used immediately. Revives (LOBBY_AND_MATCH_SERVERS.md §4): as many as you like, and the
 -- price doubles each time in the same run. The nth revive uses Revive<n>, and from the 5th on it
 -- stays Revive5. Five products because a developer product's price is fixed in the dashboard.
 Revive1={productId=0,robux=65,name='Revive',revive=1},
 Revive2={productId=0,robux=130,name='Revive',revive=2},
 Revive3={productId=0,robux=260,name='Revive',revive=3},
 Revive4={productId=0,robux=520,name='Revive',revive=4},
 Revive5={productId=0,robux=1040,name='Revive',revive=5},
 ShopReroll={productId=0,robux=15,name='Reroll',random=true},
 UpgradeReroll={productId=0,robux=15,name='Reroll',random=true},
 Banish={productId=0,robux=19,name='Banish',random=true},
 -- Packs saved to your profile, used during runs
 Rerolls5={productId=0,robux=59,rerolls=5,name='5 Rerolls',random=true},
 Rerolls15={productId=0,robux=149,rerolls=15,name='15 Rerolls',random=true},
 Banishes5={productId=0,robux=79,banishes=5,name='5 Banishes',random=true},
 Banishes15={productId=0,robux=199,banishes=15,name='15 Banishes',random=true},
 -- Price ladder (2026-10-01, the owner: "too expensive"): modelled on a successful Roblox shop.
 -- Cheap entry (39-49 R$), mid tiers 150-800, nothing above ~3,750 R$. Emeralds are worth about
 -- 10 per Robux, so a Gold Chest (300) costs about what a Legendary Chest does (~30-49 R$).
 -- Emeralds: the bonus climbs 0 -> 11% -> 21% -> 28% -> 30% -> 35% (bonusPercent).
 Emeralds1={productId=0,robux=39,emeralds=400,name='Pouch'},
 Emeralds2={productId=0,robux=149,emeralds=1700,name='Stack'},
 Emeralds3={productId=0,robux=339,emeralds=4200,name='Crate'},
 Emeralds4={productId=0,robux=799,emeralds=10500,name='Vault'},
 Emeralds5={productId=0,robux=1649,emeralds=22000,name='Hoard'},
 Emeralds6={productId=0,robux=3749,emeralds=52000,name='Treasury'},
 -- Chests (Legendary Chest: one Legendary guaranteed): 49 / 40 / 33 R$ each. Keys keep their old
 -- Royal names so existing developer products stay mapped.
 Royal1={productId=0,robux=49,chests={Legendary=1},name='1 Legendary Chest',random=true},
 Royal5={productId=0,robux=199,chests={Legendary=5},name='5 Legendary Chests',random=true},
 Royal12={productId=0,robux=399,chests={Legendary=12},name='12 Legendary Chests',random=true},
 -- Bundles
 StarterPack={productId=0,robux=49,emeralds=1500,chests={Legendary=2},rerolls=5,name='Starter Pack',oneTime='starterPack'},
 ArsenalBundle={productId=0,robux=299,emeralds=1500,signatureUpgrades=3,name='Arsenal Bundle'},
 MegaBundle={productId=0,robux=999,emeralds=3000,chests={Legendary=30},rerolls=25,banishes=10,name='Mega Chest Bundle',random=true},
 -- 100 Legendary Chests at 30 R$ each (the best chest price in the store).
 UltimateBundle={productId=0,robux=2999,emeralds=5000,chests={Legendary=100},rerolls=50,banishes=25,name='Ultimate Chest Bundle',random=true},
 -- Godly bundles (2026-10-01): one Godly weapon + a full armor set + emeralds, one time each.
 -- godly = the weapon's WeaponCatalog name. Until that weapon exists the store shows COMING SOON
 -- and the server refuses the purchase. Phoenix (Godly armor) is the premium line, Dragon Scale
 -- (Legendary armor) the cheaper one.
 BloodPhoenixBundle={productId=0,robux=1799,emeralds=3000,godly='Vampire Blade',armorSet='Phoenix',name='Blood Phoenix Bundle'},
 ShadowDragonBundle={productId=0,robux=1199,emeralds=1500,godly='Shadow Daggers',armorSet='DragonScale',name='Shadow Dragon Bundle'},
 -- Godly Starter: the buyer picks one Godly weapon (an index into GodlyWeapons) + 3 Legendary
 -- Chests, one time. The pick is saved to the profile before the prompt (ProfileService godlyPick).
 GodlyStarter={productId=0,robux=799,chests={Legendary=3},godlyPick=true,name='Godly Starter',random=true},
 -- Class unlocks (400 emeralds is ~39 R$ of emeralds, so Robux stays close to that).
 ClassThrower={productId=0,robux=49,class='Thrower',name='Thrower'},
 ClassJuggler={productId=0,robux=49,class='Juggler',name='Juggler'},
 ClassHandyman={productId=0,robux=49,class='Handyman',name='Handyman'},
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
 VIP={gamePassId=0,robux=499,name='VIP Pass'},
 QuickOpen={gamePassId=0,robux=149,name='Quick Open'},
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
function M.byProductId(id)
 for key,p in M.Products do if p.productId==id and id~=0 then return key,p end end
end
function M.day() return math.floor(os.time()/86400) end
function M.secondsToReset() return 86400-os.time()%86400 end
return M
