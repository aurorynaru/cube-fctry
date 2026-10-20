--!strict
-- C1C reusable Studio test-rig helper.
--
-- This file is NOT auto-run and is not mapped by default.project.json. A future
-- authorized execution milestone may load it through Roblox Studio MCP and call
-- C1C.buildFromPlan(plan), where `plan.rig` comes from:
--     python tool/c1c_verify.py plan --spec <spec>
--
-- Safety properties:
--   * Only creates objects under Workspace.C1C_TextureTest_<runId>.
--   * Every created object is C1C_-prefixed and carries C1C_RunId,
--     C1C_TestOnly=true and the C1C_TextureTest tag.
--   * Cleanup refuses to delete anything that fails ownership verification.
--   * Camera restoration is explicit and verified; no save/publish/upload.

local CollectionService = game:GetService("CollectionService")
local ContentProvider = game:GetService("ContentProvider")
local Selection = game:GetService("Selection")

local TAG = "C1C_TextureTest"
local PREFIX = "C1C_"
local FOLDER_PREFIX = "C1C_TextureTest_"
local RUN_ATTR = "C1C_RunId"
local TESTONLY_ATTR = "C1C_TestOnly"

local C1C = {}

local function fail(message: string): never
	error("[C1C] " .. message, 0)
end

local function assertPrefix(name: string)
	if string.sub(name, 1, #PREFIX) ~= PREFIX then
		fail("object is not C1C_-prefixed: " .. name)
	end
end

local function isValidIdentifier(value: any): boolean
	if type(value) ~= "string" or #value == 0 or #value > 64 then
		return false
	end
	return string.match(value, "^[A-Za-z0-9][A-Za-z0-9_%-]*$") ~= nil
end

local ALLOWED_CLASSES = {
	Folder = true,
	Part = true,
	Texture = true,
	BillboardGui = true,
	TextLabel = true,
}

local function validatePlan(plan: any): { [string]: any }
	if type(plan) ~= "table" then
		fail("plan must be a table")
	end
	local runId = plan.run_id
	if not isValidIdentifier(runId) then
		fail("plan.run_id must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}")
	end
	local rig = plan.rig
	if type(rig) ~= "table" or type(rig.objects) ~= "table" then
		fail("plan.rig.objects is required")
	end
	local folderPath = rig.folder
	if folderPath ~= FOLDER_PREFIX .. runId then
		fail("plan folder does not match the run ID")
	end
	local objectCount = #rig.objects
	if objectCount == 0 then
		fail("plan.rig.objects must not be empty")
	end
	if rig.object_count ~= nil and rig.object_count ~= objectCount then
		fail("plan.rig.object_count does not match the object inventory")
	end
	local seen = {}
	local folderSeen = false
	for index, item in ipairs(rig.objects) do
		if type(item) ~= "table" then
			fail("plan object " .. tostring(index) .. " is not a table")
		end
		if not ALLOWED_CLASSES[item.class_name] then
			fail("unsupported plan class: " .. tostring(item.class_name))
		end
		if not isValidIdentifier(item.name) then
			fail("plan object " .. tostring(index) .. " has an invalid name")
		end
		assertPrefix(item.name)
		if type(item.parent) ~= "string" or type(item.path) ~= "string" then
			fail("plan object " .. tostring(index) .. " needs string parent/path")
		end
		if item.path ~= item.parent .. "." .. item.name then
			fail("plan object path does not match parent/name: " .. item.path)
		end
		if item.parent ~= folderPath and string.sub(item.parent, 1, #folderPath + 1) ~= folderPath .. "." then
			fail("plan parent is outside the run folder: " .. item.parent)
		end
		if seen[item.path] then
			fail("duplicate plan object path: " .. item.path)
		end
		seen[item.path] = true
		if item.path == folderPath then
			folderSeen = true
			if item.class_name ~= "Folder" or item.parent ~= "Workspace" then
				fail("plan run folder must be a Workspace Folder")
			end
		end
		if type(item.attributes) ~= "table" or item.attributes[RUN_ATTR] ~= runId then
			fail("plan object lacks the run-ID attribute: " .. item.path)
		end
		if item.attributes[TESTONLY_ATTR] ~= true then
			fail("plan object lacks C1C_TestOnly=true: " .. item.path)
		end
		if type(item.tags) ~= "table" then
			fail("plan object tags must be a list: " .. item.path)
		end
		local hasTag = false
		for _, tag in ipairs(item.tags) do
			if tag == TAG then
				hasTag = true
			end
		end
		if not hasTag then
			fail("plan object lacks the C1C_TextureTest tag: " .. item.path)
		end
	end
	if not folderSeen then
		fail("plan does not include the run folder object")
	end
	return plan
end

local function expectedPaths(plan: { [string]: any }): { [string]: boolean }
	local expected = {}
	for _, item in ipairs(plan.rig.objects) do
		expected[item.path] = true
	end
	return expected
end

local function isDescendantOf(instance: Instance, ancestor: Instance): boolean
	local current: Instance? = instance
	while current ~= nil do
		if current == ancestor then
			return true
		end
		current = current.Parent
	end
	return false
end

local function vector3(value: any): Vector3
	return Vector3.new(value[1], value[2], value[3])
end

local function color3(value: any): Color3
	return Color3.new(value[1], value[2], value[3])
end

local function applyProperties(instance: Instance, properties: { [string]: any })
	for key, value in pairs(properties) do
		if key == "Position" or key == "Size" then
			(instance :: any)[key] = vector3(value)
		elseif key == "Color" then
			(instance :: any).Color = color3(value)
		elseif key == "Material" then
			(instance :: any).Material = Enum.Material[value]
		elseif key == "Face" then
			(instance :: any).Face = Enum.NormalId[value]
		elseif key == "Text" then
			if instance:IsA("TextLabel") then
				(instance :: any).Text = value
			end
		else
			(instance :: any)[key] = value
		end
	end
end

local function applyOwnership(instance: Instance, runId: string)
	instance:SetAttribute(RUN_ATTR, runId)
	instance:SetAttribute(TESTONLY_ATTR, true)
	CollectionService:AddTag(instance, TAG)
	assertPrefix(instance.Name)
end

local function findByPath(path: string): Instance
	local segments = string.split(path, ".")
	if segments[1] ~= "Workspace" then
		fail("only Workspace-relative paths are supported: " .. path)
	end
	local current: Instance = workspace
	for index = 2, #segments do
		local child = current:FindFirstChild(segments[index])
		if child == nil then
			fail("missing plan parent: " .. path)
		end
		current = child
	end
	return current
end

function C1C.captureBaseline(): { [string]: any }
	local camera = workspace.CurrentCamera
	if camera == nil then
		fail("Workspace.CurrentCamera is unavailable")
	end
	local children = {}
	for _, child in ipairs(workspace:GetChildren()) do
		table.insert(children, { name = child.Name, class_name = child.ClassName })
	end
	local tags = {}
	for _, tag in ipairs(CollectionService:GetTags(workspace)) do
		table.insert(tags, tag)
	end
	local tagged = {}
	for _, instance in ipairs(CollectionService:GetTagged(TAG)) do
		table.insert(tagged, instance:GetFullName())
	end
	local x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 = camera.CFrame:GetComponents()
	local selection = {}
	for _, instance in ipairs(Selection:Get()) do
		table.insert(selection, instance:GetFullName())
	end
	return {
		children = children,
		attributes = {},
		tags = tags,
		camera = {
			cframe = { x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 },
			camera_type = camera.CameraType.Name,
			viewport = { camera.ViewportSize.X, camera.ViewportSize.Y },
		},
		selection = selection,
		tagged = tagged,
	}
end

function C1C.restoreCamera(baseline: { [string]: any }): { [string]: any }
	local camera = workspace.CurrentCamera
	if camera == nil then
		fail("Workspace.CurrentCamera is unavailable")
	end
	local values = baseline.camera.cframe
	camera.CFrame = CFrame.new(table.unpack(values))
	local cameraType = Enum.CameraType[baseline.camera.camera_type]
	if cameraType ~= nil then
		camera.CameraType = cameraType
	end
	local x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 = camera.CFrame:GetComponents()
	local current = { x, y, z, r00, r01, r02, r10, r11, r12, r20, r21, r22 }
	local maxDelta = 0
	for index = 1, 12 do
		maxDelta = math.max(maxDelta, math.abs(current[index] - values[index]))
	end
	return {
		matched = maxDelta <= 1e-6 and camera.CameraType.Name == baseline.camera.camera_type,
		max_delta = maxDelta,
		camera_type = camera.CameraType.Name,
	}
end

function C1C.verifyOwnership(folder: Instance, runId: string, expected: { [string]: boolean }?): { [string]: any }
	if not folder:IsA("Folder") then
		fail("run root is not a Folder: " .. folder:GetFullName())
	end
	local violations = {}
	local namingIssues = {}
	local owned = { folder }
	local expectedRunId = runId
	local function inspect(instance: Instance)
		if not isDescendantOf(instance, folder) then
			return
		end
		if instance ~= folder then
			table.insert(owned, instance)
		end
		local fullName = instance:GetFullName()
		local name = instance.Name
		if expected ~= nil and expected[fullName] ~= true then
			local repairable = (instance:IsA("Texture") or instance:IsA("Decal"))
				and (name == "Texture" or name == "Decal")
			if not repairable then
				table.insert(violations, {
					path = fullName,
					code = "unexpected_object",
				})
			end
		end
		if string.sub(name, 1, #PREFIX) ~= PREFIX then
			if instance:IsA("Texture") or instance:IsA("Decal") then
				table.insert(namingIssues, {
					path = fullName,
					class_name = instance.ClassName,
					current_name = name,
					proposed_name = PREFIX .. instance.ClassName,
				})
			else
				table.insert(violations, {
					path = fullName,
					code = "name_prefix",
					actual = name,
				})
			end
		end
		if instance:GetAttribute(RUN_ATTR) ~= expectedRunId then
			table.insert(violations, {
				path = fullName,
				code = "run_id",
				actual = instance:GetAttribute(RUN_ATTR),
			})
		end
		if instance:GetAttribute(TESTONLY_ATTR) ~= true then
			table.insert(violations, {
				path = fullName,
				code = "test_only",
				actual = instance:GetAttribute(TESTONLY_ATTR),
			})
		end
		if not CollectionService:HasTag(instance, TAG) then
			table.insert(violations, { path = fullName, code = "tag" })
		end
		for _, child in ipairs(instance:GetChildren()) do
			inspect(child)
		end
	end
	inspect(folder)
	local outsideTagged = {}
	for _, instance in ipairs(CollectionService:GetTagged(TAG)) do
		if not isDescendantOf(instance, folder) then
			table.insert(outsideTagged, instance:GetFullName())
			table.insert(violations, {
				path = instance:GetFullName(),
				code = "tagged_outside_rig",
			})
		end
	end
	local outsidePrefixed = {}
	local outsideRunAttribute = {}
	for _, instance in ipairs(workspace:GetDescendants()) do
		if not isDescendantOf(instance, folder) then
			if string.sub(instance.Name, 1, #PREFIX) == PREFIX then
				table.insert(outsidePrefixed, instance:GetFullName())
				table.insert(violations, {
					path = instance:GetFullName(),
					code = "prefixed_outside_rig",
				})
			end
			if instance:GetAttribute(RUN_ATTR) == expectedRunId then
				table.insert(outsideRunAttribute, instance:GetFullName())
				table.insert(violations, {
					path = instance:GetFullName(),
					code = "run_attribute_outside_rig",
				})
			end
		end
	end
	local missing = {}
	local expectedCount: number? = nil
	if expected ~= nil then
		expectedCount = 0
		for path in pairs(expected) do
			expectedCount += 1
			local okPath, instance = pcall(findByPath, path)
			if not okPath or instance == nil then
				table.insert(missing, path)
			end
		end
	end
	return {
		ok = #violations == 0
			and #namingIssues == 0
			and #outsideTagged == 0
			and #outsidePrefixed == 0
			and #outsideRunAttribute == 0,
		object_count = #owned,
		expected_object_count = expectedCount,
		missing_objects = missing,
		violations = violations,
		naming_issues = namingIssues,
		outside_tagged = outsideTagged,
		outside_prefixed = outsidePrefixed,
		outside_run_attribute = outsideRunAttribute,
	}
end

function C1C.buildFromPlan(plan: { [string]: any }): { [string]: any }
	validatePlan(plan)
	local runId = plan.run_id
	local folderName = plan.rig.folder
	local expected = expectedPaths(plan)
	if workspace:FindFirstChild(folderName) ~= nil then
		fail("run folder already exists: " .. folderName)
	end
	if #CollectionService:GetTagged(TAG) > 0 then
		fail("pre-existing C1C_TextureTest tags exist; inspect before starting")
	end
	for _, instance in ipairs(workspace:GetDescendants()) do
		if string.sub(instance.Name, 1, #PREFIX) == PREFIX then
			fail("pre-existing C1C_-prefixed objects exist; inspect before starting")
		end
	end

	local phase = "creating_folder"
	local ok, resultOrError = xpcall(function()
		local folder = Instance.new("Folder")
		folder.Name = folderName
		applyOwnership(folder, runId)
		folder.Parent = workspace

		local created = { folder }
		phase = "creating_objects"
		for _, item in ipairs(plan.rig.objects) do
			if item.class_name == "Folder" or item.class_name == "TextLabel" then
				continue
			end
			local parent = findByPath(item.parent)
			if parent ~= folder and not isDescendantOf(parent, folder) then
				fail("plan parent is outside the run folder: " .. tostring(item.parent))
			end
			local instance = Instance.new(item.class_name)
			instance.Name = item.name
			applyProperties(instance, item.properties or {})
			applyOwnership(instance, runId)
			instance.Parent = parent
			table.insert(created, instance)
			if item.class_name == "BillboardGui" then
				local label = Instance.new("TextLabel")
				label.Name = "C1C_Text"
				label.Text = (item.properties or {}).Text or ""
				label.BackgroundTransparency = 1
				label.Size = UDim2.fromScale(1, 1)
				label.TextScaled = true
				label.TextColor3 = Color3.new(1, 1, 1)
				applyOwnership(label, runId)
				label.Parent = instance
				table.insert(created, label)
			end
		end

		phase = "verifying"
		local verification = C1C.verifyOwnership(folder, runId, expected)
		if not verification.ok then
			return {
				built = false,
				build_ok = true,
				preload_ok = false,
				status = "ownership_verification_failed",
				folder = folder:GetFullName(),
				created = #created,
				verification = verification,
			}
		end
		local textures = {}
		for _, instance in ipairs(folder:GetDescendants()) do
			if instance:IsA("Texture") then
				table.insert(textures, instance)
			end
		end
		phase = "preloading"
		local preloadOk = pcall(function()
			ContentProvider:PreloadAsync(textures)
		end)
		return {
			built = true,
			build_ok = true,
			preload_ok = preloadOk,
			status = preloadOk and "complete" or "preload_failed",
			folder = folder:GetFullName(),
			created = #created,
			preload = { ok = preloadOk, texture_count = #textures },
			verification = verification,
		}
	end, function(err)
		return tostring(err)
	end)

	if not ok then
		local cleanup = nil
		if workspace:FindFirstChild(folderName) ~= nil then
			local cleanupOk, cleanupResult = pcall(C1C.cleanup, runId, false, plan)
			cleanup = cleanupOk and cleanupResult or { cleaned = false, error = tostring(cleanupResult) }
		end
		return {
			built = false,
			build_ok = false,
			preload_ok = false,
			status = "build_failed",
			phase = phase,
			error = resultOrError,
			cleanup = cleanup,
		}
	end
	return resultOrError
end

function C1C.cleanup(runId: string, allowSafeRename: boolean, plan: { [string]: any }?): { [string]: any }
	if not isValidIdentifier(runId) then
		fail("cleanup run ID is invalid")
	end
	if plan ~= nil then
		validatePlan(plan)
	end
	local expected = plan ~= nil and expectedPaths(plan) or nil
	local folderName = FOLDER_PREFIX .. runId
	local folder = workspace:FindFirstChild(folderName)
	if folder == nil then
		local outsideTagged = {}
		for _, instance in ipairs(CollectionService:GetTagged(TAG)) do
			table.insert(outsideTagged, instance:GetFullName())
		end
		local outsidePrefixed = {}
		local outsideRunAttribute = {}
		for _, instance in ipairs(workspace:GetDescendants()) do
			if string.sub(instance.Name, 1, #PREFIX) == PREFIX then
				table.insert(outsidePrefixed, instance:GetFullName())
			end
			if instance:GetAttribute(RUN_ATTR) == runId then
				table.insert(outsideRunAttribute, instance:GetFullName())
			end
		end
		local clean = #outsideTagged == 0 and #outsidePrefixed == 0 and #outsideRunAttribute == 0
		return {
			cleaned = clean,
			already_clean = clean,
			reason = clean and "already clean: no run folder or tracked objects"
				or "run folder is missing but tracked objects remain; no broad cleanup performed",
			outside_tagged = outsideTagged,
			outside_prefixed = outsidePrefixed,
			outside_run_attribute = outsideRunAttribute,
		}
	end
	if not folder:IsA("Folder") then
		return {
			cleaned = false,
			reason = "run path is not a Folder; nothing was deleted",
			preserved = true,
		}
	end

	local verification = C1C.verifyOwnership(folder, runId, expected)
	if
		#verification.violations > 0
		or #verification.outside_tagged > 0
		or #verification.outside_prefixed > 0
		or #verification.outside_run_attribute > 0
	then
		return {
			cleaned = false,
			reason = "ownership verification failed; nothing was deleted",
			verification = verification,
			preserved = true,
		}
	end
	if #verification.naming_issues > 0 then
		if not allowSafeRename then
			return {
				cleaned = false,
				reason = "naming inconsistency requires allowSafeRename",
				verification = verification,
				preserved = true,
			}
		end
		for _, issue in ipairs(verification.naming_issues) do
			local instance = findByPath(issue.path)
			if instance.Parent ~= nil and instance.Parent:FindFirstChild(issue.proposed_name) ~= nil then
				return {
					cleaned = false,
					reason = "safe rename conflict at " .. issue.path,
					verification = verification,
					preserved = true,
				}
			end
			instance.Name = issue.proposed_name
		end
		verification = C1C.verifyOwnership(folder, runId, expected)
		if not verification.ok then
			return {
				cleaned = false,
				reason = "ownership still fails after safe rename",
				verification = verification,
				preserved = true,
			}
		end
	end

	-- Fresh, complete ownership read immediately before destruction.
	local fresh = C1C.verifyOwnership(folder, runId, expected)
	if not fresh.ok or #fresh.outside_tagged > 0 or #fresh.outside_prefixed > 0 or #fresh.outside_run_attribute > 0 then
		return {
			cleaned = false,
			reason = "fresh pre-destruction ownership check failed; nothing was deleted",
			verification = fresh,
			preserved = true,
		}
	end

	folder:Destroy()
	local remaining = {}
	for _, instance in ipairs(CollectionService:GetTagged(TAG)) do
		table.insert(remaining, instance:GetFullName())
	end
	local residual = {}
	local residualRunAttribute = {}
	for _, instance in ipairs(workspace:GetDescendants()) do
		if string.sub(instance.Name, 1, #PREFIX) == PREFIX then
			table.insert(residual, instance:GetFullName())
		end
		if instance:GetAttribute(RUN_ATTR) == runId then
			table.insert(residualRunAttribute, instance:GetFullName())
		end
	end
	return {
		cleaned = #remaining == 0 and #residual == 0 and #residualRunAttribute == 0,
		verification = fresh,
		remaining_tagged = remaining,
		remaining_prefixed = residual,
		remaining_run_attribute = residualRunAttribute,
	}
end

return C1C
