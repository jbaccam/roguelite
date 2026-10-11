-- Teammate revive (free, unlimited): a downed run member leaves a revive spot where they fell, and a
-- living teammate brings them back there by holding the spot's prompt: E on a keyboard, a held tap on
-- phones, Y on a controller (X already opens the shop in a run). They rise like a paid revive
-- (RogueliteMeta's rise: half health, a 3 s shield, enemies shoved back), but it never counts toward
-- the Robux price ladder. Anyone in the run can do it, any number of times.
-- 2026-10-10 play-test ("Make reviving easier, it's hella hard. It takes too long and it's too easy to
-- die when you're doing it. Especially against ranged mobs you just get volleyed with projectiles"):
--   before: 5 s, 10 studs (+4 server slack), letting go reset it to 0, more revivers were not faster,
--           and the reviver took every hit in full.
--   now:    2.5 s alone, faster with each extra reviver; 16 studs (+4); letting go drains the ring
--           slowly (20% a second) instead of emptying it; a reviver who is holding takes 40% damage and
--           regular enemies' shots that reach them stop at their bubble (EnemyAttacks).
-- Example: Ben holds Ana's ring for 1.5 s (60%), a mob makes him step away for 1 s (down to 40%), he
-- holds again and Ana stands up 1.5 s later. With Cal holding too it fills x1.5 as fast.
-- Server-timed. A client (or an exploit) can fire a prompt at once, so Triggered is ignored and each
-- hold is timed here from PromptButtonHoldBegan / Ended on the server's clock (the prompt's own
-- HoldDuration is PROMPT_HOLD, longer than any revive, so no client ends a hold by finishing it).
-- Every step checks each holder again: alive, in the run, not down, within reach (where their own
-- screen has them, CharacterService.seen, passed in by RogueliteMeta) and the run not frozen (plan L
-- pause: progress holds still and every hold drops). The protection (ReviveGuard) is on only while the
-- server counts a valid hold, never for standing near a body, and it ends with the revive.
-- RogueliteMeta passes in what this needs (canHelp, isDown, frozen, onRevive, positionOf), so this knows
-- none of its locals. The hold logic runs on plain values (the clock, positions, the guard and the view
-- are injected), so TeammateReviveTests drives it with stand-in players; the default view makes the
-- real spot. Unsandboxed ModuleScript in ServerScriptService, like RunPause; only RogueliteMeta needs it.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local R={}
R.HOLD_SECONDS=2.5 -- one reviver, from an empty ring (was 5)
-- Each extra teammate holding the same ring adds this much speed. Example: 2 holding x1.5 (1.67 s),
-- 3 holding x2 (1.25 s).
R.HELPER_BONUS=.5
-- Nobody holding: the ring drains from full to empty in this long (was: empty at once on a let-go).
R.DECAY_SECONDS=5
R.RANGE=16 -- the prompt's MaxActivationDistance, in studs (was 10), so you can revive from outside a crowd
-- The server allows a little more reach than the prompt: positions replicate a moment late, so a
-- teammate at the prompt's edge keeps the hold. 16 + 4 = 20 studs from the prompt.
R.SLACK=4
-- Share of damage a reviver takes while their hold counts (CharacterService.contact reads the player's
-- ReviveGuard attribute): 60% less. Regular enemies' shots that reach them are stopped (EnemyAttacks).
R.GUARD=.4
R.PROMPT_HOLD=60 -- the prompt's HoldDuration: longer than any revive; the server ends the hold
R.STEP=.1 -- seconds between checks (10 a second)
R.FOLDER='RogueliteReviveSpots' -- in Workspace; TeammateReviveVisuals draws each spot in it
-- Ring fill per second with `n` teammates holding; nobody holding, it drains.
function R.rate(n) return n>0 and (1+R.HELPER_BONUS*(n-1))/R.HOLD_SECONDS or -1/R.DECAY_SECONDS end

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
-- DownName, HoldSeconds; the ring as Progress (0-1) at ProgressAt (server time) moving ProgressRate a
-- second (so screens draw it smoothly from one write per change); Revivers (how many hold), and the
-- longest holder's ReviverUserId and ReviverName.
function R.view()
 local folder=workspace:FindFirstChild(R.FOLDER) or Instance.new('Folder')
 folder.Name=R.FOLDER;folder.Parent=workspace
 local v={}
 function v.create(s,began,ended,at)
  local p=s.owner;local floor=ground(at,folder)
  local model=Instance.new('Model');model.Name='ReviveSpot_'..p.UserId;model.ModelStreamingMode=Enum.ModelStreamingMode.Persistent
  model:SetAttribute('DownUserId',p.UserId);model:SetAttribute('DownName',p.DisplayName);model:SetAttribute('HoldSeconds',R.HOLD_SECONDS)
  model:SetAttribute('Progress',0);model:SetAttribute('ProgressAt',s.t);model:SetAttribute('ProgressRate',0);model:SetAttribute('Revivers',0)
  local pad=Instance.new('Part');pad.Name='Pad'
  pad.Anchored=true;pad.CanCollide=false;pad.CanTouch=false;pad.CanQuery=false;pad.CastShadow=false;pad.Transparency=1
  pad.Size=Vector3.new(8,.2,8);pad.CFrame=CFrame.new(floor+Vector3.new(0,.1,0));pad.Parent=model;model.PrimaryPart=pad
  local a=Instance.new('Attachment');a.Name='PromptAttachment';a.Position=Vector3.new(0,2.5,0);a.Parent=pad
  local prompt=Instance.new('ProximityPrompt');prompt.Name='RevivePrompt'
  prompt.ActionText='Revive';prompt.ObjectText=p.DisplayName;prompt.HoldDuration=R.PROMPT_HOLD;prompt.MaxActivationDistance=R.RANGE
  prompt.RequiresLineOfSight=false;prompt.KeyboardKeyCode=Enum.KeyCode.E;prompt.GamepadKeyCode=Enum.KeyCode.ButtonY
  prompt.Style=Enum.ProximityPromptStyle.Custom -- drawn in the green theme by TeammateReviveVisuals
  prompt.PromptButtonHoldBegan:Connect(began);prompt.PromptButtonHoldEnded:Connect(ended)
  prompt.Parent=a
  model.Parent=folder;s.model=model -- built whole first, so it replicates in one piece
  return floor+Vector3.new(0,2.6,0)
 end
 -- Only changes are written: the ring's numbers when its speed changes, not ten times a second.
 function v.publish(s,reviver,progress,rate,at,count)
  local m=s.model;if not m then return end
  if m:GetAttribute('ProgressRate')~=rate or m:GetAttribute('Revivers')~=count then
   m:SetAttribute('Progress',progress);m:SetAttribute('ProgressAt',at);m:SetAttribute('ProgressRate',rate);m:SetAttribute('Revivers',count)
  end
  local id=reviver and reviver.UserId or nil
  if m:GetAttribute('ReviverUserId')~=id then m:SetAttribute('ReviverName',reviver and reviver.DisplayName or nil);m:SetAttribute('ReviverUserId',id) end
 end
 function v.destroy(s) if s.model then s.model:Destroy();s.model=nil end end
 return v
end

-- opts: canHelp(q) (q is alive, in the run and not down), isDown(p), onRevive(p,reviver) (called once
-- per full ring, in its own thread: rising yields), frozen() (the run is paused) and positionOf(q)
-- (where q's own screen has them). Tests also pass clock, view, guard, spawn and manual (no
-- Heartbeat; they call step themselves).
function R.new(opts)
 local o={spots={}} -- downed player -> {owner,at,holds={[reviver]={began}},progress,t,model}
 local clock=opts.clock or function() return workspace:GetServerTimeNow() end
 local frozen=opts.frozen or function() return false end
 local positionOf=opts.positionOf or function(q) local r=q.Character and q.Character:FindFirstChild('HumanoidRootPart');return r and r.Position end
 local spawn=opts.spawn or task.spawn
 local view=opts.view or R.view()
 local guard=opts.guard or function(q,on) q:SetAttribute('ReviveGuard',on and R.GUARD or nil) end
 local guarded={} -- reviver -> true while their ReviveGuard is on
 -- Can q keep reviving s's player? Never themselves; alive, in the run, not down, within reach.
 local function valid(q,s)
  if q==s.owner or not opts.canHelp(q) then return false end
  local at=positionOf(q);return at~=nil and (at-s.at).Magnitude<=R.RANGE+R.SLACK
 end
 local function count(s) local n=0;for _ in s.holds do n+=1 end;return n end
 -- The longest hold on the spot: its reviver (the name the ring shows, and who gets the credit).
 local function best(s)
  local who,began
  for q,h in s.holds do if not began or h.began<began then who,began=q,h.began end end
  return who
 end
 -- The ring at `now` with the holds as they are; frozen, it stands still.
 local function value(s,now)
  if frozen() then return s.progress end
  return math.clamp(s.progress+R.rate(count(s))*(now-s.t),0,1)
 end
 -- Bank the ring up to `now` before the holds change, so each stretch fills at its own speed.
 local function advance(s,now) s.progress=value(s,now);s.t=now end
 local function publish(s)
  local n=count(s);local rate=(frozen() or (n==0 and s.progress<=0)) and 0 or R.rate(n)
  view.publish(s,best(s),s.progress,rate,s.t,n)
 end
 -- The guard follows the holds: on for every counted holder, off the moment they stop counting.
 local function refresh()
  local holding={}
  for _,s in o.spots do for q in s.holds do holding[q]=true end end
  for q in guarded do if not holding[q] then guarded[q]=nil;guard(q,false) end end
  for q in holding do if not guarded[q] then guarded[q]=true;guard(q,true) end end
 end
 local function remove(p) local s=o.spots[p];if s then o.spots[p]=nil;view.destroy(s) end end
 -- p went down at `at` (RogueliteMeta's onDied; not on a Phoenix rise). A new down replaces any old spot.
 function o.spot(p,at)
  remove(p)
  local s={owner=p,at=at,holds={},progress=0,t=clock()}
  -- Prompt events only count for this spot, never one that a later down replaced.
  local placed=view.create(s,function(q) if o.spots[p]==s then o.holdBegan(p,q) end end,function(q) if o.spots[p]==s then o.holdEnded(p,q) end end,at)
  s.at=placed or at
  o.spots[p]=s
  refresh()
 end
 -- q pressed on p's spot (PromptButtonHoldBegan). Pressing again while holding changes nothing.
 function o.holdBegan(p,q)
  local s=o.spots[p]
  if not s or not opts.isDown(p) or frozen() or not valid(q,s) then return false end
  if s.holds[q] then return true end
  local now=clock();advance(s,now)
  s.holds[q]={began=now}
  publish(s);refresh()
  return true
 end
 -- q let go (PromptButtonHoldEnded): their part stops; the ring keeps what it has and drains slowly.
 function o.holdEnded(p,q)
  local s=o.spots[p];if not s or not s.holds[q] then return end
  advance(s,clock());s.holds[q]=nil
  publish(s);refresh()
 end
 -- p's spot goes (they rose, gave up, left the run or the server), and so do p's own holds on others.
 function o.clear(p)
  remove(p)
  local now=clock()
  for _,s in o.spots do if s.holds[p] then advance(s,now);s.holds[p]=nil;publish(s) end end
  refresh()
 end
 -- The ring on p's spot at `now` (0-1), its longest holder and how many hold.
 function o.progress(p,now)
  local s=o.spots[p];if not s then return 0,nil,0 end
  return value(s,now or clock()),best(s),count(s)
 end
 -- Every STEP: bank the ring, drop holds that broke, revive on a full ring, publish the progress.
 function o.step(now)
  now=now or clock()
  local still=frozen()
  for p,s in o.spots do
   -- No longer down (rose at the wave's end, a paid revive, gave up, left): the spot goes.
   if not opts.isDown(p) then remove(p);continue end
   advance(s,now) -- the last stretch counts at the speed its holds had
   -- A freeze drops every hold (the ring keeps its fill); after it, teammates press again.
   for q in s.holds do if still or not valid(q,s) then s.holds[q]=nil end end
   local who=best(s)
   if who and s.progress>=1-1e-9 then
    -- One revive per down: the spot goes before the rise, so a second full ring can't revive twice.
    remove(p);spawn(opts.onRevive,p,who)
   else publish(s) end
  end
  refresh()
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
