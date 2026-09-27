-- Generated from combat-ready/lava-slime/StudioAnimationData.json
local data=game:GetService("HttpService"):JSONDecode([=[{"id":"lava-slime","fps":24,"bones":{"Root":{"parent":null,"rest":[0,0,0,1,1.2246467202362698e-16,-1.2246469849340659e-16,-1.2246469849340659e-16,1,-1.6292067073209182e-07,1.2246467202362698e-16,1.6292067073209182e-07,1]},"Body":{"parent":"Root","rest":[-1.8369701134416293e-17,0.14999999105930328,4.172129308699368e-09,1,6.517753392387821e-24,0,-6.517753392387821e-24,1,0,0,0,1]},"Crown":{"parent":"Body","rest":[-1.1634144437814605e-16,0.949999988079071,-2.1867390120888786e-09,1,6.517753392387821e-24,0,-6.517753392387821e-24,1,0,0,0,1]}},"motion":{"strideLength":1.1724137931034484,"nominalSpeed":1.3399014778325125,"attackImpact":0.5308333333333333,"attackRecovery":0.6283333333333333,"attackDuration":1.0833333333333333},"coordinateSpace":"Actual Roblox FBX import joint-local Transform; derived from receipt","rigType":"Bone","sourceAnimationHash":"9f64a8596f6315b2976f82bae5921c247b8f16a90be342a193ceeef4bfc8a667","importReceiptHash":"2529f9053c198930b4a56a56d772693a307459ee58bda2089c315ee99a3f59e0","baselineModelScale":0.009999999776482582,"authoringScale":1,"sourceImportAsset":"mob-production/reference-rebuilds/lava-slime/Model.fbx","sourceAnimationAsset":"mob-production/combat-ready/lava-slime/Model.blend"}]=])
data.clips={}
data.clips.Idle=require(script:WaitForChild("Idle"))
data.clips.Move=require(script:WaitForChild("Move"))
data.clips.Attack=require(script:WaitForChild("Attack"))
data.clips.Hit=require(script:WaitForChild("Hit"))
data.clips.Death=require(script:WaitForChild("Death"))
return data
