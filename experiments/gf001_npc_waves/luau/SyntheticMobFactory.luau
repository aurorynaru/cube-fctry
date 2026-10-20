--!strict
-- GF-001-Q2 synthetic-only stand-in for the small Instance/Humanoid/Signal seam.
-- Never uses Instance, game, workspace, or other engine globals.

local SyntheticMobFactory = {}

function SyntheticMobFactory.new(): any
	local issued = {}
	local factory = {
		created = {},
		failCreate = false,
		failPartial = false,
		failConnect = false,
		failDisconnect = false,
		failDestroy = false,
	}

	function factory.owns(object: any, token: any): boolean
		return type(object) == "table" and issued[object] == token and token ~= nil
	end

	function factory.create(record: any, point: any, token: any): (boolean, any)
		if factory.failCreate then
			return false, nil
		end
		local listeners: { any } = {}
		local signal = { synthetic = true }
		function signal.Connect(callback: () -> ()): any
			if factory.failConnect then
				error("synthetic connect failure", 0)
			end
			local connection = { Connected = true, synthetic = true }
			function connection.Disconnect(): boolean
				if factory.failDisconnect then
					return false
				end
				connection.Connected = false
				return true
			end
			table.insert(listeners, { callback = callback, connection = connection })
			return connection
		end
		function signal.Fire()
			-- Snapshot lets tests retain an old callback after disconnection.
			for _, entry in ipairs(table.clone(listeners)) do
				if entry.connection.Connected then
					entry.callback()
				end
			end
		end
		function signal.Snapshot(): { any }
			local callbacks = {}
			for _, entry in ipairs(listeners) do
				table.insert(callbacks, entry.callback)
			end
			return callbacks
		end
		local humanoid = { synthetic = true, Health = record.maxHealth, Died = signal }
		function humanoid.Die()
			humanoid.Health = 0
			signal.Fire()
		end
		local object = {
			synthetic = true,
			OwnerToken = token,
			MobRecordId = record.id,
			MobId = record.mobId,
			SpawnPointId = point.id,
			Humanoid = humanoid,
			Destroyed = false,
			destroyCalls = 0,
		}
		issued[object] = token
		table.insert(factory.created, object)
		function object.Destroy(): boolean
			if factory.failDestroy then
				return false
			end
			if not object.Destroyed then
				object.Destroyed = true
				object.destroyCalls += 1
			end
			return true
		end
		if factory.failPartial then
			return false, object
		end
		return true, object
	end

	return factory
end

return SyntheticMobFactory
