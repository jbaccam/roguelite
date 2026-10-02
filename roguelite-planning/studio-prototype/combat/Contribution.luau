-- Run rewards by contribution (launch audit C1, the user's formula 2026-10-02). Pure math, no
-- instances: RogueliteMeta keeps the tallies and pays through ProfileService.settleRun.
-- Each wave, a player's share is half their part of the party's damage and half their part of its
-- kills (a pet's damage and kills count for its owner). That wave pays them
-- base x (0.5 + 0.5 x contributors x share), at most 2x base, and nothing if they did no damage
-- and no kills. Example, 4 players: 40% of the work -> 0.5 + 0.5 x 4 x 0.4 = 1.3x; 10% -> 0.7x;
-- solo -> 1x. Uncapped, the party's total stays what it was (the shares add up to 1).
-- Run emeralds come in blocks every 5 waves (RunSetupRules.runEmeralds), so each block pays its
-- base times the player's average multiplier over the waves of that block they played: idling
-- through waves 1-4 and fighting in wave 5 pays 1/5 of a solo block, not all of it.
local C={MAX=2}
-- tallies: key -> {damage=n,kills=n} for this wave, run members only. Returns key -> multiplier.
-- A wave with no kills at all (a boss holding the wave) shares by damage alone, and the reverse.
function C.multipliers(tallies)
 local damage,kills,n=0,0,0
 for _,t in tallies do
  if (t.damage or 0)>0 or (t.kills or 0)>0 then damage+=math.max(0,t.damage or 0);kills+=math.max(0,t.kills or 0);n+=1 end
 end
 local out={}
 for key,t in tallies do
  local d,k=math.max(0,t.damage or 0),math.max(0,t.kills or 0)
  if d<=0 and k<=0 then out[key]=0;continue end
  local share,parts=0,0
  if damage>0 then share+=d/damage;parts+=1 end
  if kills>0 then share+=k/kills;parts+=1 end
  out[key]=math.min(C.MAX,.5+.5*n*share/parts)
 end
 return out
end
-- One stint's run emeralds (a stint is one player's stay in one run). addWave runs at every wave
-- clear the player was in the run for; block is the emeralds that clear completes for a solo player
-- (0 mid-block, the block's value on waves 5, 10, 15 ...). owed is the total so far, before VIP.
-- Example: multipliers 1.3, 1.3, 0.7, 1.3, 1.4 over waves 1-5 (average 1.2), 40-emerald block -> 48.
function C.ledger(stint) return {stint=stint,sum=0,waves=0,owed=0} end
function C.addWave(ledger,multiplier,block)
 ledger.sum+=math.clamp(multiplier or 0,0,C.MAX);ledger.waves+=1
 if (block or 0)>0 then
  ledger.owed+=block*ledger.sum/ledger.waves
  ledger.sum=0;ledger.waves=0
 end
 return ledger.owed
end
-- Whole emeralds owed so far (ProfileService.settleRun pays the difference from what was paid).
function C.owed(ledger) return ledger and math.floor(ledger.owed+1e-9) or 0 end
return C
