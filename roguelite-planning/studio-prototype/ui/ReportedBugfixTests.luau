-- Install temporarily as a ModuleScript and require in a Studio Play client after syncing UI.
-- Preview-only fixtures; no remotes, rewards or persistent profile writes.
local RS=game:GetService('ReplicatedStorage')
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
assert(RunService:IsStudio() and RunService:IsClient(),'Studio Play client required')
local player=Players.LocalPlayer
local T=require(RS.UITheme)
local Shop=require(RS.ShopUI)
local Quests=require(RS.QuestsUI)
local config=require(RS.RogueliteCombat.QuestConfig)
local gui=T.make('ScreenGui',player.PlayerGui,{Name='ReportedBugfixTests',ResetOnSpawn=false,DisplayOrder=250,ZIndexBehavior=Enum.ZIndexBehavior.Sibling})
local run=RS:WaitForChild('RogueliteRunState')
local oldReady=player:GetAttribute('ShopReady')
local oldPlayers=run:GetAttribute('ShopPlayers')
local oldCount=run:GetAttribute('ShopReady')
local checks=0
local function check(value,message) checks+=1;assert(value,message) end
local ok,err=xpcall(function()
 -- A ready teammate used to throw from StoreFX before the weapon detail existed.
 player:SetAttribute('ShopReady',true);run:SetAttribute('ShopPlayers',2);run:SetAttribute('ShopReady',1)
 local shop=Shop.new(player,{label=T.label,icon=T.icon},function() end)
 local fixture={phase='Shop',wave=2,shards=100,baggedShards=0,level=2,pendingLevels=0,revision=1,rerollPrice=5,modifier=1,ready=true,offers={},items={},weapons={
  {id='00',tier=1,copy='preview-a',canCombine=true,sell=10,damage=1234,kills=12},
  {id='00',tier=1,copy='preview-b',canCombine=true,sell=10,damage=432,kills=4},
 }}
 shop.snapshot=function() return fixture end
 shop.selected={kind='Weapon',slot=1,copy='preview-a'}
 for _,size in {Vector2.new(1600,850),Vector2.new(1024,640),Vector2.new(750,311)} do
  local host=T.frame(gui,'ShopFixture',0,0,size.X,size.Y)
  shop:render(host,size.X,size.Y,false)
  task.wait()
  local layout=host.ShopLayout
  check(layout:FindFirstChild('Details')~=nil,'ready roster prevented weapon details')
  check(layout.Details.Body.Combine.Interactable,'matching weapons cannot combine')
  check(layout.Details.Body.RunPerformance.Text:find('1234',1,true)~=nil,'weapon damage total missing')
  check(layout.Details.Body.RunPerformance.Text:find('12 kills',1,true)~=nil,'weapon kill total missing')
  check(layout.ReadyRoster:FindFirstChild('Head_'..player.UserId):FindFirstChild('Check')~=nil,'ready portrait has no check')
  check(layout.StartWave.Caption.Text:find('UNREADY',1,true)~=nil,'ready button cannot unready')
  host:Destroy()
 end
 -- The tracker collapses on completion, preserves a way to claim, and reopens for fresh quests.
 local tracker=Quests.tracker(gui,0,0,{config=config,open=function() end,claim=function() end})
 local daily={}
 for i=1,3 do local q=config.Daily[i];daily[i]={id=q.id,progress=q.target,claimed=false} end
 local view={daily=daily,streak={count=1,today=true}}
 tracker.update(view)
 check(tracker.Root:GetAttribute('Collapsed')==true,'completed daily tracker stays expanded')
 check(tracker.OpenButton.Caption.Text=='CLAIM DAILY REWARDS','collapsed tracker hides unclaimed rewards')
 daily[1].progress=0;tracker.update(view)
 check(tracker.Root:GetAttribute('Collapsed')==false,'new unfinished quest does not expand tracker')
 tracker.Root:Destroy()
 -- Two awarded chests produce two visibly separate copies plus an exact receipt.
 local shots=Quests.totalShots({emeralds=100,chests={Silver=2}},Vector2.new(100,100),Vector2.new(100,40),1)
 check(#shots==2,'reward receipt omitted a reward kind')
 Quests.claimFX(gui,shots)
 local fx=gui:FindFirstChild('ClaimFX')
 check(fx and fx:FindFirstChild('ChestCopy1') and fx:FindFirstChild('ChestCopy2'),'two chests did not burst separately')
 check(fx.ChestReceipt.Text=='+2 SILVER CHESTS','chest receipt has wrong amount')
 check(fx.EmeraldReceipt.Text=='+100 EMERALDS','emerald receipt has wrong amount')
end,debug.traceback)
player:SetAttribute('ShopReady',oldReady);run:SetAttribute('ShopPlayers',oldPlayers);run:SetAttribute('ShopReady',oldCount)
gui:Destroy()
return {passed=ok,checks=checks,error=ok and nil or err}
