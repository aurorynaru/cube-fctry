# C1E-C2B-R8 — Gate A blocker resolution and decision packet

## 1. Verdict, scope and authority

**Gate A remains BLOCKED / NOT TECHNICALLY READY.** R7 is a useful, supported-host
synthetic containment/recorder integration. The next essential work is the sole-path
OpenCode front end, genuine approval enforcement and protected evidence storage.
A separate owning broker/native transaction is **not presently essential under the
proposed threat model below**. Unconditional leak-free recovery is not a prerequisite
to meaningful authorization or containment. This is a recommendation for operator
review, not adoption of a weaker cleanup contract or a clearance to run Studio.

- Baseline verified: `4661903d4f97cdb8d62adea89544741d3a00871c`.
- Review label: 2026-10-18 (harness date, not verified UTC).
- Documentation only: this packet and `status.md`. Source, tests, configuration,
  R1–R7 history and the approved Swarm plan are preserved. Single agent, no delegation.
- Read status §2.30, the R4–R7 reports, R2/R3 provenance reports, preflight, project
  `opencode.json`, the four C2B implementation modules and their four test modules,
  and the fake MCP/disposable controller fixtures. No project `AGENTS.md` was found;
  inaccessible parents were not searched.
- No external-file reads or attempts to revisit denied locations; no installed
  launcher execution, Roblox MCP, Luau, screenshots, Studio changes, ComfyUI,
  authorization issuance/consumption, external time query, clock/ACL/configuration
  change, installation, Git staging/commit/push or Swarm activity occurred.

**Authority rule:** every decision D1–D6 in §7 is **PENDING**. Proposed numbers,
acceptance tests and milestones in this packet are not adopted live policy. R5 §8's
oversized-failure amendment remains pending. Technical evidence and operator approval
are both necessary; neither substitutes for the other. No live approval is requested.

## 2. Ownership interruption: classify the consequence, not just the leak

### 2.1 Proposed supported threat and fault model — D1

Trust the supported Windows creation-time job/suspension and handle-inheritance API
contracts, the pinned Python/CRT runtime, reviewed recorder/front-end code and their
protected deployment. Trust the operator's independently controlled approval and
storage administration. Treat model/client requests, returned text and protocol
traffic as untrusted; enforce exact dispatch policy regardless of what is advertised.
Cover ordinary documented native/CRT failures, malformed/flooded output, blocked
pipes, checked cancellation, tested controller death points, storage failures and
explicitly detected uncertainty. An ambiguous run is terminal and cannot resume,
retry or be recycled into a new observation.

Do not claim resistance to a malicious administrator/kernel, arbitrary same-user
code injection or a writer able to replace the trusted runtime, policy, configuration
or approval verifier. Job Objects are lifecycle containment, not an IPC/security
sandbox: already-running Studio and other external services are outside the job.
Prevent agent-accessible alternate launch/dispatch routes as a separate deployment
requirement (§4), rather than assuming the model is cooperative. If the operator
requires protection against hostile same-user runtime replacement, this model is
insufficient; isolation/privilege separation needs a separate justified design.

Arbitrary repeated asynchronous exceptions between every Python bytecode/native
return/close, deterministic death inside `CreateProcessW`, universal Windows/nested-job
compatibility, instantaneous revocation after bytes enter a pipe, scheduler/kernel/
disk hard deadlines and unconditional power-loss durability are not certified.
Detected anomalies must still refuse and preserve uncertainty; these qualifications
do not authorize normal-spawn fallback, guessed closes, deletion or invented evidence.

### 2.2 Consequence matrix

Classes can overlap. A possible local leak does not by itself establish class A or B.
Source anchors below refer to the current reviewed files, not a new implementation.

| Class / concrete failure | Present behavior and evidence | Adequacy / essential remaining action |
| --- | --- | --- |
| **A — unauthorized Studio operation:** direct enabled batch entry, stale aliases, automatic client calls, forged review flag, replay/parallel calls | Project `opencode.json:34–40` still configures the direct batch route. `GateAPolicy` restricts the synthetic sequence; `synthetic_state_review` is only a test boolean. No client-facing enforcement/approval authority exists. | **Inadequate for live use; essential blocker.** Replace the effective route, enforce every call immediately before dispatch and authenticate the operator pause. A catalog filter or broker alone does not solve this. |
| **A/B — eager root/descendant before containment, unexpected resume** | R6 `SyntheticBoundary.create/resume` creates into the configured job while suspended, verifies membership twice and requires resume count 1. R7 converts all three pipes before resume. Unexpected resume may have executed contained instructions; setup refuses and tears down. Legacy `run_synthetic` is still post-Popen assignment. | **Adequate for the fixed fixture under D1**, not installed topology. Future binding must exclusively use the contained boundary with reviewed exact launcher/child/delegation behavior. Never select the legacy path. Authorize launch itself before resuming any real root. |
| **B — child survives outside intended job:** breakaway, delegation to pre-existing services, inheritance of job ownership, incompatible enclosing job | Explicit handle list excludes job/root/thread; no breakaway permissions; unsupported creation refuses. R6 tests real nested-limit refusal and controller death after creation returns; R7 tests eager descendants and inherited stdout. No installed-chain evidence. | **Real topology remains essential.** Establish launcher/delegation scope and supported host. Kill-on-close cannot retract a delivered Studio request or kill an existing Studio safely. External work/cancellation remains uncertain; no retry or extra diagnostic operation. |
| **B — in-kernel creation interruption / controller death** | Creation-time job list removes the user-space unassigned-root window. Return-gap/death tests observe exact root/descendant exit without retaining a job handle. No deterministic in-kernel death experiment exists (R6 §3). | **API reliance is acceptable only if D1 is approved.** This is a qualified unverified fault boundary, not an observed escaping child. More native code would still rely on OS semantics; a broker does not automatically prove kernel failure atomicity. A reproduced supported-host escape would be a new essential blocker. |
| **C — evidence loss or false success:** capture/read/write/fsync/readback/receipt/marker failure; controller dies mid-recording | Frames persist/read back before JSON parsing; failures stop dispatch. R7 commit failure returns no success; death leaves no fabricated final commit. A marker, accepted frame or clean root exit alone is insufficient. Bytes in memory at death may be lost. | **Adequate failure classification under D1; live storage protection remains essential.** Partial/missing evidence means failed/unverifiable observation, never a reconstructed success. Before state, require a verified durable discovery checkpoint; the existing test boolean is insufficient. |
| **C/B — reader/writer/watchdog or accounting uncertainty, crash racing teardown** | Stop owned tree, bounded joins, quarantine active leases; preserve prior errors even after later cleanup. R7 receipts suppress synthetic success on uncertainty. Root exit is not job exit/EOF. A crash exactly racing stop is not atomically excluded. | **Keep current refusal semantics.** Future front end must make failure terminal and return no compatibility success. A practical testable cutoff plus recorded residual race is enough under D1; universal crash exclusion is optional. |
| **D (and C) — hidden `open_osfhandle` return** | `_PipeLease.convert/close` (`tool/c2b_native_recorder.py:46–108`) surrenders native-close authority pending the call. A registered fd is closed as CRT-owned only. An unregistered hidden return quarantines the value, refuses before resume and reports handles false/uncertain. Test `test_unregistered_crt_return_is_blocked_not_guessed_or_double_closed` verifies known tree empty and no execution marker; only the injector knows/releases the fd. | **Adequate fail-closed refusal under D1.** Possible controller-local handle/fd leak, not an established unauthorized-operation or escaped-running-child path. Do not guess a close or claim leak-free cleanup. Terminal controller exit is the containment backstop, not a successful receipt. |
| **D (and C) — hidden `CreateProcessW` return / failed nonzero outputs** | `SyntheticBoundary.create:265–312` does not infer ownership from output numbers without observed success. Known job is stopped/accounted; root/handle certainty stays false. Native/R7 tests independently verify the actual suspended root exits; unrelated failed-output sentinel remains valid. | **Adequate refusal under D1.** Unknown process/thread handles can remain local; they do not themselves resume a suspended root. Empty-job evidence does not retroactively prove root-handle ownership. In-kernel death is the separately qualified row above. |
| **D/C, potentially B if job termination is also unconfirmed — close failure or unjoined borrower** | Never retry retired CRT values; don't close borrowed descriptors while known workers are alive. Native cleanup reports are cached. Job/tree/handle fields remain distinct. Error injection covers actual-close-but-error and descriptor reuse; it is finite coverage. | **Refuse and end the controller; preserve uncertainty.** Do not relabel an accounting/termination failure as only a leak. No safe continuation or automatic recovery after an uncertain outcome. |

### 2.3 Is a separate owner essential?

**Recommendation: no broker/native ownership subsystem now.** Hidden returns tested
in R7 block before resume and do not establish an unauthorized Studio operation or
an escaping running child. D1 may accept terminal local resource ambiguity while
continuing to require every normal documented ownership transition and all known
cleanup attempts. R7's no-success-on-uncertainty rule remains unchanged.

The future stdio front end should be a disposable process, not a long-lived plugin
inside OpenCode. On uncertainty, stop the known job, join/close only conclusively
owned resources, mark the observation terminal and exit non-success; no reconnect
or restart can reuse its observation permission. If it cannot finish, operator
intervention must end that controller; do not certify a hard termination deadline.
Process exit releases its remaining local handles under the OS contract. This is
an implementation/deployment requirement for that front end, not proof that the
current callable synthetic runner forces its caller to exit.

Review nuance: R7 prose says all workers are registered before start. Current
supervisor reader setup (`tool/c2b_recording_supervisor.py:569–573`) actually calls
`reader.start()` before appending it; writers/guards register first. Thus the prose
does not prove arbitrary interruption-safe reader registration. Under D1's limited
fault model this does not justify an R8 subsystem or a universal safety claim.
The future front end must register readers before start, track start outcomes and
test interruption at that boundary; no known live route is enabled in the meantime.

Reconsider a broker only for a concrete required property the present boundary
cannot provide: a demonstrated supported-host containment escape, a real launcher
requiring separately controlled delegation, hostile same-user isolation, or an
explicit requirement to keep a long-lived controller healthy after unobservable
ownership transfers. Leak elimination alone is optional assurance. A broker would
need its own IPC/authorization/lifetime/provenance tests and cannot resolve evidence,
UTC or upstream cancellation by its mere presence.

**Proposed D1 acceptance:** retain the R6/R7 hidden-return, unrelated-handle,
fd-reuse, blocked-I/O, job-accounting and controller-death tests; normal outcomes
require confirmed root/tree/workers/handles plus verified evidence; hidden returns
must produce zero tool dispatch before resume, terminal refusal and no successful
recording. Add front-end tests proving terminal non-reuse/process exit and
reader-registration failure handling. Accept the expressly listed API/fault-model
qualifications, without changing any existing cleanup field or evidence verdict.

## 3. Installed provenance: established facts and minimal operator packet

### 3.1 What is actually established

| Evidence | Established fact | Does not establish |
| --- | --- | --- |
| R4 §1 / R5 §1, operator report | `C:\Users\juara\AppData\Local\Roblox\mcp.bat`: 341 bytes; SHA-256 `705CF29E8CA920AFC38E5E1508C797856AAFCCB913049D88FBF9D1A448D17E33`. | Independent installed-file verification, present contents or execution behavior. |
| Same report | `C:\Users\juara\AppData\Local\Roblox\Versions\version-4f087c32742644ab\StudioMCP.exe`: 8,208,336 bytes; SHA-256 `3D5CF029E535251D530BBE1E4765D4183BD1396F52D51E85C97CD98D9E285092`; operator reports valid Roblox Corporation Authenticode signature. | Reviewed arguments/dependencies/delegation, wire format, safe startup, exact source-to-build correspondence or present binary equality. Signature validity is not behavioral authorization. |
| This review of project `opencode.json` | One project Roblox entry: local, `cmd.exe /d /c %LOCALAPPDATA%\Roblox\mcp.bat`, enabled, timeout 30000; `external_directory: deny`; `edit: allow`; most shell commands ask. | Effective merged settings, all plugins, installed OpenCode version, loaded aliases/session routes or a 30-second process/upstream deadline. `edit: allow` is not protection of trusted gate code. |
| R1/R3 access refusals | Global config directory and exact launcher read were refused by the tool-policy boundary; no bypass followed. | Missing file, Windows ACL denial or permission to inspect by another method. |
| User's R8 statement that launcher contents were supplied | Contents are operator-supplied evidence in the stated handoff. Accessible R4–R7 reports preserve metadata but explicitly say contents/arguments were not inspected; the exact batch text was not located in the reviewed repository records. | The actual 341-byte script cannot be reconstructed from its hash or an assumed Roblox template. R8 does not invent a version-selection/direct-launch interpretation. |

Do not require an audit of all OpenCode or all Roblox source to begin the narrow
front end. Require provenance-bound excerpts for the exact behaviors at this boundary.
Unavailable source-to-build mapping must be marked unverified and supported by an
operator-approved substitute (e.g. matching vendor build documentation plus isolated
fake-server conformance evidence); it cannot silently become verified source evidence.

### 3.2 Minimal credential-free evidence request — for later operator submission

Supply one packet **inside an operator-selected accessible project location**, as
data, without launching `mcp.bat`, `StudioMCP.exe` or activating MCP:

1. **Launcher text:** reattach the already supplied exact batch bytes (preserving
   encoding/line endings) or identify the accessible artifact that contains them;
   attach original path, 341-byte count, digest and acquisition method. Explain each
   selection/expansion/argument/cwd and whether the executable above is the selected
   child. Supply only specifically referenced helper/config excerpts if needed.
   No repeat broad installed-directory inspection or executable upload is needed.
2. **Roblox launch contract:** confirm the reported executable identity/signature
   record's acquisition method/build version; identify exact child/runtime or
   pre-existing-service delegation, environment inputs and stdio ownership. Supply
   matching vendor/source excerpts for startup, wire names/lifecycle/result shapes,
   output transformations and cancellation limits where available. Mark unknowns;
   don't run the binary to fill gaps. Do not assume direct launch equals the batch.
3. **Installed OpenCode boundary identity:** exact executable/package path, version/
   build and digest; relevant MCP SDK/dependency versions and plugin/hook identities.
   Supply matching excerpts or build-bound documentation for config precedence,
   spawn/cwd/environment, initialize/tools-list/alias creation, timeouts, automatic
   retries/reconnect, concurrent calls, cancellation and result parsing/truncation.
   A generic upstream link or a version slogan alone is insufficient.
4. **Effective route inventory:** credential-free list of all loaded config paths
   and override sources (project/global/managed/CLI/environment as applicable),
   resolved Roblox command/enabled/timeout/tool permissions and relevant plugins;
   names/presence of relevant environment overrides, never secret values. Inventory
   duplicate aliases, existing loaded sessions and any direct-launch/alternate tool
   or shell route. State how the direct binding/stale sessions would be retired.

Redact unrelated providers, credentials, keys, cookies and tokens; mark omissions
without changing the relevant command or control semantics. Original-path/digest/
acquisition provenance must distinguish a redacted excerpt from exact original
bytes. No credentials, full environment dump, credential-store read or recursive
external access is requested. Unresolved redactions affecting launch or policy keep
the affected fact unverified. New exact-file permission would be a separate scope;
this packet does not grant it. No configuration change is requested in R8.

## 4. Smallest sole-path MCP front end — specification only

Preserve Option B's independently enforced authorization, pre-parse recording and
contained process boundary. Reuse reviewed primitives; do not expose the mutation
adapter/harness or turn fixture scenario inputs into arbitrary live argv.

### 4.1 Topology and local initialization

Future topology: **OpenCode → one restricted stdio front end → R6/R7 contained
process/recorder boundary → the pinned reviewed Roblox launcher chain → Studio**.
Replace the existing **effective** `roblox_studio` entry. Do not add a second tee,
server, alias or optional safe route beside a direct route. A reviewed future diff
and new-session binding inventory must prove the replacement. Existing in-memory
tools do not disappear merely because a disk entry changes.

Automatic OpenCode startup may start **only the inert front end**. It may answer
local `initialize`, `notifications/initialized`, bounded `ping` and `tools/list`
according to a fixed, reviewed client contract. It must not spawn/resume/connect the
upstream child, discover Studio, contact time services or obtain approval as a side
effect of initialization, catalog enumeration or reconnect. Upstream MCP initialize
is a separate explicitly approved launch/protocol operation, even though it is not
a Studio observation tool call. Reject unsupported versions/capabilities/methods;
never relay arbitrary lifecycle traffic or the unrestricted upstream catalog.

Catalog: exactly reviewed `list_roblox_studios` and `get_studio_state` wire operations,
with pinned front-facing names/alias mapping. Discovery has `{}` arguments only;
state requires exactly the reviewed target UUID, with no defaults/extra keys.
Expose no Luau, screenshots, script reads, console, play/stop, mutations, insertion,
uploads, subagents, arbitrary commands, resources/prompts/tasks or generic forwarding.
Advertised JSON schemas aid the client; strict runtime validation is authoritative.
Keep protocol logging on stderr and frontend stdout MCP-only; bound both directions.

### 4.2 Dispatch and genuine review pause

One locked state machine owns one observation and one outstanding upstream request:

`INERT → launch-authorized → contained/initialized → discovery-spent → discovery-checkpoint → WAIT_REVIEW → state-spent → FINALIZING → TERMINAL`.

Any error/withdrawal/expiry/uncertainty goes terminal; there is no retry transition.
The initial operator scope may cover one discovery plus conditional one state, but
cannot pre-satisfy the actual post-discovery review. Persist/verify the complete
discovery request/response and validation/timing checkpoint before presenting it
for review. Human continuation must bind that checkpoint digest, observation ID,
same live frontend/upstream session and exact state arguments. Absence, decline,
channel loss, expiry or evidence failure dispatches **zero state bytes**. A model
message, boolean flag, tools/call argument or generic OpenCode permission prompt
does not constitute that review. Review wait is bounded by approved expiry/startup/
session budgets; no infinite idle upstream session is required.

R7's final receipt is written after teardown; `policy.recorded()` alone is not a
durable human-review checkpoint. A future frontend needs a small new-only verified
checkpoint while keeping the final session verdict contingent on teardown, final
storage and post-time checks. Neither checkpoint nor frame acceptance means final
success. Default idle/paused unsolicited upstream traffic stops the session unless
an exact bounded control addition has been reviewed first; no speculative forwarding.

Every tool call is checked **before** it reaches the upstream writer. Persist exact
intended outbound bytes first; after that potentially slow storage, recheck all
authorization/time/revocation/evidence/session prerequisites at the write boundary
(§5). Mark the one-shot attempt spent before any possible first byte. Short writes
may complete the same fixed frame only while the attempt remains permitted and
before its unchanged deadline; partial/error/uncertain write never permits replay.
Correlate IDs internally and reject duplicate, wrong-type, extra and trailing frames.

Preserve raw binary stdout from the child **before SDK/JSON parsing**, with the
existing frame/stream limits and readback/hash checks. Client-facing serialization
or a model transcript cannot substitute for this original boundary evidence.
Contain before resume using creation-time job list, explicit inherited pipe list,
checked membership/resume and R7 lease ownership. Register all workers before start;
stop tree, join borrowers, then close owned descriptors. Keep native/CRT/worker/
root/tree certainty separate and propagate every uncertainty to the final verdict.

### 4.3 Retry, reconnect and bypass resistance

- Reject rather than queue a second concurrent operation; two racing dispatches
  must not both pass a policy check. Reject repeats even with new JSON-RPC IDs.
- Client cancellation/disconnect, upstream death or frontend uncertainty ends the
  observation. No diagnostic, fallback, version negotiation retry or fresh child.
- A new frontend process starts inert. Observation attempts spent before a crash
  remain spent in protected replay state; reconnect cannot reset authority. Do not
  automatically recover incomplete records into permission to dispatch.
- Installed client defaults must be inspected and disabled where relevant; frontend
  one-shot enforcement must also withstand simulated retries/reconnects regardless
  of client promises. A narrower catalog alone is insufficient.
- Effective tool/shell/plugin permissions and trusted-file deployment must prevent
  the agent from selecting a direct launcher, modifying the gate, forging approval
  or restoring old bindings. Current project `edit: allow`/shell `ask` do not prove
  this. Operator-managed protections must be verified at the actual deployment;
  do not claim protection against deliberate operator bypass or same-user takeover.

No frontend, new CLI, live executable option or configuration patch is delivered
or activated in R8. Missing installed contract details are design inputs to resolve,
not permission to trial-and-error against Studio.

## 5. Minimum approval and trusted-time contract — D3/D4

### 5.1 Human scope, one-shot use and withdrawal

Software must verify a bounded approval through **one independently operator-controlled
authenticated channel**, outside model-exposed MCP/tool arguments and agent-writable
records. Provision the actual principal/channel/verification root separately; an
existing suitable local operator interface is preferable to a new general approval
service. If the agent has the same ability to produce channel messages as the
approver, the channel is inadequate. A local declaration or mutation
`AuthorizationStore` does not authenticate human intent.

Minimum verified scope: named actor/channel reference, unique approval/observation
identity, explicit UTC approval/not-before/expiry, pinned launcher/frontend/runtime/
policy/catalog digests, effective binding, exact target expectations, exact operations
and arguments/order/maximum attempts, lifecycle/control/teardown scope, deadlines,
limits and exact private new-only evidence destination/policy. Expectations include
UUID `577768ad-49d8-42f5-ac96-8c66cd12a144`, actual `Place1`, Edit, non-Team-Create,
unsaved, place/game/creator IDs 0, creator type User and user ID 11822718311, subject
to fresh operator confirmation in a later authorized process. History is not current
identity; missing server fields must never be supplied from those expectations.
Changed targets require offline plan review, not substitution. Discovery may list
other instances but may not contact them.

Maintain protected one-shot/replay state separate from the mutation store: attempt
intent becomes permanently spent **before** write, bound to the verified scope and
session. Crash after spending but before sending sacrifices availability; it never
restores permission. Ambiguous persistence stops. Genuine post-discovery continuation
is an authenticated event referring to the verified checkpoint, not another tool.
No authorization records are generated, issued or consumed by this review.

Withdrawal must be deliverable while waiting/in flight. Serialize authenticated
withdrawal and the final dispatch decision through the same gate: a withdrawal
acknowledged before the first-write transition prevents that write; channel loss,
stale/unknown status or verification failure also refuses. Check again before each
remaining partial-write attempt; if already transmitted, stop local dispatch/owned
tree and retain uncertainty without claiming Studio cancellation. Revocation cannot
unsend bytes or promise zero remote work after an acknowledged in-flight abort.
This linearization rule is implementable; instantaneous distributed revocation is
not. No long disk operation or unguarded queue may sit after the final validity check.

### 5.2 Independent UTC and monotonic deadlines

Keep R5 §7's **two independent authenticated UTC sources**. The minimum software is
a pure verifier over provenance-bound source evidence and local capture brackets,
not a clock-sync client. Operator-managed acquisition must supply approved source
identities, authentication, independence, synchronization/error bounds, exact
generation semantics, capture delay and measured/documented drift/timer limits.
Unsigned copied times, two endpoints backed by the same clock, bare HTTPS Date or
local UTC formatting are insufficient. No actual source is selected/contacted here.

At a common monotonic anchor M, compute each conservative UTC interval [Li, Ui]
including source error, bracket/transit delay, precision and drift (R5 §7 formula).
Require fresh, synchronized, overlapping intervals; use their **covering interval**
`[min(Li), max(Ui)]`, never an average or a conveniently narrow intersection. Advance
with monotonic elapsed time plus worst-case drift. Refuse missing bounds, disagreement,
stale evidence, excessive interval width, wall/monotonic step, suspend/resume, reboot
or lost monitoring samples. A reboot invalidates the mapping; persisted monotonic
values do not authorize a later process/boot by themselves.

Immediately before launch/resume and each actual dispatch require:

1. The whole current UTC interval is at/after approval/not-before and strictly
   before expiry, with scope/authentication/current withdrawal verified.
2. `latest_possible_UTC + full_operation_budget + drift/timer_margin < expiry`.
   Discovery/state budget remains 30 seconds each; launch/handshake and review wait
   need their own explicit bounds. Proposal: 30-second launch/handshake budget
   beginning before create, with a fresh check after setup/before resume and before
   each protocol write. A stuck kernel call cannot be made hard-bounded by this timer.
3. An absolute `monotonic_ns` deadline set before request persistence/write and
   clamped to the conservative expiry-derived deadline. Validation at/after deadline
   refuses. Traffic, retries, storage delay and human review cannot reset it.
4. Evidence storage/checkpoint health and one-shot state still verified. A wall-time
   check before writing a slow evidence file is not the final dispatch-time check.

Retain R5's candidate limits **for decision, not as approved values**: each source
capture ≤5 seconds; covering width ≤2 seconds; calibration age ≤60 seconds at dispatch;
independent post-check within 60 seconds of observation. Require an explicit numeric
platform drift/precision bound supported by evidence; none is invented here. A long
review pause requires fresh approved calibration or refusal. Obtain independent
post-observation comparisons before certifying authorization-time validity; failed
post-check invalidates that claim, preserves evidence and prevents another call.

**Software:** exact schema/scope/one-shot enforcement, authenticated-channel
verification, serialized withdrawal/dispatch, pure UTC interval arithmetic, monitoring
and monotonic guards, pre-write rechecks, original evidence and terminal failures.
**Operator prerequisites:** actual independent approval principal/channel and protected
verification state; supported host/runtime; approved/acquired authenticated time
evidence and numeric bounds; safe evidence deployment; effective route retirement.
Software booleans cannot stand in for those prerequisites.

## 6. Evidence decision — D2/D5, exact proposed contract

The collector already supplies exclusive creates, short-write handling, file
flush/fsync/readback, actual-byte SHA-256 and marker/manifest verification. It does
not supply production ACLs, a race-free namespace, full disk allocation accounting,
aggregate quota enforcement, a live review checkpoint or universal durability.
`verify_recording()` currently explicitly verifies **offline synthetic** receipts;
do not relabel them as live records or loosen it to accept arbitrary live evidence.

### 6.1 Proposed operator decision text — not adopted

> Approve R5 §8's bounded-failure amendment with the following interpretation.
> At the reviewed child-stdout capture boundary, every successful accepted response
> must retain and readback-verify its full original envelope and framing bytes,
> at most 65,536 bytes **including delimiter**, before parsing/acceptance. This is
> transport evidence only, not a claim of complete Studio/upstream semantics.
> Any oversized response fails the observation, stops further dispatch and initiates
> reviewed teardown; retain only its first at most 65,536 bytes, explicitly marked
> incomplete oversized-failure evidence. Do not drain/store its tail, retry or make
> the conditional state call. Count/hash retained bytes only. Consumed OS-read counts
> are separately labeled lower bounds; total upstream length stays unknown unless
> independently established. Combined stream/control/metadata copies must not hide
> additional response-tail bytes. Any other failure likewise retains only verified
> bounded originals with its refusal and cleanup uncertainty; no partial evidence
> becomes success. Preserve the same access, retention and redaction requirements.
>
> Interpret 65,536 as a **distinct response-content cap**, allowing explicitly
> budgeted duplicate frame/stream copies. It is not a 65,536-byte physical-storage
> promise. Approve the proposed session/campaign limits below only after their
> implementation and storage preflight are verified. If total physical storage per
> response must instead be 65,536 bytes, reject this interpretation and keep live
> work blocked pending a reviewed layout; do not silently retrofit deduplication.

Proposed finite accounting (new limits require implementation; they are not claims
about R7 enforcement):

| Dimension | Proposed bound / measurement |
| --- | --- |
| Per inbound upstream frame, including initialize/control | 65,536 bytes including LF/CRLF; exact cap succeeds only with all other checks. Oversize prefix ≤65,536, never an extra tail in another file. |
| Session upstream stdout / stderr distinct content | 262,144 / 65,536 bytes respectively; 32 frames maximum for acceptance, refused 33rd delimiter may be retained within stream cap. Same R7 bounds. Reads ≤4,096 bytes; already consumed crossing bytes are not full upstream length. |
| Duplicate raw stdout files plus stream copy | ≤524,288 total file-content bytes; plus stderr ≤65,536, thus raw copies ≤589,824 bytes/session. Preserve explicit duplicate accounting; no extra copy outside the ledger. |
| Outbound upstream records | ≤4,096 bytes/frame and ≤65,536 bytes/session, including request/control copies. No unconstrained caller data. |
| Persisted client-side input/output transcripts, if retained | ≤262,144 bytes/session in total; no reconstructed client output replaces raw upstream evidence. Frontend input frame ≤4,096 bytes; excess/repeated catalog traffic refuses. |
| All other records | ≤262,144 bytes/session for approval/time/checkpoint/receipt/manifest/diagnostics/marker combined. Oversized prerequisite evidence refuses before launch; reserve finalization space before dispatch, never truncate a success receipt. |
| Session aggregate | ≤2,097,152 bytes (2 MiB) sum of **all retained logical file lengths**, including duplicates, temporary/partial files, both directions and metadata. Category maxima sum to 1,179,648 bytes; remaining room is not permission to exceed a category cap or retain missing tails. Reserve within the aggregate for finalization/refusal. |
| Campaign aggregate | Proposal: at most 16 observation directories and 33,554,432 logical bytes (32 MiB), including failed/abandoned runs; one active run. No automatic deletion/rotation to regain capacity. New attempts always require separately valid authority; this quota is not permission for 16 calls. |
| Physical NTFS capacity | Track separately from logical/content limits: cluster allocation, directories, filesystem overhead, approved backups and reserve all consume capacity. Operator-selected quota/allocation ceiling and required free headroom must be numeric and verified before use. Proposal: reserve at least 16 MiB free/quota headroom for the next ≤2 MiB session, but verify this covers the approved cluster/layout/file-count costs; refuse if not. A free-space sample is not a reservation. No claim of physical allocation enforcement exists today. |

The category sum is 589,824 raw + 65,536 outbound + 262,144 client transcripts
plus 262,144 other records. Aggregate admission/reservation must count failed partial
writes and concurrent collectors; unknown allocated/storage state blocks new work.
Use a protected quota/reservation and exclusive writer or substantiate an equivalent
operator-managed capacity guarantee. Disk-full can still occur; it must fail closed.
No high-assurance reason to require storage immune to all possible device failures.

### 6.2 Storage, confidentiality and practical recovery decision

Operator must name the exact NTFS parent/volume, owner, permitted readers/writers
and agent/child access model. Verify inherited and explicit DACLs and effective
access/group membership on parent, ancestors and newly created leaves. Exclude
unapproved broad readers/writers, synced/shared folders and automatic upload/staging.
Raw discovery/state/user/path/text data is private/adversarial; validate identities
on protected originals. Share only a separately redacted copy with a redaction
manifest, using approved recipients/backups. Hashes or Python 0700 are not DACL proof.

For this limited observation, the minimal recommended path-race model is exclusively
controlled ancestors and a single trusted storage writer, with no concurrent rename/
replacement by any other permitted principal/process during collection. Verify the
agent/upstream cannot replace the gate or evidence namespace. If that cannot be
established, handle-based no-follow/relative-open protection becomes **essential**;
do not require a new storage subsystem before testing the simpler deployment.
Point-in-time ACL text alone does not exclude a racing authorized writer, and hashes
are not tamper-proof against a trusted principal recomputing them.

Retain protected originals **at least 30 days and until review completion, whichever
is later**; disposal remains an explicit operator decision. Agree approved backup
location/access and recovery owner. Proposal for the fault model: checked full
writes, flush/fsync/readback and verified checkpoints/final manifest on the supported
NTFS host; after interruption preserve the partial directory, never overwrite/resume
it or regenerate a success marker. A new process verifies all files before using a
completed record. Missing/torn/changed files, uncertain writes/flushes/close/readback,
quota exhaustion or ACL/path uncertainty mean **no trusted success and no next call**.
Record whatever failure evidence can be verified; if storage itself fails, propagate
failure without inventing a durable final receipt.

Power loss may lose even recently read-back data; this proposal does not certify
universal power-loss persistence. Later recovery must detect missing/inconsistent
records and classify them unverifiable, never repeat an observation automatically.
If the operator requires guaranteed retention across power loss, specify a supported
device/filesystem/backup guarantee and evidence separately before launch. A dead
controller cannot promise a final receipt. Approved backup/restore tests demonstrate
recoverability for the selected fault model, not immunity to every power cut.

### 6.3 Proposed acceptance tests

Use synthetic temporary stores/fixtures; production provisioning is separately owned:

- Preserve exact UTF-8, whitespace and LF/CRLF; assert files exist and compare before
  parser invocation. Test 65,536-byte frame and 65,537-byte refusal; oversized tail
  must appear in no file and dispatch count must not increase.
- Cross stdout/stderr/frame/session, outbound, metadata, logical aggregate and campaign
  thresholds independently; count duplicate/partial files. Simulate quota exhaustion,
  reservations racing and uncertain allocation accounting: one winner or refusal,
  never oversubscription or success. Test file allocation/headroom on the selected
  NTFS layout, not an equation equating logical bytes to physical bytes.
- Test short/zero writes, disk-full, fsync failure, wrong readback, checkpoint failure,
  receipt/marker failure and process death before/after each checkpoint/commit step.
  Assert no next tool call; preserve the failed name; verify or reject after restart.
  A valid marker with altered/missing files still fails. Do not reconstruct evidence.
- On an operator-provisioned test NTFS directory, verify intended writer/readers and
  negative read/write/rename access for an unapproved ordinary principal; verify
  new-leaf inheritance and reparse refusal. For the exclusive-writer model, verify
  other processes/principals cannot replace ancestors during collection. If using
  handle-based protection, attempt replacement at controlled open/readback seams.
- Restore a synthetic completed record from the approved backup and verify the
  original digests/access policy; reject a partial/corrupt restored record. Test
  retention expiry/review hold without automatic deletion. No destructive power-cut
  experiment or claim of universal durability is required under the proposed model.

## 7. Exact pending operator decisions

Each item needs a recorded approve/reject/revise disposition and explicit scope.
All remain **PENDING**; this is a decision packet, not an authorization form to fill
for a Studio run. Rejection keeps the corresponding blocker open.

| ID | Proposed decision for operator review | Evidence/condition before it can close a blocker |
| --- | --- | --- |
| **D1 — fault/ownership model** | Accept §2.1's trusted supported-Windows/runtime scope and terminal uncertainty; defer owning broker/unconditional local leak recovery. Preserve every current cleanup/evidence contract. | Existing R6/R7 evidence plus future frontend terminal/no-reuse/reader-registration tests. Real topology still required; no claim of in-kernel universal proof. |
| **D2 — oversized retention / accounting** | Approve §6.1/R5 §8 accepted-full versus failed-prefix text, distinct-content interpretation and explicit session/campaign budgets. Or require a different reviewed layout. | Implement/test the new budgets; separately name physical quota/headroom values and verify actual storage accounting. Synthetic prefix tests are not policy approval. |
| **D3 — independent human approval** | Name the operator principal, authenticated out-of-model approval/withdrawal channel, verification root and ownership protections; approve §5.1 scope/spent-attempt and withdrawal linearization semantics, including post-discovery digest-bound review. | Demonstrate agent cannot forge/change it; denial/replay/crash/reconnect/concurrency/withdrawal tests. No mutation authorization-store lifecycle reused. |
| **D4 — trusted time** | Select two independent authenticated source/acquisition methods; approve numeric source freshness/query/uncertainty/post-check, drift/precision and launch/review budgets (§5.2). | Evidence substantiating bounds/independence and pure-verifier tests; actual acquisition is separately permitted later. R5's candidate 5s/2s/60s/60s limits are not approved by this packet. |
| **D5 — storage fault/privacy model** | Name NTFS parent/principals, exclusive-writer or handle-based model, quota/reserve, confidentiality/backup/retention/recovery owner and required durability level (§6.2). | Effective ACL/path/headroom/new-leaf tests and fault/recovery evidence. Existing ≥30-day-and-review retention is preserved; no ACL changes in R8. |
| **D6 — installed contract / sole route** | Supply §3.2's minimal provenance packet; review pinned command/catalog/client behavior and retirement plan. Agree any substitute for unavailable build-matched source evidence explicitly. | Offline contract review and fake-client/contained-child conformance. A later exact Roblox-entry change/new-session activation requires its own approval; none requested or made now. |

## 8. Dependency-ordered readiness matrix

Milestones below are recommendations, not instructions to continue R8:
**M0** evidence/decision closure; **M1 (R9 proposal)** fixed-catalog fake-only stdio
frontend contract; **M2** focused approval/time enforcement and protected-storage
implementation/qualification; **M3** complete offline readiness/sole-route deployment
review; **M4** separately approved route replacement/activation and, only after its
prerequisites are confirmed, separately authorized bounded observation. Gate A stays
blocked through incomplete prerequisites; none of M0–M4 is performed by this packet.
Rows are dependency order, not an assertion that the last rows are low priority.

| Rank / requirement | Present evidence | Missing evidence | Consequence if unresolved | Assurance class | Proposed implementation / operator decision | Exact acceptance test | Next milestone / dependency |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **1. Pinned installed/client/launch contract** | Project entry; operator-reported sizes/hashes/signature; R3 denial; synthetic stdio contract. | Exact supplied batch text, resolved chain/delegation, build-bound OpenCode/SDK/plugin behavior and effective sources (§3.2). | Cannot pin replacement or contained launch; guessing aliases/argv/startup can bypass policy. | **Essential.** Whole-vendor source audit optional; boundary provenance is not. | D6 packet and minimal relevant source/contract excerpts; retain unknowns explicitly. | Offline reconcile paths/args/digests and all override sources; source-derived client sequence must match fixed catalog/lifecycle; unknown behavior yields no spawn. Test supplied batch interpretation without executing it. | **M0**, before installing a real binding; supplies M1 contract. |
| **2. Policy/evidence/storage decisions** | R5 §8 and R8 proposals; existing original-retention requirements and caps. | D1–D5 dispositions, principals/numeric time/storage budgets/fault model. | No legitimate live policy to implement/approve. | **Essential decisions**; universal no-leak/power-loss proof optional under approved D1/D5. | Decide §7 without treating tests as consent. | Decision record explicitly addresses each ID, values and exceptions; no implied approval of prefix/duplicate storage. A missing field leaves that gate false. | **M0**; prerequisite for production M2 contracts. |
| **3. Working restricted stdio frontend** | R7 recorder/policy primitives; no frontend/catalog/OpenCode input path. | Client-facing lifecycle/catalog, pre-dispatch locked policy, genuine-pause checkpoint, frontend worker lifecycle and bounded client traffic. | OpenCode cannot use the recorder as a restricted MCP server. | **Essential; highest next engineering priority.** | §4; reuse contained recorder, no general proxy framework. Fake child only at M1; deny by default with injected synthetic prerequisite results. | Source-derived fake OpenCode client: initialize/tools-list yields exactly 2 schemas and **0 child launches**; absent auth/evidence yields **0 upstream writes**; approved synthetic discovery then pause yields **0 state calls** until digest-bound continuation; forbidden/extra/duplicate/parallel/reconnect requests never increase dispatch. | **M1/R9**, after enough M0 client contract evidence; no config activation. |
| **4. Authenticated scope/replay/revocation enforcement** | Exact synthetic order; mutation store expressly not an approval authority. | Actual independent channel and protected state, pre-write validity checks, permanent spent-attempt state, cancellation semantics. | Forged flag/replay/race could permit unauthorized observation. | **Essential.** | D3; narrow verifier/control channel and serialized gate, separate from mutation store. | Forge/wrong actor/scope/target/args/checkpoint/expired approval: **0 bytes**. Race 2 calls: ≤1 attempt. Crash at spent-before-write: restart sends **0 replay bytes**. Acknowledged withdrawal before write: **0 bytes**; in-flight withdrawal stops local tree, no retry, no remote-cancel claim. Slow request persistence followed by revoke must refuse. | **M2**, built against M1 seam; independent operator provisioning required. |
| **5. Private safe evidence + aggregate budgets** | Pre-parse readback, hashes, exclusive create, caps and failure tests; ACL/race/durability not established. | D2/D5 approval, checkpoint and budget enforcement, exact NTFS/effective-access/path/physical-capacity/retention recovery evidence. | Evidence disclosure/replacement/loss or unbounded copies; no trusted review or success. | **Essential.** Handle-based storage conditional on failure of exclusive-writer model; universal power-loss immunity optional. | §6 minimal deployment and bounded writer; fail closed on uncertain persistence. | Execute §6.3, including parse-order proof, +1 byte cap, duplicate/partial aggregate counts, no state after checkpoint failure, ACL negative access and restart/restore rejection. | **M2**, alongside authorization; evidence decision before production layout. |
| **6. Independent UTC/expiry at dispatch** | Absolute monotonic request watchdog; R5 interval design; UTC always false. | Two approved authenticated evidence inputs and justified numeric bounds, verifier/monitoring/post-check implementation. | Monotonic timeout cannot prove approval unexpired; delayed write might outlive authority. | **Essential.** Time-sync daemon optional/unneeded. | D4; pure interval verifier plus dispatch guard, operator-managed acquisition. | Synthetic overlap/cover computation; reject nonoverlap/stale/missing bounds/step/suspend/reboot. Test expiry equality and full 30s+margin: reject. Delay storage past freshness/expiry: **0 write bytes**. Failed post-check withholds validity and next call. | **M2**, after D4 and M1 gate; no actual time requests in offline implementation tests. |
| **7. Contained exact installed topology** | R6/R7 creation-time membership/suspension, explicit inheritance, blocked I/O/tree/death fixtures; supported host only. | Reviewed installed launch profile/environment/cwd/delegation equivalence and pinned real-binding adaptation. | A shell/uncontained fallback or delegated work could evade intended lifecycle control. | **Essential real binding; no further native owner required absent concrete failure/D1 rejection.** | Carry exact profile through existing boundary only after provenance; no arbitrary argv API. Supported-host refusal, no breakaway/fallback. | Fake analogue of reviewed shell/child chain: no execution before membership, eager children stay in job, hidden returns refuse, no ordinary Popen/late assignment, controller death closes tree. Check installed-profile pin mismatch refuses before launch without running installed binary. | **M3**, depends M0/M1/M2; existing 93 R6/R7 tests are historical evidence, not real-launch proof. |
| **8. Sole effective route and stale-binding retirement** | One project direct entry, no effective inventory or replacement. | All aliases/sessions/plugins/agent shell routes, reviewed minimal diff, trusted deployment protections and separately authorized activation evidence. | Restricted frontend can be bypassed via old route or gate replacement. | **Essential.** | D6 plus §4.3; replace same effective entry, protect code/state, retire old loaded routes. | Offline config/permission fixture with global override/duplicate/stale alias must fail sole-route check. Later activation inventory must show only restricted catalog, no direct Roblox route and no agent-writable gate; automatic startup dispatch count remains 0. | **M3** plan, **M4** separately approved deployment; no activation now. |
| **9. Real-wire/identity observation refusal contract** | Strict synthetic wrappers/typed IDs; no real response; upstream completeness always unverified. | Build-bound expected lifecycle/name/schema and plan to preserve/refuse unknown real results, current operator expectations later. | Cannot claim compatibility/identity or continue state on ambiguous discovery. | **Essential refusal contract; actual live compatibility is an observation outcome, not a pretext for unapproved probing.** | Pin expected candidate contract from permitted evidence; unsupported result ends observation for later offline review. No guessing wrappers or backfilling fields. | Fixtures: duplicate keys/IDs, missing identity, alias/version/wrapper mismatch and silent shortening retain originals and withhold claims; bad discovery produces 0 state dispatch. Later authorized unknown output must likewise stop without retry. | **M3** before M4; observed compatibility may remain failed after an authorized attempt. |
| **10. Final prerequisite review** | R8 documents open gates; no live readiness evidence. | All essential rows closed with authoritative evidence, then separate launch/protocol/observation scope/expiry approval. | Gate A remains blocked regardless of passing synthetic tests. | **Essential.** | M3 independent check against actual deployment/decisions; no automatic gate promotion. | Deliberately remove any prerequisite (provenance, sole route, approval, time, storage, limits): startup stays inert / dispatch 0. Review records every unresolved qualifier and verifies final manifests/status, not marker existence alone. | **M3**, before any M4 execution approval consideration. |
| **11. Unconditional ownership/power-loss/hard-stop certification** | Qualified finite Windows/death/fault tests, no universal proof. | Universal in-kernel/cross-version/interleaving/device guarantees, if demanded. | Under approved D1/D5, lost availability/ambiguous local resources or evidence cause refusal; no established extra unauthorized-operation path. | **Deferred optional assurance**, except a reproduced escape or explicitly adopted stronger requirement. | No broker, native transaction, deduplicating store or time service solely for absolute guarantees. Reopen only a concrete requirement/failure. | Preserve current failure tests; any supported-host escape, false success or unauthorized write reproduction becomes an essential defect with a focused regression. No impossible universal acceptance test. | **Deferred**; not ahead of M1/M2. |

**Ranked practical priorities:** (1) obtain the small installed/effective contract
packet and decisions; (2) implement the actual restricted client-facing path offline;
(3) enforce independent approval/revocation and safe evidence storage, with trusted
UTC as part of the dispatch gate; (4) qualify the exact contained profile and sole
route/deployment; (5) perform the later complete readiness review. Gate B bounded
Luau/serialization/path/stability/same-read identity blockers remain separate and
unchanged; this catalog must never expose Gate B as a way to discover missing fields.

## 9. Smallest next executable offline milestone and STOP

**Recommended R9: fixed-catalog, fake-only stdio frontend conformance**, after the
minimal client packet and applicable decisions are supplied. Implement local inert
initialize/tools-list, strict bounded client decoding and one locked one-shot
discovery → durable synthetic checkpoint → explicit synthetic continuation → state
sequence over `run_contained_synthetic` primitives. Use injected clearly synthetic
approval/time/storage verifiers with a production default of refusal; test failure,
replay/reconnect/parallelism and pause behavior. Do not treat an injected test result
as a genuine approval channel. Run a source-derived fake OpenCode client, not the
installed enabled MCP configuration. Keep only fixed bundled child scenarios and
no real executable/argv/environment/live option, registration or activation.

If the packet/decisions are unavailable, the executable next action is **offline
packet reconciliation/contract review**, not an assumed live binding. R9 should
close frontend usability and denial behavior, not claim the actual operator/time/
NTFS prerequisites are solved. M2 then implements only those missing approved gate
controls and storage protections, reusing suitable existing primitives. No second
containment framework or speculative broker is justified by R8.

## 10. Verification and completion boundary

R8 is documentation-only. Source/test statements were checked against the actual
modules/tests listed in §1; R7's **155 focused passed; 360 full run, 359 passed,
1 existing symlink skip** are historical R7 results, not tests rerun by R8. No source
defect requiring an R8 code fix was established under the proposed fault model;
the future live frontend and deployment remain expressly blocked.

Verification covers referenced project paths/section/source/test anchors, consistency
of pending-vs-approved policy, bytes/copy-budget arithmetic and milestone dependencies,
preservation of R1–R7/approved-plan history, tracked whitespace (`git diff --check`)
and the new untracked report
(`git diff --no-index --check -- /dev/null docs/C1E_C2B_R8_GATE_A_DECISIONS.md`).
Both whitespace checks **PASS, exit 0**, with LF-to-CRLF warnings only. Project
reference paths were checked with dedicated glob/read tools; section/source/test
anchors, budget sums and pending-decision/dependency consistency were reviewed
manually. Git status was compared with the initial inventory: the R8 report is the
only new path; existing unrelated dirty/untracked work remains. Diff statistics
include pre-existing work and are not an R8-only change count. Results are also
recorded in status §2.31.
No runtime suites or installed client/server were launched for this documentation
review. **STOP after R8. Gate A remains BLOCKED until a later review establishes its
prerequisites; do not request or initiate live Studio execution.**
