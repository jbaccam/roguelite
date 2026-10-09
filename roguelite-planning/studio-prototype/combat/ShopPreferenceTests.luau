-- Shop items and build preference (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md
-- "Items"; items audit 6.1-6.6). Pure: no Instances, no Play, no rewards. Run with
-- `python roguelite-planning/studio-prototype/combat/run_shop_tests.py build/luau-validation/luau.exe`,
-- or in Studio Edit with the place's modules or fresh copies (tools/FreshRequire):
--   local C=game.ReplicatedStorage.RogueliteCombat
--   print(require(<this module>)(require(C.WeaponCatalog),require(C.CharacterStats),require(C.EconomyConfig),
--     require(C.ShopCatalog),require(C.LevelUpCatalog)))
-- Covers the three family items, Toolbelt, the tier moves and their prices, the fixed card texts,
-- which builds are offered what (ShopCatalog.usable), the preference pools and their weights by
-- copies, the tier-or-lower rule, and that Thrower and the class lists are gone. Not ShopService's
-- dice (Play only; ShopTests rolls the real shop). Returns the number of checks.
return function(Weapons,Stats,E,Catalog,Upgrades)
 local checks=0
 local function check(ok,msg) checks+=1;assert(ok,msg) end
 local function near(a,b,msg) check(math.abs(a-b)<1e-6,msg..': '..tostring(a)..' / '..tostring(b)) end
 local function item(id) local e=Catalog.ById[id];assert(e,'missing shop entry '..id);return e end
 local neutral={};for _,d in Stats.List do neutral[d.id]=d.base end
 local function with(over) local s=table.clone(neutral);for k,v in over do s[k]=v end;return s end

 -- Family items (spec "Items", audit 6.1): Tier I, base 16, cap 5, one stat, the level-up art.
 for _,row in {{'knee','Knee of Justice','MeleeDamage',12,'Melee'},{'fingercannon','Finger Cannon','RangedDamage',12,'Ranged'},{'pocketweather','Pocket Weather','ElementalDamage',10,'Elemental'}} do
  local e=item(row[1])
  check(e.name==row[2] and e.kind=='Item' and e.tier==1 and e.basePrice==16 and e.cap==5,row[1]..': Tier I, 16, cap 5')
  local n=0;for _ in e.modifiers do n+=1 end
  check(n==1 and e.modifiers[row[3]]==row[4] and next(e.percent)==nil,row[1]..': exactly +'..row[4]..' '..row[3])
  check(e.icon==Upgrades.IconIds[row[3]],row[1]..': the '..row[3]..' level-up art')
  check(e.tags[1]==row[5],row[1]..': card reads Item · '..row[5])
 end
 check(item('knee').description=='Your melee weapons (swings, stabs and punches) deal 12% more damage.','Knee text')
 check(item('fingercannon').description=='Your ranged weapons deal 12% more damage: guns, throws, explosives, sprays and streams.','Finger Cannon text')
 check(item('pocketweather').description=='Elemental weapons deal 10% more damage, and all your burns and poison deal 10% more.','Pocket Weather text')
 -- Toolbelt (audit 6.2): +10 Utility Power, base 16.
 local belt=item('toolbelt')
 check(belt.tier==1 and belt.basePrice==16 and belt.cap==5 and belt.modifiers.UtilityPower==10 and belt.structure,'Toolbelt: Tier I, 16, +10 Utility Power, structure')
 check(belt.icon==Upgrades.IconIds.UtilityPower and belt.tags[1]=='Utility','Toolbelt: Utility Power art, reads Item · Utility')
 check(belt.description=='Utility weapons and turrets deal 10% more damage (+10% Utility Power).','Toolbelt text')
 -- Prices for base 16 at shop waves 2 / 5 / 8 / 11 / 15 / 20 (audit 6.1).
 for i,wave in {2,5,8,11,15,20} do near(E.price(16,wave,1),({21,29,36,44,55,68})[i],'base 16 at wave '..wave) end
 -- Tier moves (audit 6.5): one copy each; Bubble Wrap and the Gatling Rig stay Tier IV.
 for _,row in {{'pencil',2,42},{'straws',3,90},{'bouncy',3,80},{'bubble',4,145}} do
  local e=item(row[1]);check(e.tier==row[2] and e.basePrice==row[3] and e.cap==1,row[1]..': Tier '..row[2]..', base '..row[3]..', 1 copy')
 end
 if Catalog.ById.turret_gatling then check(item('turret_gatling').tier==4,'Gatling Rig stays Tier IV') end
 near(E.price(42,8,1),math.floor(42+8+42*8*.1+1e-8),'Pencil price at wave 8')
 -- Ball and Chain is general damage (audit 6.3).
 check(#item('ballchain').tags==1 and item('ballchain').tags[1]=='Damage','Ball and Chain tags: Damage only')
 -- Card kinds: every passive reads Item; turrets read Turret; nothing reads Utility (audit 6.4).
 for _,e in Catalog.List do
  if e.kind~='Weapon' then check(e.kind=='Item' or (e.kind=='Turret' and e.turret~=nil),'card kind for '..e.id..': '..e.kind) end
 end
 -- Fixed texts (audit 6.4).
 local texts={
  bouncy='Throws, cards, yo-yos and magic bolts bounce to 1 more enemy (60-65% damage). Not guns, melee, explosives, fire or gas throws, bowling balls or sprays.',
  pencil='Bullets, throws, cards and magic bolts go through 1 more enemy (70% damage). Not melee, explosives, gas clouds, bowling balls or sprays.',
  straws='+1 shot or throw every attack: guns, rockets, staffs, cards, throws and turrets. Not melee, returning throws (Boomerang, Mjolnir) or sprays.',
  battery='Every 5th hit you land zaps 1 enemy nearby with lightning for 40% damage. Any weapon. Lightning weapons zap 1 more.',
  ketchup="Rocket Launcher, Pandora's Box and Molotov deal 15% more damage.",
  sock='+10 luck: better shop offers and level-up cards, and more heart drops.',
  penny='+6 luck (better shop offers and level-up cards, more heart drops), and 3% of enemy hits miss you.',
  hotsauce='Explosions, fire and gas puddles, lightning chains, sprays and streams reach 15% wider.',
 }
 for id,text in texts do check(item(id).description==text,'text for '..id..': '..item(id).description) end
 check(Upgrades.ById.MeleeDamage.description=='Strengthens melee weapons: swings, stabs and punches.','level-up Melee text')
 check(Upgrades.ById.RangedDamage.description=='Strengthens every non-melee attack: shots, throws, explosives, sprays and streams.','level-up Ranged text')
 -- Thrower is gone, and no shop text claims a stream bounces or pierces.
 for _,e in Catalog.List do
  check(not string.find(e.name..' '..(e.description or ''),'Thrower',1,true),'no Thrower in '..e.id)
  if e.weaponId then local w=Weapons.ById[e.weaponId];check(w and not w.godly and string.find(e.description,w.class or '?',1,true)==1,'weapon offer names its starter class: '..e.id) end
 end

 -- Who is offered what (ShopCatalog.usable; CharacterStats.usesStat for the family stats).
 local function usable(id,carried,stats,turrets) return Catalog.usable(item(id),carried,stats or neutral,turrets or 0) end
 check(usable('knee',{'03'}) and usable('knee',{'19'}) and not usable('knee',{'00'}) and not usable('knee',{'17'}),'Knee: melee weapons only (not the 12-stud Duck)')
 check(usable('fingercannon',{'00'}) and usable('fingercannon',{'13'}) and usable('fingercannon',{'11'}) and usable('fingercannon',{'17'}) and usable('fingercannon',{'29'}),'Finger Cannon: guns, throws, rockets, spray and streams')
 check(not usable('fingercannon',{'03'}) and not usable('fingercannon',{'06','19'}),'Finger Cannon: not for swings')
 check(usable('fingercannon',{'31'}) and usable('fingercannon',{'37'}),'Finger Cannon: the throwing hybrids (Mjolnir, Trident)')
 check(usable('pocketweather',{'30'}) and usable('pocketweather',{'17'}) and usable('pocketweather',{'08'}) and not usable('pocketweather',{'03'}),'Pocket Weather: elemental weapons')
 check(usable('pocketweather',{'03'},with({BurnChance=5})) and usable('pocketweather',{'00'},with({PoisonChance=15})),'Pocket Weather: any build with a burn or poison chance')
 check(not usable('toolbelt',{'00','03'}) and not usable('toolbelt',{}),'Toolbelt: no utility weapon, no turret -> not offered')
 check(usable('toolbelt',{'24'}) and usable('toolbelt',{'05'}) and usable('toolbelt',{'29'}),'Toolbelt: a utility weapon (Nail Gun, Spatula, Washer)')
 check(usable('toolbelt',{'00'},nil,1),'Toolbelt: owning a turret item')
 check(usable('protein',{'03'}) and usable('ballchain',{'00'}) and usable('protein',{}),'general items for every build')
 check(#Catalog.worksWith(item('bouncy'),{'17','28','29'},neutral)==0 and #Catalog.worksWith(item('pencil'),{'17','28','29'},neutral)==0,'spray and streams take no bounce or pierce')
 check(#Catalog.worksWith(item('hotsauce'),{'17','28','29'},neutral)==3,'Hot Sauce works with the Duck, Vacuum and Washer (Area Size widens them)')
 check(#Catalog.worksWith(item('bouncy'),{'22'},neutral)==0 and #Catalog.worksWith(item('pencil'),{'22'},neutral)==0,'Bowling Ball: no Bouncy Ball or Pencil (the cards say so)')
 -- No dead items: each item some non-Godly weapon (or a turret) can use.
 local ids={};for _,w in Weapons.List do if not w.godly then table.insert(ids,w.id) end end
 for _,e in Catalog.List do if e.kind~='Weapon' then check(Catalog.usable(e,ids,neutral,0),'usable by some weapon: '..e.id) end end

 -- Build preference: what each equipped copy wants, weighted by copies.
 check(Catalog.PREFER_ITEMS==.15 and Catalog.PREFER_SAME_WEAPON==.10 and Catalog.PREFER_TYPE==.15,'rates: 15% items, 10% same weapon, 15% shared type')
 for _,t in Weapons.Types do check(Catalog.TypeWants[t]~=nil,'every weapon type wants something: '..t) end
 local wanted={}
 for _,e in Catalog.List do for _,tag in e.tags or {} do wanted[tag]=true end end
 for t,tags in Catalog.TypeWants do for _,tag in tags do check(wanted[tag],t..' wants a tag some item has: '..tag) end end
 local function weight(id,equipped,turrets) return Catalog.preferenceWeight(item(id),equipped,turrets or 0) end
 local katanas={'03','03','03','00'} -- 3 Katanas (melee, Blade) and a Glock (Gun)
 near(weight('knee',katanas),3,'Knee suits the 3 Katana copies')
 near(weight('fingercannon',katanas),1,'Finger Cannon suits the Glock')
 near(weight('broken',katanas),3,'Blade copies want crit')
 near(weight('headband',katanas),1,'Gun copies want attack speed')
 near(weight('protein',katanas),0,'general damage gets no preference')
 near(weight('ballchain',katanas),0,'Ball and Chain no longer counts as melee')
 near(weight('turret_nail',katanas),0,'no Tool weapon and no turret: no turret preference')
 near(weight('turret_nail',{'24'}),1,'Nail Gun (Tool) prefers turret items')
 near(weight('toolbelt',{'24','28'}),2,'two Tool copies prefer Toolbelt twice')
 near(weight('turret_nail',{'00'},1),1,'owning a turret counts as one Tool copy')
 near(weight('toolbelt',{'05'}),1,'Spatula (utility flag) prefers Toolbelt')
 near(weight('pocketweather',{'30','30','14'}),3,'every elemental copy counts')
 near(weight('marshmallow',{'30'}),1,'Elemental type wants burn')
 near(weight('potlid',{'06'}),1,'Blunt wants armor')
 near(weight('cheese',{'01'}),1,'Culinary wants health')
 near(weight('banana',{'21'}),1,'Trick wants dodge and moving')
 near(weight('ketchup',{'11'}),1,'Explosive wants explosion damage')
 near(weight('pencil',{'13','13'}),2,'Thrown copies want pierce')
 near(weight('knee',{'36'}),1,'a Godly copy counts too')
 near(weight('fingercannon',{'31'}),1,'Mjolnir throws: Ranged')
 near(weight('knee',{}),0,'nothing equipped: no preference')
 -- The preferred item pool takes the rolled tier or lower.
 local pool={item('knee'),item('broken'),item('straws'),item('protein'),item('fingercannon')}
 local function names(list) local out={};for _,e in list do table.insert(out,e.id) end;table.sort(out);return table.concat(out,',') end
 local list,weights=Catalog.preferredItems(pool,katanas,0,2)
 check(names(list)=='broken,fingercannon,knee','Tier II roll: Knee (I), Broken Glasses (II), Finger Cannon (I); no Straws (III), no Protein: '..names(list))
 for i,e in list do near(weights[i],weight(e.id,katanas),'pool weight '..e.id) end
 check(names((Catalog.preferredItems(pool,katanas,0,1)))=='fingercannon,knee','Tier I roll: Tier I items only')
 check(names((Catalog.preferredItems(pool,katanas,0,3)))=='broken,fingercannon,knee,straws','Tier III roll: Straws join (the Glock uses it)')
 check(#(Catalog.preferredItems(pool,{},0,4))==0,'nothing equipped: empty pool, the normal roll runs')
 -- Weapon offers: a shared type with an equipped copy, weighted by those copies.
 local wpool={item('weapon_04_1'),item('weapon_07_1'),item('weapon_01_1'),item('weapon_32_1')}
 local typed,tw=Catalog.preferredWeapons(wpool,{'03','03','00'})
 local byId={};for i,e in typed do byId[e.weaponId]=tw[i] end
 check(byId['04']==2 and byId['32']==2 and byId['07']==1 and byId['01']==nil,'2 Katanas + Glock: Kusarigama 2, Excalibur 2, Draco 1, no Frying Pan')
 typed,tw=Catalog.preferredWeapons(wpool,{'32'})
 byId={};for i,e in typed do byId[e.weaponId]=tw[i] end
 check(byId['04']==1 and byId['32']==1 and byId['07']==nil,'Excalibur (Blade, Elemental): one copy counts once')
 typed=Catalog.preferredWeapons(wpool,{'36'});check(#typed==2,'a Godly copy (Reaper: Blade) shares its type')
 check(#(Catalog.preferredWeapons(wpool,{}))==0,'nothing equipped: no shared type')
 -- One pick by weight.
 local a,b={id='a'},{id='b'}
 check(Catalog.pickWeighted({a,b},{1,3},.2)==a and Catalog.pickWeighted({a,b},{1,3},.3)==b and Catalog.pickWeighted({a,b},{1,3},.999)==b,'weighted pick')
 check(Catalog.pickWeighted({a,b},{0,0},.5)==nil and Catalog.pickWeighted({},{},.5)==nil,'no weight: nil')
 check(Catalog.pickWeighted({a,b},{0,2},0)==b,'a zero weight is never picked')
 return checks
end
