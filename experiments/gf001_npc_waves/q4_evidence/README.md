# GF-001-Q4 offline parity evidence

Fresh outputs from the unchanged Q1 dump/runner/comparator under pinned Luau
0.743 and the existing Python reference. Historical Q1/Q2/Q3 files are preserved.
These files verify core-language parity, not Roblox engine behavior or the new
binding (which is exercised by `../luau/run_binding_tests.luau`).

- `vectors.json`: fresh `parity/dump_vectors.luau` output.
- `luau_results.jsonl`: fresh `parity/parity_run.luau` output.
- `python_results.jsonl`: fresh comparator/reference output.

Exact commands, results, hashes, limitations and preservation checks are in
`docs/GF_001_Q4_OFFLINE_BINDING_IMPLEMENTATION.md` at the repository root.
