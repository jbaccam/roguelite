-- Save migration checks for Thrower -> Chef (2026-10-09, plans/2026-10-09-chef-roster-weapon-types-design.md
-- "Save, product and quest migration"). Runs ProfileService's real source with stand-ins for Roblox
-- services: no DataStores, no players, no background loops, nothing saved. Old-save fixtures go
-- through P.migrate (what every load runs): Thrower only, Juggler only, both, Thrower picked,
-- Brawler + Frying Pan picked, a fresh profile, an already migrated one (twice = once), then the
-- ClassThrower receipt and both load paths (Studio's fresh profile, a live save from a fake lock).
-- `ProfileMigrationTests(source, modules)`: source = ProfileService.luau's text; modules = real
-- WeaponCatalog, MonetizationConfig, ChestConfig and PetConfig (ArmorCatalog and WeaponJournal
-- optional). Returns the number of checks. Studio Edit, with tools/dev_server.py running:
--   local HS=game:GetService('HttpService');local base='http://127.0.0.1:8934/studio-prototype/'
--   local Fresh=loadstring(HS:GetAsync(base..'tools/FreshRequire.luau?t='..os.clock(),true))()(base)
--   local C=game.ReplicatedStorage.RogueliteCombat
--   print(loadstring(Fresh.source('combat/ProfileMigrationTests.luau'))()(Fresh.source('combat/ProfileService.luau'),
--    {WeaponCatalog=Fresh.require('WeaponCatalog'),MonetizationConfig=Fresh.require('MonetizationConfig'),
--     ChestConfig=require(C.ChestConfig),PetConfig=require(C.PetConfig),ArmorCatalog=require(C.ArmorCatalog)}))
return function(source,modules)
 local checks=0
 local function check(condition,message) assert(condition,message);checks+=1 end
 local W,Money=modules.WeaponCatalog,modules.MonetizationConfig
 for _,name in {'WeaponCatalog','MonetizationConfig','ChestConfig','PetConfig'} do assert(modules[name],'ProfileMigrationTests needs '..name) end
 local function copy(v) if type(v)~='table' then return v end;local c={};for k,x in v do c[k]=copy(x) end;return c end
 local function same(a,b)
  if type(a)~='table' or type(b)~='table' then return a==b end
  for k,v in a do if not same(v,b[k]) then return false end end
  for k in b do if a[k]==nil then return false end end
  return true
 end
 local function set(t) local out={};for k,v in t do if v then table.insert(out,k) end end;table.sort(out);return table.concat(out,',') end

 -- ProfileService with stand-ins. studio: RunService:IsStudio(). lock: ProfileLock's stand-in.
 local noop=function() end
 local Players={PlayerAdded={Connect=noop},PlayerRemoving={Connect=noop},GetPlayers=function() return {} end}
 local function load(studio,lock)
  local folder={}
  function folder:WaitForChild(name) return {Name=name} end
  function folder:FindFirstChild() return nil end -- no QuestService or TutorialConfig: both optional
  local services={Players=Players,RunService={IsStudio=function() return studio end},
   HttpService={GenerateGUID=function() return 'test-job' end,JSONEncode=function() return '{}' end},
   DataStoreService={GetDataStore=function(_,name) return {name=name} end}, -- only ever handed to the lock stand-in
   ServerScriptService=folder,ReplicatedStorage={WaitForChild=function() return folder end}}
  local stand={ -- modules a migration never needs
   ProfileLock=lock or {claim=function() error('no DataStore here') end,write=function() error('no DataStore here') end},
   SkillTreeConfig={serialize=function() return '' end},EggConfig={},AdminConfig={isTestRun=function() return false end},
   ArmorCatalog={StudioGrant={},Slots={},pieceId=function(set,slot) return set..'.'..slot end},
   WeaponJournal={clean=function(j) return type(j)=='table' and j or {} end,view=function() return {} end},
  }
  local env=setmetatable({
   game={JobId='',GetService=function(_,name) return assert(services[name],name) end,ReplicatedStorage=services.ReplicatedStorage,BindToClose=noop},
   workspace={GetAttribute=noop},task={spawn=noop,wait=noop,delay=noop,defer=noop},Random={new=function() return {} end},warn=noop,
   require=function(token) local name=type(token)=='table' and token.Name;return assert(modules[name] or stand[name],'no stand-in for '..tostring(name)) end,
  },{__index=getfenv(0)})
  local fn,err=loadstring(source,'=ProfileService');assert(fn,err)
  setfenv(fn,env)
  local P=fn()
  P.publish=noop -- attributes and the daily view are not part of a migration
  return P
 end
 local function player(id) return {UserId=id,Name='Test'..id,Parent=Players,SetAttribute=noop,GetAttribute=noop,Kick=noop} end
 local P=load(true)
 check(type(P.migrate)=='function','ProfileService has P.migrate')

 -- The roster this migration follows (the core change): Pan is Chef's, Gloves are Brawler's.
 check(W.ById['01'].class=='Chef' and W.ById['14'].class=='Chef' and W.ById['05'].class=='Chef','Frying Pan, Molotov and Spatula are Chef weapons')
 check(W.ById['19'].class=='Brawler' and W.ById['03'].class=='Brawler','Boxing Gloves and Katana are Brawler weapons')
 check(W.ById['12'].class=='Juggler' and W.ById['17'].class=='Juggler','Boomerang and Rubber Duck are Juggler weapons')
 check(W.ById['36'].godly and W.ById['36'].class==nil,"Reaper's Scythe is Godly, no class")

 -- Old live saves: the three starting classes with the Frying Pan, Glock and Magic Staff (the fresh
 -- profile before 2026-10-09), Brawler + Pan picked, plus `extra` (replaces whole fields).
 local function old(extra)
  local d={version=1,emeralds=500,bought=0,classes={Brawler=true,Gunner=true,Mage=true},
   weapons={['01']={tier=2,have=1},['00']={tier=1,have=0},['30']={tier=1,have=3}},
   chests={Gold=1},pity={Legendary=4,Godly=2},loadout={class='Brawler',weapon='01'},
   quests={classWins={Brawler=true},unlocks={}},tutorial={step='Done'}}
  for k,v in extra or {} do d[k]=v end
  return d
 end
 local function with(base,more) local t=copy(base);for k,v in more do t[k]=v end;return t end
 local OLD_WEAPONS=old().weapons
 -- Migrates a copy, checks nothing owned was lost and that a second run changes nothing.
 local function migrate(save,name)
  local after=P.migrate(copy(save))
  for id,rec in save.weapons or {} do
   local r=after.weapons[id];check(r~=nil and r.tier==rec.tier and r.have==rec.have,name..': keeps weapon '..id..' with its tier and copies')
  end
  check(after.emeralds==(save.emeralds or 0),name..': emeralds untouched')
  check(same(P.migrate(copy(after)),after),name..': running it twice = once')
  check(after.classes.Thrower==nil,name..': no Thrower class left')
  return after
 end

 -- 1. Thrower only: Thrower is Chef, Brawler's Pan pick goes to the Gloves, wins and chests carry over.
 local d=migrate(old({classes={Brawler=true,Gunner=true,Mage=true,Thrower=true},
  weapons=with(OLD_WEAPONS,{['12']={tier=3,have=1},['14']={tier=1,have=2}}),
  quests={classWins={Brawler=true,Thrower=true},unlocks={WaveRider=true}},chests={Thrower=2,Gold=1}}),'Thrower only')
 check(set(d.classes)=='Brawler,Chef,Gunner,Mage','Thrower only: owns Chef instead, got '..set(d.classes))
 check(same(d.weapons['19'],{tier=1,have=0}),'Thrower only: Brawler gets the Boxing Gloves')
 check(same(d.weapons['01'],{tier=2,have=1}),'Thrower only: the Pan (Chef default) stays at Tier II')
 check(d.loadout.class=='Brawler' and d.loadout.weapon=='19','Thrower only: Brawler + Pan becomes Brawler + Gloves')
 check(d.quests.classWins.Chef==true and d.quests.classWins.Thrower==nil and d.quests.classWins.Brawler==true,'Thrower only: a Thrower map win counts for Chef')
 check(d.quests.unlocks.WaveRider==true,'Thrower only: Wave Rider stays claimed')
 check(same(d.chests,{Wooden=2,Gold=1}),'Thrower only: old Thrower chests are still Wooden')
 -- Only the Thrower class at all (no starting three): Chef gets its default, the Frying Pan.
 d=migrate({classes={Thrower=true},weapons={['12']={tier=1,have=0}},loadout={}},'Thrower alone')
 check(set(d.classes)=='Chef' and same(d.weapons['01'],{tier=1,have=0}),'Thrower alone: Chef with the Frying Pan')
 check(next(d.loadout)==nil,'Thrower alone: no pick stays no pick')

 -- 2. Juggler only: nothing renamed; the old Juggler default (Gloves, Brawler's now) goes to the Duck.
 d=migrate(old({classes={Brawler=true,Gunner=true,Mage=true,Juggler=true},
  weapons=with(OLD_WEAPONS,{['17']={tier=1,have=0},['19']={tier=2,have=0}}),loadout={class='Juggler',weapon='19'}}),'Juggler only')
 check(set(d.classes)=='Brawler,Gunner,Juggler,Mage','Juggler only: same classes, no Chef')
 check(d.loadout.class=='Juggler' and d.loadout.weapon=='17','Juggler only: Juggler + Gloves becomes Juggler + Rubber Duck')
 check(same(d.weapons['19'],{tier=2,have=0}),'Juggler only: the Gloves keep Tier II (and are Brawler\'s default now)')

 -- 3. Thrower and Juggler: both kept; a Boomerang pick (Juggler's now) still fits Juggler.
 d=migrate(old({classes={Brawler=true,Gunner=true,Mage=true,Thrower=true,Juggler=true},
  weapons=with(OLD_WEAPONS,{['12']={tier=2,have=0},['13']={tier=1,have=1},['17']={tier=1,have=0}}),loadout={class='Juggler',weapon='12'}}),'Thrower and Juggler')
 check(set(d.classes)=='Brawler,Chef,Gunner,Juggler,Mage','Thrower and Juggler: Chef and Juggler, got '..set(d.classes))
 check(d.loadout.class=='Juggler' and d.loadout.weapon=='12','Thrower and Juggler: Juggler + Boomerang stays')

 -- 4. Thrower picked: the pick is a Chef pick; its starter stays when it fits Chef.
 local thrower={classes={Brawler=true,Gunner=true,Mage=true,Thrower=true},weapons=with(OLD_WEAPONS,{['12']={tier=1,have=0},['14']={tier=3,have=0},['36']={tier=1,have=0}})}
 d=migrate(old(with(thrower,{loadout={class='Thrower',weapon='14'}})),'Thrower + Molotov')
 check(d.loadout.class=='Chef' and d.loadout.weapon=='14','Thrower + Molotov becomes Chef + Molotov')
 d=migrate(old(with(thrower,{loadout={class='Thrower',weapon='12'}})),'Thrower + Boomerang')
 check(d.loadout.class=='Chef' and d.loadout.weapon=='01','Thrower + Boomerang (Juggler\'s now) becomes Chef + Frying Pan')
 d=migrate(old(with(thrower,{loadout={class='Thrower',weapon='36'}})),'Thrower + Godly')
 check(d.loadout.class=='Chef' and d.loadout.weapon=='36','Thrower + an owned Godly becomes Chef + that Godly')

 -- 5. Brawler + Pan and other Brawler picks.
 d=migrate(old(),'Brawler + Pan')
 check(d.loadout.class=='Brawler' and d.loadout.weapon=='19','Brawler + Pan becomes Brawler + Boxing Gloves')
 check(same(d.weapons['01'],{tier=2,have=1}) and same(d.weapons['19'],{tier=1,have=0}),'Brawler + Pan: keeps the Pan, gains the Gloves')
 check(set(d.classes)=='Brawler,Gunner,Mage','Brawler + Pan: no class added')
 d=migrate(old({weapons=with(OLD_WEAPONS,{['36']={tier=1,have=0}}),loadout={class='Brawler',weapon='36'}}),'Brawler + Godly')
 check(d.loadout.weapon=='36','Brawler + an owned Godly stays')
 d=migrate(old({loadout={class='Brawler',weapon='36'}}),'Brawler + unowned Godly')
 check(d.loadout.weapon=='19','Brawler + a Godly not owned goes to the Gloves')
 d=migrate(old({weapons=with(OLD_WEAPONS,{['03']={tier=4,have=0}}),loadout={class='Brawler',weapon='03'}}),'Brawler + Katana')
 check(d.loadout.weapon=='03','Brawler + an owned Katana stays')
 d=migrate(old({loadout={class='Gunner',weapon='01'}}),'Gunner + Pan')
 check(d.loadout.class=='Gunner' and d.loadout.weapon=='00','Gunner + Pan goes to the Glock')
 d=migrate(old({loadout={class='Handyman',weapon='24'}}),'Handyman not owned')
 check(next(d.loadout)==nil,'a pick for a class not owned is dropped (the lobby starts on Brawler)')
 d=migrate(old({loadout={class='Thrower',weapon='12'}}),'Thrower picked, not owned')
 check(next(d.loadout)==nil and d.classes.Chef==nil,'a Thrower pick without the class gives no Chef and is dropped')
 d=migrate(old({loadout='junk'}),'junk pick')
 check(type(d.loadout)=='table' and next(d.loadout)==nil,'a malformed pick becomes no pick')

 -- 6. Fresh profile: Brawler, Gunner and Mage with Boxing Gloves, Glock and Magic Staff.
 d=P.migrate({})
 check(set(d.classes)=='Brawler,Gunner,Mage','fresh: Brawler, Gunner, Mage')
 local ids={};for id,r in d.weapons do table.insert(ids,id);check(same(r,{tier=1,have=0}),'fresh: '..id..' at Tier I') end
 table.sort(ids);check(table.concat(ids,',')=='00,19,30','fresh: Glock, Boxing Gloves, Magic Staff, got '..table.concat(ids,','))
 check(next(d.loadout)==nil and d.emeralds==0,'fresh: no pick, no emeralds')
 check(same(P.migrate(copy(d)),d),'fresh: running it again changes nothing')

 -- 7. Already migrated: a Chef save is left exactly as it is.
 local done=old({classes={Brawler=true,Gunner=true,Mage=true,Chef=true},
  weapons=with(OLD_WEAPONS,{['19']={tier=1,have=0},['05']={tier=2,have=1}}),loadout={class='Chef',weapon='05'},
  quests={classWins={Chef=true},unlocks={WaveRider=true}},picks={},journal={}})
 local once=P.migrate(copy(done))
 check(same(once.classes,done.classes) and same(once.weapons,done.weapons) and same(once.loadout,done.loadout) and same(once.quests,done.quests),'already migrated: classes, weapons, pick and quests unchanged')
 check(same(P.migrate(copy(once)),once),'already migrated: twice = once')

 -- 8. The ClassThrower receipt: same key and product id, grants Chef and its Frying Pan.
 local product=Money.Products.ClassThrower
 check(product.class=='Chef' and product.productId==3716086758 and Money.byProductId(3716086758)=='ClassThrower','ClassThrower: same product id, grants Chef')
 local function grantReceipt(pl) -- the fields RogueliteMeta's grantProduct passes
  return P.grant(pl,{emeralds=product.emeralds,paid=true,chests=product.chests,class=product.class,rerolls=product.rerolls,banishes=product.banishes,signatureUpgrades=product.signatureUpgrades})
 end
 local ana=player(1);P.profiles[ana]=P.migrate({});P.loaded[ana]=true
 check(grantReceipt(ana),'ClassThrower receipt: granted')
 d=P.profiles[ana]
 check(d.classes.Chef==true and d.classes.Thrower==nil and same(d.weapons['01'],{tier=1,have=0}),'ClassThrower receipt: Chef with a new Frying Pan')
 check(d.emeralds==0 and d.bought==0,'ClassThrower receipt: no emeralds on the side')
 local ben=player(2);P.profiles[ben]=P.migrate(copy(old()));P.loaded[ben]=true
 grantReceipt(ben)
 check(P.profiles[ben].classes.Chef and same(P.profiles[ben].weapons['01'],{tier=2,have=1}),'ClassThrower receipt: a Pan already owned keeps its tier')
 local cal=player(3);P.profiles[cal]=P.migrate({});P.loaded[cal]=true
 P.grant(cal,{class='Thrower'})
 check(P.profiles[cal].classes.Chef and P.profiles[cal].classes.Thrower==nil,'a grant still naming Thrower (older server) gives Chef')
 -- Starters after the receipt (the server rule, same as validLoadout).
 check(P.setLoadout(ana,'Chef','01'),'Chef + Frying Pan can be picked')
 local ok,why=P.setLoadout(ana,'Brawler','01');check(not ok and why=='Choose a weapon for your class','Brawler + Frying Pan is refused')
 check(P.setLoadout(ana,'Brawler','19') and P.profiles[ana].loadout.weapon=='19','Brawler + Boxing Gloves can be picked')
 ok,why=P.setLoadout(ana,'Thrower','01');check(not ok and why=='Class locked','the Thrower class is gone')
 P.addCopies(P.profiles[ana],'36',1);check(P.setLoadout(ana,'Mage','36'),'an owned Godly fits any class')
 ok,why=P.buyClass(ana,'Thrower',400);check(not ok and why=='Unknown class','Thrower cannot be bought with emeralds')

 -- 9. Load paths. Studio: always the in-memory fresh profile, migrated, never a DataStore.
 local tom=player(4);P.load(tom)
 check(set(P.profiles[tom].classes)=='Brawler,Gunner,Mage' and P.profiles[tom].weapons['19']~=nil and P.profiles[tom].weapons['01']==nil,'Studio load: fresh profile with the Gloves, no Pan')
 -- Live: a Thrower save from the (stand-in) lock comes out as Chef; loading writes nothing.
 local writes=0
 local saved=old({classes={Brawler=true,Gunner=true,Mage=true,Thrower=true},weapons=with(OLD_WEAPONS,{['12']={tier=1,have=0}}),loadout={class='Thrower',weapon='12'}})
 local live=load(false,{claim=function() return copy(saved),'ok' end,write=function() writes+=1;return true end})
 local una=player(5);live.load(una)
 d=live.profiles[una]
 check(d and live.loaded[una] and set(d.classes)=='Brawler,Chef,Gunner,Mage','live load: Thrower save loads as Chef')
 check(d.loadout.class=='Chef' and d.loadout.weapon=='01' and d.tutorial.step=='Done','live load: Thrower + Boomerang loads as Chef + Frying Pan')
 check(writes==0,'live load: nothing written while loading')
 return checks
end
