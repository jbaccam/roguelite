-- A lifetime boundary for presentation-only production effects. No remotes or gameplay state.
-- The shared VfxKit scheduler retires cancelled jobs on its next frame; their callbacks cannot
-- create new effects after the owning preview closes. Short helper bursts own only destroyed parts.
local Scope = {}
function Scope.new(kit, folder)
	local active = true
	local pending = {}
	local scheduler = table.clone(task)
	scheduler.delay = function(seconds, callback)
		if not active then
			return
		end
		local thread
		thread = task.delay(seconds, function()
			pending[thread] = nil
			if active and folder.Parent then
				callback()
			end
		end)
		pending[thread] = true
		return thread
	end
	local scoped = table.clone(kit)
	-- This isolated one-weapon theatre must not lose auras when framing a long attack.
	-- Production multiplayer distance culling is unchanged outside this scoped adapter.
	scoped.near = function() return active and folder.Parent ~= nil end
	scoped.animate = function(duration, update, cleanup, category, budget)
		if not active or not folder.Parent then
			return
		end
		kit.animate(duration, function(t, age)
			if not active or not folder.Parent then
				return true
			end
			return update(t, age)
		end, function()
			if active and folder.Parent and cleanup then
				cleanup()
			end
		end, "showcase_" .. tostring(category), math.min(budget or 32, 48))
	end
	return scoped,
		function()
			active = false
			for thread in pending do
				pcall(task.cancel, thread)
			end
			table.clear(pending)
		end,
		scheduler
end
return Scope
