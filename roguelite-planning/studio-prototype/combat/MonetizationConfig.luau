-- Robux catalog shared by server and UI. Prices here are display values; Roblox charges
-- whatever the developer product / game pass is set to in the Creator Dashboard.
-- productId / gamePassId 0 = not created yet: live servers refuse the purchase, Studio
-- simulates the grant into the in-memory profile so every flow can be tested.
-- random=true marks paid random items (hidden where PolicyService restricts them).
local M={}

M.Products={
 -- In-run, used immediately
 Revive={productId=0,robux=65,name='Revive'},
 ShopReroll={productId=0,robux=15,name='Reroll',random=true},
 UpgradeReroll={productId=0,robux=15,name='Reroll',random=true},
 Banish={productId=0,robux=19,name='Banish',random=true},
 -- Packs saved to your profile, used during runs
 Rerolls5={productId=0,robux=59,rerolls=5,name='5 Rerolls',random=true},
 Rerolls15={productId=0,robux=149,rerolls=15,name='15 Rerolls',random=true},
 Banishes5={productId=0,robux=79,banishes=5,name='5 Banishes',random=true},
 Banishes15={productId=0,robux=199,banishes=15,name='15 Banishes',random=true},
 -- Emeralds
 Emeralds1={productId=0,robux=99,emeralds=100,name='Pouch'},
 Emeralds2={productId=0,robux=449,emeralds=550,name='Stack'},
 Emeralds3={productId=0,robux=899,emeralds=1200,name='Crate'},
 Emeralds4={productId=0,robux=1799,emeralds=2600,name='Vault'},
 -- Chests (Legendary Chest: 14 weapons, one Legendary guaranteed). Keys keep their old Royal
 -- names so existing developer products stay mapped.
 Royal1={productId=0,robux=149,chests={Legendary=1},name='1 Legendary Chest',random=true},
 Royal5={productId=0,robux=599,chests={Legendary=5},name='5 Legendary Chests',random=true},
 Royal12={productId=0,robux=1299,chests={Legendary=12},name='12 Legendary Chests',random=true},
 -- Bundles
 StarterPack={productId=0,robux=49,emeralds=150,chests={Legendary=1},rerolls=5,name='Starter Pack',oneTime='starterPack'},
 ArsenalBundle={productId=0,robux=499,emeralds=500,signatureUpgrades=3,name='Arsenal Bundle'},
 MegaBundle={productId=0,robux=2999,emeralds=3000,chests={Legendary=15},rerolls=25,banishes=10,name='Mega Chest Bundle',random=true},
 -- Godly bundles (2026-10-01): one Godly weapon + a full armor set + emeralds, one time each.
 -- godly = the weapon's WeaponCatalog name. Until that weapon exists the store shows COMING SOON
 -- and the server refuses the purchase. Phoenix (Godly armor) is the premium line, Dragon Scale
 -- (Legendary armor) the cheaper one.
 BloodPhoenixBundle={productId=0,robux=2499,emeralds=1000,godly='Vampire Blade',armorSet='Phoenix',name='Blood Phoenix Bundle'},
 ShadowDragonBundle={productId=0,robux=1499,emeralds=500,godly='Shadow Daggers',armorSet='DragonScale',name='Shadow Dragon Bundle'},
 -- Class unlocks
 ClassThrower={productId=0,robux=149,class='Thrower',name='Thrower'},
 ClassJuggler={productId=0,robux=149,class='Juggler',name='Juggler'},
 ClassHandyman={productId=0,robux=149,class='Handyman',name='Handyman'},
}
M.EmeraldPacks={'Emeralds1','Emeralds2','Emeralds3','Emeralds4'}
M.ChestPacks={'Royal1','Royal5','Royal12'}
M.RerollPacks={'Rerolls5','Rerolls15'}
M.BanishPacks={'Banishes5','Banishes15'}
M.GodlyBundles={'BloodPhoenixBundle','ShadowDragonBundle'}
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

-- Revive: death-screen continue for the current run.
M.ReviveLimitPerRun=1
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
