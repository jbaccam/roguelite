-- Server-owned Ray Gun impact policy, also read by cosmetic previews for the exact radius.
-- Each projectile can damage a target once: direct and splash victims share `seen`.
local Catalog=require(script.Parent.WeaponCatalog)
local Stats=require(script.Parent.CharacterStats)
local Tags=game:GetService('CollectionService')
local R={}
local function tier(d) return math.clamp(math.floor(tonumber(d.tier) or 1),1,4) end
function R.radius(d)
 local spec=Catalog.Godly['41']
 return math.clamp(spec.burstRadius[tier(d)]*Stats.mult((d.stats and d.stats.AreaSize) or 0),2,12)
end
function R.factor(d,distance,radius)
 local spec=Catalog.Godly['41'];radius=radius or R.radius(d)
 if distance<0 or distance>radius then return 0 end
 return spec.burstFactor[tier(d)]*(1-(1-spec.splashEdge)*math.clamp(distance/radius,0,1))
end
function R.allowed(npc,d)
 local h=npc and npc:FindFirstChildOfClass('Humanoid')
 local root=npc and npc:FindFirstChild('HumanoidRootPart')
 return npc and npc:IsDescendantOf(workspace) and Tags:HasTag(npc,'RogueliteZombie')
  and h and h.Health>0 and root and (not d.practiceTarget or npc:GetAttribute('PracticeTarget')==true)
end
-- `visible(point,root)` uses the authoritative wall-only ray filter. `damage` remains the
-- combat service callback (which validates owner/run state). No remotes supply candidates.
function R.apply(d,point,direct,seen,candidates,visible,damage,scale)
 if d.id~='41' then return 0 end
 local radius=R.radius(d);local eligible={}
 for order,npc in candidates do
  if npc~=direct and not seen[npc] and R.allowed(npc,d) then
   local root=npc:FindFirstChild('HumanoidRootPart');local distance=(root.Position-point).Magnitude
   if distance<=radius and visible(point,root.Position) then table.insert(eligible,{npc=npc,distance=distance,order=order}) end
  end
 end
 table.sort(eligible,function(a,b) return a.distance==b.distance and a.order<b.order or a.distance<b.distance end)
 local count=0
 for i=1,math.min(#eligible,Catalog.Godly['41'].splashTargets) do
  local hit=eligible[i]
  -- Mark before the callback so secondary effects/re-entrancy and later pierced legs cannot
  -- add another hit from this projectile. StatProjectiles handles direct damage once.
  if not seen[hit.npc] then
   seen[hit.npc]=true;count+=1
   damage(hit.npc,d.damage*(scale or 1)*R.factor(d,hit.distance,radius),d,true)
  end
 end
 return count,radius
end
return R
