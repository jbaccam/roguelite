-- Only rows 2 and 4 of the supplied atlas; coordinates use its 1254px source.
local RunService=game:GetService('RunService')
local V={}
local atlas='rbxassetid://131707953627421'
local rows={
 [2]={{25,280,260,270},{285,280,275,270},{565,280,225,270},{790,280,215,270},{1005,280,249,270}},
 [4]={{25,790,260,215},{285,790,180,215},{465,790,180,215},{645,790,265,215},{910,790,330,215}},
}
function V.mount(visuals)
 local active={};local rng=Random.new()
 RunService.RenderStepped:Connect(function()
  local camera=workspace.CurrentCamera;if not camera then return end
  local now=os.clock();local focal=camera.ViewportSize.Y/(2*math.tan(math.rad(camera.FieldOfView)/2))
  for i=#active,1,-1 do
   local e=active[i];local age=now-e.born
   if age>=e.duration then e.anchor:Destroy();table.remove(active,i)
   else
    local t=age/e.duration
    local scale=(.65+.35*math.min(age/.035,1))*(1-.2*t)
    local depth=math.max(.5,(e.anchor.Position-camera.CFrame.Position):Dot(camera.CFrame.LookVector))
    local pixels=math.min(52,camera.ViewportSize.Y*.075,e.studs*focal/depth)*scale
    e.gui.Size=UDim2.fromOffset(pixels,pixels)
    e.picture.ImageTransparency=math.clamp((t-.2)/.8,0,1)
   end
  end
 end)
 return function(position,normal)
  local camera=workspace.CurrentCamera
  if atlas=='' or not camera or (position-camera.CFrame.Position).Magnitude>150 then return end
  if #active>=96 then table.remove(active,1).anchor:Destroy() end
  local row=rng:NextNumber()<.8 and 2 or 4
  local variant=rng:NextInteger(1,#rows[row]);local rect=rows[row][variant]
  local anchor=Instance.new('Part');anchor.Name='BulletImpact';anchor.Size=Vector3.one*.05
  anchor.Anchored=true;anchor.Transparency=1;anchor.CanCollide=false;anchor.CanTouch=false;anchor.CanQuery=false;anchor.CastShadow=false
  anchor.Position=position+(normal or Vector3.zero)*.07
  anchor:SetAttribute('AtlasRow',row);anchor:SetAttribute('Variant',variant);anchor.Parent=visuals
  local gui=Instance.new('BillboardGui');gui.Name='ImpactSprite';gui.Adornee=anchor;gui.AlwaysOnTop=false;gui.LightInfluence=0;gui.MaxDistance=150;gui.Parent=anchor
  local picture=Instance.new('ImageLabel');picture.BackgroundTransparency=1;picture.Size=UDim2.fromScale(1,1);picture.ScaleType=Enum.ScaleType.Fit
  picture.Image=atlas;picture.Rotation=rng:NextNumber(-25,25)
  local factor=1024/1254
  picture.ImageRectOffset=Vector2.new(math.round(rect[1]*factor),math.round(rect[2]*factor))
  picture.ImageRectSize=Vector2.new(math.round(rect[3]*factor),math.round(rect[4]*factor));picture.Parent=gui
  table.insert(active,{anchor=anchor,gui=gui,picture=picture,born=os.clock(),duration=rng:NextNumber(.16,.23),studs=rng:NextNumber(.95,1.35)})
 end
end
return V
