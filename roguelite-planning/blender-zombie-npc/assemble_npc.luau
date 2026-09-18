-- Run on a selected import of Zombie_R15_Parts.fbx in Studio Edit mode.
-- Creates a separate NPC copy. The selected source remains available.
local selected = game:GetService("Selection"):Get()
assert(#selected == 1 and selected[1]:IsA("Model"), "Select the imported zombie Model")
local source = selected[1]
local names = {"LowerTorso", "UpperTorso", "Head", "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm", "RightHand", "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "RightUpperLeg", "RightLowerLeg", "RightFoot"}
local found = {}
for _, name in names do
    local candidates = {}
    for _, item in source:GetDescendants() do
        if item.Name == name and item:IsA("MeshPart") then table.insert(candidates, item) end
    end
    assert(#candidates == 1, "Expected one MeshPart named " .. name)
    found[name] = candidates[1]
end
assert(not source:FindFirstChildWhichIsA("Bone", true), "Use the Parts FBX, not the skinned FBX")
assert(not workspace:FindFirstChild("Zombie_NPC"), "Zombie_NPC already exists")
local npc = source:Clone()
npc.Name = "Zombie_NPC"
local parts = {}
for _, item in npc:GetDescendants() do
    if item:IsA("MeshPart") and found[item.Name] then parts[item.Name] = item end
end
-- The standard FBX import is upright with Blender Z converted to Roblox Y.
-- World-space bounds account for the importer preserving a part rotation.
local lower = parts.LowerTorso
local cf, sz = lower.CFrame, lower.Size
local worldHeight = math.abs(cf.RightVector.Y)*sz.X + math.abs(cf.UpVector.Y)*sz.Y + math.abs(cf.LookVector.Y)*sz.Z
local unit = worldHeight / 0.67
npc:ScaleTo(npc:GetScale() / unit)
local origin = parts.LowerTorso.Position - Vector3.new(0, 3.14, 0)
local root = Instance.new("Part")
root.Name = "HumanoidRootPart"
root.Size = Vector3.new(1.5, 1.5, 0.8)
root.Transparency = 1
root.CanCollide = false
root.Anchored = true -- Release when the NPC spawn/AI service takes control.
root.CFrame = CFrame.new(origin + Vector3.new(0, 2.95, 0))
root.Parent = npc
parts.HumanoidRootPart = root
local joints = {
    {"Root", "HumanoidRootPart", "LowerTorso", 0,0,2.95},
    {"Waist", "LowerTorso", "UpperTorso", 0,0,3.48},
    {"Neck", "UpperTorso", "Head", 0,0,4.95},
}
for _, side in {"Left", "Right"} do
    local sign = side == "Left" and 1 or -1
    table.insert(joints, {side.."Shoulder", "UpperTorso", side.."UpperArm", sign*1.4,0,4.67})
    table.insert(joints, {side.."Elbow", side.."UpperArm", side.."LowerArm", sign*1.4,0,3.70})
    table.insert(joints, {side.."Wrist", side.."LowerArm", side.."Hand", sign*1.4,-.035,2.91})
    table.insert(joints, {side.."Hip", "LowerTorso", side.."UpperLeg", sign*.43,0,2.99})
    table.insert(joints, {side.."Knee", side.."UpperLeg", side.."LowerLeg", sign*.43,0,1.89})
    table.insert(joints, {side.."Ankle", side.."LowerLeg", side.."Foot", sign*.43,0,.65})
end
for _, j in joints do
    local a,b = parts[j[2]], parts[j[3]]
    local frame = CFrame.new(origin + Vector3.new(j[4], j[6], -j[5]))
    local motor = Instance.new("Motor6D")
    motor.Name = j[1]
    motor.Part0 = a
    motor.Part1 = b
    motor.C0 = a.CFrame:ToObjectSpace(frame)
    motor.C1 = b.CFrame:ToObjectSpace(frame)
    motor.Parent = a
end
for name,p in parts do
    if name ~= "HumanoidRootPart" then
        p.Parent = npc
        p.Anchored = false
        p.Massless = true
        p.CanCollide = false
        p.Color = Color3.new(1,1,1)
    end
end
local humanoid = Instance.new("Humanoid")
humanoid.RigType = Enum.HumanoidRigType.R15
humanoid.AutomaticScalingEnabled = false
humanoid.HipHeight = 2.20
humanoid.BreakJointsOnDeath = false
humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
humanoid.Parent = npc
Instance.new("Animator", humanoid)
npc.PrimaryPart = root
npc.Parent = workspace
game:GetService("Selection"):Set({npc})
print("Zombie_NPC assembled: 15 articulated parts, 15 Motor6Ds, Humanoid and Animator. Validate in Animation Editor before production use.")
