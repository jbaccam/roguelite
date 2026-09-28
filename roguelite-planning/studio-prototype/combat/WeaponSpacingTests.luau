-- Disposable Studio check for WeaponSpacing (not mapped into the Rojo tree).
-- Run with execute_luau in Edit; returns a summary string.
local mod=game.ReplicatedStorage.RogueliteCombat.WeaponSpacing:Clone()
local S=require(mod)
local fails,checks={},0
local function check(c,msg) checks+=1 if not c then table.insert(fails,msg) end end
local function body(p,axis,half,r,mass) return {a=p-axis*half,b=p+axis*half,r=r,mass=mass} end
local function gap(b1,o1,b2,o2)
 local c1,c2=S.closest(b1.a+o1,b1.b+o1,b2.a+o2,b2.b+o2);return (c2-c1).Magnitude-(b1.r+b2.r)
end
-- Separated capsules are untouched.
local A=body(Vector3.new(0,0,0),Vector3.yAxis,1,.5);local B=body(Vector3.new(3,0,0),Vector3.yAxis,1,.5)
local o=S.solve({A,B});check(o[1].Magnitude<1e-6 and o[2].Magnitude<1e-6,'separated moved')
-- Overlap resolves; equal masses share the push.
B=body(Vector3.new(.6,0,0),Vector3.yAxis,1,.5);o=S.solve({A,B})
check(gap(A,o[1],B,o[2])>-.01,'overlap not resolved')
check(math.abs(o[1].Magnitude-o[2].Magnitude)<1e-4,'equal mass asymmetric')
-- A swinging (heavy) weapon shoves the idle one.
local H=body(Vector3.new(0,0,0),Vector3.zAxis,2,.5,S.AttackMass);o=S.solve({H,B})
check(o[1].Magnitude<o[2].Magnitude/5,'heavy moved too much')
check(gap(H,o[1],B,o[2])>-.01,'heavy overlap unresolved')
-- Coincident capsules separate without NaN.
o=S.solve({body(Vector3.zero,Vector3.yAxis,1,.5),body(Vector3.zero,Vector3.yAxis,1,.5)})
check(o[1].X==o[1].X and o[2].Magnitude>.3,'coincident fail')
-- Dense random six-weapon clusters: finite, capped, small residual.
local rng=Random.new(7);local worst=0
for _=1,300 do
 local bodies={}
 for i=1,6 do
  local axis=Vector3.new(rng:NextNumber(-1,1),rng:NextNumber(-1,1),rng:NextNumber(-1,1));if axis.Magnitude<.1 then axis=Vector3.yAxis end
  bodies[i]=body(Vector3.new(rng:NextNumber(-3,3),rng:NextNumber(-.5,.5),rng:NextNumber(-3,3)),axis.Unit,rng:NextNumber(0,2.5),rng:NextNumber(.2,.9),i==1 and S.AttackMass or 1)
 end
 local off=S.solve(bodies,8)
 for i=1,6 do local v=off[i];check(v.X==v.X and v.Magnitude<=S.MaxOffset+1e-4,'bad offset') end
 for i=1,5 do for j=i+1,6 do worst=math.min(worst,gap(bodies[i],off[i],bodies[j],off[j])) end end
end
check(worst>-.05,'dense residual '..worst)
-- Capsule axis from real katana bounds.
local k=S.capsule(Vector3.new(.85,5.96,1.54),Vector3.zero)
check(math.abs((k.b-k.a).Magnitude-(5.96-2*k.r))<1e-4 and k.a.X==0,'capsule axis')
-- Pushes apply immediately; the return home is eased.
local g=S.smooth(Vector3.zero,Vector3.new(1,0,0),1/60);local r=S.smooth(Vector3.new(1,0,0),Vector3.zero,1/60)
check(g.X==1 and r.X>.8 and r.X<1,'smoothing rates')
mod:Destroy()
return string.format('%d checks, %d failures; worst residual gap=%.3f\n%s',checks,#fails,worst,table.concat(fails,'\n'))
