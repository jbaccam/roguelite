local Data=require(script.Parent.RolledShirtData)
local V={}
local function triangle(model, a, b, c, color, thickness)
    local ab, ac, bc = b-a, c-a, c-b
    local ab2, ac2, bc2 = ab:Dot(ab), ac:Dot(ac), bc:Dot(bc)
    if ab2 > ac2 and ab2 > bc2 then
        c, a = a, c
    elseif ac2 > ab2 and ac2 > bc2 then
        a, b = b, a
    end
    ab, ac, bc = b-a, c-a, c-b
    local right = ac:Cross(ab).Unit
    local back = bc.Unit
    local up = bc:Cross(right).Unit
    local h = math.abs(ab:Dot(up))
    local function wedge(size, cf)
        local part = Instance.new('WedgePart')
        part.Name = 'CottonFacet'
        part.Size = size
        part.CFrame = cf
        part.Color = color
        part.Material = Enum.Material.SmoothPlastic
        part.Anchored = true
        part.CanCollide = false
        part.CanTouch = false
        part.CanQuery = false
        part.CastShadow = false
        part.TopSurface = Enum.SurfaceType.Smooth
        part.BottomSurface = Enum.SurfaceType.Smooth
        part.Parent = model
    end
    wedge(Vector3.new(thickness, h, math.abs(ab:Dot(back))), CFrame.fromMatrix((a+b)/2, right, up, back))
    wedge(Vector3.new(thickness, h, math.abs(ac:Dot(back))), CFrame.fromMatrix((a+c)/2, -right, up, -back))
end

-- One MeshPart per panel when editable meshes are available; exact triangle
-- fallback preserves the authored shape when a client has no mesh budget.
local meshAvailable=script.Parent:GetAttribute('UseEditableDesignerMeshes')==true
function V.geometry(parent,data,size,name)
 local model=Instance.new('Model');model.Name=name or 'ClothPanel'
 local vertices={};local lo=Vector3.new(math.huge,math.huge,math.huge);local hi=-lo
 for i,p in data.vertices do local v=Vector3.new(p[1],p[2],p[3])*size;vertices[i]=v;lo=lo:Min(v);hi=hi:Max(v) end
 local editable
 local ok,part=pcall(function()
  if not meshAvailable then return nil end
  editable=game:GetService('AssetService'):CreateEditableMesh();if not editable then return nil end
  local ids={};for i,v in vertices do ids[i]=editable:AddVertex(v) end
  local colors={};for i,c in data.colors do colors[i]=editable:AddColor(Color3.new(c[1],c[2],c[3]),1) end
  for _,t in data.triangles do
   local face=editable:AddTriangle(ids[t[1]+1],ids[t[2]+1],ids[t[3]+1]);local color=colors[t[4]]
   editable:SetFaceColors(face,{color,color,color})
  end
  return game:GetService('AssetService'):CreateMeshPartAsync(Content.fromObject(editable))
 end)
 if ok and part then
  part.Name='AuthoredClothMesh';part.Anchored=true;part.CanCollide=false;part.CanTouch=false;part.CanQuery=false;part.CastShadow=false
  part.DoubleSided=true;part.Material=Enum.Material.SmoothPlastic;part.Color=Color3.new(1,1,1)
  part.Size=hi-lo;part.CFrame=CFrame.new((lo+hi)/2);part.Parent=model
  model:SetAttribute('MeshPresentation',true)
 else
  meshAvailable=false
  if editable then editable:Destroy() end
  for _,t in data.triangles do local c=data.colors[t[4]];triangle(model,vertices[t[1]+1],vertices[t[2]+1],vertices[t[3]+1],Color3.new(c[1],c[2],c[3]),.005) end
  model:SetAttribute('MeshPresentation',false)
 end
 model.WorldPivot=CFrame.identity;model.Parent=parent;return model
end
function V.create(parent)
 return V.geometry(parent,Data,Vector3.one,'BundledDesignerTee')
end
return V
