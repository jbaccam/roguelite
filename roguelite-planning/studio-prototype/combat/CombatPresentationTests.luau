-- Pure presentation invariants; call run(require(CombatPresentationPolicy)).
return function(P)
 local checks=0
 local function check(ok,why) checks+=1;assert(ok,why) end
 check(P.ownsCue(10,10),'owner sees own cue')
 check(not P.ownsCue(20,10),'teammate cue hidden')
 check(not P.ownsCue(nil,nil),'missing ownership is not a match')
 check(not P.ownsCue('10',10),'invalid ownership is not coerced')
 check(P.ownsCue(-1,10,true),'isolated showcase may display its scripted cue')
 for _,v in {Vector2.new(1920,1080),Vector2.new(1280,720),Vector2.new(750,369),Vector2.new(390,844),Vector2.new(3840,2160)} do
  for _,fov in {35,70,100} do for _,nominal in {44,58} do
   for tick=0,50 do
    local previous=math.huge
    for _,distance in {2,10,25,50,90,140} do
     local d=P.headline(v,distance,fov,nominal,tick/40)
     check(d.text<=48*math.clamp(math.min(v.X,v.Y)/900,.25,1.35),'pop never exceeds viewport cap')
     check(d.text<=previous,'distant teammate text never grows')
     check(d.width<=v.X*.46 and d.height<v.Y*.2,'headline fits phone/desktop display')
     check(d.stroke<=3*math.clamp(math.min(v.X,v.Y)/900,.25,1.35),'outline scales with text')
     previous=d.text
    end
   end
   check(not P.headline(v,-1,fov,nominal,0).visible,'behind-camera text hidden')
   check(not P.headline(v,141,fov,nominal,0).visible,'distant text culled')
  end end
 end
 return {passed=true,checks=checks}
end
