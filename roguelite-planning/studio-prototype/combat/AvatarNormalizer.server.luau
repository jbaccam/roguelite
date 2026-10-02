-- Server-owned spawning from a normalized avatar. Armor, shirts, floating weapons and
-- animations are authored for a standard-proportion R15 body, so tall/Rthro/custom-mesh
-- bodies, layered clothing and animation packs are replaced. Colors, classic clothing,
-- face, hair (layered too) and hat/face accessories stay so players remain recognizable.
local Players=game:GetService('Players')
Players.CharacterAutoLoads=false
-- A match server spawns nobody until its map is in place (MatchService -> ServerRole.setMap).
-- After 30 s players spawn anyway; MatchService sends them back to a lobby if the match is bad.
local Role=require(game:GetService('ServerScriptService'):WaitForChild('ServerRole')) -- sandboxed; this script is not
local function waitForMap()
 local started=os.clock()
 while not Role.ready() and os.clock()-started<30 do task.wait(.1) end
end

local KEEP_ACCESSORIES={
 [Enum.AccessoryType.Hat]=true,
 [Enum.AccessoryType.Face]=true,[Enum.AccessoryType.Eyebrow]=true,[Enum.AccessoryType.Eyelash]=true,
}
local MAX_ACCESSORIES=4 -- hats and face accessories; hair is always kept
local SCALES={HeightScale=1,WidthScale=1,DepthScale=1,HeadScale=1,BodyTypeScale=0,ProportionScale=0}
local ZEROED={
 'Head','Torso','LeftArm','RightArm','LeftLeg','RightLeg',
 'IdleAnimation','WalkAnimation','RunAnimation','JumpAnimation','FallAnimation','ClimbAnimation','SwimAnimation','MoodAnimation',
}

local function normalized(player)
 local source
 if player.UserId>0 then
  local ok,result=pcall(Players.GetHumanoidDescriptionFromUserId,Players,player.UserId)
  if ok then source=result end
 end
 local d=Instance.new('HumanoidDescription')
 if not source then return d end
 for _,key in {'HeadColor','TorsoColor','LeftArmColor','RightArmColor','LeftLegColor','RightLegColor','Shirt','Pants','GraphicTShirt','Face'} do
  d[key]=source[key]
 end
 for key,value in SCALES do d[key]=value end
 for _,key in ZEROED do d[key]=0 end
 local kept,capped={},0
 for _,a in source:GetAccessories(true) do
  -- Most modern hair is layered (it wraps the head); other layered items are clothing, which the
  -- armor shirts replace. A worn helmet still hides hair (ArmorService).
  if a.AccessoryType==Enum.AccessoryType.Hair then
   table.insert(kept,{AssetId=a.AssetId,AccessoryType=a.AccessoryType,IsLayered=a.IsLayered,Order=a.IsLayered and a.Order or nil,Puffiness=a.IsLayered and a.Puffiness or nil})
  elseif not a.IsLayered and KEEP_ACCESSORIES[a.AccessoryType] and capped<MAX_ACCESSORIES then
   capped+=1
   table.insert(kept,{AssetId=a.AssetId,AccessoryType=a.AccessoryType,IsLayered=false})
  end
 end
 d:SetAccessories(kept,true)
 source:Destroy()
 return d
end

local descriptions,loading,normalizedCharacter={},{},{}
local function load(player)
 local ok,err=pcall(player.LoadCharacterWithHumanoidDescription,player,descriptions[player]:Clone())
 if ok then normalizedCharacter[player]=player.Character end
 return ok,err
end
local function spawn(player)
 if loading[player] or player.Parent~=Players then return end
 loading[player]=true
 descriptions[player]=descriptions[player] or normalized(player)
 local ok,err=load(player)
 if not ok then
  warn('AvatarNormalizer: normalized load failed for',player.Name,err)
  descriptions[player]=Instance.new('HumanoidDescription');load(player)
 end
 loading[player]=nil
end

local function added(player)
 player.CharacterAdded:Connect(function(character)
  -- Signals are deferred, so identify our spawns after the load call returns. A
  -- character made by anything else (e.g. a plain LoadCharacter in a test) is replaced.
  while loading[player] do task.wait() end
  if player.Character~=character then return end
  if normalizedCharacter[player]~=character then spawn(player);return end
  character:SetAttribute('NormalizedAvatar',true)
  local h=character:WaitForChild('Humanoid',10);if not h then return end
  if h.RigType~=Enum.HumanoidRigType.R15 then warn('AvatarNormalizer: set Game Settings > Avatar to R15; got',h.RigType) end
  h.Died:Connect(function()
   task.wait(Players.RespawnTime)
   -- RogueliteMeta holds the respawn while the death screen offers Revive / Give Up.
   while player.Parent==Players and player:GetAttribute('HoldRespawn') and player.Character==character do task.wait(.2) end
   if player.Parent==Players and player.Character==character then spawn(player) end
  end)
 end)
 waitForMap()
 spawn(player)
end
-- Server scripts (revive, give up) respawn through the same normalized path.
local respawn=script:FindFirstChild('RespawnPlayer') or Instance.new('BindableFunction')
respawn.Name='RespawnPlayer';respawn.Parent=script
respawn.OnInvoke=function(player) spawn(player);return player.Character end
Players.PlayerAdded:Connect(added)
for _,p in Players:GetPlayers() do task.spawn(added,p) end
Players.PlayerRemoving:Connect(function(p)
 if descriptions[p] then descriptions[p]:Destroy() end
 descriptions[p]=nil;loading[p]=nil;normalizedCharacter[p]=nil
end)
