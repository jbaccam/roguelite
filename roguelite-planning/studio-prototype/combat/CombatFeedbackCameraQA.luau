-- Optional temporary CLIENT Play camera for CombatFeedbackPlayQA. No gameplay/UI state edits.
-- Load with the same HTTP/read + loadstring pattern in client MCP. Camera auto-restores when
-- the fixture disappears. Stop Play after QA. Root screenshot tool captures the production FX.
return function()
 local Run=game:GetService('RunService');assert(Run:IsStudio() and Run:IsRunning() and Run:IsClient(),'Studio CLIENT Play only')
 local stage=assert(workspace:FindFirstChild('CombatFeedbackQA'),'Start server fixture first')
 local camera=workspace.CurrentCamera
 local oldType,oldSubject,oldCF,oldFov=camera.CameraType,camera.CameraSubject,camera.CFrame,camera.FieldOfView
 local center=stage:GetAttribute('Center');local active=true;local connection
 local function restore()
  if not active then return end;active=false
  if connection then connection:Disconnect() end
  camera.CameraType=oldType;camera.CameraSubject=oldSubject;camera.CFrame=oldCF;camera.FieldOfView=oldFov
 end
 connection=Run.RenderStepped:Connect(function()
  if not stage.Parent then restore();return end
  camera.CameraType=Enum.CameraType.Scriptable;camera.FieldOfView=58
  camera.CFrame=CFrame.lookAt(center+Vector3.new(0,43,48),center+Vector3.new(0,1,0))
 end)
 return {camera='Three production combat lanes',autoRestore=true}
end
