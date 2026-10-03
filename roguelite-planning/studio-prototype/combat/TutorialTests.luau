-- Pure checks for TutorialConfig and the shared-crystal split (EconomyConfig.shareIndex). Run in
-- Studio Edit on fresh repo copies (plans/2026-10-03-tutorial-build-steps.md "Running Luau checks"):
-- `TutorialTests(TutorialConfig, EconomyConfig, RunXP, glockBase, itemBase)` returns the number of checks.
return function(T,E,XP,glockBase,itemBase)
 local checks=0
 local function check(condition,message) assert(condition,message);checks+=1 end
 glockBase=glockBase or 19;itemBase=itemBase or 14

 -- The economy: one level-up card after wave 1 and enough crystals for the guided Glock;
 -- two cards after wave 2 and a full shop.
 local shop1,shop2=T.economy(E,XP,glockBase,itemBase)
 check(shop1.cards==1 and shop1.level==2,'wave 1 gives exactly one level-up (level 2), got '..shop1.cards)
 check(shop1.shards>=shop1.glock,('shop 1 affords the Glock: %d shards, Glock %d'):format(shop1.shards,shop1.glock))
 check(shop1.shards-shop1.glock<shop1.glock,'shop 1 is not rich enough for two Glocks')
 check(shop2.cards==2 and shop2.level==4,'wave 2 gives two level-ups (level 4), got '..shop2.cards..' / level '..shop2.level)
 check(shop2.shards>=80 and shop2.shards<=110,'shop 2 has about 95 shards, got '..shop2.shards)

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
 check(T.SeedCopies[T.SeedArmor]==1 and T.SeedArmor==T.SeedArmorSet..'.'..T.SeedArmorSlot,'the seeded armor piece id matches its set and slot')

 -- Every line the guide can show exists.
 for _,id in {'Welcome','Pan','Crystals','LevelUp','Shop','ShopGo','Survive','LevelUp2','Shop2','Boss','RedCircle','BossDown','Loot','Chests','ChestOpen','ChestTap','ChestMore','Armory','Upgrade','Equip','Equipped','Offer','Play'} do
  check(type(T.Lines[id])=='string' and #T.Lines[id]>0,'line '..id)
 end
 return checks
end
