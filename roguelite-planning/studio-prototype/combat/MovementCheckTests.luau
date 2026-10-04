-- Pure checks for MovementCheck (run in Studio Edit: loadstring this file and call it with the module).
return function(M)
 local count=0
 local function check(ok,msg) count+=1;assert(ok,msg) end
 -- Runs `seconds` of samples every 0.1 s moving at `vx` studs/s; returns the first verdict and its time.
 local function run(s,t0,from,seconds,vx,opts)
  opts=opts or {}
  local p=from
  for i=1,math.floor(seconds*10+.5) do
   local t=t0+i*.1;p+=Vector3.new(vx*.1,(opts.climb or 0)*.1,0)
   local why=M.step(s,t,p,opts.speed or 24,opts.gap or 3,opts.vy or 0,opts.inside~=false)
   if why then return why,t,p end
  end
  return nil,t0+seconds,p
 end
 -- Walking and sprinting at full speed for 10 s never trips it.
 local s=M.new(Vector3.zero,0)
 check(run(s,0,Vector3.zero,10,24)==nil,'walking at 24 is fine')
 s=M.new(Vector3.zero,0);check(run(s,0,Vector3.zero,10,44.8,{speed=40})==nil,'top speed 40 with the air bonus is fine')
 -- A short burst (lag catch-up, boss knockback ~28 studs/s) passes.
 s=M.new(Vector3.zero,0);run(s,0,Vector3.zero,2,24)
 local why=run(s,2,Vector3.new(48,0,0),.3,90);check(why==nil,'0.3 s burst at 90 passes')
 -- A speed hack at 100 studs/s is caught within a second.
 s=M.new(Vector3.zero,0);local w,t=run(s,0,Vector3.zero,3,100)
 check(w=='speed' and t<=1.5,'100 studs/s caught: '..tostring(w)..' at '..tostring(t))
 -- Safe spot is the last standing position before the cheat.
 s=M.new(Vector3.zero,0);run(s,0,Vector3.zero,2,20);local before=s.safe
 w=run(s,2,before,3,120)
 check(w~=nil and (s.safe-before).Magnitude<25,'safe spot stays near where the cheat began')
 -- A teleport of 150 studs is caught on the spot.
 s=M.new(Vector3.zero,0);run(s,0,Vector3.zero,1,10)
 check(M.step(s,1.1,Vector3.new(170,0,0),24,3,0,true)=='teleport','teleport caught at once')
 -- Flying: hovering 30 studs up for 2.5 s; falling from a ledge is not flying; a jump isn't either.
 s=M.new(Vector3.zero,0);w,t=run(s,0,Vector3.zero,4,5,{gap=30,vy=0})
 check(w=='fly' and t>=2.5 and t<=2.7,'hovering caught after 2.5 s: '..tostring(w)..' '..tostring(t))
 s=M.new(Vector3.zero,0);check(run(s,0,Vector3.zero,4,5,{gap=30,vy=-40})==nil,'falling is not flying')
 s=M.new(Vector3.zero,0);check(run(s,0,Vector3.zero,1,5,{gap=9,vy=0})==nil,'a jump is not flying')
 -- Leaving the arena for a second is caught; ducking out for half a second isn't.
 s=M.new(Vector3.zero,0);w,t=run(s,0,Vector3.zero,3,5,{inside=false})
 check(w=='bounds' and t>=1 and t<=1.2,'outside for 1 s caught')
 s=M.new(Vector3.zero,0);check(run(s,0,Vector3.zero,.5,5,{inside=false})==nil,'outside for 0.5 s is fine')
 -- A server move (reset) starts clean: no false teleport afterwards.
 s=M.new(Vector3.zero,0);run(s,0,Vector3.zero,1,10);M.reset(s,Vector3.new(500,0,0),1)
 check(run(s,1,Vector3.new(500,0,0),2,20)==nil,'after a server move all is well')
 -- An approved dash (2026-10-04, CharacterStats.Dash.Allowance): 30 more studs pass for 1.5 s. 40
 -- studs in the first 0.1 s is a strike without it (limit 24 x 1.5 x 0.1 + 16 = 19.6), fine with it (49.6).
 s=M.new(Vector3.zero,0);M.allow(s,0,30);M.step(s,.1,Vector3.new(40,0,0),24,3,0,true)
 check(s.strikes==0,'a dash within its allowance is no strike')
 s=M.new(Vector3.zero,0);M.step(s,.1,Vector3.new(40,0,0),24,3,0,true)
 check(s.strikes==1,'the same burst without a dash is a strike')
 M.allow(s,0,30);M.allow(s,0,30);check(s.bonus==30,'allowances replace each other, never stack')
 -- The dash curve (CharacterStats.Dash): 280 studs/s easing out ((1-u)^3) to the run speed over
 -- 0.3 s; studs covered after t s. At a run of 16: 0.3 x (16 + 264/4) = 24.6 studs.
 local function dashed(t,speed) local u=math.min(t/.3,1);return speed*.3*u+(280-speed)*.3/4*(1-(1-u)^4) end
 -- That dash every 3 s while walking at 16 never trips it, sampled 0.1 s apart as the guard does.
 s=M.new(Vector3.zero,0);local at,p=0,Vector3.zero
 for _=1,4 do
  M.allow(s,at,30)
  for i=1,3 do w=M.step(s,at+i*.1,p+Vector3.new(dashed(i*.1,16),0,0),23.2,3,0,true);check(w==nil,'a dash passes') end
  at+=.3;p+=Vector3.new(dashed(.3,16),0,0)
  w,at,p=run(s,at,p,2.7,16,{speed=23.2});check(w==nil,'walking after a dash passes')
 end
 -- A 100 studs/s speed hack that got one dash allowance is still caught, by 1.2 s.
 s=M.new(Vector3.zero,0);M.allow(s,0,30);w,t=run(s,0,Vector3.zero,3,100)
 check(w=='speed' and t<=1.2,'a speed hack with a dash allowance is caught: '..tostring(w)..' at '..tostring(t))
 -- Bounds: walls from -100..100 in X and Z, margin 20.
 local wall=function(x,z,sx,sz) return {CFrame=CFrame.new(x,5,z),Size=Vector3.new(sx,10,sz)} end
 local box=M.bounds({wall(-100,0,2,200),wall(100,0,2,200),wall(0,-100,200,2),wall(0,100,200,2)},20)
 check(box and math.abs(box[1]+121)<1e-6 and math.abs(box[2]-121)<1e-6,'box from walls + margin')
 check(M.inside(box,Vector3.new(115,0,0)) and not M.inside(box,Vector3.new(130,0,0)),'inside / outside')
 check(M.inside(nil,Vector3.new(1e6,0,0)),'no walls: everywhere is inside')
 -- A rotated wall (45 degrees) widens the box by its corners.
 local rot={CFrame=CFrame.Angles(0,math.rad(45),0),Size=Vector3.new(10,4,10)}
 local rb=M.bounds({rot},0);check(math.abs(rb[2]-math.sqrt(50))<1e-3,'rotated part extents')
 return count
end
