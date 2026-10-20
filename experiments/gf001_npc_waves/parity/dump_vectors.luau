--!strict
-- GF-001-Q1 parity: dumps the shared vectors to canonical JSON on stdout.
--
-- Run from experiments/gf001_npc_waves/parity/ with the pinned standalone Luau
-- CLI and redirect stdout to vectors.json (exact command in
-- docs/GF_001_Q1_LUAU_PARITY_QUALIFICATION.md). vectors.json is the input the
-- Python reference harness consumes; regenerate it after editing vectors.luau.

local Pjson = require("./pjson")
local Vectors = require("./vectors")

print(Pjson.encode(Vectors.list))

return 0
