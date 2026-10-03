local E={
 WEAPON_SELL_REFUND=.25, REROLL_BASE_WAVE=.75, REROLL_STEP_WAVE=.40,
 FLAT_WAVE_PRICE=1, INFLATION_RATE=.10, GLOBAL_SHOP_PRICE_MODIFIER=1,
 STARTING_SHARDS=60, MAX_SHARDS=1000000, DEBUG_CURRENCY_ENABLED=true,
 OFFER_COUNT=4, ITEM_CAPACITY=16, MAX_ITEM_COPIES=5,
 -- Shop timer: the next wave starts when every living player presses GO, or after this long.
 SHOP_SECONDS=120,
 WAVE_SECONDS=30, WAVE_REWARD_BASE=12, WAVE_REWARD_SCALE=3, KILL_SHARDS=1, DESIGNER_BONUS_SHARDS=2,
 TIER_PRICE_BANDS={{12,25},{30,55},{60,95},{110,160}}, TIER_DAMAGE_MULTIPLIERS={1,1.2,1.45,1.75},
 -- Tier words never borrow rarity words (RARITY_GODLY_ARMOR.md §5): Common..Legendary mean rarity only.
 TIER_NAMES={'Tier I','Tier II','Tier III','Tier IV'},
}
-- Run-shop weapon rarity (RARITY_GODLY_ARMOR.md §5, gentler per the user 2026-10-02: "don't make it
-- too rare, and it should depend on wave and luck"). A weapon offer is picked by weight: Common 1,
-- and a rarer weapon's weight grows from its wave-1 value to its wave-20 value. Luck multiplies it by
-- (1 + Luck/100), never past a Common's 1. Godly weapons are never sold in runs.
-- Example, no Luck: a weapon offer is Legendary about 10% of the time on wave 1, 16% on wave 20
-- (19% if every weapon were equally likely).
E.RARITY_OFFER={Common={1,1},Rare={.8,1},Epic={.6,.9},Legendary={.4,.8}}
function E.rarityWeight(rarity,wave,luck)
 local w=E.RARITY_OFFER[rarity];if not w then return 0 end
 local t=math.clamp(((tonumber(wave) or 1)-1)/19,0,1)
 return math.min(1,(w[1]+(w[2]-w[1])*t)*(1+math.clamp(tonumber(luck) or 0,0,100)/100))
end
-- Rarer weapons cost more in runs: half the §5 premium (which was x1.15 / x1.4 / x2).
E.RARITY_PRICE={Common=1,Rare=1.1,Epic=1.2,Legendary=1.5}
function E.integer(v,min,max) return type(v)=='number' and v==v and v%1==0 and v>=min and v<=max end
function E.price(base,wave,modifier)
 return math.max(1,math.floor((base+wave*E.FLAT_WAVE_PRICE+base*wave*E.INFLATION_RATE)*math.clamp(modifier or 1,.2,3)*E.GLOBAL_SHOP_PRICE_MODIFIER+1e-8))
end
function E.reroll(wave,count)
 local step=math.max(1,math.floor(wave*E.REROLL_STEP_WAVE))
 return math.floor(wave*E.REROLL_BASE_WAVE)+step*(count+1)
end
-- Selling (recycling) a weapon pays 25% of what that weapon, at its tier, costs in the shop right
-- now for this player, at least 1. It does not matter what was paid, so a free starting weapon sells
-- too. Example: a base-20 Tier I weapon costs 23 on wave 1 (sells for 5) and 50 on wave 10 (sells for
-- 12). Using the player's own price means a discount can never make selling a profit.
function E.sellValue(base,wave,modifier) return math.max(1,math.floor(E.price(base,wave,modifier)*E.WEAPON_SELL_REFUND)) end
function E.modifier(stats) return math.clamp(1+(stats.ShopPricePercent or 0)/100-(stats.ShopDiscount or 0)/100,.2,3) end
-- Ordered rarity thresholds. Luck is earned within the run and never changed by Robux.
local rarity={
 [2]={minWave=2,perWave=.06,cap=.60},
 [3]={minWave=6,perWave=.015,cap=.20},
 [4]={minWave=12,perWave=.0015,cap=.05},
}
function E.rarityChance(tier,wave,luck)
 local rule=rarity[tier]
 if not rule then return tier==1 and 1 or 0 end
 if wave<rule.minWave then return 0 end
 local boost=1+math.clamp(luck or 0,0,100)/100
 return math.min(rule.cap,(wave-rule.minWave+1)*rule.perWave*boost)
end
function E.rollTier(wave,luck,rng)
 local draw=rng:NextNumber()
 for tier=4,2,-1 do if draw<E.rarityChance(tier,wave,luck) then return tier end end
 return 1
end
-- Each shop offer's tier chances, {I,II,III,IV}, exactly as rollTier draws them: one draw checked
-- against Tier IV's chance, then III's, then II's. The REROLL odds note (ShopUI) shows these.
-- Example, wave 10 with no Luck: IV 0%, III 7.5%, II 46.5%, I 46%.
function E.tierOdds(wave,luck)
 local odds,taken={0,0,0,0},0
 for tier=4,2,-1 do local c=math.max(taken,E.rarityChance(tier,wave,luck));odds[tier]=c-taken;taken=c end
 odds[1]=1-taken
 return odds
end
function E.weaponSlot(wave,slot,rng)
 if wave<=2 then return slot<=2 end
 if wave<=5 and slot==1 then return true end
 return rng:NextNumber()<.35
end
function E.classBonus(wave) return wave<=5 and (6-wave)*.03 or 0 end
return E
