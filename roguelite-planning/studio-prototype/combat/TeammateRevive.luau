-- Teammate revive (free, unlimited): a downed run member leaves a revive spot where they fell, and a
-- living teammate brings them back there by holding the spot's prompt for 5 s: E on a keyboard, a
-- held tap on phones, Y on a controller (X already opens the shop in a run). They rise like a paid
-- revive (RogueliteMeta's rise: half health, a 3 s shield, enemies pushed back), but it never counts
-- toward the Robux price ladder. Example: Ben holds Ana's spot for 5 s, Ana stands up there with 50%
-- health, and her next REVIVE still costs 65 R$. Anyone in the run can do it, any number of times.
-- Server-timed. A client (or an exploit) can fire a prompt at once, so Triggered is ignored and each
-- hold is timed here from PromptButtonHoldBegan / Ended on the server's clock. A revive needs one
-- teammate's own unbroken hold of HOLD_SECONDS, and every step checks that teammate again: alive, in
-- the run, not down, within reach, and the run not frozen (plan L pause). Several teammates holding
-- at once is not faster: the progress is the longest single hold, never a sum. Example: Ben holds
-- from 0 s, Cal from 2 s, Ben lets go at 3 s: the ring drops to Cal's 1 s and Ana stands up at 7 s.
-- RogueliteMeta passes in what this needs (canHelp, isDown, frozen, onRevive), so this knows none of
-- its locals. The hold logic runs on plain values (the clock, positions and the view are injected),
-- so TeammateReviveTests drives it with stand-in players; the default view makes the real spot.
-- Unsandboxed ModuleScript in ServerScriptService, like RunPause; only RogueliteMeta requires it.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local R={}
R.HOLD_SECONDS=5
R.RANGE=10 -- the prompt's MaxActivationDistance, in studs
-- The server allows a little more reach than the prompt: positions replicate a moment late, so a
-- teammate at the prompt's edge keeps the hold. 10 + 4 = 14 studs from the prompt.
R.SLACK=4
-- A hold let go in its last half second still counts: the reviver's own 5 s ends a moment before
-- the server's (their press took a moment to arrive), and the release can arrive first. Example: the
-- server saw the press at 0.0 and the release at 4.7: the hold stays, and Ana stands up at 5.0 if
-- Ben is still alive and in reach then. A release at 4.4 resets it.
R.RELEASE_GRACE=.5
R.STEP=.1 -- seconds between checks (10 a second)
R.FOLDER='RogueliteReviveSpots' -- in Workspace; TeammateReviveVisuals draws each spot in it

-- Where the spot lies: the floor under where they fell (they may have died mid-jump). Bodies, enemies
-- and anything you can walk through are skipped. Nothing below (a fall): about where their feet were.
local function ground(at,folder)
 local ignore={folder}
 for _,q in Players:GetPlayers() do if q.Character then table.insert(ignore,q.Character) end end
 for _,npc in Tags:GetTagged('RogueliteZombie') do table.insert(ignore,npc) end
 local mobs=workspace:FindFirstChild('RogueliteEnemies');if mobs then table.insert(ignore,mobs) end
 local params=RaycastParams.new();params.FilterType=Enum.RaycastFilterType.Exclude;params.FilterDescendantsInstances=ignore;params.RespectCanCollide=true
 local hit=workspace:Raycast(at+Vector3.new(0,1,0),Vector3.new(0,-40,0),params)
 return hit and hit.Position or at-Vector3.new(0,3,0)
end
-- The real spot: a Model (Persistent, so every client has it however far away they stand; the place
-- streams) holding an invisible 8x8 Pad on the floor, which TeammateReviveVisuals draws the ring and
-- the name on, and the prompt 2.5 studs up, about chest height. The pad can't be touched, hit or
-- stood on, and raycasts pass through it. Attributes on the Model for the clients: DownUserId,
-- DownName and HoldSeconds; while someone holds, HoldStartedAt (server time), ReviverUserId and
-- ReviverName.
function R.view()
 local folder=workspace:FindFirstChild(R.FOLDER) or Instance.new('Folder')
 folder.Name=R.FOLDER;folder.Parent=workspace
 local v={}
 function v.create(s,began,ended,at)
  local p=s.owner;local floor=ground(at,folder)
  local model=Instance.new('Model');model.Name='ReviveSpot_'..p.UserId;model.ModelStreamingMode=Enum.ModelStreamingMode.Persistent
  model:SetAttribute('DownUserId',p.UserId);model:SetAttribute('DownName',p.DisplayName);model:SetAttribute('HoldSeconds',R.HOLD_SECONDS)
  local pad=Instance.new('Part');pad.Name='Pad'
  pad.Anchored=true;pad.CanCollide=false;pad.CanTouch=false;pad.CanQuery=false;pad.CastShadow=false;pad.Transparency=1
  pad.Size=Vector3.new(8,.2,8);pad.CFrame=CFrame.new(floor+Vector3.new(0,.1,0));pad.Parent=model;model.PrimaryPart=pad
  local a=Instance.new('Attachment');a.Name='PromptAttachment';a.Position=Vector3.new(0,2.5,0);a.Parent=pad
  local prompt=Instance.new('ProximityPrompt');prompt.Name='RevivePrompt'
  prompt.ActionText='Revive';prompt.ObjectText=p.DisplayName;prompt.HoldDuration=R.HOLD_SECONDS;prompt.MaxActivationDistance=R.RANGE
  prompt.RequiresLineOfSight=false;prompt.KeyboardKeyCode=Enum.KeyCode.E;prompt.GamepadKeyCode=Enum.KeyCode.ButtonY
  prompt.Style=Enum.ProximityPromptStyle.Custom -- drawn in the green theme by TeammateReviveVisuals
  prompt.PromptButtonHoldBegan:Connect(began);prompt.PromptButtonHoldEnded:Connect(ended)
  prompt.Parent=a
  model.Parent=folder;s.model=model -- built whole first, so it replicates in one piece
  return floor+Vector3.new(0,2.6,0)
 end
 -- Only changes are written, so a steady hold replicates once, not ten times a second.
 function v.publish(s,reviver,began)
  local m=s.model;if not m then return end
  if m:GetAttribute('HoldStartedAt')~=began then m:SetAttribute('HoldStartedAt',began) end
  local id=reviver and reviver.UserId or nil
  if m:GetAttribute('ReviverUserId')~=id then m:SetAttribute('ReviverName',reviver and reviver.DisplayName or nil);m:SetAttribute('ReviverUserId',id) end
 end
 function v.destroy(s) if s.model then s.model:Destroy();s.model=nil end end
 return v
end

-- opts: canHelp(q) (q is alive, in the run and not down), isDown(p), onRevive(p,reviver) (called once
-- per full hold, in its own thread: rising yields) and frozen() (the run is paused). Tests also pass
-- clock, positionOf(q), view, spawn and manual (no Heartbeat; they call step themselves).
function R.new(opts)
 local o={spots={}} -- downed player -> {owner,at,holds={[reviver]={began,released}},model}
 local clock=opts.clock or function() return workspace:GetServerTimeNow() end
 local frozen=opts.frozen or function() return false end
 local positionOf=opts.positionOf or function(q) local r=q.Character and q.Character:FindFirstChild('HumanoidRootPart');return r and r.Position end
 local spawn=opts.spawn or task.spawn
 local view=opts.view or R.view()
 -- Can q keep reviving s's player? Never themselves; alive, in the run, not down, within reach.
 local function valid(q,s)
  if q==s.owner or not opts.canHelp(q) then return false end
  local at=positionOf(q);return at~=nil and (at-s.at).Magnitude<=R.RANGE+R.SLACK
 end
 -- The longest hold on the spot: its reviver and when it began.
 local function best(s)
  local who,began
  for q,h in s.holds do if not began or h.began<began then who,began=q,h.began end end
  return who,began
 end
 local function remove(p) local s=o.spots[p];if s then o.spots[p]=nil;view.destroy(s) end end
 -- p went down at `at` (RogueliteMeta's onDied; not on a Phoenix rise). A new down replaces any old spot.
 function o.spot(p,at)
  remove(p)
  local s={owner=p,at=at,holds={}}
  -- Prompt events only count for this spot, never one that a later down replaced.
  local placed=view.create(s,function(q) if o.spots[p]==s then o.holdBegan(p,q) end end,function(q) if o.spots[p]==s then o.holdEnded(p,q) end end,at)
  s.at=placed or at
  o.spots[p]=s
 end
 -- q pressed on p's spot (PromptButtonHoldBegan). Pressing again while holding changes nothing, so
 -- it can't restart or stretch a hold; a press after a late release (RELEASE_GRACE) carries it on.
 function o.holdBegan(p,q)
  local s=o.spots[p]
  if not s or not opts.isDown(p) or frozen() or not valid(q,s) then return false end
  local h=s.holds[q]
  if h then h.released=nil else s.holds[q]={began=clock()} end
  view.publish(s,best(s))
  return true
 end
 -- q let go (PromptButtonHoldEnded): their hold resets, unless it was in its last RELEASE_GRACE.
 function o.holdEnded(p,q)
  local s=o.spots[p];local h=s and s.holds[q];if not h then return end
  if clock()-h.began>=R.HOLD_SECONDS-R.RELEASE_GRACE then h.released=true else s.holds[q]=nil end
  view.publish(s,best(s))
 end
 -- p's spot goes (they rose, gave up, left the run or the server), and so do p's own holds on others.
 function o.clear(p)
  remove(p)
  for _,s in o.spots do if s.holds[p] then s.holds[p]=nil;view.publish(s,best(s)) end end
 end
 -- Seconds of the longest hold on p's spot at `now`, and whose.
 function o.progress(p,now)
  local s=o.spots[p];if not s then return 0 end
  local who,began=best(s)
  return began and (now or clock())-began or 0,who
 end
 -- Every STEP: drop holds that broke, revive on a full hold, publish the progress.
 function o.step(now)
  now=now or clock()
  local still=frozen()
  for p,s in o.spots do
   -- No longer down (rose at the wave's end, a paid revive, gave up, left): the spot goes.
   if not opts.isDown(p) then remove(p);continue end
   -- A freeze resets every hold; after it, teammates press again.
   for q in s.holds do if still or not valid(q,s) then s.holds[q]=nil end end
   local who,began=best(s)
   if who and now-began>=R.HOLD_SECONDS then
    -- One revive per down: the spot goes before the rise, so a second full hold can't revive twice.
    remove(p);spawn(opts.onRevive,p,who)
   else view.publish(s,who,began) end
  end
 end
 if not opts.manual then
  local since=0
  RunService.Heartbeat:Connect(function(dt) since+=dt;if since<R.STEP then return end;since=0;o.step() end)
 end
 return o
end

-- The revive shove (any rise: paid, teammate, Phoenix, wave's end; RogueliteMeta's rise drives it,
-- numbers in MonetizationConfig.RevivePush*). Plain values, so TeammateReviveTests checks it: `mobs` is
-- a list of tables with a `position`; each one within `radius` of `at` (flat) gets {mob, direction
-- (flat unit, straight away from the spot), distance} that leaves it at least `clear` out and moves it
-- at least `min`. Example (14, 13, 4): 2 studs off moves 11 to 13; 10 off moves 4 to 14; 15 off stays.
-- A pile right on the spot fans out around it (golden-angle turns by list order), never all one way.
function R.shovePlan(at,mobs,radius,clear,min)
 local plans={}
 for i,mob in mobs do
  local offset=Vector3.new(mob.position.X-at.X,0,mob.position.Z-at.Z);local d=offset.Magnitude
  if d<radius then
   local direction=d>.1 and offset/d or Vector3.new(math.cos(i*2.39996),0,math.sin(i*2.39996))
   table.insert(plans,{mob=mob,direction=direction,distance=math.max(min,clear-d)})
  end
 end
 return plans
end
-- How much of a shove is done at u (0..1 of its time): an ease-out cubic, so it reads as a knock,
-- not a slide. Example: 0.25 s, 11 studs: 7.7 studs in the first 0.08 s, the last 0.4 in the final 0.08.
function R.shoveEase(u) u=math.clamp(u,0,1);return 1-(1-u)^3 end
return R
