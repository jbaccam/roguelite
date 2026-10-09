-- Pure checks for TutorialConfig and the shared-crystal split (EconomyConfig.shareIndex). Run in
-- Studio Edit on fresh repo copies (plans/2026-10-03-tutorial-build-steps.md "Running Luau checks"):
-- `TutorialTests(TutorialConfig, EconomyConfig, RunXP, glockBase, itemBase, WeaponCatalog)` returns the
-- number of checks. WeaponCatalog is optional: with it, the tutorial pair is checked against the roster.
return function(T,E,XP,glockBase,itemBase,Weapons)
 local checks=0
 local function check(condition,message) assert(condition,message);checks+=1 end
 glockBase=glockBase or 19;itemBase=itemBase or 14

 -- The economy (crystals worth 1, like normal runs): one level-up card after wave 1, earned late
 -- in it, and enough crystals for the guided Glock; one more card after wave 2.
 local shop1,shop2=T.economy(E,XP,glockBase,itemBase)
 check(shop1.cards==1 and shop1.level==2,'wave 1 gives exactly one level-up (level 2), got '..shop1.cards)
 check(math.ceil(XP.required(1)/E.KILL_SHARDS)>=T.Waves[1].count*.75,'the first level-up comes late in wave 1, not in its first kills')
 check(shop1.shards>=shop1.glock,('shop 1 affords the Glock: %d shards, Glock %d'):format(shop1.shards,shop1.glock))
 check(shop1.shards-shop1.glock<shop1.glock,'shop 1 is not rich enough for two Glocks')
 check(shop2.cards==1 and shop2.level==3,'wave 2 gives one level-up (level 3), got '..shop2.cards..' / level '..shop2.level)
 check(shop2.shards>=50 and shop2.shards<=75,'shop 2 has about 63 shards, got '..shop2.shards)

 -- Waves: three, the boss on the last, every count positive.
 check(#T.Waves==T.BOSS_WAVE,'the boss wave is the last tutorial wave')
 for i,w in T.Waves do check(type(w.count)=='number' and w.count>0,'wave '..i..' has enemies') end
 check(T.Offers[2] and T.Offers[2][1]=='weapon_00_1','the shop after wave 1 offers the Glock in slot 1')

 -- Shared crystals: round-robin, so 50 across 3 players is 17 / 17 / 16 and one player gets all 50.
 local function split(total,count)
  local got={};for i=1,count do got[i]=0 end
  for n=1,total do local i=E.shareIndex(n,count);got[i]+=1 end
  return got
 end
 local three=split(50,3)
 check(three[1]==17 and three[2]==17 and three[3]==16,('50 across 3 is 17/17/16, got %d/%d/%d'):format(three[1],three[2],three[3]))
 check(split(50,1)[1]==50,'a solo player gets every boss crystal')
 local four=split(50,4);check(four[1]+four[2]+four[3]+four[4]==50 and math.max(table.unpack(four))-math.min(table.unpack(four))<=1,'any split is even to one crystal')

 -- Steps: lobby steps move forward only and never back into the run.
 check(T.Steps[1]=='Run' and T.Steps[#T.Steps]=='Done','steps start at Run and end at Done')
 check(T.canStep('Chests','Armory') and T.canStep('Chests','Done'),'lobby steps move forward, skipping is fine')
 check(not T.canStep('Armory','Chests'),'steps never move back')
 check(not T.canStep('Run','Chests'),'the run step is left only by the reward, never by the client')
 check(not T.canStep('Chests','Run') and not T.canStep('Done','Play'),'nothing goes back to the run or out of Done')
 check(not T.canStep('Chests','Nope'),'unknown steps are refused')

 -- Reward and seed: what the chest code and the Armory steps expect.
 check(T.Reward.chests[T.SeedChest]==3 and T.Reward.emeralds==100,'3 Silver Chests and 100 emeralds')
 check(T.SeedCopies[T.Weapon]==2,'the seeded chest has two copies of the tutorial weapon (its Tier II upgrade)')
 -- Brawler + Boxing Gloves (2026-10-09): the Frying Pan is Chef's now, and a run only starts with a
 -- weapon of its class (RunSetupRules.validLoadout), so the tutorial launch would be refused.
 check(T.Class=='Brawler' and T.Weapon=='19','the tutorial is Brawler with the Boxing Gloves')
 check(T.SeedCopies['01']==nil,'no Frying Pan copies are seeded any more')
 if Weapons then
  local w=Weapons.ById[T.Weapon]
  check(w~=nil and not w.godly and w.class==T.Class,'the tutorial weapon is a starter of the tutorial class')
 end
 check(T.SeedCopies[T.SeedArmor]==1 and T.SeedArmor==T.SeedArmorSet..'.'..T.SeedArmorSlot,'the seeded armor piece id matches its set and slot')

 -- Every line the guide can show exists.
 for _,id in {'Welcome','Gloves','Crystals','CrystalsUse','LevelUp','Shop','ShopGo','Survive','LevelUp2','Shop2','Boss','RedCircle','Loot','Chests','ChestOpen','ChestTap','ChestMore','Armory','Upgrade','Equip','Equipped','Offer','Play'} do
  check(type(T.Lines[id])=='string' and #T.Lines[id]>0,'line '..id)
 end
 check(type(T.GuideName)=='string' and #T.GuideName>0 and #T.GuideName<=14,'the guide has a short name for his tag')
 check(string.find(T.Lines.Welcome,T.GuideName,1,true)~=nil,'the welcome line says his name')
 for id,line in T.Lines do check(not string.find(string.lower(line),'%f[%a]pans?%f[%A]'),'no line still talks about the pan: '..id) end
 return checks
end
