-- Deterministic client presentation. Server timestamps align the slam with damage.
local M={}
local function cf(x,y,z,lift,forward)
    return CFrame.new(0,lift or 0,-(forward or 0))*CFrame.Angles(math.rad(x or 0),math.rad(y or 0),math.rad(z or 0))
end
local function smooth(t) return t*t*(3-2*t) end
-- Shared constants and scratch: pose() runs per zombie per frame. `out` (optional) is the
-- caller's buffer, cleared and refilled so it equals a fresh table.
local SIDES={'Left','Right'}
local SLAM_KEYS={'waist','neck','shoulder','elbow','wrist','root','lift'}
local slamValues={}
local slamKeys={
    {t=0,waist=-26,neck=16,shoulder=25,elbow=12,wrist=-8,root=-.03,lift=0},
    {t=.32,waist=-16,neck=12,shoulder=154,elbow=18,wrist=-12,root=-.08,lift=.08},
    {t=.46,waist=-48,neck=24,shoulder=60,elbow=4,wrist=8,root=-.06,lift=-.80},
    {t=.58,waist=-46,neck=22,shoulder=58,elbow=7,wrist=4,root=-.05,lift=-.73},
    {t=1,waist=-26,neck=16,shoulder=25,elbow=12,wrist=-8,root=-.03,lift=0},
}
function M.slam(age,out)
    local a,b=slamKeys[1],slamKeys[2]
    for i=2,#slamKeys do a,b=slamKeys[i-1],slamKeys[i];if age<=b.t then break end end
    local alpha=math.clamp((age-a.t)/(b.t-a.t),0,1)
    alpha=(b.t==.46) and alpha*alpha or smooth(alpha)
    local v=slamValues;for _,key in SLAM_KEYS do v[key]=a[key]+(b[key]-a[key])*alpha end
    local poses=out or {};table.clear(poses)
    poses.Root=cf(0,0,0,v.root);poses.Waist=cf(v.waist,0,0,v.lift);poses.Neck=cf(v.neck)
    for _,side in SIDES do
        local sign=side=='Left' and 1 or -1
        poses[side..'Shoulder']=cf(v.shoulder,0,sign*-4)
        poses[side..'Elbow']=cf(v.elbow);poses[side..'Wrist']=cf(v.wrist)
        poses[side..'Hip']=cf(7);poses[side..'Knee']=cf(-13);poses[side..'Ankle']=cf(6)
    end
    return poses
end
-- Regular and baby zombies hold both arms straight out while chasing. `reach`
-- (0..1) fades between hanging arms and that reach; the mutant keeps its hunch.
-- 92 deg offsets the 9 deg forward torso lean so the arms read level in world.
local REACH_SHOULDER,REACH_ELBOW=92,8
local function mix(a,b,t) return a+(b-a)*t end
-- The Bloater (round 10): a heavy side-to-side waddle on short legs, arms held out clear of its belly
-- with a small swing against the same-side leg. Armed (attackAge: from EnemyAttackStart, the fuse
-- ExploderService bursts), it braces over 0.35 s: knees bent wide, arms flung out and up, chest and
-- head thrown back while the belly swells (Round10World scales it locally). Roll sign: +z turns a
-- hanging arm toward +X, so outward is -z on the left (s=1) and +z on the right (s=-1).
function M.bloater(phase,stride,clock,armedAge,out)
    local step=math.sin(phase);local bounce=math.cos(phase*2);local idle=math.sin(clock*1.7)
    local brace=armedAge and armedAge>=0 and smooth(math.clamp(armedAge/.35,0,1)) or 0
    local tremble=brace>0 and math.sin(clock*41)*1.6*brace or 0
    local poses=out or {};table.clear(poses)
    for _,side in SIDES do
        local s=side=='Left' and 1 or -1;local wave=step*s
        poses[side..'Shoulder']=cf(mix(10-wave*16*stride+idle*2,28,brace),0,s*mix(-24-math.max(0,wave)*4*stride,-74,brace)+tremble*s)
        poses[side..'Elbow']=cf(mix(16+math.max(0,wave)*10*stride,8,brace))
        poses[side..'Wrist']=cf(mix(-4,10,brace))
        poses[side..'Hip']=cf(mix(4+wave*22*stride,10,brace),0,s*mix(1,-7,brace))
        poses[side..'Knee']=cf(mix(-8-math.max(0,-wave)*28*stride,-24,brace))
        poses[side..'Ankle']=cf(mix(4-wave*7*stride,13,brace),0,s*mix(0,7,brace))
    end
    poses.Root=cf(0,0,0,mix(-.04+bounce*.05*stride,-.32,brace))
    -- The waddle rolls the whole body over each planted foot (z), with a little twist (y).
    poses.Waist=cf(mix(-3+bounce*1.2*stride,9,brace),mix(math.cos(phase)*3*stride,0,brace),mix(step*8*stride,0,brace)+tremble*.6,idle*.03)
    poses.Neck=cf(mix(2+idle*1.5-bounce*1.2*stride,16,brace),0,mix(-step*4*stride,0,brace))
    return poses
end
function M.pose(kind,phase,stride,reach,clock,attackAge,attackImpact,attackRecovery,out)
    if kind=='Mutant' and attackAge and attackAge>=0 and attackAge<=1 then return M.slam(attackAge,out) end
    if kind=='Bloater' then return M.bloater(phase,stride,clock,attackAge,out) end
    local step=math.sin(phase);local bounce=math.cos(phase*2);local idle=math.sin(clock*2.1)*.012
    local poses=out or {};table.clear(poses);local mutant=kind=='Mutant';local baby=kind=='Baby'
    reach=mutant and 0 or math.clamp(reach or 0,0,1)
    for _,side in SIDES do
        local s=side=='Left' and 1 or -1;local wave=step*s
        -- Reaching arms keep a small bob that still opposes the same-side leg.
        local hang=(mutant and 25 or baby and 16 or 12)-wave*(mutant and 15 or 24)*stride
        local out=REACH_SHOULDER-wave*6*stride
        poses[side..'Shoulder']=cf(mix(hang,out,reach),0,s*mix(-4,3,reach),wave*.025*stride)
        poses[side..'Elbow']=cf(mix((mutant and 12 or 16)+math.max(0,wave)*8*stride,REACH_ELBOW+math.sin(phase-.4)*s*2*stride,reach))
        poses[side..'Wrist']=cf(mutant and -8 or -5)
        poses[side..'Hip']=cf((mutant and 5 or 6)+wave*(mutant and 22 or 31)*stride)
        poses[side..'Knee']=cf((mutant and -8 or -12)-math.max(0,-wave)*(mutant and 24 or 34)*stride)
        poses[side..'Ankle']=cf((mutant and 3 or 6)-wave*8*stride)
    end
    poses.Root=cf(0,0,0,mutant and -.03 or -.045)
    poses.Waist=cf((mutant and -26 or -9)+bounce*1.5*stride,math.cos(phase)*2*stride,step*(mutant and 4 or 3.5)*stride,idle+bounce*(mutant and .08 or baby and .045 or .055)*stride)
    poses.Neck=cf((mutant and 16 or 6)-math.cos(phase*2-.35)*1.5*stride,0,mutant and 0 or 2-math.sin(phase-.25)*2*stride)
    if not mutant and attackAge and attackAge>=0 and attackAge<=(attackRecovery or .58) then
        local impact=attackImpact or .24;local recovery=attackRecovery or .58
        local anticipation=math.clamp(attackAge/(impact*.7),0,1)
        local strike=math.clamp((attackAge-impact*.7)/(impact*.3),0,1)
        local relax=smooth(math.clamp((attackAge-impact)/(recovery-impact),0,1))
        -- Pull back from the rest arm, swipe forward, settle back to rest.
        local rest=mix(12,REACH_SHOULDER,reach);local pulled=smooth(anticipation)
        local arm=(rest*(1-pulled)-26*pulled+110*strike)*(1-relax)+rest*relax
        local elbow=mix(16,REACH_ELBOW,reach)
        poses.RightShoulder=cf(arm,-10*(1-relax),-7)
        poses.RightElbow=cf(elbow+22*anticipation*(1-strike)*(1-relax))
        poses.LeftShoulder=cf(mix(20,REACH_SHOULDER,reach),0,mix(6,3,reach));poses.LeftElbow=cf(mix(25,REACH_ELBOW,reach))
        poses.Waist=cf(-9-9*strike*(1-relax),-12*(anticipation-2*strike)*(1-relax))
    end
    return poses
end
return M
