-- First-join tutorial data (plans/2026-10-03-tutorial-design.md). Shared by the server
-- (TutorialDirector, ProfileService, RogueliteMeta) and the client guide (TutorialGuide).
-- Plain data and pure functions only: tests load it with loadstring in Studio Edit.
local T={}

-- The run: Pine Valley as a Brawler with the Frying Pan, three waves, the boss on wave 3.
T.Map='PineValley';T.MapName='Pine Valley';T.Class='Brawler';T.Weapon='01'
T.START_SHARDS=0 -- no starting crystals: the money clearly comes from crystals
T.CRYSTAL_VALUE=5 -- each kill's crystal (shards and XP); normal runs use EconomyConfig.KILL_SHARDS
T.BOSS_WAVE=3
-- A fixed boss health, no difficulty or party scaling: a weak build (~22 damage a second) needs
-- about 30 s, a typical one (~35) about 19 s.
T.BOSS_HP=650
T.VICTORY_DELAY=4 -- seconds between the boss wave clearing and the results screen (VICTORY banner)
T.MAX_WAVE_SECONDS=90 -- a wave that somehow never empties ends anyway
T.WELCOME_SECONDS=3 -- Studio: the welcome line shows this long before wave 1 starts
-- Enemies per wave, all spawned at once and never respawned; the wave ends when they are dead.
-- roster: EnemyCatalog ids (nil = the map's own mix, which has a Baby Zombie in every 4).
T.Waves={
 {count=6,roster='regular-zombie'},
 {count=15},
 {count=4,roster='regular-zombie'}, -- plus the boss
}
-- Forced shop offers: [shop wave][slot] = ShopCatalog id. The shop after wave 1 is wave 2's.
T.Offers={[2]={[1]='weapon_00_1'}} -- slot 1: the Glock, Tier I
-- Paid once, when the boss wave is cleared.
T.Reward={chests={Silver=3},emeralds=100}
-- The first Silver Chest opened after the reward also holds these copies (on top of its roll):
-- two Frying Pans (enough for the Tier II upgrade) and an Iron helmet to equip.
T.SeedChest='Silver'
T.SeedCopies={['01']=2,['Iron.Helmet']=1}
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
 Pan="Your pan swings by itself. Just move!",
 Crystals="Grab the crystals: they're XP and money.",
 LevelUp="You leveled up! Pick any upgrade.",
 Shop="After every wave you can shop. Crystals pay for it. Buy anything you like!",
 ShopGo="Nice! Press GO when you're ready.",
 Survive="Survive wave 3 and beat the boss!",
 LevelUp2="Two level-ups! Pick your upgrades.",
 Shop2="Your turn. Buy what you like, then press GO.",
 Boss="Here he comes! Beat the Hammer Zombie Boss!",
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
-- glockBase/itemBase: ShopCatalog base prices of the Glock (Tier I) and a Protein Shake.
-- Returns what the player has at each shop. Example (2026-10-03 numbers): shop 1 has 45 shards
-- at level 2 (1 card); after the Glock (24) and a Protein Shake (18), shop 2 has 96 at level 4
-- (2 cards).
function T.economy(E,XP,glockBase,itemBase)
 local shards,level,xp=T.START_SHARDS,1,0
 local function kills(n)
  local amount=n*T.CRYSTAL_VALUE;shards+=amount
  local l,x,gained=XP.add(level,xp,amount);level,xp=l,x
  return gained
 end
 local function clear(nextWave) shards+=E.WAVE_REWARD_BASE+(nextWave-1)*E.WAVE_REWARD_SCALE end
 local cards1=kills(T.Waves[1].count);clear(2)
 local shop1={shards=shards,level=level,cards=cards1,glock=E.price(glockBase,2,1),item=E.price(itemBase,2,1)}
 shards-=shop1.glock
 if shards>=shop1.item then shards-=shop1.item;shop1.boughtItem=true end
 local cards2=kills(T.Waves[2].count);clear(3)
 return shop1,{shards=shards,level=level,cards=cards2}
end
return T
