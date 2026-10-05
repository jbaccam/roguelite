-- Temporary ordinary server Script in Studio Play; not packaged by Rojo.
assert(game:GetService('RunService'):IsStudio(),'Studio only')
local H=game:GetService('HttpService')
local P=require(game.ServerScriptService.ProfileService)
local S=require(game.ServerScriptService.ShopService)
local E=require(game.ServerScriptService.CombatEffectsService)
local Characters=require(game.ServerScriptService.CharacterService)
local C=game.ReplicatedStorage.RogueliteCombat
local J=require(C.WeaponJournal)
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
while not P.loaded[p] or not Characters.states[p] or not p.Character do task.wait() end
local old=J.clean(P.profiles[p].journal);local run=game.ReplicatedStorage.RogueliteRunState
local oldTest=run:GetAttribute('AdminTestRun');local wasMember=S.isMember(p)
local fixtures={};local checks=0
local function check(v,msg) checks+=1;assert(v,msg) end
local ok,result=xpcall(function()
 S.join(p);run:SetAttribute('AdminTestRun',false)
 local function target(practice)
  local m=Instance.new('Model');m.Name='JournalProbe'
  local r=Instance.new('Part');r.Name='HumanoidRootPart';r.Anchored=true;r.CanCollide=false;r.Position=p.Character.HumanoidRootPart.Position+Vector3.new(0,0,-10);r.Parent=m
  local hum=Instance.new('Humanoid');hum.MaxHealth=100;hum.Health=100;hum.Parent=m
  if practice then m:SetAttribute('PracticeTarget',true) end
  m.Parent=workspace;game:GetService('CollectionService'):AddTag(m,'RogueliteZombie');table.insert(fixtures,m);return m
 end
 local stats=table.clone(Characters.states[p].stats);stats.CritChance=0;stats.Knockback=0;stats.ChainCount=0;stats.BurnChance=0;stats.PoisonChance=0;stats.SlowChance=0
 local d={id='00',owner=p,character=p.Character,stats=stats,slotIndex=1,copyId='journal-probe'}
 local before=J.clean(P.profiles[p].journal);local r=before.weapons['00'] or {damage=0,kills=0}
 local npc=target(false);local actual=E.hit(npc,5,d);E.hit(npc,10000,d)
 local row=P.profiles[p].journal.weapons['00']
 check(actual>0 and math.abs(row.damage-r.damage-100)<.001,'server actual damage, not overkill')
 check(row.kills==r.kills+1,'one kill from lethal hit')
 E.hit(npc,10000,d);check(row.kills==r.kills+1,'dead target cannot count twice')
 E.hit(target(true),20,d);check(row.damage==r.damage+100,'practice target excluded')
 run:SetAttribute('AdminTestRun',true);E.hit(target(false),10000,d)
 check(row.damage==r.damage+100,'admin test damage excluded')
 check(not P.recordItemBuy(p,'soup'),'admin purchase excluded')
 run:SetAttribute('AdminTestRun',false)
 check(P.recordItemBuy(p,'soup'),'validated item purchase recorded')
 check(P.profiles[p].journal.items.soup==(before.items.soup or 0)+1,'item counter')
 P.publish(p);local view=H:JSONDecode(p:GetAttribute('ProfileJournal'))
 check(view.weapons['00'].kills==row.kills,'published snapshot')
 check(P.save(p)==true,'Studio in-memory save path')
 return {passed=true,checks=checks,damage=100,kills=1}
end,debug.traceback)
for _,m in fixtures do m:Destroy() end
P.profiles[p].journal=old;run:SetAttribute('AdminTestRun',oldTest);P.publish(p)
-- Keep an existing player's membership untouched; this fixture is discarded on Stop.
script:SetAttribute('Result',H:JSONEncode({ok=ok,result=result,previousMember=wasMember}))
