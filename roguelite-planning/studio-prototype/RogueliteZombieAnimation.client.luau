-- Procedural R15 locomotion. Runs on every client; no animation upload required.
local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
local tracked = {}
local function track(npc)
    if tracked[npc] then return end
    local joints = {}
    for _, item in npc:GetDescendants() do
        if item:IsA("Motor6D") then joints[item.Name] = item end
    end
    tracked[npc] = {joints = joints, phase = 0, reach = 0, stride = 0}
end
CollectionService:GetInstanceAddedSignal("RogueliteZombie"):Connect(track)
CollectionService:GetInstanceRemovedSignal("RogueliteZombie"):Connect(function(npc) tracked[npc] = nil end)
for _, npc in CollectionService:GetTagged("RogueliteZombie") do track(npc) end
RunService.PreSimulation:Connect(function(dt)
    for npc, state in tracked do
        local root = npc:FindFirstChild("HumanoidRootPart")
        local humanoid = npc:FindFirstChildOfClass("Humanoid")
        if not npc.Parent then tracked[npc] = nil continue end
        if not root or not humanoid then continue end
        local alive = humanoid.Health > 0
        local velocity = root.AssemblyLinearVelocity
        local speed = Vector3.new(velocity.X, 0, velocity.Z).Magnitude
        local blend = 1 - math.exp(-dt * 10)
        state.reach += ((alive and npc:GetAttribute("Chasing") and 1 or 0) - state.reach) * blend
        state.stride += ((alive and math.clamp(speed / 15.2, 0, 1) or 0) - state.stride) * blend
        state.phase += dt * math.max(speed, 1) * 0.75
        local function pose(name, x, y, z)
            local motor = state.joints[name]
            if not motor or not motor:IsDescendantOf(npc) then
                motor = npc:FindFirstChild(name, true)
                state.joints[name] = motor
            end
            if motor then motor.Transform = CFrame.Angles(math.rad(x), math.rad(y or 0), math.rad(z or 0)) end
        end
        for _, side in {"Left", "Right"} do
            local sign = side == "Left" and 1 or -1
            local wave = math.sin(state.phase) * sign
            pose(side.."Shoulder", 83 * state.reach + wave * 3 * state.stride, 0, sign * 3 * state.reach)
            pose(side.."Elbow", 8 * state.reach)
            pose(side.."Wrist", -5 * state.reach)
            pose(side.."Hip", wave * 34 * state.stride)
            pose(side.."Knee", -math.max(0, -wave) * 42 * state.stride)
            pose(side.."Ankle", -wave * 8 * state.stride)
        end
        pose("Waist", -7 * state.reach, 0, math.sin(state.phase) * 2 * state.stride)
        pose("Neck", 5 * state.reach, 0, 3)
    end
end)
