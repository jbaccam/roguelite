local RunService=game:GetService('RunService')
local Tags=game:GetService('CollectionService')
local C=game.ReplicatedStorage.RogueliteCombat
local Roll=require(C.RolledShirtVisual)
local Garment=require(C.DesignerShirtVisual)
local V={}
function V.mount(folder)
 local template=Roll.create(nil)
 local flights,garments,pending={},{},{}
 local refresh=0
 RunService.RenderStepped:Connect(function(dt)
  local now=os.clock();refresh-=dt
  if refresh<=0 then
   refresh=.12
   local wanted={};local count=0;local camera=workspace.CurrentCamera
   for _,npc in Tags:GetTagged('RogueliteZombie') do
    local root=npc:FindFirstChild('HumanoidRootPart')
    if npc:IsDescendantOf(workspace) and npc:GetAttribute('DesignerShirt') and root and (root.Position-camera.CFrame.Position).Magnitude<120 and count<40 then
     count+=1;wanted[npc]=true
     if not garments[npc] and not pending[npc] then
      pending[npc]=true
      task.spawn(function()
       local r=Garment.create(npc,folder)
       if r then
        if npc.Parent and npc:GetAttribute('DesignerShirt') then garments[npc]=r else r.model:Destroy() end
       end
       pending[npc]=nil
      end)
     end
    end
   end
   for npc,r in garments do if not wanted[npc] then r.model:Destroy();garments[npc]=nil end end
  end
  for npc,r in garments do
   if not npc.Parent then r.model:Destroy();garments[npc]=nil else Garment.step(r) end
  end
  for key,r in flights do
   if now-r.updated>(r.terminal and r.duration or .18) then r.model:Destroy();flights[key]=nil
   else
    local t=math.clamp((now-r.updated)/r.duration,0,1)
    local pos=r.origin:Lerp(r.finish,t)
    r.model:PivotTo(CFrame.lookAt(pos,pos+r.direction)*CFrame.Angles(0,0,(now-r.born)*4)*CFrame.Angles(0,math.pi/2,0))
   end
  end
 end)
 return function(origin,finish,key,speed,terminal)
  if not key or (finish-origin).Magnitude<.001 then return end
  local now=os.clock();local r=flights[key]
  if not r then
   local count=0;for _ in flights do count+=1 end;if count>=24 then return end
   r={model=template:Clone(),born=now};r.model:SetAttribute('ProjectileId',key);r.model:SetAttribute('LaunchOrigin',origin);r.model.Parent=folder;flights[key]=r
  end
  r.terminal=terminal;r.origin=origin;r.finish=finish;r.direction=(finish-origin).Unit;r.updated=now
  r.duration=math.clamp((finish-origin).Magnitude/(speed or 65),1/240,.1)
  r.model:PivotTo(CFrame.lookAt(origin,finish)*CFrame.Angles(0,math.pi/2,0))
 end
end
return V
