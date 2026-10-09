local clip=game:GetService("HttpService"):JSONDecode([=[{"duration":2.283333,"loop":false,"fps":60}]=])
clip.frames={}
for _,frame in require(script:WaitForChild("Frames01")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames02")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames03")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames04")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames05")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames06")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames07")) do table.insert(clip.frames,frame) end
return clip
