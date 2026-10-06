-- Presentation only. Never changes simulation, warnings, hit tests or rewards.
local Q={}
Q.Profiles={
 {name='Low',effects=.35,lights=0,auras=0,shardHz=20,shadows=false},
 {name='Balanced',effects=.65,lights=4,auras=12,shardHz=30,shadows=true},
 {name='Full',effects=1,lights=12,auras=32,shardHz=60,shadows=true},
}
function Q.new()
 -- A keyboard/touchscreen does not tell us GPU strength. Start conservatively
 -- on every device, then earn higher detail using actual frame performance.
 return {level=1,slow=0,fast=0,elapsed=0,frames=0,warmup=5}
end
-- Three slow seconds lower detail; fifteen healthy seconds restore one step.
-- Ignore long loading/background stalls and allow startup to settle.
function Q.sample(s,dt)
 if dt<=0 or dt~=dt or dt>.25 then s.elapsed=0;s.frames=0;s.slow=0;s.fast=0;return end
 if s.warmup>0 then s.warmup-=dt;return end
 s.elapsed+=dt;s.frames+=1
 if s.elapsed<1 then return end
 local average=s.elapsed/s.frames
 s.slow=average>1/40 and s.slow+s.elapsed or 0
 s.fast=average<1/55 and s.fast+s.elapsed or 0
 s.elapsed=0;s.frames=0
 if s.slow>=3 and s.level>1 then s.level-=1;s.slow=0;s.fast=0
 elseif s.fast>=15 and s.level<3 then s.level+=1;s.fast=0;s.slow=0 end
end
local state=Q.new()
local player
function Q.get()
 local mode=player and player:GetAttribute('Setting_VisualQuality')
 return Q.Profiles[mode=='Low' and 1 or mode=='Full' and 3 or state.level]
end
if game:GetService('RunService'):IsClient() then
 player=game:GetService('Players').LocalPlayer
 local function modeChanged()
  -- Returning to Auto must not reuse a high level learned on a lighter scene.
  state=Q.new()
 end
 player:GetAttributeChangedSignal('Setting_VisualQuality'):Connect(modeChanged)
 game:GetService('RunService').RenderStepped:Connect(function(dt)
  local mode=player:GetAttribute('Setting_VisualQuality')
  if mode~='Low' and mode~='Full' then Q.sample(state,dt) end
  local name=Q.get().name
  if player:GetAttribute('LocalVisualQuality')~=name then player:SetAttribute('LocalVisualQuality',name) end
 end)
end
return Q
