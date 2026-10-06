-- Studio CLIENT only. require(thisModule)() checks production cursor ownership using a tiny
-- temporary ScreenGui; sends no remotes, changes no player attributes and awards nothing.
return function()
 local Run=game:GetService('RunService')
 assert(Run:IsStudio() and Run:IsClient(),'Studio client only')
 local RS=game:GetService('ReplicatedStorage')
 local T=require(RS:WaitForChild('UITheme'))
 local Input=game:GetService('UserInputService')
 local Gui=game:GetService('GuiService')
 local player=game:GetService('Players').LocalPlayer
 local screen=Instance.new('ScreenGui');screen.Name='ResultsCursorQA';screen.Enabled=false;screen.Parent=player.PlayerGui
 local button=Instance.new('TextButton');button.Size=UDim2.fromOffset(1,1);button.Parent=screen
 local oldMouse,oldIcon,oldSelection=Input.MouseBehavior,Input.MouseIconEnabled,Gui.SelectedObject
 local camera=workspace.CurrentCamera
 local oldType,oldSubject,oldFov=camera.CameraType,camera.CameraSubject,camera.FieldOfView
 local dispose=T.freeMenuCursor(screen)
 local key='ResultsCursorQACamera'
 local ok,err=xpcall(function()
  Run:BindToRenderStep(key,Enum.RenderPriority.Camera.Value,function() Input.MouseBehavior=Enum.MouseBehavior.LockCenter;Input.MouseIconEnabled=false end)
  screen.Enabled=true;Gui.SelectedObject=button
  task.wait(.25)
  assert(Input.MouseBehavior==Enum.MouseBehavior.Default and Input.MouseIconEnabled,'results lost cursor to camera')
  screen.Enabled=false
  task.wait(.25)
  assert(Input.MouseBehavior==Enum.MouseBehavior.LockCenter,'hidden results still override camera input')
  assert(Gui.SelectedObject~=button,'hidden results retained gamepad selection')
  screen.Enabled=true;task.wait(.25)
  assert(Input.MouseBehavior==Enum.MouseBehavior.Default,'second results failed to acquire cursor')
  screen:Destroy();task.wait(.25)
  assert(Input.MouseBehavior==Enum.MouseBehavior.LockCenter,'destroyed results leaked cursor callback')
 end,debug.traceback)
 Run:UnbindFromRenderStep(key);dispose();screen:Destroy()
 Input.MouseBehavior=oldMouse;Input.MouseIconEnabled=oldIcon;Gui.SelectedObject=oldSelection
 camera.CameraType=oldType;camera.CameraSubject=oldSubject;camera.FieldOfView=oldFov
 assert(ok,err)
 return {passed=true,checks=5,scope='production menu cursor ownership; no teleport or rewards'}
end
