-- Pure checks for Contribution (run in Studio Edit: loadstring this file and call it with the module).
return function(C)
 local count=0
 local function check(ok,msg) count+=1;assert(ok,msg) end
 local function near(a,b,msg) check(math.abs(a-b)<1e-6,msg..' ('..tostring(a)..' vs '..tostring(b)..')') end
 -- The user's examples: 4 players, 40% -> 1.3x, 10% -> 0.7x; solo -> 1x.
 local m=C.multipliers({a={damage=400,kills=4},b={damage=100,kills=1},c={damage=250,kills=2.5},d={damage=250,kills=2.5}})
 near(m.a,1.3,'40% of a 4-player party');near(m.b,.7,'10% of a 4-player party')
 near(m.a+m.b+m.c+m.d,4,'party total unchanged')
 near(C.multipliers({solo={damage=5,kills=0}}).solo,1,'solo is 1x')
 -- Nothing done: 0, and they don't count as a contributor for the others.
 m=C.multipliers({a={damage=100,kills=2},idle={damage=0,kills=0}})
 near(m.idle,0,'no damage and no kills pays nothing');near(m.a,1,'the only contributor is a solo share')
 -- Half damage, half kills.
 m=C.multipliers({a={damage=90,kills=0},b={damage=10,kills=2}})
 near(m.a,.5+.5*2*(.9/2),'a: 90% damage, 0% kills');near(m.b,.5+.5*2*((.1+1)/2),'b: 10% damage, 100% kills')
 -- No kills this wave (a boss holding it): damage alone.
 m=C.multipliers({a={damage=75,kills=0},b={damage=25,kills=0}})
 near(m.a,1.25,'damage-only wave a');near(m.b,.75,'damage-only wave b')
 -- Cap: one player doing everything in a party of 4 earns 2x, not 2.5x.
 m=C.multipliers({a={damage=1000,kills=10},b={damage=1e-9,kills=0},c={damage=1e-9,kills=0},d={damage=1e-9,kills=0}})
 near(m.a,2,'capped at 2x')
 check(next(C.multipliers({}))==nil,'empty party')
 -- Ledger: blocks of 5 waves pay base x the average multiplier of the waves played.
 local l=C.ledger('s1')
 for i,mult in {1.3,1.3,.7,1.3,1.4} do C.addWave(l,mult,i==5 and 40 or 0) end
 check(C.owed(l)==48,'block of 5 at average 1.2 -> 48, got '..C.owed(l))
 for i=6,10 do C.addWave(l,1,i==10 and 40 or 0) end
 check(C.owed(l)==88,'second block at 1x -> 88')
 -- Solo with every wave played pays exactly the old blocks.
 l=C.ledger('s2');for w=1,20 do C.addWave(l,1,w%5==0 and 33 or 0) end
 check(C.owed(l)==132,'solo 20 waves = 4 blocks of 33')
 -- Idle for 4 waves, fight in the 5th: 1/5 of the block.
 l=C.ledger('s3');for w=1,5 do C.addWave(l,w==5 and 1 or 0,w==5 and 40 or 0) end
 check(C.owed(l)==8,'idle 4 of 5 waves -> 8 of 40')
 -- Joining for only the last wave of a block: that wave's multiplier on the whole block (as before).
 l=C.ledger('s4');C.addWave(l,1,40)
 check(C.owed(l)==40,'late joiner, one wave, full block')
 -- Mid-block nothing is owed yet (leaving between blocks pays completed blocks only, as before).
 l=C.ledger('s5');C.addWave(l,2,0);C.addWave(l,2,0)
 check(C.owed(l)==0,'nothing owed mid-block')
 check(C.owed(nil)==0,'no ledger')
 return count
end
