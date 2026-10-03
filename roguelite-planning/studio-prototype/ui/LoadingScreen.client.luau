-- Loading screens (ReplicatedFirst.LoadingScreen, a LocalScript beside LoadingScreenUI).
-- Joining or arriving: shows where this player landed (the `loading` teleport data that MatchService
-- sets, else the lobby) and follows real steps: the game loads, the save loads (ProfileLoaded), the
-- character spawns. Then it fades out. Never stays longer than MAX_SECONDS.
-- Leaving: when the server sets the player's TravelTo attribute (MatchService, just before a
-- teleport) the screen for that destination comes up at once and is handed to SetTeleportGui, so
-- the same art covers the trip. Teleport data and TravelTo are cosmetic only.
local ReplicatedFirst=game:GetService('ReplicatedFirst')
local Players=game:GetService('Players')
local TeleportService=game:GetService('TeleportService')
local ContentProvider=game:GetService('ContentProvider')
local LS=require(script.Parent:WaitForChild('LoadingScreenUI'))
local MAX_SECONDS=30
-- Longest wait for AssetPreloader (icons, map-select islands, Armory hall) once the character is in.
local WARM_SECONDS=10
local player=Players.LocalPlayer
local playerGui=player:WaitForChild('PlayerGui')
pcall(function() ReplicatedFirst:RemoveDefaultLoadingScreen() end)

local function arriving()
 local ok,data=pcall(TeleportService.GetLocalPlayerTeleportData,TeleportService)
 local trip=ok and type(data)=='table' and data.loading
 if type(trip)=='table' and LS.valid(trip.map) then return trip.map,trip.difficulty end
 return 'Lobby',nil
end
-- Waits until done() is true, the time runs out, or the screen is gone.
local function waitFor(done,seconds,screenGui)
 local start=os.clock()
 while screenGui.Parent and not done() and os.clock()-start<seconds do task.wait(.1) end
end

-- Arrival -------------------------------------------------------------------------------------
do
 local destId,difficulty=arriving()
 local dest=LS.Dest[destId]
 local gui,screen=LS.screenGui(destId,difficulty)
 gui.Parent=playerGui
 -- AssetPreloader only points the camera at its stages while this is set (the screen hides it).
 playerGui:SetAttribute('LoadingScreenUp',true)
 ContentProvider:PreloadAsync({gui})
 local started=os.clock()
 local function finish()
  playerGui:SetAttribute('LoadingScreenUp',false)
  if gui.Parent then screen:finish(function() gui:Destroy() end) end
 end
 task.delay(MAX_SECONDS,finish)
 task.spawn(function()
  screen:step(dest.going,0,.4)
  if not game:IsLoaded() then game.Loaded:Wait() end
  screen:step('Loading your save',.4,.7)
  waitFor(function() return player:GetAttribute('ProfileLoaded')==true or player:GetAttribute('ProfileLoadFailed')~=nil end,15,gui)
  screen:step(dest.area,.7,.9)
  waitFor(function()
   local c=player.Character
   return c~=nil and c:FindFirstChild('HumanoidRootPart')~=nil
  end,MAX_SECONDS-(os.clock()-started),gui)
  -- The theme images the first screen shows, so the HUD doesn't pop in under the fade.
  local preload={}
  for _,id in LS.Asset do table.insert(preload,id) end
  local loaded=false
  task.spawn(function() pcall(ContentProvider.PreloadAsync,ContentProvider,preload);loaded=true end)
  waitFor(function() return loaded end,3,gui)
  -- Every menu icon and the 3D backdrops, so nothing pops in on the first open. The preloader
  -- starts with the HUD (lobby or arena) and sets AssetWarmReady when it is done.
  screen:step('Getting the menus ready',.9,.99)
  waitFor(function() return playerGui:GetAttribute('AssetWarmReady')==true end,
   math.min(WARM_SECONDS,math.max(0,MAX_SECONDS-(os.clock()-started))),gui)
  finish()
 end)
end

-- Departure -----------------------------------------------------------------------------------
local leaving -- {gui, screen} while a trip is under way
local function cancel()
 if not leaving then return end
 leaving.gui:Destroy();leaving=nil
end
local function depart(destId,difficulty)
 if leaving or not LS.valid(destId) then return end
 local gui,screen=LS.screenGui(destId,difficulty)
 gui.Parent=playerGui
 screen:step(LS.Dest[destId].going,0,.35)
 leaving={gui=gui,screen=screen}
 pcall(TeleportService.SetTeleportGui,TeleportService,gui)
end
local function travelChanged()
 local to=player:GetAttribute('TravelTo')
 if to==nil then cancel() else depart(to,player:GetAttribute('TravelDifficulty')) end
end
player:GetAttributeChangedSignal('TravelTo'):Connect(travelChanged)
travelChanged()
player.OnTeleport:Connect(function(state)
 if state==Enum.TeleportState.Failed then cancel() end
end)
