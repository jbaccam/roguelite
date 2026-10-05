-- Compact top-row stars from the supplied atlas. Impacts use rows 2 and 4.
local RunService=game:GetService('RunService')
local V={}
local atlas='rbxassetid://131707953627421'
local rects={{35,75,150,170},{202,79,115,163},{725,83,106,157}}
local sizes={['00']=.85,['07']=1.05,['09']=1.3}
function V.mount(visuals,options)
 options=options or {}
 local renderKey=options.renderKey or 'RogueliteMuzzleFlashes'
 local active={}
 local pool={}
 local last=setmetatable({},{__mode='k'})
 local rng=Random.new()
 local function allocate(variant)
  local anchor=Instance.new('Part');anchor.Name='MuzzleFlashReady';anchor.Size=Vector3.one*.05
  anchor.Anchored=true;anchor.Transparency=1;anchor.CanCollide=false;anchor.CanTouch=false;anchor.CanQuery=false;anchor.CastShadow=false;anchor.Parent=visuals
  local gui=Instance.new('BillboardGui');gui.Name='MuzzleSprite';gui.Adornee=anchor;gui.AlwaysOnTop=false;gui.LightInfluence=0;gui.MaxDistance=150;gui.Size=UDim2.fromOffset(20,20);gui.Parent=anchor
  local picture=Instance.new('ImageLabel');picture.BackgroundTransparency=1;picture.Size=UDim2.fromScale(1,1);picture.ScaleType=Enum.ScaleType.Fit
  picture.Image=atlas;picture.ImageTransparency=1
  local rect=rects[variant];local factor=1024/1254
  picture.ImageRectOffset=Vector2.new(math.round(rect[1]*factor),math.round(rect[2]*factor))
  picture.ImageRectSize=Vector2.new(math.round(rect[3]*factor),math.round(rect[4]*factor));picture.Parent=gui
  return {anchor=anchor,gui=gui,picture=picture,variant=variant}
 end
 -- Retaining image instances prevents short flashes expiring before decoding.
 for i=1,6 do table.insert(pool,allocate((i-1)%#rects+1)) end
 task.spawn(function() pcall(function() game:GetService('ContentProvider'):PreloadAsync({atlas}) end) end)
 local function remove(i)
  local e=table.remove(active,i)
  e.anchor.Name='MuzzleFlashReady';e.picture.ImageTransparency=1
  e.model=nil;table.insert(pool,e)
 end
 RunService:BindToRenderStep(renderKey,Enum.RenderPriority.Character.Value+2,function()
  if not visuals.Parent then
   for i=#active,1,-1 do remove(i) end
   for _,e in pool do e.anchor:Destroy() end
   RunService:UnbindFromRenderStep(renderKey);return
  end
  local camera=workspace.CurrentCamera
  local now=os.clock()
  for i=#active,1,-1 do
   local e=active[i];local age=now-e.born
   if age>=e.duration or not e.model:IsDescendantOf(visuals) then remove(i)
   elseif camera then
    -- Sample after the weapon render step so recoil/bob cannot detach the flash.
    e.anchor.CFrame=e.model:GetPivot()*CFrame.new(e.offset)
    local depth=math.max(.5,(e.anchor.Position-camera.CFrame.Position):Dot(camera.CFrame.LookVector))
    local focal=camera.ViewportSize.Y/(2*math.tan(math.rad(camera.FieldOfView)/2))
    local t=age/e.duration
    local pixels=math.min(46,camera.ViewportSize.Y*.065,e.studs*focal/depth)*(1-.35*t)
    e.gui.Size=UDim2.fromOffset(pixels,pixels)
    e.picture.ImageTransparency=math.clamp((t-.25)/.75,0,1)
   end
  end
 end)
 return function(model,id,offset,shotId)
  local camera=workspace.CurrentCamera
  if not sizes[id] or not camera or not model:IsDescendantOf(visuals) then return end
  local position=model:GetPivot():PointToWorldSpace(offset)
  if (position-camera.CFrame.Position).Magnitude>150 then return end
  local previous=last[model]
  -- One server launch token per trigger, shared by every shotgun pellet.
  if previous and previous.shot==shotId then return end
  local variant=rng:NextInteger(1,#rects)
  if previous and variant==previous.variant then variant=variant%#rects+1 end
  last[model]={shot=shotId,variant=variant}
  if #active>=48 then remove(1) end
  local e
  for i=#pool,1,-1 do if pool[i].variant==variant then e=table.remove(pool,i);break end end
  e=e or allocate(variant)
  local anchor,gui,picture=e.anchor,e.gui,e.picture
  anchor.Name='MuzzleFlash';anchor.Position=position
  anchor:SetAttribute('AtlasRow',1);anchor:SetAttribute('Variant',variant);anchor:SetAttribute('WeaponId',id);anchor:SetAttribute('ShotId',shotId)
  picture.ImageTransparency=0;picture.Rotation=rng:NextNumber(-30,30)
  e.model=model;e.offset=offset;e.born=os.clock();e.duration=rng:NextNumber(.055,.085);e.studs=sizes[id]*rng:NextNumber(.85,1.15)
  table.insert(active,e)
 end
end
return V
