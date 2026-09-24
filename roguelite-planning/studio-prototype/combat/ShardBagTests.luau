-- Temporary normal Studio server Script; excluded from the shipping project.
local RS=game.ReplicatedStorage
local C=RS.RogueliteCombat
local S=require(game.ServerScriptService.ShopService)
local D=require(game.ServerScriptService.ShardDropService)
local Characters=require(game.ServerScriptService.CharacterService)
local p=game.Players:GetPlayers()[1] or game.Players.PlayerAdded:Wait()
while not (S.states[p] and Characters.states[p] and p.Character and p.Character:FindFirstChild('HumanoidRootPart')) do task.wait() end
local other=game.ServerScriptService:FindFirstChild('LevelUpTests')
if other then while not other:GetAttribute('Result') do task.wait() end end
local checked=0
local function check(ok,message) checked+=1;assert(ok,message) end
local function drop(value)
 local root=p.Character.HumanoidRootPart
 local m=Instance.new('Model');m.Name='ShardBagTestDrop';m.Parent=workspace.RogueliteShardDrops
 local d={model=m,owner=p,value=value,origin=root.Position,position=root.Position,born=workspace:GetServerTimeNow()-2,collected=false}
 table.insert(D.drops,d);return d
end
local ok,err=xpcall(function()
 local s=S.states[p];s.shards=0;s.baggedShards=0;s.level=1;s.xp=0;s.pendingLevels=0;s.upgradeOffers={}
 S.phase='Combat';RS.RogueliteRunState:SetAttribute('WaveEndsAt',workspace:GetServerTimeNow()+1000)
 for _=1,5 do drop(1) end
 D.clear(true)
 check(s.baggedShards==5 and s.shards==0 and s.xp==0,'Five leftover units become bags, not immediate currency or XP')
 D.clear(true);check(s.baggedShards==5,'Repeated cleanup cannot duplicate bags')
 for i=1,5 do
  local d=drop(1);check(D.collect(p,d),'Real magnetic pickup accepted')
  D.step(d.started+1)
  check(s.shards==i*2 and s.xp==i*2 and s.baggedShards==5-i,'First five pickups double currency and XP')
 end
 check(S.creditShards(p,1,true) and s.shards==11 and s.xp==11,'Sixth unit returns to normal')
 check(S.creditShards(p,5,false),'Store five more units')
 S.creditShards(p,2,true)
 check(s.baggedShards==3 and s.shards==15,'Multi-unit pickup consumes the same number of bag units')
 S.creditShards(p,5,true)
 check(s.baggedShards==0 and s.shards==23,'Partially covered pickup conserves value')
 local before=s.shards;local xp=s.xp
 S.creditShards(p,7,false)
 check(s.shards==before and s.xp==xp and s.baggedShards==7,'Banking never awards XP or currency')
 drop(2);D.clear(false);check(s.baggedShards==7,'Practice abort does not add bags')
 S.phase='Shop';check(not S.creditShards(p,1,true),'No pickup awards outside combat')
 check(not S.creditShards(p,-1,false) and not S.creditShards(p,0/0,false),'Invalid values rejected')
 S.phase='Combat';drop(2);check(S.finishWave(),'Wave transition completes')
 check(s.baggedShards==9,'Unused bags survive and new leftovers add to them')
 check(Characters.states[p].folder:GetAttribute('BaggedShards')==9,'Bag count replicated to HUD')
 -- Leave normal test state, with visible bags and earned choices for client inspection.
 s.level=4;s.pendingLevels=3;s.upgradeOffers={};S.prepareUpgrades(p);S.publish(p)
end,debug.traceback)
D.clear(false)
S.phase='Shop';RS.RogueliteRunState:SetAttribute('Phase','Shop');C:SetAttribute('ZombiesEnabled',false)
script:SetAttribute('Result',game.HttpService:JSONEncode({passed=ok,assertions=checked,error=err}))
print('ShardBagTests',ok,checked,err)
