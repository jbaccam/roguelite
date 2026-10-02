-- What this player pays for every developer product and pass. Managed pricing is on in the
-- Creator Hub: Roblox sets regional prices (30-100% of the list price) and runs price tests, so
-- buttons must show Roblox's answer, not MonetizationConfig's list price. Each answer is stored
-- as Price_<key> on the local player; MonetizationConfig.price(key) reads it (sandboxed UI
-- modules can read attributes but not call MarketplaceService). Unsandboxed LocalScript in
-- StarterPlayerScripts. Re-asked every 10 minutes, since a price test can change a price.
local Players = game:GetService("Players")
local Market = game:GetService("MarketplaceService")
local RS = game:GetService("ReplicatedStorage")
local Money = require(RS:WaitForChild("RogueliteCombat"):WaitForChild("MonetizationConfig"))
local player = Players.LocalPlayer

local function info(id, kind)
	local ok, result = pcall(function()
		return Market:GetProductInfoAsync(id, kind)
	end)
	if not ok then
		ok, result = pcall(function()
			return Market:GetProductInfo(id, kind)
		end)
	end
	return ok and type(result) == "table" and result or nil
end

local function remember(key, result)
	local price = result and result.PriceInRobux
	if type(price) == "number" and price > 0 then
		player:SetAttribute("Price_" .. key, price)
	end
end

local function refresh()
	for key, product in Money.Products do
		if product.productId > 0 then
			remember(key, info(product.productId, Enum.InfoType.Product))
			task.wait(0.1)
		end
	end
	for key, pass in Money.Passes do
		if pass.gamePassId > 0 then
			remember(key, info(pass.gamePassId, Enum.InfoType.GamePass))
		end
	end
end

while true do
	refresh()
	task.wait(600)
end
