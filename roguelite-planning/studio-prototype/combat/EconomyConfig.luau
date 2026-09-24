local E={
 WEAPON_SELL_REFUND=.50, REROLL_BASE_WAVE=.75, REROLL_STEP_WAVE=.40,
 FLAT_WAVE_PRICE=1, INFLATION_RATE=.10, GLOBAL_SHOP_PRICE_MODIFIER=1,
 STARTING_SHARDS=60, MAX_SHARDS=1000000, DEBUG_CURRENCY_ENABLED=true,
 OFFER_COUNT=4, ITEM_CAPACITY=16, MAX_ITEM_COPIES=5,
 WAVE_SECONDS=30, WAVE_REWARD_BASE=12, WAVE_REWARD_SCALE=3, KILL_SHARDS=2, DESIGNER_BONUS_SHARDS=2,
 TIER_PRICE_BANDS={{12,25},{30,55},{60,95},{110,160}}, TIER_DAMAGE_MULTIPLIERS={1,1.2,1.45,1.75},
 TIER_NAMES={'Common','Uncommon','Rare','Legendary'},
}
function E.integer(v,min,max) return type(v)=='number' and v==v and v%1==0 and v>=min and v<=max end
function E.price(base,wave,modifier)
 return math.max(1,math.floor((base+wave*E.FLAT_WAVE_PRICE+base*wave*E.INFLATION_RATE)*math.clamp(modifier or 1,.2,3)*E.GLOBAL_SHOP_PRICE_MODIFIER+1e-8))
end
function E.reroll(wave,count)
 local step=math.max(1,math.floor(wave*E.REROLL_STEP_WAVE))
 return math.floor(wave*E.REROLL_BASE_WAVE)+step*(count+1)
end
function E.refund(paid) return math.floor(paid*E.WEAPON_SELL_REFUND) end
function E.modifier(stats) return math.clamp(1+(stats.ShopPricePercent or 0)/100-(stats.ShopDiscount or 0)/100,.2,3) end
-- Ordered rarity thresholds. Luck is earned within the run and never changed by Robux.
local rarity={
 [2]={minWave=2,perWave=.06,cap=.60},
 [3]={minWave=4,perWave=.02,cap=.25},
 [4]={minWave=8,perWave=.0023,cap=.08},
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
function E.weaponSlot(wave,slot,rng)
 if wave<=2 then return slot<=2 end
 if wave<=5 and slot==1 then return true end
 return rng:NextNumber()<.35
end
function E.classBonus(wave) return wave<=5 and (6-wave)*.03 or 0 end
return E
