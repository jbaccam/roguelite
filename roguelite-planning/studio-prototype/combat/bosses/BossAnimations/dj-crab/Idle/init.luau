local clip=game:GetService("HttpService"):JSONDecode([=[{"duration":3.8709677,"loop":true,"beats":8,"note":"8 beats at 124 BPM: frames 0-92 at 1/24 s, then a closure frame at 3.8709677 s equal to frame 0 (the loop is exactly 8 beats, not 93/24 s)"}]=])
clip.frames={}
for _,frame in require(script:WaitForChild("Frames01")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames02")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames03")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames04")) do table.insert(clip.frames,frame) end
for _,frame in require(script:WaitForChild("Frames05")) do table.insert(clip.frames,frame) end
return clip
