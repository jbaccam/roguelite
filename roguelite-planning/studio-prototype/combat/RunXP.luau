-- Pure run progression. No persistent/account XP and no client award remote.
local X={XP_PER_SHARD=1,MAX_LEVEL=1000}
function X.required(level) return 20+(math.clamp(level,1,X.MAX_LEVEL)-1)*10 end
function X.add(level,xp,amount)
 if type(amount)~='number' or amount~=amount or amount%1~=0 or amount<0 or amount>1000000 then return level,xp,0 end
 local gained=0
 xp+=amount
 while level<X.MAX_LEVEL and xp>=X.required(level) do xp-=X.required(level);level+=1;gained+=1 end
 if level==X.MAX_LEVEL then xp=math.min(xp,X.required(level)) end
 return level,xp,gained
end
-- XP Gain (2026-10-12): whole XP for a pickup of `total` crystals at xpGainPercent (the XPGain stat,
-- -50..200), plus the fraction carried from earlier pickups; returns whole, newCarry (0 <= carry < 1).
-- Example: +15%: 1 crystal = 1.15 XP; 20 crystals = 23 XP. Seven single crystals at +15% give
-- 1,1,1,1,1,1,2 (8.05 XP, 0.05 carried), so a small bonus is never lost to rounding.
function X.gain(total,xpGainPercent,carry)
 if type(total)~='number' or total~=total or total%1~=0 or total<0 then return 0,carry or 0 end
 local pct=math.clamp(tonumber(xpGainPercent) or 0,-50,200)
 if pct~=pct then pct=0 end
 carry=math.clamp(tonumber(carry) or 0,0,.999999)
 if carry~=carry then carry=0 end
 local exact=total*X.XP_PER_SHARD*(1+pct/100)+carry
 local whole=math.floor(exact+1e-6) -- 20 x 1.15 is 22.999...; it should read 23
 return whole,math.clamp(exact-whole,0,.999999)
end
return X
