local clip=game:GetService("HttpService"):JSONDecode([=[{"duration":1.5,"loop":true}]=])
clip.frames={}
for _,frame in require(script:WaitForChild("Frames01")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames02")) do table.insert(clip.frames,frame) end
return clip
