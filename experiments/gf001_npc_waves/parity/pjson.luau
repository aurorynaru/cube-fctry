--!strict
-- GF-001-Q1 parity: minimal canonical JSON serializer for harness-owned data.
--
-- Part of experiments/gf001_npc_waves/parity/ (isolated, non-production).
-- Serializes only the plain scalar/table projections built by this harness:
-- flat maps with string keys, arrays with contiguous 1..n entries, nil, booleans,
-- finite numbers and ASCII strings. Map keys are sorted so output is canonical.
-- It is not a general-purpose JSON library and intentionally errors on anything
-- else. Numbers use %d for integral values and tostring (shortest round-trip
-- within %.14g) otherwise; the Python comparator parses and compares structures,
-- so textual float formatting differences are irrelevant.

local Pjson = {}

local function encodeString(value: string): string
	local out = '"'
	for index = 1, #value do
		local byte = string.byte(value, index)
		if byte == 34 then
			out = out .. '\\"'
		elseif byte == 92 then
			out = out .. "\\\\"
		elseif byte < 32 then
			out = out .. string.format("\\u%04x", byte)
		else
			out = out .. string.sub(value, index, index)
		end
	end
	return out .. '"'
end

local function encodeNumber(value: number): string
	if value ~= value or value == math.huge or value == -math.huge then
		error("[GF001-Q1] cannot encode nonfinite numbers", 0)
	end
	if value % 1 == 0 and math.abs(value) < 1e15 then
		return string.format("%d", value)
	end
	return tostring(value)
end

local function isArrayLike(value: { [any]: any }): boolean
	local count = #value
	if count == 0 then
		return next(value) == nil
	end
	return next(value, count) == nil
end

function Pjson.encode(value: any): string
	if value == nil then
		return "null"
	end
	local kind = type(value)
	if kind == "boolean" then
		if value then
			return "true"
		end
		return "false"
	end
	if kind == "number" then
		return encodeNumber(value)
	end
	if kind == "string" then
		return encodeString(value)
	end
	if kind == "table" then
		if isArrayLike(value) then
			local items = {}
			for index = 1, #value do
				table.insert(items, Pjson.encode(value[index]))
			end
			return "[" .. table.concat(items, ",") .. "]"
		end
		local keys = {}
		for key in pairs(value) do
			table.insert(keys, tostring(key))
		end
		table.sort(keys)
		local fields = {}
		for _, key in ipairs(keys) do
			table.insert(fields, encodeString(key) .. ":" .. Pjson.encode(value[key]))
		end
		return "{" .. table.concat(fields, ",") .. "}"
	end
	error("[GF001-Q1] cannot encode type " .. kind, 0)
end

return Pjson
