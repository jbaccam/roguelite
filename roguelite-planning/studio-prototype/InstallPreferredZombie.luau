-- Edit-mode integration; run after CreateNativeZombie.luau if reconstructing.
local CollectionService = game:GetService("CollectionService")
local display = assert(workspace:FindFirstChild("Zombie_R15_ProvidedTextures_Studio"), "Preferred zombie must exist")
assert(display:FindFirstChild("HumanoidRootPart") and display:FindFirstChildOfClass("Humanoid"), "Incomplete rig")
local folder = game.ServerStorage:FindFirstChild("RogueliteNPCs")
if not folder then folder = Instance.new("Folder"); folder.Name = "RogueliteNPCs"; folder.Parent = game.ServerStorage end
-- Stage replacement before removing the obsolete imported enemy.
local replacement = display:Clone()
replacement.Name = "Zombie_NPC"
replacement:SetAttribute("ComparisonPreview", nil)
replacement:SetAttribute("StaticDisplay", nil)
replacement:SetAttribute("VisualSource", "Zombie_R15_ProvidedTextures_Studio")
CollectionService:RemoveTag(replacement, "RogueliteZombie")
for _, item in replacement:GetDescendants() do
    if item:IsA("BaseScript") then item:Destroy()
    elseif item:IsA("Motor6D") then item.Transform = CFrame.identity
    elseif item:IsA("BasePart") then
        item.Anchored = item.Name == "HumanoidRootPart"
        item.CanCollide = item.Name == "UpperTorso" or item.Name == "LowerTorso"
    end
end
replacement.PrimaryPart = replacement.HumanoidRootPart
replacement.Humanoid.WalkSpeed = 13.5
replacement.Humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
local old = folder:FindFirstChild("Zombie_NPC")
if old then old:Destroy() end
local imported = folder:FindFirstChild("Zombie_ImportedSource")
if imported then imported:Destroy() end
replacement.Parent = folder
CollectionService:RemoveTag(display, "RogueliteZombie")
display:SetAttribute("StaticDisplay", true)
display:SetAttribute("ComparisonPreview", nil)
for _, item in display:GetDescendants() do
    if item:IsA("BasePart") then item.Anchored = true; item.CanCollide = false
    elseif item:IsA("Motor6D") then item.Transform = CFrame.identity end
end
return {template=replacement:GetFullName(),display=display:GetFullName(),speed=13.5,count=5}
