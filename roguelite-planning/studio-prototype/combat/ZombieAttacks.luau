-- Server-owned attacks. No remote accepts client hit/target/position claims.
local Players=game:GetService('Players')
local combat=game.ReplicatedStorage:WaitForChild('RogueliteCombat')
local Types=require(combat:WaitForChild('ZombieTypes'))
local Characters=require(script.Parent:WaitForChild('CharacterService'))
local A={}
local states=setmetatable({},{__mode='k'})
-- Slam hits, impacts and serials per Mutant, for Studio QA (RegularEnemyQA). A server table, not
-- attributes, which replicated to every client on every hit though no client read them.
A.tally=setmetatable({},{__mode='k'})
local function tally(npc)
    local t=A.tally[npc];if not t then t={hits=0,serial=0};A.tally[npc]=t end
    return t
end
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
-- The Mutant slams on the move, like the other enemies (EnemyAttacks): until the hammer lands it
-- keeps walking (the chase loop steers) and turning toward its target, and the warning circle
-- travels in front of it. The circle stops where the slam lands.
local TURN_RATE=math.rad(360)
-- Turned by an AlignOrientation, never CFrame writes, which stop a walking Humanoid dead
-- (see EnemyAttacks). release() hands facing back to the Humanoid. Written only once the aim has
-- turned more than ~2 degrees since the last write (each write replicates); the slam lands on
-- s.center, never on the body's facing.
local FACE_DOT=math.cos(math.rad(2))
local function face(root,s)
    if s.faced and s.faced:Dot(s.direction)>=FACE_DOT then return end
    s.faced=s.direction
    local align=root:FindFirstChild('AttackFacing')
    if not align then
        local attachment=Instance.new('Attachment');attachment.Name='AttackFacingAttachment';attachment.Parent=root
        align=Instance.new('AlignOrientation');align.Name='AttackFacing';align.Mode=Enum.OrientationAlignmentMode.OneAttachment
        align.Attachment0=attachment;align.MaxTorque=math.huge;align.Responsiveness=60;align.Parent=root
    end
    align.CFrame=CFrame.lookAt(Vector3.zero,s.direction);align.Enabled=true
end
local function release(npc,h)
    local root=npc:FindFirstChild('HumanoidRootPart');local align=root and root:FindFirstChild('AttackFacing')
    if align then align.Enabled=false end
    if h then h.AutoRotate=true end
end
local function follow(npc,root,target,s,now,circle)
    local dt=math.min(now-(s.last or now),.1);s.last=now
    if target and target.Parent then
        local delta=target.Position-root.Position;local flat=Vector3.new(delta.X,0,delta.Z)
        if flat.Magnitude>.05 then
            local want=flat.Unit;local angle=math.acos(math.clamp(s.direction:Dot(want),-1,1));local step=TURN_RATE*dt
            s.direction=angle<=step and want or CFrame.Angles(0,s.direction:Cross(want).Y>=0 and step or -step,0):VectorToWorldSpace(s.direction)
        end
    end
    face(root,s)
    if not circle then return end
    local center=root.Position+s.direction*Types.Slam.offset
    local ground=workspace:Raycast(center+Vector3.yAxis*8,-Vector3.yAxis*30,s.params)
    if ground then
        s.center=ground.Position
        -- Only replicate real moves; a standing Mutant sends nothing.
        local shown=npc:GetAttribute('SlamPosition')
        if not shown or (shown-s.center).Magnitude>.15 then npc:SetAttribute('SlamPosition',s.center) end
    end
end
function A.update(npc,target)
    if npc:GetAttribute('ZombieType')~='Mutant' then return false end
    local ok,h,root=available(npc);local s=states[npc]
    if not ok then if s then states[npc]=nil end;return false end
    local now=workspace:GetServerTimeNow()
    if not s then s={nextAttack=0};states[npc]=s end
    if s.start then
        h.AutoRotate=false
        local age=now-s.start
        follow(npc,root,target,s,now,age<Types.Slam.impact)
        if age>=Types.Slam.impact and not s.hit then
            s.hit=true -- consume once even when nobody is in range or damage is blocked
            local p=params(npc)
            for _,player in Players:GetPlayers() do
                local char=player.Character;local pr=char and char:FindFirstChild('HumanoidRootPart')
                local ph=char and char:FindFirstChildOfClass('Humanoid')
                if Characters.states[player] and ph and ph.Health>0 and pr and Types.inSlam(s.center,Characters.seen(player,pr)) then -- as their screen shows them
                    -- A low eye-to-body ray prevents damage through arena walls.
                    local origin=root.Position+Vector3.yAxis
                    if not workspace:Raycast(origin,pr.Position-origin,p) then
                        local amount=Characters.contact(player,npc:GetAttribute('SlamDamage') or Types.Slam.damage,nil,npc)
                        local t=tally(npc);t.hits+=1;t.lastDamage=amount
                    end
                end
            end
            tally(npc).lastImpact=now
        end
        if age>=Types.Slam.recovery then
            s.start=nil;release(npc,h);npc:SetAttribute('Attacking',false)
            return false
        end
        return false -- the chase keeps steering through the slam
    end
    if now<s.nextAttack or not target or not target.Parent then return false end
    local th=target.Parent:FindFirstChildOfClass('Humanoid')
    if not th or th.Health<=0 then return false end
    local delta=target.Position-root.Position;local flat=Vector3.new(delta.X,0,delta.Z)
    if flat.Magnitude>Types.Slam.trigger or math.abs(delta.Y)>Types.Slam.maxHeight then return false end
    local p=params(npc)
    if workspace:Raycast(root.Position,target.Position-root.Position,p) then return false end
    local look=root.CFrame.LookVector
    local direction=flat.Magnitude>.05 and flat.Unit or Vector3.new(look.X,0,look.Z).Unit
    local center=root.Position+direction*Types.Slam.offset
    local ground=workspace:Raycast(center+Vector3.yAxis*8,-Vector3.yAxis*30,p)
    if not ground then return false end
    s.center=ground.Position;s.start=now;s.hit=false;s.nextAttack=now+Types.Slam.cooldown
    s.params=p;s.last=now;s.direction=direction;s.faced=nil
    npc:SetAttribute('SlamPosition',s.center)
    tally(npc).serial+=1 -- QA only; the client draws from SlamStart and SlamPosition
    npc:SetAttribute('SlamStart',now);npc:SetAttribute('Attacking',true)
    -- No stop: it slams on the move.
    h.AutoRotate=false;face(root,s)
    return false
end
-- A slam in progress, wind-up to recovery: the chase loop updates it every frame and looks for a
-- new one only on its 0.1 s tick (EnemyAttacks.busy).
function A.busy(npc)
    local s=states[npc];return s~=nil and s.start~=nil
end
-- Drop a slam in progress without its hit (admin Freeze), so it can't land the moment the
-- Mutant updates again. The cooldown stays; the next slam starts a fresh wind-up.
function A.cancel(npc)
    local s=states[npc];if not s or not s.start then return end
    s.start=nil
    release(npc,npc:FindFirstChildOfClass('Humanoid'))
    npc:SetAttribute('Attacking',false)
    npc:SetAttribute('SlamStart',nil) -- the client drops the slam pose and ground warning too
end
return A
