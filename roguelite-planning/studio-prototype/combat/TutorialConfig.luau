-- First-join tutorial data (plans/2026-10-03-tutorial-design.md). Shared by the server
-- (TutorialDirector, ProfileService, RogueliteMeta) and the client guide (TutorialGuide).
-- Plain data and pure functions only: tests load it with loadstring in Studio Edit.
local T={}

-- The run: Pine Valley as a Brawler with the Baseball Bat, three waves, the boss on wave 3. It was the
-- Frying Pan until the Pan became Chef's (2026-10-09): a run only starts with a weapon of its class.
-- The Boxing Gloves had it for a day; the Bat is Brawler's starter since 2026-10-10.
T.Map='PineValley';T.MapName='Pine Valley';T.Class='Brawler';T.Weapon='06'
T.START_SHARDS=0 -- no starting crystals: the money clearly comes from crystals
-- Crystals are normal ones: one per kill, worth 1 (EconomyConfig.KILL_SHARDS). They were worth 5,
-- which levelled players up on the 4th kill (user, 2026-10-03: "1 crystal should BE ONE CRYSTAL").
T.BOSS_WAVE=3
-- A fixed boss health, no difficulty or party scaling: a weak build (~22 damage a second) needs
-- about 30 s, a typical one (~35) about 19 s.
T.BOSS_HP=650
T.VICTORY_DELAY=4 -- seconds between the boss wave clearing and the results screen (his crystals land)
T.MAX_WAVE_SECONDS=180 -- a wave that somehow never empties ends anyway
-- After the loading screen, Eggbert's welcome shows this long before wave 1 (user, 2026-10-03:
-- "the tutorial needs like 5 seconds after loading in before starting").
T.WELCOME_SECONDS=5
-- Enemies per wave, all spawned at once and never respawned; the wave ends when they are dead.
-- roster: EnemyCatalog ids (nil = the map's own mix, which has a Baby Zombie in every 4).
-- More of them (user, 2026-10-03: "we need more zombie killing"; was 6 / 15 / 4).
T.Waves={
 {count=24,roster='regular-zombie'},
 {count=30},
 {count=10,roster='regular-zombie'}, -- plus the boss
}
-- Forced shop offers: [shop wave][slot] = ShopCatalog id. The shop after wave 1 is wave 2's.
-- 2026-10-18 (user: "add combining weapons and tiers to the tutorial, players have reported not
-- knowing they could combine weapons ... briefly describe classes and attributes / stat boosts for
-- using the right weapons"): shop 1 sells a second Baseball Bat, Tier I (was the Glock), so the
-- player combines the pair into Tier II; shop 2 sells Boxing Gloves, Tier I: a Brawler weapon (+10%
-- class specialty) and Blunt like the Bat, so the pair turns on the Blunt set bonus.
T.Offers={[2]={[1]='weapon_06_1'},[3]={[1]='weapon_19_1'}}
T.CombineWeapon='06';T.ClassWeapon='19';T.WeaponType='Blunt'
-- How long the Tier II line stays after the combine, and the Blunt set line after the Gloves.
T.TIERS_SECONDS=6;T.TYPES_SECONDS=7
-- Paid once, when the boss wave is cleared.
T.Reward={chests={Silver=3},emeralds=100}
-- The first Silver Chest opened after the reward is these copies instead of a roll: two Baseball
-- Bats (enough for the Tier II upgrade) and an Iron helmet to equip.
T.SeedChest='Silver'
T.SeedCopies={['06']=2,['Iron.Helmet']=1}
T.SeedArmor='Iron.Helmet'
T.SeedArmorSet='Iron';T.SeedArmorSlot='Helmet'
-- Saved progress (ProfileService tutorial.step). 'Run' until the boss wave is won, then the lobby
-- steps, then 'Done'. The lobby steps only move forward.
T.Steps={'Run','Chests','Armory','Equip','Offer','Play','Done'}
function T.stepIndex(step) return table.find(T.Steps,step) end
function T.canStep(from,to)
 local a,b=T.stepIndex(from),T.stepIndex(to)
 return a~=nil and b~=nil and a>=2 and b>a
end
-- How long the PLAY arrow stays before the tutorial counts as done.
T.PLAY_SECONDS=10

-- The guide is the egg merchant from the lobby, Eggbert (named by the user, 2026-10-03): the name
-- tag over his portrait and his speech bubble in the lobby (EggMerchant).
T.GuideName='Eggbert'
-- What Eggbert says, by id (TutorialGuide picks the id). Arrows suggest; lines never ask for one
-- particular pick, and every step moves on whatever the player picks (user, 2026-10-03).
T.Lines={
 Welcome="Welcome to Wavebreaker! I'm Eggbert. Let's get you ready.",
 Bat="Your bat swings by itself. Just move!",
 Crystals="Crystals! Walk over them to grab them.",
 CrystalsUse="Crystals are your XP and your money for the shop.",
 LevelUp="You leveled up! Pick any upgrade.",
 Shop="After every wave you can shop. Crystals pay for it. Buy anything you like!",
 ShopGo="Nice! Press GO when you're ready.",
 Combine="Two of the same weapon and tier combine! Tap one, then press Combine.",
 CombineTap="Press Combine to merge them into Tier II.",
 Tiers="Tier II! Higher tiers hit harder. Two Tier IIs combine into Tier III.",
 Class="You're a Brawler. Brawler weapons, like these Gloves, deal 10% more damage.",
 Types="Bat and Gloves are both Blunt. 2 or more of one type give a set bonus!",
 Survive="Survive wave 3 and beat the boss!",
 LevelUp2="Two level-ups! Pick your upgrades.",
 Shop2="Your turn. Buy what you like, then press GO.",
 Boss="Here he comes! Beat the Hammer Brute!",
 RedCircle="Red circle = move!",
 Loot="Let's go spend that loot.",
 Chests="Welcome to the lobby! Let's open what you earned.",
 ChestOpen="Chests give you weapons and armor. Copies make them stronger!",
 ChestTap="Tap the chest to open it!",
 ChestMore="Open the rest!",
 Armory="Now let's power up your gear.",
 Upgrade="Copies and emeralds power up your gear. Upgrade something!",
 Equip="You got armor too. Put some on!",
 Equipped="Looking good! Armor stays on you every run.",
 Offer="Want a head start? Here's a one-time deal.",
 Play="Now go break some waves!",
}
-- Art for the guide (uploaded 2026-10-03; ui/assets/tutorial/asset-ids.json).
T.Asset={portrait='rbxassetid://108357696326171',arrow='rbxassetid://74984560082682'}

-- The tutorial's economy, walked the way the run pays it (ShopService): each kill's crystal is
-- shards and XP, and a clear pays EconomyConfig's wave reward for the wave that comes next.
-- weaponBase/itemBase: ShopCatalog base prices of shop 1's guided weapon (the Baseball Bat, Tier I)
-- and a Protein Shake; gloveBase: shop 2's Boxing Gloves, Tier I.
-- Returns what the player has at each shop. Example (2026-10-18 numbers): 24 kills + 15 for the
-- clear = 39 shards at shop 1, level 2 (1 card, at the 20th kill); after the Bat (28) 11 are left,
-- too few for a Protein Shake (18); 30 more kills + 18 = 59 at shop 2, level 3 (1 card), enough for
-- the Gloves (34).
function T.economy(E,XP,weaponBase,itemBase,gloveBase)
 local shards,level,xp=T.START_SHARDS,1,0
 local function kills(n)
  local amount=n*E.KILL_SHARDS;shards+=amount
  local l,x,gained=XP.add(level,xp,amount);level,xp=l,x
  return gained
 end
 local function clear(nextWave) shards+=E.WAVE_REWARD_BASE+(nextWave-1)*E.WAVE_REWARD_SCALE end
 local cards1=kills(T.Waves[1].count);clear(2)
 local shop1={shards=shards,level=level,cards=cards1,weapon=E.price(weaponBase,2,1),item=E.price(itemBase,2,1)}
 shards-=shop1.weapon
 if shards>=shop1.item then shards-=shop1.item;shop1.boughtItem=true end
 local cards2=kills(T.Waves[2].count);clear(3)
 return shop1,{shards=shards,level=level,cards=cards2,gloves=gloveBase and E.price(gloveBase,3,1) or nil}
end
return T
