local E={
 WEAPON_SELL_REFUND=.50, BASE_REROLL_COST=2, REROLL_WAVE_SCALE=.75, REROLL_INCREASE=2,
 FLAT_WAVE_PRICE=1, INFLATION_RATE=.06, GLOBAL_SHOP_PRICE_MODIFIER=1,
 STARTING_GOLD=60, MAX_GOLD=1000000, DEBUG_CURRENCY_ENABLED=true,
 OFFER_COUNT=4, ITEM_CAPACITY=16, MAX_ITEM_COPIES=5,
 WAVE_SECONDS=30, WAVE_REWARD_BASE=12, WAVE_REWARD_SCALE=3, KILL_GOLD=2,
 TIER_PRICE_BANDS={{12,25},{30,55},{60,95},{110,160}}, TIER_DAMAGE_MULTIPLIERS={1,1.2,1.45,1.75},
 TIER_NAMES={'Common','Uncommon','Rare','Legendary'},
}
function E.integer(v,min,max) return type(v)=='number' and v==v and v%1==0 and v>=min and v<=max end
function E.price(base,wave,modifier)
 return math.max(1,math.floor((base+wave*E.FLAT_WAVE_PRICE)*(1+wave*E.INFLATION_RATE)*math.clamp(modifier or 1,.2,3)*E.GLOBAL_SHOP_PRICE_MODIFIER+1e-8))
end
function E.reroll(wave,count) return E.BASE_REROLL_COST+math.floor(wave*E.REROLL_WAVE_SCALE)+count*E.REROLL_INCREASE end
function E.refund(paid) return math.floor(paid*E.WEAPON_SELL_REFUND) end
function E.modifier(stats) return math.clamp(1+(stats.ShopPricePercent or 0)/100-(stats.ShopDiscount or 0)/100,.2,3) end
return E
