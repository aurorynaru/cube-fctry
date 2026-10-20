# C1E-C2B-R4 — Offline MCP recording supervisor

## Decision

**Offline implementation and synthetic Windows verification are complete. Gate A
remains NOT TECHNICALLY READY and no Studio connection is authorized.** Passing
these tests establishes local recorder behavior, not installed StudioMCP behavior,
upstream completeness, protected storage, trusted UTC, or OpenCode integration.

Baseline: `4661903d4f97cdb8d62adea89544741d3a00871c`. Single agent; no Swarm or
delegation. No Roblox MCP tool, StudioMCP/launcher execution, Luau, screenshot,
Studio mutation, upload, save/publish, ComfyUI, authorization-store operation,
dependency installation, configuration change, Git staging, commit or push was
performed. Only controlled Python fake children were launched. Read-only HTTPS
documentation retrieval was used to consult the official contracts below.
Existing working-tree work, including the pre-existing `opencode.json` change,
was preserved. Tests used temporary synthetic evidence directories, removed by
test cleanup; no live evidence directory or approval was created.

## 1. Evidence provenance and documented expectations

### Operator-supplied observations, not agent-acquired file evidence

| Artifact | Operator-supplied size | Operator-supplied SHA-256 |
| --- | ---: | --- |
| `C:\Users\juara\AppData\Local\Roblox\mcp.bat` | 341 bytes | `705CF29E8CA920AFC38E5E1508C797856AAFCCB913049D88FBF9D1A448D17E33` |
| `C:\Users\juara\AppData\Local\Roblox\Versions\version-4f087c32742644ab\StudioMCP.exe` | 8,208,336 bytes | `3D5CF029E535251D530BBE1E4765D4183BD1396F52D51E85C97CD98D9E285092` |

The operator also reports **Valid Windows Authenticode signature — Roblox
Corporation** for the executable. R4 did not read/hash/execute either installed
file or independently validate that signature. Launcher contents/arguments,
source-to-build correspondence, effective runtime topology and actual framing
remain unverified. These supplied observations supplement the historical R3
access-denial record; they do not retroactively turn R3 into a successful read.

### Official sources consulted

- [Roblox: Connect to the Roblox Studio MCP server](https://create.roblox.com/docs/studio/mcp)
  documents a local subprocess using stdio, with Windows launcher examples and
  the discovery/state tools. It does not establish the installed binary's bytes
  on the wire, exact result wrapper, completeness or cancellation behavior.
- [MCP 2025-11-25: Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
  requires UTF-8 JSON-RPC messages delimited by newlines, without embedded
  newlines; stdout is MCP-only and stderr is a separate logging stream.
- [MCP 2025-11-25: Lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
  specifies initialize/version/capability negotiation, initialized notification,
  pings/logging during initialization, and transport-level stdio shutdown. There
  is no JSON-RPC `shutdown` method. Cancellation is a recommendation, not proof
  an operation stopped; the recorder uses teardown on refusal.

These are **documented expectations**, not verified behavior of StudioMCP.exe.
The selected version and strict fixture capability/result shapes are offline
contracts only. No fallback version, inferred wrapper or tool alias is tried.

## 2. Implementation and boundary

| File | Responsibility |
| --- | --- |
| `tool/c2b_recording_supervisor.py` | Fixed synthetic-child launcher, Gate A policy, bounded pipe capture, explicit protocol state/control handling, monotonic watchdog, Windows Job Object termination, new-only evidence and verification |
| `tests/fixtures/c2b_fake_mcp.py` | Controlled fake stdio server and failure scenarios; no Roblox import, connection or network behavior |
| `tests/test_c2b_recording_supervisor.py` | 35 new policy, Windows subprocess and fault-injection tests |
| `tool/c2b_evidence.py` | Reused unchanged: strict duplicate/nonfinite-rejecting JSON, byte digests, exclusive short-write-aware flush/fsync/readback writer, plain-directory checks |

The only runner is `run_synthetic(parent, name, scenario, *,
synthetic_state_review=False, window_seconds=30.0)`. It launches the exact bundled
fixture with the current Python runtime, `-I -u`, `shell=False`, explicit pipes
and `close_fds=True`. Scenario names are a fixed allow-list. There is **no arbitrary
command/argv, live flag, MCP proxy CLI, approval API or OpenCode binding**. A
non-Windows host refuses child launch. Python/source/fixture integrity is a local
trust assumption, not a sandbox against someone rewriting the repository/runtime.
The receipt hashes the actual fixture bytes read before launch, but does not
authenticate them or defeat a concurrent replacement.

The capture boundary is the fake child's **stdout anonymous pipe as read by this
Python supervisor**, before JSON interpretation or display transformation. This
is not the internal Studio bridge, OpenCode SDK output, or a model transcript.
No displayed JSON is reconstructed as raw evidence.

### Exact permitted tool sequence

`GateAPolicy` permits only these short wire-name expectations, with exact keys:

1. `tools/call` with `{"name":"list_roblox_studios","arguments":{}}`, once.
2. Pause after successfully recording and checking discovery. A second call is
   refused until the policy's explicit review transition.
3. `tools/call` with `{"name":"get_studio_state","arguments":{"studio_id":"577768ad-49d8-42f5-ac96-8c66cd12a144"}}`, once.
4. Done: no repeat, retry, polling, fallback, alternate target or extra tool.

The runner's explicitly named `synthetic_state_review=True` only simulates that
review boundary in tests. It is not an operator declaration or live pause/approval
implementation. With the default false value, the fake connection is closed
after discovery. Session-facing `roblox_studio_...` aliases are denied by this
wire policy; correspondence with the real server must be independently reviewed.

Missing/extra arguments, `_meta`, task options, alternate IDs and every other
tool/method are rejected. Luau, screenshots, uploads/inserts/generation, mutation,
playtest, save/publish, script access and subagents are outside the allow-list.
`tools/list`, resources/prompts enumeration and arbitrary control forwarding are
not implicitly added as permissions.

### Explicit lifecycle and control scope

- Fixed `initialize`, protocol `2025-11-25`, empty client capabilities, fixed
  offline clientInfo. The fixture's exact tools/logging capability shape and
  name/version result are checked. Unsupported negotiation stops before tools.
- Exactly one `notifications/initialized`, with no response ID; its bounded
  writer is checked before discovery. There is no fictitious shutdown request.
- Server `ping` requests with a string or integer ID and absent/empty params
  receive a separately recorded empty-result response. Reused server request
  IDs are refused. Outbound writes are serialized and handle short pipe writes.
- Bounded `notifications/message` logging frames with enumerated levels and
  checked params are retained separately from responses. Their data is never
  executed, interpreted as a command, or treated as tool success.
- Unrequested progress, cancellation, list-changed notifications, roots,
  sampling, elicitation, tasks and unknown/ambiguous messages stop the session.
  No progress token is requested. Notifications never reset a deadline.
- Refusal closes stdin and terminates the owned process tree as needed. No
  extra MCP cancellation, diagnostic call, reconnect or retry is dispatched.
  Any future change to this control scope needs explicit review/authorization.

## 3. Actual guarantees and limits

| Property | What the implementation provides |
| --- | --- |
| Byte preservation | Binary reads, no text-mode newline conversion. Exact whitespace, UTF-8 byte sequences and LF/CRLF are retained. Each consumed complete frame is exclusively written, synced and read back **before** parsing. Combined retained stdout and stderr prefixes are also saved separately. |
| Correlation | One outstanding client request, fresh string IDs, exact type/value comparison, exact JSON-RPC response envelope. Unmatched, duplicate, ambiguous, malformed, batched, invalid UTF-8, duplicate-key and nonfinite responses fail closed. Unsolicited/trailing output invalidates the session. |
| Accepted-frame cap | At most **65,536 raw bytes including the delimiter**, before JSON parsing, for every frame including initialization/control. Exactly-at-cap and one-byte-over-cap cases are tested. |
| Other resource bounds | OS reads at most 4,096 bytes; stdout retained at most 262,144 bytes per session; stderr at most 65,536 bytes; refusal after more than 32 complete frames. No unbounded event queue. These stricter synthetic safeguards are not silently approved live policy. |
| Oversize/failure | Refuse, retain only bounded received prefixes and label them incomplete failure evidence. A read can contain bytes beyond the retained prefix; read-byte counts are lower bounds on upstream output, not full lengths. The tail is not drained for evidence. |
| Real watchdog | Independently scheduled thread uses `monotonic_ns`, with a fixed absolute deadline starting immediately before each request's persistence/write attempt. Deadline includes frame storage and validation. Tests use shortened real deadlines; default is 30 seconds. No message resets it; a response validated at/after the deadline is refused. |
| Deadline reporting | Request ID/method, monotonic start/deadline/validation/finish and watchdog firing/lateness are recorded. `accepted` describes that frame's local validation only; it never overrides a later session failure or implies compatibility. |
| Process ownership | Windows Job Object with kill-on-close, assigned before the trusted fixture receives any stdin. Bounded root wait and active-job-process verification, root-kill fallback, and pipe-thread joins. An actual sleeping descendant is tested. Failed containment prevents all dispatch. |
| Uncertain stop | Kill requests alone are insufficient. Unconfirmed root/tree/reader/writer/watchdog exit or failed termination/handle verification produces uncertainty and withholds session success. Fault injection tests cover missing confirmation and failed kill/wait. |
| Storage | Atomic new run-directory creation; exclusive `xb` files; no overwrite/resume. Existing helper checks ancestors for symlink/reparse entries, handles short writes, flushes/fsyncs, compares readback bytes and hashes actual retained bytes. Storage failure aborts; no trusted final marker is produced for an unverified write. |
| Readback verification | `receipt.json` lists retained-file byte counts/SHA-256; `COMMITTED.json` hashes the receipt. `verify_recording()` rejects non-regular/reparse files, unsafe manifest names and changed files/receipt. Marker means local consistency, not a successful observation. |
| Completeness | Always `upstream_completeness="unverified"`, `full_upstream_response_claim=false`, `compatibility_pass=false`, total upstream bytes null. Valid downstream JSON never proves upstream completeness. |

Additional limits:

- The accepted-frame cap is not a 65,536-byte total-directory limit. Raw stream
  prefixes and consumed frame files intentionally duplicate bounded bytes; the
  aggregate raw stdout copies can total 524,288 bytes, plus stderr, bounded
  outbound records and metadata. Python object overhead is not an exact RAM
  ceiling. The supervisor cannot bound the child's own allocations or Studio CPU.
- Scheduler/OS stalls prevent a universal physical hard-stop guarantee. The
  independent watchdog can stop the child while the controller is stalled in
  validation (tested), but cannot interrupt an arbitrarily stuck filesystem call
  or the whole Python process being suspended. Process creation, final evidence
  fsync/readback and total runner lifetime have no certified hard deadline.
- Intended outbound bytes are saved before writing. `writes` records actual
  completed pipe-write byte counts and timing/errors; file existence alone does
  not prove all intended bytes were sent or that a server consumed them.
- Job assignment occurs after `Popen`. This is safe for the **controlled fixture**
  because it waits for stdin before spawning a descendant. An untrusted live
  launcher needs separately verified pre-execution containment (including its
  shell/child chain); these tests do not prove that topology is containable.
- Stopping the local stdio child would not prove a request already delivered to
  Studio stopped executing. Local process-tree verification is not upstream
  cancellation verification. Uncertainty requires an operator stop, not a retry.
- Discovery/state semantics are strict synthetic fixtures: one JSON text block;
  discovery `studios` ID/name entries (1–16, unique, exactly one expected ID named
  Place1); state requires all expected place/user/mode/Team Create fields. Values
  are fixtures/expectations, never current observations. No identity is filled
  from request/history. Unknown real wrappers require a later offline decoder
  review; these fixtures are not newly accepted live envelopes.
- Explicit errors/truncation/unknown wrappers are refused. Silently shortened
  but plausible results remain inherently undetectable here; a dedicated test
  preserves that limitation and still withholds completeness/compatibility.
- Reparse checks have path races; hashes/markers are same-user-recomputable, not
  authentication or immutability. File fsync is not proof of Windows directory
  power-loss durability, private ACLs, quota or write-access exclusivity.

## 4. Synthetic verification actually executed

Final code verification on Windows:

| Command | Result |
| --- | --- |
| `python -m unittest discover -s tests -p "test_*.py"` | **PASS: 265 tests run, 1 existing Windows symlink skip, 31.772s; 264 passed.** Includes all 35 new supervisor tests and 25 unchanged evidence-helper tests. |
| `python -m compileall -q tool/c2b_recording_supervisor.py tests/test_c2b_recording_supervisor.py tests/fixtures/c2b_fake_mcp.py` | **PASS**, exit 0, no compiler output. Parent directories verified first. |

The existing skip is `test_asset_registry.RegistryTests.test_symlink_escape`
(`symlinks unavailable`), not a new supervisor skip. All new Windows tests ran.
The broader suite uses existing local doubles/synthetic temporary stores; no real
Studio, authorization lifecycle or ComfyUI interaction was used.

Coverage includes normal initialization/discovery/state, default discovery-only
pause, exact tool/argument/order denials, initialization ping/timeout, logging and
ping responses, forbidden/unrequested notifications/server requests, malformed
frames/UTF-8/duplicate keys/nonfinite numbers/batches, typed ID mismatch/duplicate
responses, exact cap/oversize, bytewise split UTF-8 and CRLF, short outbound
writes, EOF/truncated/trailing output, crashes mid-frame and immediately after a
response, separate binary stderr noise, stdout/stderr/log/session floods, real
elapsed timeout, log traffic not resetting deadlines, independent watchdog during
stalled validation, ignored EOF, actual owned descendant termination, uncertain
stop, failed containment before dispatch, storage failure/child stop/no marker,
new-only reuse refusal, tamper checks and silent-upstream-shortening limits.

An earlier 31-test focused run passed in 8.682s; a subsequent 56-test combined
supervisor/helper run passed in 9.105s, before the final added cases. The final
265-test result above supersedes those intermediate test totals. Documentation
whitespace/final-diff checks are recorded in `status.md` §2.27.

## 5. Remaining gates before any real transport observation

### OpenCode and installed transport integration

1. Obtain scoped permitted read-only inspection or provenance-pinned supplied
   copies of the launcher/child chain and exact installed OpenCode/SDK/plugin
   build/config sources. Verify actual launch arguments, source/runtime digests,
   effective merged config, environment overrides, framing/parsing, output limits,
   timeout/cancellation, auto-discovery and reconnect behavior. Operator-provided
   hashes/signature do not settle those facts.
2. Review a separate live binding outside the parsed/displayed tool-result path.
   Pin its command, runtime/source, target/name mapping, control policy and
   capture boundary. It must be the sole Roblox stdio path, not an optional tee
   alongside a bypass route. R4 supplies no live executable path option or
   ready-to-paste config.
3. Resolve OpenCode's initialization, `tools/list`, pings, protocol capabilities,
   default retries and parallelism against the exact approved protocol plan.
   An automatic extra request is not implicitly permitted by discovery approval.
   Any required policy addition must be reviewed before activation, not discovered
   by launching Studio. Do not expose arbitrary tools from the real tool catalog.
4. Implement a genuine review/approval pause, new-only evidence completion before
   next dispatch, independent withdrawal/expiry checking at each dispatch, and
   correct stop propagation. The synthetic switch is not usable as human approval.
   Preserve bytes before OpenCode SDK parsing; plugin display hooks are too late.
5. Separately approve any exact Roblox-registration-only configuration change and
   verify activation in a new session. No `opencode.json` or global setting was
   changed in R4; existing loaded bindings cannot be assumed replaced in place.

### Windows evidence storage

Before live launch, the operator must establish an exclusively controlled private
NTFS parent, owner/effective ACL evidence, restricted inherited access, no unapproved
sync/sharing/automatic staging, and disk/quota headroom. Address path replacement
with verified exclusive ownership or handle-based no-follow protections. Validate
the chosen durability/backup policy and readback/hash evidence; fail before the
next call on any storage failure. `0700`, hashes and passing temporary-directory
tests do not establish these controls. Retain protected originals for **at least
30 days and until compatibility review finishes, whichever is later**; disposal
is operator-decided. Any sharing copy must be separately redacted with a manifest;
identity checks use protected originals. No live storage was provisioned here.

### UTC approval/expiry and withdrawal verification

UTC verification is **not implemented** and every receipt says `utc_verified=false`.
No new clock query, synchronization or settings change was made. R2's correction
stands: the historical UTC-versus-Philippine calendar-date difference is timezone
conversion, not demonstrated clock drift.

Before approval/launch, agree bounded comparison procedures and numeric freshness,
precision, transit-delay, drift and uncertainty limits for two independent trusted
authenticated UTC sources. Bracket each comparison with local UTC/monotonic samples;
require fresh synchronized evidence with overlapping conservative intervals. Missing,
stale, uncertain or conflicting sources stop verification; do not average them or
silently widen tolerances. Advance the covering UTC interval using monotonic elapsed
time plus bounded drift. Its entire interval must be after approval and before
expiry; **latest possible UTC + the full 30-second call window + drift margin must
be strictly before expiry** at each dispatch. Recheck withdrawal through the verified
operator channel, detect wall-clock steps/suspend/reboot/lost samples, and perform
post-observation checks. Failed mapping withholds authorization-time validity and
prevents another call. No numerical tolerance or trusted time source is invented
by R4; a monotonic timeout alone cannot verify UTC approval expiry.

### Unresolved oversized-failure evidence policy

C2A's complete-raw-retention wording and bounded incomplete oversized-failure
prefixes still require an explicit separate policy decision. Arbitrary full
oversized retention cannot coexist with a strict per-response retained-byte cap.
R4 tests prefix-only **failure** evidence; it does not approve that policy for live
collection, expand the cap, or call a prefix a full response. Before live work,
resolve whether capped incomplete failure evidence is permitted, or commission
a separately reviewed bounded full-retention design. Missing resolution blocks
launch regardless of an otherwise favorable Gate A declaration.

### Exact separate authorization required — future template, not a request

**First complete the technical/policy review above. No live authorization is
requested, issued or consumed here.** A later written declaration through an
independently verified named operator/channel must bind:

- Unique observation/approval reference; explicit UTC approval and expiry verified
  by the agreed interval procedure; current withdrawal status.
- The reviewed exact launcher/arguments/child chain, executable identity/digests,
  Python/recorder source digests, effective OpenCode binding and startup/termination
  plan; explicitly authorize **launch/connection and the enumerated initialize,
  initialized, ping/logging and teardown traffic**, not merely the two tool labels.
- Current intended historical Studio ID `577768ad-49d8-42f5-ac96-8c66cd12a144`,
  operator-confirmed unsaved local Place1, Edit, non-Team-Create, PlaceId=0,
  GameId=0, CreatorId=0, CreatorType=User, signed-in user ID=11822718311. These are
  expectations to verify, not server evidence. A changed target needs an offline
  plan revision and new review before connection.
- Exactly one `roblox_studio_list_roblox_studios({})`; at most 16 entries, exactly
  one expected ID with a consistent name; then **only after protected capture,
  validation and the explicit review pause** at most one
  `roblox_studio_get_studio_state({"studio_id":"577768ad-49d8-42f5-ac96-8c66cd12a144"})`.
  Pin their reviewed wire-name mapping and exact arguments. Require independently
  supplied identity fields; missing identity or an unknown wrapper stops.
- 65,536-byte complete-response limit, 30 seconds per call and all reviewed
  control/session limits; no retry, polling, fallback, target substitution or
  extra diagnostic tool. Exact protected new-only evidence destination, approved
  collection fields, failure-prefix policy, hashes, retention/redaction and access
  rules. No fabricated version, identity, completeness or timestamp metadata.
- Explicit exclusions: Luau/Gate B, screenshots, mutations, camera/viewport,
  upload/insert/generate, playtest, save/publish, ComfyUI, authorization-store
  operations, B1 events and production approval. Stop after discovery/state and
  report offline. Approval cannot waive an unresolved technical blocker.

Gate B's source/boundedness/serialization/path/stability/same-read identity
requirements remain blocked under the original preflight. R4 provides no Gate B
implementation or authorization. **STOP after the synthetic tests and this handoff.**
