-- "Loading your save..." while ProfileService is still loading this player's save (a DataStore
-- outage is retried for about a minute), and "Couldn't load your save" when it gave up, just before
-- the server asks them to rejoin (launch audit S2). Reads the server-set ProfileLoadState attribute:
-- 'loading', 'failed' or nil. A normal load takes well under 2 s, so the banner waits 2 s to show.
local Players=game:GetService('Players')
local player=Players.LocalPlayer
local T=require(game.ReplicatedStorage:WaitForChild('UITheme'))
local C=T.Color
local gui=Instance.new('ScreenGui');gui.Name='SaveStatus';gui.ResetOnSpawn=false;gui.DisplayOrder=90
gui.ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets;gui.Enabled=false;gui.Parent=player:WaitForChild('PlayerGui')
local W,H=440,92
local panel=T.panel(gui,'Panel',0,0,W,H,'panel');panel.AnchorPoint=Vector2.new(.5,0);panel.Position=UDim2.new(.5,0,0,12)
local scale=Instance.new('UIScale');scale.Parent=panel
local title=T.label(panel,'Title','',16,10,W-32,40,28,C.lime)
local sub=T.text(panel,'Sub','',16,52,W-32,26,17,C.muted);sub.TextXAlignment=Enum.TextXAlignment.Center
-- Phones: never wider than the screen less 12 px a side.
local function fit() scale.Scale=math.clamp((gui.AbsoluteSize.X-24)/W,.5,1) end
gui:GetPropertyChangedSignal('AbsoluteSize'):Connect(fit)
local shownFor -- the 'loading' that started the 2 s wait
local function refresh()
 local state=player:GetAttribute('ProfileLoadState')
 if state=='failed' then
  title.Text="COULDN'T LOAD YOUR SAVE";title.TextColor3=C.negative
  sub.Text='Your progress is safe. Please rejoin in a minute.'
  gui.Enabled=true;fit()
 elseif state=='loading' then
  title.Text='LOADING YOUR SAVE...';title.TextColor3=C.lime
  sub.Text='Roblox is slow to answer. Hang on, this can take up to a minute.'
  local mine={};shownFor=mine
  task.delay(2,function() if shownFor==mine and player:GetAttribute('ProfileLoadState')=='loading' then gui.Enabled=true;fit() end end)
 else shownFor=nil;gui.Enabled=false end
end
player:GetAttributeChangedSignal('ProfileLoadState'):Connect(refresh)
refresh()
