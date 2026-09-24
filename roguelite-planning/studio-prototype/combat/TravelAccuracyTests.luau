return function(combat)
 local T=require(combat.ProjectileTarget);local A=require(combat.ArcMotion);local P=require(combat.SpecialMotion)
 local M=require(combat.WeaponMotion);local U=require(combat.UtilityMotion);local S=require(combat.CharacterStats);local C=require(combat.WeaponCatalog)
 local checks=0;local function check(v,msg) checks+=1;assert(v,msg) end
 for _,distance in {8,20,35} do for _,velocity in {Vector3.zero,Vector3.new(12,0,0),Vector3.new(0,0,12),Vector3.new(6,0,-8)} do
  for _,id in {'14','15','18','33'} do
   local origin=Vector3.new(4,5,0);local target=Vector3.new(0,5,-distance);local delay=id=='33' and .24 or .07
   local function duration(d) return (id=='33' or id=='18') and A.duration(id,d,90) or P.duration(Vector3.zero,Vector3.xAxis*d,28) end
   local point,time=T.intercept(origin,target,velocity,duration,delay)
   check((point-target-velocity*time).Magnitude<.001,'Intercept does not follow target motion')
   check(math.abs(time-delay-duration((point-origin).Magnitude))<.002,'Intercept flight time inconsistent')
  end
 end end
 local stop=Vector3.new(0,0,-3)
 local point=T.intercept(Vector3.zero,Vector3.new(0,0,-12),Vector3.new(0,0,16),function() return 2 end,0,stop)
 check((point-stop).Magnitude<.001,'Prediction overshoots stopped pursuer')
 point=T.intercept(Vector3.zero,Vector3.new(0,0,-12),Vector3.new(0,0,16),function() return 2 end,0,stop,Vector3.new(0,0,8))
 check((point-Vector3.new(0,0,13)).Magnitude<.001,'Prediction ignores retreating player movement')
 for _,id in {'01','05','06','20','26','27','31'} do
  local template=combat.WeaponTemplates[id];local size=template:GetAttribute('BoundsSize');local center=template:GetAttribute('BoundsCenter')
  for _,distance in {1,1.8,2.5} do for _,yaw in {0,math.pi/2,math.pi} do
   local root=CFrame.new(0,6,0)*CFrame.Angles(0,yaw,0);local aim=root.Position+root.LookVector*distance-Vector3.yAxis*2.8
   local attack=M.attackRoot(root,aim);local style=M.chooseStyle(id,1,3,distance,8);local hit=false
   for i=0,100 do
    local age=M.SwingHitStart+(M.SwingHitEnd-M.SwingHitStart)*i/100
    local cf=M.pose(attack,4.2,1,aim,0,age,'Melee',id,root.LookVector,8,size,center,style)
    local p=(cf*CFrame.new(center)):PointToObjectSpace(aim);local half=size*.5+Vector3.one*.65
    if math.abs(p.X)<=half.X and math.abs(p.Y)<=half.Y and math.abs(p.Z)<=half.Z then hit=true end
   end
   check(hit,'Close baby target missed by '..id)
  end end
 end
 check(U.inCone(Vector3.zero,-Vector3.zAxis,Vector3.new(4,0,-10),20,9.6,4),'Vacuum cone too narrow')
 check(not U.inCone(Vector3.zero,-Vector3.zAxis,Vector3.new(8,0,-4),20,9.6,4),'Vacuum captures outside triangle')
 check(U.pull(Vector3.new(0,0,-6),Vector3.zero,-Vector3.zAxis,7).Magnitude==0,'Vacuum pulls inside safe distance')
 check(U.pull(Vector3.new(4,0,-15),Vector3.zero,-Vector3.zAxis,7).Z>0,'Vacuum force points away')
 local stats=S.resolve('Brawler',1,{})
 local gloves=S.weapon(C.ById['19'],stats,'Brawler',1)
 check(gloves.cooldown<.45 and M.SwingDuration/gloves.motionRate<.35,'Gloves too slow')
 check(S.weapon(C.ById['22'],stats,'Brawler',1).nativePierce>=3,'Bowling ball lacks native pierce')
 check(S.weapon(C.ById['08'],stats,'Brawler',1).projectileSpeed>=150,'Poison projectile too slow')
 check(A.duration('18',20,90)>.48,'Cards not slowed')
 return {checks=checks}
end
