-- Studio client: actual modal geometry, responsive resize and opening-tween ownership.
return function()
 local R=game:GetService('RunService');assert(R:IsStudio() and R:IsClient(),'Studio client only')
 local T=require(game.ReplicatedStorage.UITheme)
 local gui=Instance.new('ScreenGui');gui.Name='MenuScaleQA';gui.Parent=game.Players.LocalPlayer.PlayerGui
 local host=T.frame(gui,'Viewport',0,0,1920,1080)
 local checks=0;local measured={};local win
 local function check(ok,message) checks+=1;assert(ok,message) end
 local ok,err=xpcall(function()
  for _,large in {false,true} do
   for _,size in {Vector2.new(1920,1080),Vector2.new(2560,1440),Vector2.new(1366,768),Vector2.new(1024,768),Vector2.new(844,390),Vector2.new(667,375)} do
    host.Size=UDim2.fromOffset(size.X,size.Y);task.wait()
    win=T.window(host,'WindowQA','Menu readability',large and 1100 or 920,640,nil,{large=large})
    task.wait(.2)
    local p,s=win.Holder.AbsolutePosition-host.AbsolutePosition,win.Holder.AbsoluteSize
    check(p.X>=-1 and p.X+s.X<=size.X+1,'window width '..tostring(size))
    check(p.Y-30*win.Scale.Scale>=-1 and p.Y+s.Y<=size.Y+1,'window height/title '..tostring(size))
    if size.X==1920 then
     check(win.Scale.Scale> (large and 1.3 or 1.15),'desktop menu did not grow')
     table.insert(measured,{large=large,scale=win.Scale.Scale,width=s.X,height=s.Y})
    end
    win.Close();win=nil
   end
  end
  host.Size=UDim2.fromOffset(1920,1080);task.wait()
  win=T.window(host,'ResizeQA','Resize during open',920,640)
  host.Size=UDim2.fromOffset(1366,768);task.wait(.05)
  local settled=win.Scale.Scale;task.wait(.2)
  check(math.abs(win.Scale.Scale-settled)<.0001,'opening tween overwrote responsive scale')
  win.Close();win=nil
 end,debug.traceback)
 if win then win.Close() end;gui:Destroy();assert(ok,err)
 return {checks=checks,desktop=measured}
end
