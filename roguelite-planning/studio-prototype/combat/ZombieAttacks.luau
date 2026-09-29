-- Server-owned attacks. No remote accepts client hit/target/position claims.
local Players=game:GetService('Players')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Types=require(combat:WaitForChild('ZombieTypes'))
local Characters=require(script.Parent:WaitForChild('CharacterService'))
local A={}
local states=setmetatable({},{__mode='k'})
local function params(npc)
    local exclude={npc,workspace:FindFirstChild('RogueliteEnemies')}
    for _,player in Players:GetPlayers() do if player.Character then table.insert(exclude,player.Character) end end
    local p=RaycastParams.new();p.FilterType=Enum.RaycastFilterType.Exclude;p.FilterDescendantsInstances=exclude
    return p
end
local function available(npc)
    local h=npc:FindFirstChildOfClass('Humanoid');local root=npc:FindFirstChild('HumanoidRootPart')
    return npc:IsDescendantOf(workspace) and not npc:GetAttribute('PracticeTarget') and h and h.Health>0 and root and combat:GetAttribute('ZombiesEnabled')==true,h,root
end
function A.update(npc,target)
    if npc:GetAttribute('ZombieType')~='Mutant' then return false end
    local ok,h,root=available(npc);local s=states[npc]
    if not ok then if s then states[npc]=nil end;return false end
    local now=workspace:GetServerTimeNow()
    if not s then s={nextAttack=0};states[npc]=s end
    if s.start then
        h:Move(Vector3.zero);h:MoveTo(root.Position);h.AutoRotate=false
        root.AssemblyLinearVelocity=Vector3.new(0,root.AssemblyLinearVelocity.Y,0)
        local age=now-s.start
        if age>=Types.Slam.impact and not s.hit then
            s.hit=true -- consume once even when nobody is in range or damage is blocked
            local p=params(npc)
            for _,player in Players:GetPlayers() do
                local char=player.Character;local pr=char and char:FindFirstChild('HumanoidRootPart')
                local ph=char and char:FindFirstChildOfClass('Humanoid')
                if Characters.states[player] and ph and ph.Health>0 and pr and Types.inSlam(s.center,pr.Position) then
                    -- A low eye-to-body ray prevents damage through arena walls.
                    local origin=root.Position+Vector3.yAxis
                    if not workspace:Raycast(origin,pr.Position-origin,p) then
                        local amount=Characters.contact(player,npc:GetAttribute('SlamDamage') or Types.Slam.damage)
                        npc:SetAttribute('SlamHits',(npc:GetAttribute('SlamHits') or 0)+1)
                        npc:SetAttribute('LastSlamDamage',amount)
                    end
                end
            end
            npc:SetAttribute('LastSlamImpact',now)
        end
        if age>=Types.Slam.recovery then
            s.start=nil;h.AutoRotate=true;npc:SetAttribute('Attacking',false)
            return false
        end
        return true
    end
    if now<s.nextAttack or not target or not target.Parent then return false end
    local th=target.Parent:FindFirstChildOfClass('Humanoid')
    if not th or th.Health<=0 then return false end
    local delta=target.Position-root.Position;local flat=Vector3.new(delta.X,0,delta.Z)
    if flat.Magnitude>Types.Slam.trigger or math.abs(delta.Y)>Types.Slam.maxHeight then return false end
    local p=params(npc)
    if workspace:Raycast(root.Position,target.Position-root.Position,p) then return false end
    if flat.Magnitude>.05 then root.CFrame=CFrame.lookAt(root.Position,root.Position+flat) end
    local center=root.Position+root.CFrame.LookVector*Types.Slam.offset
    local ground=workspace:Raycast(center+Vector3.yAxis*8,-Vector3.yAxis*30,p)
    if not ground then return false end
    s.center=ground.Position;s.start=now;s.hit=false;s.nextAttack=now+Types.Slam.cooldown
    npc:SetAttribute('SlamPosition',s.center)
    npc:SetAttribute('SlamSerial',(npc:GetAttribute('SlamSerial') or 0)+1)
    npc:SetAttribute('SlamStart',now);npc:SetAttribute('Attacking',true)
    h.AutoRotate=false;h:Move(Vector3.zero);h:MoveTo(root.Position)
    return true
end
-- Drop a slam in progress without its hit (admin Freeze), so it can't land the moment the
-- Mutant updates again. The cooldown stays; the next slam starts a fresh wind-up.
function A.cancel(npc)
    local s=states[npc];if not s or not s.start then return end
    s.start=nil
    local h=npc:FindFirstChildOfClass('Humanoid');if h then h.AutoRotate=true end
    npc:SetAttribute('Attacking',false)
    npc:SetAttribute('SlamStart',nil) -- the client drops the slam pose and ground warning too
end
return A
