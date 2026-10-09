-- StarterPlayerScripts.EnemyHealthBars: compact world health bars over ordinary enemies (round 10
-- spec: every damageable thing shows truthful health). A bar shows for an enemy that is damaged
-- (within FAR studs) or close enough to threaten (NEAR), and fades HOLD seconds after its last
-- change, so a full-health crowd far away never becomes a wall of UI. Bosses and leaders use the
-- HUD boss bar; coffins have their own bars (Round10Hud); a Bloater's arming tag is separate.
-- Pooled BillboardGuis (MAX at once, nearest first), updated ten times a second: cheap at 100 mobs.
local Players=game:GetService('Players')
local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local TweenService=game:GetService('TweenService')
local player=Players.LocalPlayer
local MAX,FAR,NEAR,HOLD=24,70,12,2.5
local RED=Color3.fromRGB(239,35,47)
local pool,used={},{}
local seen={} -- npc -> {health, changedAt}
local function make()
 local g=Instance.new('BillboardGui');g.Name='EnemyHealthBar';g.Size=UDim2.fromOffset(64,9);g.LightInfluence=0;g.AlwaysOnTop=false;g.MaxDistance=FAR+10;g.ResetOnSpawn=false
 local track=Instance.new('Frame');track.Name='Track';track.Size=UDim2.fromScale(1,1);track.BackgroundColor3=Color3.fromRGB(22,29,32);track.BorderSizePixel=0;track.Parent=g
 Instance.new('UICorner',track).CornerRadius=UDim.new(0,3)
 local stroke=Instance.new('UIStroke');stroke.Color=Color3.fromRGB(8,10,11);stroke.Thickness=1.5;stroke.Parent=track
 local trail=Instance.new('Frame');trail.Name='Trail';trail.Size=UDim2.fromScale(1,1);trail.BackgroundColor3=Color3.fromRGB(248,172,104);trail.BorderSizePixel=0;trail.Parent=track
 Instance.new('UICorner',trail).CornerRadius=UDim.new(0,3)
 local fill=Instance.new('Frame');fill.Name='Fill';fill.Size=UDim2.fromScale(1,1);fill.BackgroundColor3=RED;fill.BorderSizePixel=0;fill.Parent=track
 Instance.new('UICorner',fill).CornerRadius=UDim.new(0,3)
 return {gui=g,fill=fill,trail=trail,track=track,stroke=stroke}
end
local function take() return table.remove(pool) or make() end
local function give(b) b.gui.Adornee=nil;b.gui.Parent=nil;b.ratio=nil;table.insert(pool,b) end
local function eligible(npc)
 return not npc:GetAttribute('IsBoss') and not npc:GetAttribute('EventObjective') and not npc:GetAttribute('PracticeTarget') and not npc:GetAttribute('DeathPopped')
end
local acc=0
RunService.Heartbeat:Connect(function(dt)
 acc+=dt;if acc<.1 then return end;acc=0
 local root=player.Character and player.Character:FindFirstChild('HumanoidRootPart')
 local camera=workspace.CurrentCamera
 local from=root and root.Position or camera and camera.CFrame.Position
 if not from or player:GetAttribute('LobbyPreviewActive')==true then for npc,b in used do give(b);used[npc]=nil end;return end
 local now=os.clock();local list={}
 for _,npc in Tags:GetTagged('RogueliteZombie') do
  local h=npc:FindFirstChildOfClass('Humanoid');local r=npc:FindFirstChild('HumanoidRootPart')
  if h and r and h.Health>0 and h.MaxHealth>0 and npc:IsDescendantOf(workspace) and eligible(npc) then
   local s=seen[npc];if not s then s={health=h.Health,changedAt=-math.huge};seen[npc]=s end
   if h.Health~=s.health then s.health=h.Health;s.changedAt=now end
   local d=(r.Position-from).Magnitude
   local damaged=h.Health<h.MaxHealth-1e-3 and d<=FAR and now-s.changedAt<=HOLD
   if damaged or d<=NEAR then table.insert(list,{npc=npc,h=h,r=r,d=d}) end
  end
 end
 table.sort(list,function(a,b) return a.d<b.d end)
 local keep={}
 for i=1,math.min(MAX,#list) do
  local e=list[i];keep[e.npc]=true
  local b=used[e.npc]
  if not b then
   b=take();used[e.npc]=b
   local size=e.npc:GetExtentsSize()
   b.gui.StudsOffsetWorldSpace=Vector3.new(0,size.Y*.55+.9,0);b.gui.Size=UDim2.fromOffset(math.clamp(size.X*12,46,90),9)
   b.gui.Adornee=e.r;b.gui.Parent=player:WaitForChild('PlayerGui')
  end
  local ratio=math.clamp(e.h.Health/e.h.MaxHealth,0,1)
  if b.ratio~=ratio then
   local down=b.ratio and ratio<b.ratio
   b.ratio=ratio;b.fill.Size=UDim2.fromScale(ratio,1)
   if down then TweenService:Create(b.trail,TweenInfo.new(.45,Enum.EasingStyle.Quad,Enum.EasingDirection.Out,0,false,.1),{Size=UDim2.fromScale(ratio,1)}):Play() else b.trail.Size=b.fill.Size end
  end
 end
 for npc,b in used do if not keep[npc] then give(b);used[npc]=nil end end
 for npc in seen do if not npc.Parent then seen[npc]=nil end end
end)
