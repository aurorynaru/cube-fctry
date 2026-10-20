--!strict
-- GF-001 offline NPC wave prototype: configuration validation.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production, not mapped by
-- default.project.json and never loaded by the main game). Pure Luau: no
-- Roblox engine APIs. Inputs are plain data so any game mode can supply them.

local Config = {}

export type RewardDef = {
	points: number,
}

export type MobDef = {
	displayName: string,
	maxHealth: number,
	reward: RewardDef,
}

export type SpawnPointDef = {
	id: string,
	capacity: number,
	position: { x: number, y: number, z: number },
}

export type WaveDef = {
	mobId: string,
	count: number,
	spawnInterval: number,
	startDelay: number,
}

export type WavesConfig = {
	maxActiveMobs: number,
	interWaveDelay: number,
	mobs: { [string]: MobDef },
	spawnPoints: { SpawnPointDef },
	waves: { WaveDef },
}

local function addError(errors: { string }, message: string)
	table.insert(errors, message)
end

local function isNonEmptyString(value: any): boolean
	return type(value) == "string" and #value > 0
end

local function isPositiveNumber(value: any): boolean
	return type(value) == "number" and value > 0 and value < math.huge
end

local function isPositiveInteger(value: any): boolean
	return isPositiveNumber(value) and value % 1 == 0
end

local function isNonNegativeNumber(value: any): boolean
	return type(value) == "number" and value >= 0 and value < math.huge
end

local function isNonNegativeInteger(value: any): boolean
	return isNonNegativeNumber(value) and value % 1 == 0
end

local function isArray(value: any): boolean
	if type(value) ~= "table" then
		return false
	end
	local count = 0
	for key in pairs(value) do
		if type(key) ~= "number" or key % 1 ~= 0 or key < 1 or key > #value then
			return false
		end
		count += 1
	end
	return count == #value
end

local function isFinite(value: any): boolean
	return type(value) == "number" and value == value and math.abs(value) < math.huge
end

local function validateMobs(config: any, errors: { string }): boolean
	if type(config.mobs) ~= "table" then
		addError(errors, "mobs must be a table of mob definitions")
		return false
	end
	if next(config.mobs) == nil then
		addError(errors, "mobs must define at least one mob")
		return false
	end
	local valid = true
	for mobId, mobDef in pairs(config.mobs) do
		local label = "mobs." .. tostring(mobId)
		if not isNonEmptyString(mobId) then
			addError(errors, "mob ids must be non-empty strings")
			valid = false
		end
		if type(mobDef) ~= "table" then
			addError(errors, label .. " must be a table")
			valid = false
		else
			local def: any = mobDef
			if not isNonEmptyString(def.displayName) then
				addError(errors, label .. ".displayName must be a non-empty string")
				valid = false
			end
			if not isPositiveNumber(def.maxHealth) then
				addError(errors, label .. ".maxHealth must be a number > 0")
				valid = false
			end
			if type(def.reward) ~= "table" or not isNonNegativeInteger(def.reward.points) then
				addError(errors, label .. ".reward.points must be an integer >= 0")
				valid = false
			end
		end
	end
	return valid
end

local function validateSpawnPoints(config: any, errors: { string }): boolean
	if not isArray(config.spawnPoints) then
		addError(errors, "spawnPoints must be an array of spawn point definitions")
		return false
	end
	if #config.spawnPoints < 1 then
		addError(errors, "spawnPoints must define at least one spawn point")
		return false
	end
	local valid = true
	local seenIds = {}
	for index, spawnPoint in ipairs(config.spawnPoints) do
		local label = "spawnPoints[" .. tostring(index) .. "]"
		if type(spawnPoint) ~= "table" then
			addError(errors, label .. " must be a table")
			valid = false
		else
			if not isNonEmptyString(spawnPoint.id) then
				addError(errors, label .. ".id must be a non-empty string")
				valid = false
			elseif seenIds[spawnPoint.id] then
				addError(errors, label .. ".id duplicates an earlier spawn point id")
				valid = false
			else
				seenIds[spawnPoint.id] = true
			end
			if not isPositiveInteger(spawnPoint.capacity) then
				addError(errors, label .. ".capacity must be a positive integer")
				valid = false
			end
			if
				type(spawnPoint.position) ~= "table"
				or not isFinite(spawnPoint.position.x)
				or not isFinite(spawnPoint.position.y)
				or not isFinite(spawnPoint.position.z)
			then
				addError(errors, label .. ".position must have numeric x, y and z")
				valid = false
			end
		end
	end
	return valid
end

local function validateWaves(config: any, errors: { string }): boolean
	if not isArray(config.waves) then
		addError(errors, "waves must be an array of wave definitions")
		return false
	end
	if #config.waves < 1 then
		addError(errors, "waves must define at least one wave")
		return false
	end
	local mobsAreTables = type(config.mobs) == "table"
	local valid = true
	for index, wave in ipairs(config.waves) do
		local label = "waves[" .. tostring(index) .. "]"
		if type(wave) ~= "table" then
			addError(errors, label .. " must be a table")
			valid = false
		else
			if not isNonEmptyString(wave.mobId) then
				addError(errors, label .. ".mobId must be a non-empty string")
				valid = false
			elseif not mobsAreTables or type(config.mobs[wave.mobId]) ~= "table" then
				addError(errors, label .. ".mobId does not reference a defined mob")
				valid = false
			end
			if not isPositiveInteger(wave.count) then
				addError(errors, label .. ".count must be a positive integer")
				valid = false
			end
			if not isNonNegativeNumber(wave.spawnInterval) then
				addError(errors, label .. ".spawnInterval must be a number >= 0")
				valid = false
			end
			if wave.startDelay ~= nil and not isNonNegativeNumber(wave.startDelay) then
				addError(errors, label .. ".startDelay must be a number >= 0")
				valid = false
			end
		end
	end
	return valid
end

function Config.validate(config: any): (boolean, any)
	if type(config) ~= "table" then
		return false, { "config must be a table" }
	end
	local errors = {}
	if not isPositiveInteger(config.maxActiveMobs) then
		addError(errors, "maxActiveMobs must be a positive integer")
	end
	if not isNonNegativeNumber(config.interWaveDelay) then
		addError(errors, "interWaveDelay must be a number >= 0")
	end
	local mobsValid = validateMobs(config, errors)
	local spawnPointsValid = validateSpawnPoints(config, errors)
	local wavesValid = validateWaves(config, errors)
	if not (mobsValid and spawnPointsValid and wavesValid) or #errors > 0 then
		return false, errors
	end
	local normalized = {
		maxActiveMobs = config.maxActiveMobs,
		interWaveDelay = config.interWaveDelay,
		mobs = config.mobs,
		spawnPoints = config.spawnPoints,
		waves = {},
	}
	for _, wave in ipairs(config.waves) do
		local waveDef: any = wave
		table.insert(normalized.waves, {
			mobId = waveDef.mobId,
			count = waveDef.count,
			spawnInterval = waveDef.spawnInterval,
			startDelay = waveDef.startDelay or 0,
		})
	end
	return true, normalized
end

return Config
