-- Per-player arena atmosphere; lobby and existing maps (no Center) use the Default profile.
-- The sky, atmosphere and post effects saved in Lighting are never shown: they are whatever an
-- editor last previewed (on 2026-10-02 the desert's EgyptianSky and DesertGrade, which put an
-- Egyptian sky over the lobby and a second sky over every map). Edit MapEnvironments.<Map> instead.
local Players = game:GetService('Players')
local RS = game:GetService('ReplicatedStorage')
local Lighting = game:GetService('Lighting')
local RunService = game:GetService('RunService')
local player = Players.LocalPlayer
local profiles = RS:WaitForChild('MapEnvironments')
local combat = RS:WaitForChild('RogueliteCombat')
local current
local authored = {}
local parked = Instance.new('Folder') -- Client-owned, never replicated or rendered.
parked.Name = 'OriginalEnvironmentParking'
local function isLook(v) return v:IsA('Sky') or v:IsA('Atmosphere') or v:IsA('PostEffect') end
for _, v in Lighting:GetChildren() do
 if isLook(v) then v.Parent = parked end
end
-- Saved children that replicate after this script starts are parked too.
Lighting.ChildAdded:Connect(function(v)
 if isLook(v) and not table.find(authored, v) then
  task.defer(function() if v.Parent == Lighting and not table.find(authored, v) then v.Parent = parked end end)
 end
end)
local function apply(id)
 if id == current then return end
 local profile = profiles:FindFirstChild(id) or profiles.Default
 for _, v in authored do v:Destroy() end
 table.clear(authored)
 for property, value in profile:GetAttributes() do
  -- Renderer choice is Studio-only; all arenas share Realistic with authored local grades.
  if property ~= 'Center' and property ~= 'LightingStyle' and property ~= 'PrioritizeLightingQuality' then
   Lighting[property] = value
  end
 end
 for _, v in profile:GetChildren() do
  local copy = v:Clone()
  table.insert(authored, copy)
  copy.Parent = Lighting
 end
 current = id
 player:SetAttribute('LocalEnvironment', id)
end
local function update()
 local id = combat:GetAttribute('RunMap')
 local profile = type(id) == 'string' and profiles:FindFirstChild(id)
 local root = player.Character and player.Character:FindFirstChild('HumanoidRootPart')
 local center = profile and profile:GetAttribute('Center')
 -- Physical location avoids a dark lobby during group departure and restores it on return.
 local inside = root and center and (root.Position - center).Magnitude < 1500
 apply(inside and id or 'Default')
end
combat:GetAttributeChangedSignal('RunMap'):Connect(update)
player.CharacterAdded:Connect(function() task.defer(update) end)
local elapsed = 0
RunService.Heartbeat:Connect(function(dt)
 elapsed += dt
 if elapsed >= .1 then elapsed = 0; update() end
end)
update()

