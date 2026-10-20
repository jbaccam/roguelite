-- Admin shop controls (2026-10-20): ShopCatalog.drawTier, entryForKey and placeQueued, which
-- ShopService's admin odds and shop queue use. Pure. Run with
-- `python roguelite-planning/studio-prototype/combat/run_shop_tests.py build/luau-validation/luau.exe`.
-- Returns the number of checks.
return function(Catalog,Weapons)
 local checks=0
 local function check(ok,msg) checks+=1;assert(ok,msg) end
 -- Tier odds: one draw across the percents; zero tiers never come up.
 check(Catalog.drawTier({0,0,50,50},.2)==3 and Catalog.drawTier({0,0,50,50},.7)==4,'50/50 III and IV')
 check(Catalog.drawTier({0,0,0,100},0)==4 and Catalog.drawTier({0,0,0,100},.999)==4,'only Tier IV')
 check(Catalog.drawTier({100,0,0,0},.999)==1,'only Tier I')
 check(Catalog.drawTier({0,0,0,0},.5)==nil,'all zero: normal odds')
 check(Catalog.drawTier({1,1,1,1},.6)==3,'totals other than 100 scale')
 for n=0,.99,.01 do local t=Catalog.drawTier({0,30,0,70},n);check(t==2 or t==4,'no zero tier at '..n) end
 -- Keys: a sold weapon at any tier, an item as it is, never a Godly weapon.
 local fart,godly
 for _,w in Weapons.List do if w.name=='Fart Gun' then fart=w end;if w.godly and not godly then godly=w end end
 check(fart~=nil and godly~=nil,'catalog has the Fart Gun and a Godly weapon')
 local e=Catalog.entryForKey('w:'..fart.id,3)
 check(e and e.weaponId==fart.id and e.tier==3,'Fart Gun III')
 check(Catalog.entryForKey('w:'..fart.id,9).tier==4,'tier clamps to IV')
 check(Catalog.entryForKey('w:'..godly.id,2)==nil,'Godly weapons are never shop entries')
 local item;for _,x in Catalog.List do if x.kind~='Weapon' then item=x;break end end
 check(Catalog.entryForKey('i:'..item.id,4)==item,'an item keeps its own tier')
 check(Catalog.entryForKey('i:'..('weapon_'..fart.id..'_1'))==nil,'i: never names a weapon')
 check(Catalog.entryForKey('x:nope')==nil and Catalog.entryForKey(nil)==nil,'unknown keys')
 -- Placement: each queued offer in a different refilled slot, extras dropped.
 local placed=Catalog.placeQueued({'a'},{2,3,4},function() return .5 end)
 check(placed[3]=='a' and placed[2]==nil and placed[4]==nil,'middle slot for draw .5')
 local seq,i={0,0,0},0
 placed=Catalog.placeQueued({'a','b','c','d'},{1,5,6},function() i+=1;return seq[i] or 0 end)
 local n=0;for slot,id in placed do n+=1;check(slot==1 or slot==5 or slot==6,'only refilled slots') end
 check(n==3,'extras beyond the free slots are dropped')
 check(next(Catalog.placeQueued({'a'},{},function() return 0 end))==nil,'no free slot: nothing placed')
 return checks
end
