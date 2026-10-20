# C1E-C2B-R10 — Installed OpenCode provenance and fake-only compatibility

## 1. Classification and scope

**QUALIFIED fake-only compatibility for the pinned release's selected serial
stdio profile (§8).** Official release/SDK source and the release's SDK patch now
support a source-derived Python fake client. Two confirmed envelope mismatches
were corrected, and 210 focused tests / 415 full-suite tests ran (§8.6). This is
not execution of the JavaScript SDK, installed OpenCode, or a live integration.
Installed-executable-to-source correspondence and actual loaded settings remain
unverified. Earlier **C. BLOCKED** records below are historical evidence stops.

**Gate A remains BLOCKED / NOT TECHNICALLY READY. D1–D6 remain PENDING.**
No live Roblox execution is authorized. Option B's independent authorization,
original-byte evidence, creation-time containment and fail-closed recovery remain
required. R9's candidate passes are historical synthetic evidence only.

- Baseline checked: `4661903d4f97cdb8d62adea89544741d3a00871c`.
- Resumed permission check: operator changed project configuration after the initial
  R10 stop. This is a new, explicitly disclosed R10 configuration change (§2.4),
  not part of the unchanged initial R10 baseline. The single authorized package
  Read retry was again policy-denied; external inspection stopped there.
- Operator-packet resume (historical): reviewed `docs/R10_OPERATOR_EVIDENCE.txt` as operator-provided
  data, hashed the repository packet, and reconciled the later disk disablement
  recorded in status §2.33. No installed-file read was retried or installed
  executable run. Earlier unavailable-fact tables are historical; §2.5 supersedes
  their evidence availability, not their account of the denied agent access.
- Review label: 2026-10-18, from the harness; not authenticated UTC.
- Single agent, no delegation or Swarm. Earlier resumes changed only this report
  and `status.md`; the current authorized source review additionally changes the
  synthetic frontend, adds a release-derived fixture/tests and source-acquisition
  packet, and appends the implementation handoff (§8.5). Existing work and records,
  including the approved `.swarm/plan.md`, were preserved.
- Read status §2.32, R9, R8 (including decisions/readiness), R7, R2's historical
  access/configuration record, project `opencode.json`, the R4–R9 recorder,
  containment, evidence, frontend/review source and relevant tests/fixture.
  Repository `**/AGENTS.md` search found none; inaccessible parents were not searched.
- Repository search for installed package/version/SDK/override evidence found no
  build-matched implementation packet. The existing status toolchain row names
  `opencode-swarm v7.197.3` as a session observation, not a loaded-plugin audit.
  No network/vendor lookup was made in the initial offline review. The current
  continuation explicitly authorizes pinned official source retrieval (§8.1).

## 2. Evidence ledger: operator observations versus independent inspection

### 2.1 Operator-supplied installation inventory (initial handoff, historical)

The following comes from the operator's R10 handoff, reporting independent Windows
PowerShell observations. Codex did **not** inspect these original files or rerun
the inventory commands. No original-byte packet or acquisition transcript was
supplied in the repository reviewed here.

| Observation | Operator-supplied value | Qualification |
| --- | --- | --- |
| Node.js / npm | `v24.11.1` / `11.6.2` | Inventory context; not proof of the executable's embedded runtime. |
| npm global root | `C:\nvm4w\nodejs\node_modules` | Reported root, not independently resolved physical identity. |
| Global packages | `opencode-ai@1.19.0`; `opencode-swarm@7.197.3` | Inventory only; neither loaded plugins nor MCP SDK versions follow from this. |
| Command resolution | `C:\nvm4w\nodejs\opencode.ps1`, `opencode.cmd`, `opencode` | All three resolved paths were reported. Only the first two launch behaviors were supplied. |
| Launcher modification time | October 16, 2026, 8:09:25 PM for all three | Operator Windows display; timezone/offset and authenticated clock accuracy unspecified. Do not convert to a claimed UTC instant. |
| Reported `Target` paths | Into `C:\Users\juara\AppData\Local\nvm\v24.11.1\` | Does not establish all filesystem indirections or final executable identity. |

| Reported launcher | Length (bytes) | Operator-reported SHA-256 |
| --- | ---: | --- |
| `C:\nvm4w\nodejs\opencode.ps1` | 496 | `7DC7F9E963B88BBFB7A529A82D1922ADF642D386F096FC250E891E374884EE8E` |
| `C:\nvm4w\nodejs\opencode.cmd` | 148 | `B53B698473BFA46E09487E485A7F1AD5B4881F8A8B319D3619AA251F3BE8AE10` |
| `C:\nvm4w\nodejs\opencode` | 296 | `0F2F05DCD20BCAEFD7C050E8D6505D58D4136E896EA38AE9EFE561911F04AF6C` |

Operator-inspected command excerpts:

```text
opencode.cmd: "%dp0%\node_modules\opencode-ai\bin\opencode.exe" %*
opencode.ps1: "$basedir/node_modules/opencode-ai/bin/opencode.exe"
```

The operator reports PowerShell argument-array forwarding and pipeline-input
support. Both inspected Windows launchers therefore reference the next candidate
executable **`C:\nvm4w\nodejs\node_modules\opencode-ai\bin\opencode.exe`**.
These excerpts are not asserted to reproduce the hashed launcher bytes. They do
not establish that executable's digest, runtime, SDK, source correspondence or
absence of further delegation. No behavior is inferred for the extensionless
launcher beyond its reported metadata.

### 2.2 Initial exact-file inspection and stop (historical)

After repository inspection, one dedicated Read call targeted:

`C:\nvm4w\nodejs\node_modules\opencode-ai\package.json`

The tool refused it with a policy-rule list including early
`external_directory: ask`, scoped allows and later wildcard
`external_directory: deny`. No package contents were returned. This establishes
a **tool-policy refusal**, not a Windows ACL denial, missing file or corrupt install.

External installation inspection stopped at that boundary. The executable was
not read, hashed, resolved, signature-checked or run; no shell, alternate path,
copy, network retrieval or other tool was used to bypass the refusal. Global
configuration was not probed after this refusal. There was no permission change.

| Required installed fact | R10 result |
| --- | --- |
| Package original path | Exact requested path above; contents and physical resolution unavailable. |
| `name`, `version`, `bin`, `exports`, dependencies, optional/platform/runtime identifiers | Unavailable from installed metadata. `opencode-ai@1.19.0` remains operator inventory evidence. |
| Executable logical path / package relationship | Launcher-referenced package-relative `bin\opencode.exe`, per operator excerpts only. Package `bin` agreement unverified. |
| Executable final resolved identity / length / SHA-256 | **Unavailable**. Launcher hashes are not executable hashes. |
| Executable modification time and source/timezone | **Unavailable**. Reported launcher timestamps cannot be transferred to it. |
| Windows file/product/version metadata | **Unavailable**, not established absent. |
| Authenticode status / signer | **Unavailable**, not established unsigned. |
| Separate Windows executable package | **Unknown**; no package metadata was acquired to identify one. Do not guess a platform-package name or search `node_modules`. |
| Internal runtime / MCP SDK / plugin integration | **Unknown**. Installed Node.js and npm versions do not establish these. |
| Source-to-build correspondence | **Unverified**. Even future metadata/hash/signature acquisition alone would not prove embedded source or SDK behavior. |

### 2.3 Initial independently inspected project identity (historical)

`C:\AI\slop\roblox-factory\opencode.json` original on-disk SHA-256, acquired
read-only with PowerShell `Get-FileHash -Algorithm SHA256 -LiteralPath`:

`20508710E7B9A5B9B39BB125C1BB9AEF88247950204FF2CF9C94D84A4DFCC604`

This matches the historical R2 project-file digest; it proves neither loaded
configuration nor executable identity. R10 did not change it. `git diff --
opencode.json` still shows only the pre-existing `edit: deny` → `allow` change
relative to baseline; `external_directory: deny` is unchanged from baseline.

### 2.4 Resumed permission check — new operator configuration change

On resumption (2026-10-18 harness label, not authenticated UTC), the agent first
read the current project `opencode.json`, acquired its original on-disk SHA-256
with read-only PowerShell `Get-FileHash -LiteralPath ... -Algorithm SHA256`, and
reviewed `git diff -- opencode.json`:

`6631EC7B24102DAFE010F0AA94DD7D26337C84A9A9EB4080AD6FB3E3BDBC7BCD`

This differs from the initial R10/R2 digest in §2.3. The operator's new disk rules
are `external_directory` wildcard `deny` with exact `allow` entries for:

- `C:/nvm4w/nodejs/node_modules/opencode-ai/package.json`
- `C:/nvm4w/nodejs/node_modules/opencode-ai/bin/opencode.exe`

The current `edit` object has wildcard `allow` and exact `deny` entries for both
files. The historical scalar edit deny→allow change remains pre-existing; the
new exact-file permissions are disclosed separately here. The agent made no
configuration edit. MCP registrations still contain the direct enabled Roblox
batch route and enabled ComfyUI entry with 30000 ms disk timeouts; neither was
modified, activated or contacted. A disk digest is not proof of effective access,
configuration precedence or retirement of any session route.

**Actual retry result: DENIED.** Exactly one dedicated Read retry targeted
`C:\nvm4w\nodejs\node_modules\opencode-ai\package.json`, the same path/tool as
the original refusal. The tool returned “The user has specified a rule which
prevents you from using this specific tool call.” Its relevant-rule list included
early `external_directory: ask`, wildcard `deny`, and both new forward-slash
exact-file `allow` entries. **No package contents were returned.** This records
the observed tool-policy boundary; it does not establish Windows ACL state,
file existence, a path-separator diagnosis, or installed rule precedence. No
alternate spelling, tool, shell command, copied file or network source was tried.

External inspection stopped immediately. The executable was not read, hashed,
resolved, signature-checked or executed. No package scripts, OpenCode command,
Roblox MCP process or MCP tool was run. No global configuration probe followed.
All installed-fact entries in §2.2 remain unavailable/unknown; `name`, `version`,
`bin`, `exports`, dependencies and optional/platform/runtime identifiers could not
be inspected. Operator inventory `opencode-ai@1.19.0` is still not independently
verified installed package metadata.

**Next minimum evidence: operator-generated PowerShell packet, §6.1.** Request
that the operator collect only the two exact files' original-path length/SHA-256,
filesystem timestamp and indirection/final-identity evidence, selected package
fields, executable version metadata and offline Authenticode result, with
acquisition method/date/timezone and errors/unavailable fields identified. The
existing §6.1 commands are for operator execution only; none were run by the
agent. No executable upload is needed. Stop on access error without alternate-path
retry. Any separate platform package must first be identified by returned metadata
and its exact candidate paths reviewed before further access. Build/SDK/hooks and
credential-free effective-setting evidence in §6.2 follow identity acquisition;
neither a hash nor a version label alone proves the installed client contract.

### 2.5 Operator acquisition packet — current evidence review

**Received:** `docs/R10_OPERATOR_EVIDENCE.txt`, 161 displayed lines, **6,365 bytes**.
Agent-computed SHA-256 of the repository packet's original on-disk bytes:

`FB4C9E37BEAEDB13F52563CCFC3DB04180147343E9ABCE9276DD1EC19307F5A4`

This pins the reviewed submission, not the installed files or the authenticity of
the transcript. The agent read this accessible packet as data and did not rerun
its commands. The two installed-file digests below are **operator-reported**;
neither installed original nor original `package.json` bytes were supplied for
independent rehashing. Both digests pass 64-hex-character syntax checks. Selected
JSON output cannot reconstruct the 812-byte package or verify its reported hash.

**Acquisition provenance:** the transcript has start/end markers, commands and
outputs, Windows PowerShell Desktop **5.1.26100.9444**, host executable, user/run-as
user, machine, PID and working directory. Start is `20261018144638`, end
`20261018144942`; `Get-Date -Format o` reports
`2026-10-18T14:46:38.8672409+08:00`, and `Get-TimeZone` reports Singapore Standard
Time / `08:00:00`. These are operator-host clock/timezone observations, not
authenticated UTC or D4 evidence. No collection error appears in the supplied
transcript; `$ErrorActionPreference = 'Stop'` is recorded. This is not an
independent guarantee that every relevant event or output was captured.

| Required §6.1 item | Packet observation / completeness finding |
| --- | --- |
| Exact original logical paths, lengths, hashes | Present, lines 36–78; see table below. `FullName` repeats the requested paths. |
| Filesystem modification times / source | Present as `LastWriteTimeUtc` from `Get-Item`. The requested literal `TimestampSource` field was omitted, but the command identifies its filesystem source; clock accuracy remains unauthenticated. |
| Indirection / final identity | Leaf `LinkType`/`Target` present. Optional handle-based helper was not run; no `FinalHandlePath`, volume/file ID or full ancestor-resolution evidence. Final physical identity remains unavailable. |
| Selected package fields | All requested selections present, lines 83–121; interpreted below. Original manifest bytes, resolved dependency lock/build manifest and platform-package manifest absent. |
| Executable version resource | All requested fields present, lines 124–139. Descriptive resource metadata only. |
| Authenticode | Status, signer, thumbprint and qualification present, lines 141–155. Qualification is limited as described below. |
| Acquisition stability / offline conditions | No explicit statement about install/update/races during the separate reads, or evidence of network isolation. The printed trust qualification alone does not establish isolation. Request a short operator clarification, not a repeat collection. |

| Operator-hashed file | Length | Operator-reported SHA-256 | `LastWriteTimeUtc` |
| --- | ---: | --- | --- |
| `C:\nvm4w\nodejs\node_modules\opencode-ai\package.json` | 812 | `3D8D4CDC137D50237711B9DA187BD190E5B273CFAC25ADFAD31BE5F0EF691BFD` | `2026-10-16T12:09:24.4788519Z` |
| `C:\nvm4w\nodejs\node_modules\opencode-ai\bin\opencode.exe` | 180714888 | `BB731F311416DF16691FA16763EB87657C4A5F5F3BCFF5202718C416E8F7AB1A` | `2026-10-16T12:09:25.4534944Z` |

**Package identity / path reconciliation:** selected metadata reports
`name: opencode-ai`, `version: 1.19.0`, and
`bin: {opencode: ./bin/opencode.exe}`. This agrees with the historical npm inventory
and both supplied Windows launcher excerpts. `exports`, `dependencies` and
`engines` select as null; selection does not distinguish an absent property from
an explicit null or prove there are no bundled dependencies/SDK. `os` lists
`darwin`, `linux`, `win32`; `cpu` lists `arm64`, `x64`, not the executable's measured
PE architecture. Twelve optional platform packages are declared at exact
`1.19.0`, including `opencode-windows-x64`, `opencode-windows-x64-baseline` and
`opencode-windows-arm64`. Declaration alone does not prove installed selection.

The manifest leaf has `LinkType: null` and reports Target
`C:\Users\juara\AppData\Local\nvm\v24.11.1\node_modules\opencode-ai\package.json`.
The executable reports `LinkType: HardLink` and two Targets:

- `C:\Users\juara\AppData\Local\nvm\v24.11.1\node_modules\opencode-ai\node_modules\opencode-windows-x64\bin\opencode.exe`
- `C:\Users\juara\AppData\Local\nvm\v24.11.1\node_modules\opencode-ai\bin\opencode.exe`

These are operator-observed link/path associations, not independent final-handle
resolution, a separate hash of each Target, or proof of the command selected by a
running session. They identify **`opencode-windows-x64` as the concrete candidate**,
consistent with its `1.19.0` optional declaration. Its own installed version/bin
and build provenance remain unverified. The exact candidate manifest for review is
`C:\Users\juara\AppData\Local\nvm\v24.11.1\node_modules\opencode-ai\node_modules\opencode-windows-x64\package.json`;
that manifest path is inferred from the reported layout, not observed/read.
The executable candidate is the first reported Target above. Naming these paths
does not authorize access or execution. A small already available platform/build
manifest or equivalent artifact mapping is sufficient; no recursive scan or second
executable copy is required.

**Executable metadata:** FileName agrees with the requested executable;
OriginalFilename is `bun.exe`, FileVersion and ProductVersion are **`1.3.14`**,
ProductName is **`Bun`**, CompanyName is **`Oven`**. This is consistent with a
Bun-derived version resource, but does not independently prove the selected runtime,
embedded OpenCode version, source commit or SDK. It does not contradict the
package's `1.19.0`: package version and resource version describe different things.
Do not replace the OpenCode package version with the Bun resource version.

**Signature qualification:** operator `Get-AuthenticodeSignature` reports
**`Valid`**, signer
`CN="Anomaly Innovations, Inc https://anoma.ly/", O="Anomaly Innovations, Inc https://anoma.ly/", L=Dover, S=Delaware, C=US`,
and certificate thumbprint **`77F28D7AB97A6983B005FCDABD6A25F62EF424D4`**
(40 hexadecimal characters; a certificate identifier, not the executable SHA-256).
The packet labels it **“Offline Windows trust/cache result only.”** Preserve that
operator qualification; network isolation was not demonstrated by the transcript.
No certificate chain/validity window, timestamp countersignature, trust policy or
online revocation result is supplied. Do not infer current online trust, publisher
release/build correspondence, embedded code/SDK behavior or execution authority.
This is reported local Windows validation, not an independently verified signature.

**§6.1 disposition:** core two-file metadata/hash/package/resource/signature
collection is supplied, with the provenance limits above. The former “no packet”
blocker is superseded. Final-handle identity stays explicitly unavailable and the
short stability/offline clarification is outstanding; neither is a reason to retry
denied access. At that review there was no build-contract/SDK/plugin/effective-settings
packet or observed client traffic. The later authorized source review (§8) supplies
conditional release evidence and narrow corrections, not installed-client traffic.

### 2.6 Current project disk state — later than the permission retry

Status §2.33's subsequent workspace check recorded both MCP entries disabled on
disk. This resume read the repository config and independently rehashed it:

`6C2656F8245444E0B169F1501E7312716615F409D90CC9AB04A76BC9E6E7BB32`

`roblox_studio.enabled` and `comfyui.enabled` are both **false**; their stored
commands and timeout values (30000) remain present, as do §2.4's exact-file rules.
The `6631…7BCD` permission-edit digest and enabled-entry observations in earlier
sections are historical, not the current disk state. The agent made no config edit.
Disk disablement is not effective merged configuration, a loaded-plugin inventory,
proof of zero running routes, or evidence that stale sessions/aliases were retired.

## 3. Historical installed-contract gap matrix: all 14 investigation areas

**No exact installed OpenCode client-message contract can currently be stated.**
The following pre-source-review matrix is retained as history; §8.3 supplies the
current release-source expectation map, without claiming installed equivalence.
No build-derived expectation is attributed to inventory, tool display names or
R9's fixture. The table separates concrete R9 behavior from missing client evidence.
Every conditional incompatibility below remains unresolved; none is an observation
that OpenCode 1.19.0 actually sends that traffic.

Source abbreviations: **F** = `tool/c2b_restricted_frontend.py`; **S** =
`tool/c2b_recording_supervisor.py`; **V** = `tool/c2b_synthetic_review.py`.
Line anchors refer to the unchanged R10-reviewed repository files.

| Area | Reviewed candidate boundary / possible incompatibility | Essential installed evidence still missing |
| --- | --- | --- |
| 1. Process spawning / stdio | F:280–284 starts inert; its child path is only F:70–80 → S:564–650 → R7/R6 fixed Python fixture. This is not OpenCode's spawn. | Exact client executable/shell/argv, cwd, environment allowlist/expansion, stderr handling, ownership and disposal; Windows-specific wrapping and plugin effects. |
| 2. Framing / lifecycle | F:120–194,206–277 requires bounded UTF-8 NDJSON JSON-RPC 2.0; no batches, extra envelope keys, duplicate keys, nonfinite numbers or partial lines. | Build-selected transport/serializer/parser, delimiters, buffering and close ordering; SDK version and resolved code. Other framing/controls would refuse. |
| 3. Initialize | F:162–172 accepts only `2025-11-25`, `{}` capabilities and exact bounded `clientInfo: {name,version}`. No negotiation. | Actual first protocolVersion, supported negotiation set, exact clientInfo and capabilities, including optional fields. Any different version/nonempty capabilities/additional clientInfo keys would terminate R9. |
| 4. Initialized notification | F:147–157 accepts once after initialize, params absent or `{}`. | Actual notification contents/order, any metadata or other startup notifications. Extra startup controls would refuse. |
| 5. tools/list / pagination | F:175–178 accepts absent/empty params; returns fixed tools without `nextCursor`. | Initial/list-refresh request parameters, pagination termination/refresh logic, metadata/cursor injection. Cursor or `_meta` on a request would refuse. |
| 6. Naming / aliases | F:22–29,90–113 publishes and accepts only two short wire names. Prefixed aliases are rejected. | Model-facing alias generation, sanitization/collisions and reverse mapping to original wire names. A model-facing prefix is not automatically a wire-name mismatch. |
| 7. Argument serialization | F:90–113 requires exactly `name` + object `arguments`, discovery `{}`, state exact UUID; no params `_meta`, task or additional arguments. | Exact callTool construction, omitted/default arguments, parsed JSON representation, metadata/progress injection and plugin rewrites. Missing arguments or added metadata would refuse. |
| 8. Result / error parsing | F:183–192 returns JSON-RPC `result` or terminal `error` code `-32000`. S:495–541 accepts one text content block containing strict synthetic JSON; `isError` true and unknown wrappers refuse. | Client SDK result schema/version, treatment of `isError`, JSON-RPC errors, content/structuredContent, schema conversion, model-visible conversion and plugin error handling. No client acceptance can be inferred from Python `json.loads`. |
| 9. Timeouts / cancellation | F:151–156,254–255 makes cancellation/any in-flight second frame terminal. V:141–175 has genuine bounded review; S:377–457 has absolute per-request watchdog. | Actual timeout start/default/config mapping, progress resets, cancellation notification/reason, wait and teardown behavior. Project `30000` is just a disk value, not an end-to-end deadline. |
| 10. Retry / reconnect | No retry; F:196–204 closes, new frontend starts inert; new-only observation storage blocks reopening. | Automatic reconnect/restart/backoff/retry triggers, new client/session IDs and any tool retry policy. Fresh process/ID must never replenish observation authority. |
| 11. Concurrency / scheduling | F:120–125,206–265 aborts rather than queueing an active tool plus any second frame, including ping/cancel/catalog. | SDK parallel requests, scheduler, background ping/catalog refresh and cancellation races. Ordinary background traffic during a tool could terminate this candidate. |
| 12. Response size / transformations | F:19–21,183–186: client input ≤4096 bytes; 64 handled frames; combined handled input/serialized success output ≤262144; success response ≤65536. S:220–277,351–375 retains bounded raw child stdout before parsing. | Client/SDK buffering/frame limits and model/plugin transformation/truncation thresholds. Display capping is not a wire-limit measurement or original-byte evidence. |
| 13. Registration / precedence | Stored direct batch command remains, now disabled on project disk (§2.6); no effective-route proof. | Build-specific config loader/merge semantics for all applicable scopes and override sources, effective commands/permissions/timeouts and session cache lifetime. |
| 14. Plugin hooks | Project JSON has no `plugin` field; npm inventory lists swarm. No plugin code was read or loaded. | Actual loaded plugin entrypoints/versions/digests, load ordering and hooks that alter schemas/tools/arguments/requests/results/config, including any bundled integrations. Inventory does not prove activation or absence of other plugins. |

At this historical evidence stop no source-supported correction could be selected.
The later §8 corrections are limited to newly supported envelopes. Do not add
negotiation, metadata acceptance, queuing, aliases, retry, generic forwarding or a
new tool merely to imitate a generic MCP SDK. Confirmed differences require narrow
offline review and regression coverage while preserving the authorization boundary.

### Exact candidate messages — not installed-build messages

These are illustrative R9 fixture messages (UTF-8, one LF-terminated JSON object
per line); IDs are illustrative, not observed OpenCode allocation:

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"R9 synthetic candidate client","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"ping"}
{"jsonrpc":"2.0","id":3,"method":"tools/list"}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"list_roblox_studios","arguments":{}}}
{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"get_studio_state","arguments":{"studio_id":"577768ad-49d8-42f5-ac96-8c66cd12a144"}}}
```

This is not an executable concatenated test: await each response; discovery needs
separate TEST-ONLY launch injection; state additionally needs the verified discovery
checkpoint and separately injected TEST-ONLY continuation before its request.
Neither injection is an MCP operation or human approval. Initialize replies with
`capabilities: {"tools":{}}`, fixed test-only serverInfo and the same candidate
version. Only then may initialized → READY occur. The catalog is exactly:

- `list_roblox_studios`: object schema, empty properties, `additionalProperties:false`.
- `get_studio_state`: object schema, required `studio_id` string with `const`
  `577768ad-49d8-42f5-ac96-8c66cd12a144`, `additionalProperties:false`.

Runtime enforcement remains authoritative. Typed IDs are strings of 1–128
characters or integers strictly between `-2**53` and `2**53`, never reused within
the connection. Notifications have no response; malformed/uncorrelatable IDs use
null in a refusal. Terminal success also ends the disposable frontend.

`tests/fixtures/c2b_synthetic_client.py:5,27–38` imports S's `PROTOCOL` constant.
Its agreement with R9 is therefore not independent installed-client evidence;
its name/version are synthetic. A future build-bound fixture must cite external
build evidence for each derived expectation instead of silently inheriting it.

## 4. Effective settings reconciliation

| Question | Permitted finding / remaining limit |
| --- | --- |
| Project identity | Initial digest in §2.3, permission-edit digest/denied retry in §2.4, latest disk-disablement digest in §2.6; F is not registered. |
| Permissions | Current disk external wildcard deny plus two exact allows; edit wildcard allow plus two exact denies (§2.4); shell default ask with listed Git allow/deny patterns. The package Read retry was denied despite both allows appearing in the returned rule list. |
| Earlier ask versus deny | Prior operator `ask` may refer to a different scope/time/session. Initial R10 and resumed refusals are separate observations. New operator exact-file rules are disclosed in §2.4; their appearance in the refusal does not prove effective access or precedence. Rule display order is not build-matched proof of source attribution or session snapshots. |
| Global/user config | Historical R1/R2 identify denied candidates `C:\Users\juara\.config\opencode\opencode.json` and `opencode.jsonc`. Actual active global path, existence, contents and alternatives remain unverified; no fresh global read attempted. |
| CLI / environment / managed scopes | Applicable names, values affecting source selection, presence and priority are unknown. No full environment/argv/credential dump or installed config/debug command was run. |
| Plugins | Operator npm inventory: swarm `7.197.3`, OpenCode `1.19.0`. No project plugin declaration. Effective loaded set, dependencies and hook effects unknown. |
| MCP entries on disk | `roblox_studio`: local `cmd.exe /d /c %LOCALAPPDATA%\Roblox\mcp.bat`; `comfyui`: local `comfy-mcp`; both **disabled**, timeout 30000 (§2.6). Neither was contacted. |
| Effective MCP merge | Unknown: replacement/deep merge, duplicate names/aliases, enabled/timeout overrides and source order need installed code plus provenance-bound settings. One project entry does not prove one effective route. |
| Tool aliases / stale sessions | Survival across changes, caching and cleanup/restart semantics unverified. Visible session tool definitions are not an installed-build transcript or a complete sole-route inventory. Disk changes cannot be presumed to retire in-memory routes. |

**Future replacement requirement, not an R10 configuration action:** after build
contract and D6 review, identify the winning effective Roblox key and every alias/
alternate route. A separately approved deployment must replace that direct binding
with one pinned restricted frontend through the R7/R6 boundary, remove effective
duplicates/bypasses, and retire old processes/sessions/tool caches using verified
client lifecycle semantics. A clean-session inventory must prove only the two
reviewed tools and zero upstream launches during startup/catalog/reconnect.
Protect trusted code/config and independent authority/evidence state. Do not
activate a second restricted route alongside the direct route. Exact merge diff,
activation procedure and sole-route proof remain blocked on the missing evidence;
no such edit, disablement, restart or activation was performed here.

## 5. Historical Phase E gate and coverage disposition

**Prior review: Phase E NOT ENTERED.** No verified installed messages existed from which to build
the fake client. Running R9's own fixture again would not satisfy this prerequisite.
No R10 tests/fixtures/runtime code were added or changed, and no synthetic children
or frontend were launched. The following maps required future coverage to reviewed
historical assertions, without calling them R10 execution or build-derived tests.

| Required coverage | Existing source/test anchor | R10 build-bound disposition |
| --- | --- | --- |
| Initialize/capabilities; initialized; ping/catalog | `ContractTests.test_startup_initialize_catalog_and_ping_never_create_child`, `test_initialize_exact_version_capabilities_and_lifecycle`, `test_stdio_only_protocol_stdout_and_diagnostic_stderr` | Blocked on §3 areas 1–5; preserve zero launches. |
| Published names/schemas; exact args | `test_forbidden_aliases_tools_and_wrong_arguments`; F:22–29,90–113 | Blocked on naming/reverse mapping, schema/serialization evidence; fixed two-tool catalog preserved. |
| Discovery/checkpoint; explicit test-only continuation; conditional state | `IntegratedTests.test_true_pause_durable_checkpoint_then_explicit_state`, `test_missing_continuation_prevents_state`, `test_checkpoint_rechecked_after_state_intent_storage_before_first_byte` | Build-bound driver blocked; genuine WAIT_REVIEW/digest binding and per-write checks retained. |
| Wrong/forbidden tools; extra args; unsupported versions | Contract tests above plus `test_every_other_method_is_refused` | Blocked for client-derived variants; strict terminal refusal retained. |
| Tool result/error handling | S:495–541; supervisor `test_rpc_tool_error_truncation_version`, reused by R7 `ContainedProtocolTests` | Installed parser/model/plugin expectations missing; R9 frontend-to-installed-client error delivery not verified. |
| Repeated IDs; concurrency | `test_duplicate_ids_and_bounded_catalog_traffic`, `test_duplicate_discovery_new_id_does_not_retry`, `test_concurrent_requests_refuse_instead_of_queue` | Installed allocator/scheduler unknown; never relax one-shot attempts. |
| Cancellation/timeout | `test_inflight_client_cancellation_stops_before_next_tool`, `test_request_timeout_and_unknown_server_envelopes`, `test_reader_deadline_race_does_not_disarm_already_due_watchdog` | Actual client cancellation/default deadlines unknown; local termination is not Studio cancellation. |
| Reconnect/retry | `test_reconnection_while_paused_cannot_resume_or_erase_uncertainty`, `test_duplicate_discovery_new_id_does_not_retry` | Automatic installed behavior unverified; retries/restarts must not replenish authority. |
| Disconnect | `test_stdio_disconnect_and_pipelined_tools_never_succeed`, `test_client_output_failure_after_recording_is_not_frontend_success` | Installed close/error reaction unknown; verified recording is distinct from successful delivery. |
| Malformed/oversized frames | `test_malformed_oversized_and_unexpected_frames`, `test_exact_client_frame_crlf_and_typed_ids`; contained inherited supervisor protocol tests | Client framing/limits missing; preserve raw-byte-before-parse retention and bounded failure evidence. |
| Terminal refusal | `test_unauthorized_discovery_is_terminal_and_cannot_retry`, `test_uncertain_cleanup_never_returns_success_or_allows_restart`, controller-death tests | No installed reconnection acceptance claim; uncertainty remains terminal. |

All unqualified test names in this table are in
`tests/test_c2b_restricted_frontend.py`; supervisor/R7 exceptions are identified.
Future tests must use bundled synthetic fixtures and creation-time containment,
never installed OpenCode, `mcp.bat` or StudioMCP as the test child in this scope.

## 6. Smallest operator evidence request — data only

### 6.1 Two exact installed files

**Collection received; see §2.5.** The following is the historical operator request,
retained for acquisition-method comparison, not a request to rerun it. Only a
short clarification of offline conditions and acquisition stability remains;
optional final-handle identity was not collected and stays unavailable.

Historical operator action requested, not performed by Codex: in an
already offline/network-isolated Windows PowerShell session, collect only these
two exact files' metadata and the selected package fields below. Paste the output
into an operator-selected accessible project packet with acquisition method/date
and timezone. No executable upload, recursive scan, installation, config change,
global filesystem grant or execution of OpenCode/package scripts is requested.

The first block hashes original files, reports metadata and selects package fields;
it does not load package code. Stop on an access error and report it; do not retry
through another path. Authenticode is requested only offline because Windows trust
validation may otherwise attempt network retrieval. Its result is local trust/cache
evidence, not independent online revocation or behavioral/source attestation.

```powershell
$ErrorActionPreference = 'Stop'
$pkg = 'C:\nvm4w\nodejs\node_modules\opencode-ai\package.json'
$exe = 'C:\nvm4w\nodejs\node_modules\opencode-ai\bin\opencode.exe'
foreach ($path in @($pkg, $exe)) {
    $item = Get-Item -LiteralPath $path
    [pscustomobject]@{
        RequestedPath = $path; FullName = $item.FullName; Length = $item.Length
        SHA256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        LastWriteTimeUtc = $item.LastWriteTimeUtc.ToString('o')
        TimestampSource = 'Windows filesystem LastWriteTimeUtc; clock not authenticated'
        LinkType = $item.LinkType; Target = $item.Target
    } | ConvertTo-Json -Depth 5
}
$p = Get-Content -LiteralPath $pkg -Raw | ConvertFrom-Json
$p | Select-Object name, version, bin, exports, dependencies, optionalDependencies,
    os, cpu, engines | ConvertTo-Json -Depth 20
$v = (Get-Item -LiteralPath $exe).VersionInfo
$v | Select-Object FileName, OriginalFilename, FileVersion, ProductVersion,
    ProductName, CompanyName | ConvertTo-Json
$sig = Get-AuthenticodeSignature -LiteralPath $exe
[pscustomobject]@{
    Status = [string]$sig.Status
    Signer = $sig.SignerCertificate.Subject
    SignerThumbprint = $sig.SignerCertificate.Thumbprint
    TrustQualification = 'Offline Windows trust/cache result only'
} | ConvertTo-Json
```

`FullName`, `Resolve-Path` or a leaf `Target` alone does not resolve ancestor NVM
indirections. For the same exact two requested paths, this optional small Win32
helper obtains the final normalized DOS path from a read-only file handle; it
compiles only the shown helper, never loads the target executable as code. If
helper compilation/access is unavailable, report final identity as unavailable
instead of broadening access. These commands have **not** been run by Codex.

```powershell
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class R10Path {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern uint GetFinalPathNameByHandleW(
        SafeFileHandle file, StringBuilder path, uint size, uint flags);
}
'@
foreach ($path in @($pkg, $exe)) {
    $f = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Read,
        [IO.FileShare]::Read)
    try {
        $b = New-Object Text.StringBuilder 32768
        $n = [R10Path]::GetFinalPathNameByHandleW($f.SafeFileHandle, $b, 32768, 0)
        if ($n -eq 0 -or $n -ge 32768) { throw 'Final path unavailable' }
        [pscustomobject]@{RequestedPath=$path; FinalHandlePath=$b.ToString()} |
            ConvertTo-Json
    } finally { $f.Dispose() }
}
```

Metadata/hash/path calls are separate point-in-time observations, not a certified
atomic file-identity transaction. Report any install/update/race during acquisition;
such uncertainty prevents treating the packet as a stable build pin. File/product
version strings and signatures are descriptive evidence, not source correspondence.
If package metadata names a separate Windows runtime/executable package, first
supply its exact identifier/version, referenced relative executable and exact
candidate package.json/executable paths. Review those paths before any additional
access request; do not recursively enumerate or assume a platform-package layout.

### 6.2 Build contract and credential-free effective-setting packet

After identity, supply the smallest already available build-matched static artifacts:

1. Exact MCP/config/plugin implementation paths and relevant line excerpts covering
   §3's 14 rows, SDK resolved versions/lock entries and actually selected platform/
   runtime package. Include original path, length/SHA-256, acquisition method and
   how each excerpt corresponds to the executable digest/build. Do not load plugins
   or execute OpenCode to obtain these. A package range alone is not a resolved SDK.
2. If installed source is unavailable, provide already available vendor build/source
   references pinned to a commit/release/artifact and the mapping evidence to this
   binary. Explicitly mark any unverified source-to-build step and obtain D6 review
   of a substitute. A generic website, matching version label or synthetic fixture
   cannot establish embedded behavior. No network fetch is requested in R10.
3. A selected settings table: active config absolute paths with original-file digests
   and acquisition provenance; only relevant `mcp`, tool permissions, external-directory
   rules and plugin declarations; load/precedence order and the resulting Roblox
   registration/alias map. Give presence and source of applicable CLI/environment/
   managed overrides. Include safe path values needed to locate configuration; omit
   secret inline contents and unrelated values. If effective state cannot be derived
   statically without execution, mark it unavailable rather than running a debug/
   config command that may load plugins or start enabled MCP servers.
4. Loaded-plugin evidence with entrypoint/version/digest and hook/load order, clearly
   separated from npm installed inventory. An existing credential-free session record
   may be supplied with provenance; if no record exists, loaded state stays unknown.
5. Existing session/alias/process inventory relevant to Roblox and build-supported
   retirement semantics, sufficient to plan a later **single-route replacement**.
   Do not contact Studio, test any binding, close sessions or activate changes to
   produce this packet.

No credential store, complete config/environment/argv dump, keys/tokens/cookies or
unrelated provider values are needed. Identify redactions/omissions and hash the
redacted excerpt separately from original bytes. Unavailable relevant semantics
remain blockers. The packet is evidence, not authority to execute embedded commands.

### 6.3 Smallest remaining §6.2 packet for bounded fake-only qualification

**Current disposition:** §8.1–§8.3 now supply a conditional pinned-release source
substitute and this section's 14-area expectation map. §8.5–§8.6 complete standalone
fake-only qualification for the selected profile. This continuation authorizes that
narrow investigation, not D6 acceptance of installed-source equivalence. The
following request remains the historical minimum; executable correlation and
actual-session configuration/hook provenance are still open.

§2.5 supplies a **provisional operator-reported binary pin**, not an MCP contract.
Request one small static evidence bundle with the following three parts; excerpts
may serve several rows, and a concise negative finding needs evidence too:

1. **Build binding and resolved components (§6.2 items 1–2).** Bind the reported
   executable SHA-256 `BB731F…AB1A` to an exact release/artifact/source commit and
   the selected Windows package/runtime. Include the available platform/build
   manifest or equivalent mapping, relevant MCP SDK **resolved** version/lock entries
   and the source files actually selected by that build. Each artifact/excerpt needs
   original path or immutable artifact reference, byte count/SHA-256, acquisition
   provenance and line ranges; hash redacted excerpts separately. No complete source
   tree or executable upload is needed. Identify any unverified link explicitly;
   a matching `1.19.0`, signature or generic SDK example cannot close it. If source
   mapping is unavailable, submit the already available pinned vendor substitute
   for D6 review under §6.2 item 2; acceptance is still pending.
2. **Boundary contract (§3 areas 1–12).** Supply only the selected MCP integration
   and SDK/transport excerpts needed to derive: Windows spawn/shell/argv/cwd/env,
   stderr/ownership/disposal; framing/IDs/close; initialize version negotiation,
   exact clientInfo/capabilities and initialized/startup notifications; ping/catalog
   parameters/pagination; alias generation/reverse mapping and call serialization
   (including omitted args, `_meta`/progress); result/error/schema/model conversion
   and limits/truncation; timeout/progress/cancel; retry/reconnect; concurrency and
   background controls. Record exact JSON/byte expectations, scheduling/limits and
   source anchors for a fake driver. An existing provenance-bound inert trace can
   corroborate those excerpts; no new installed-client execution is requested.
   Unknown behavior remains unknown; do not invent a compatible value or relax R9.
3. **Selected configuration/hook profile (§3 areas 13–14; §6.2 items 3–4).** Provide
   build-specific config selection/merge/permission and plugin-load/hook excerpts,
   plus a credential-free table of the relevant source paths/digests, applicable
   CLI/environment/managed override presence/source and resulting command/timeout/
   permissions/alias map for the profile being modeled. Identify hook entrypoints,
   exact versions/digests/order affecting MCP, or support their absence. npm inventory
   and the missing project `plugin` field do not prove no hooks are active. Use an
   existing session record only if claiming this session's loaded profile; if it
   is unavailable, that state stays unknown. A separately defined static test profile
   must be labeled conditional and cannot be reported as actual-session equivalence.

The minimum acceptance artifact is a **14-row expectation-to-source map** tied to
that binary/component/profile pin and §5's test categories. It must support the
two-tool lifecycle, success/error handling and relevant negative traffic without
importing the candidate fixture's own constants as independent expectations.
Final-handle identity alone cannot supply this contract; its present absence need
not prevent narrowly attributed static-component testing if the build/artifact
binding is otherwise supported and the limitation is explicit. Clarify whether
an update/race affected the pin before using it as stable evidence.

**Testing boundary:** actual stale-session/process inventory and successful
sole-route retirement (§6.2 item 5), real Roblox launcher/topology qualification,
live activation and production approval/time/storage controls remain later Gate A
requirements. They are not required to run a standalone source-attributed fake
driver against the bundled contained fake child, provided that test makes no claim
about actual loaded routes or live readiness. Build-supported retirement semantics
can be recorded from the same static code now; no session needs to be closed or
binding activated to collect evidence. D6 and all other decisions remain PENDING.
This resume only identifies the minimum: no fixture was constructed or run,
Phase E remains unentered, and no R11 advancement is authorized.

## 7. Earlier verification, remaining gates and STOP (historical runs)

**Prior permission-retry resume (historical):** only this report and `status.md`
were edited by the agent. That resume's config read/digest/diff and one denied
exact package Read were new evidence for §2.4. Initial R10 checks below remain
historical; the historical 16/16 config
preservation result does not describe the operator's subsequent configuration
change. No runtime tests were rerun during the resume. Resume documentation checks
are recorded separately below.

| Resume check | Actual result |
| --- | --- |
| Project config SHA-256 before retry and after documentation edits | Same current digest both times: `6631EC7B24102DAFE010F0AA94DD7D26337C84A9A9EB4080AD6FB3E3BDBC7BCD`; distinct from the initial R10 digest. |
| Authorized package Read retry | **DENIED**, no contents; no executable inspection or alternate access attempted. |
| `git diff --check` | **PASS, exit 0**; no whitespace diagnostics, LF→CRLF advisories only. |
| R10 report `git diff --no-index --check -- /dev/null ...` | No whitespace diagnostics; native exit **1** for nonempty untracked report versus empty, LF→CRLF advisory only. |
| Working-tree inventory | Agent edited only this report and `status.md`; no staging. Final inventory also showed new untracked `danceAnimation.md` absent from entry inventory; it was not created, read or edited by this agent. Existing work preserved; no claim that the entire working tree was static. |

**Earlier documentation-only R10 reviews.** Runtime suites, R10 focused tests, full unittest
discovery, registry/art validators and Python compilation were **not rerun**.
No Python source changed and no tests were relabeled as installed compatibility.
Historical R9 final results remain: **194 focused passed, 0 skipped, 23.804s**;
**399 full run, 398 passed, 1 existing symlink skip, 36.272s**. R9 registry/art/
compilation results remain historical as recorded in R9 §6. The historical skip
is `test_asset_registry.RegistryTests.test_symlink_escape` (`symlinks unavailable`).

R10 verification: repository/source/section/test references reviewed; project
config digest acquired; tracked and new-report whitespace checked; before/after
SHA-256 compared for 16 preserved config/plan/source/test/R7–R9 report files; final
working-tree inventory compared with entry inventory.

| R10 check | Actual result |
| --- | --- |
| `git diff --check` | **PASS, exit 0**, no whitespace errors; LF→CRLF advisory warnings for pre-existing `docs/IMPLEMENTATION_STATUS.md` and updated `status.md`. |
| `git diff --no-index --check -- /dev/null docs/C1E_C2B_R10_OPENCODE_COMPATIBILITY.md` | **PASS: no whitespace diagnostics**, LF→CRLF advisory only. Native status **1** denotes differences from empty for this nonempty untracked report; corrected checking wrapper exits **0** and rejects statuses above 1. |
| Read-only SHA-256 before/after comparison | **PASS: 16/16 identical**: project config, approved plan, six C2B source modules, five C2B test modules and R7/R8/R9 reports. No runtime code was executed to hash them. |
| `git status --short` versus entry inventory | Same pre-existing dirty/untracked paths, plus this new R10 report; `status.md` was already dirty and received the R10 update. No staging/deletion or new runtime artifact. |

The preserved approved-plan SHA-256 is
`DBF77AD2F79F32DCC3CB8AF8E8E6CB25D2FDB8052B213D3198C138D83000ED46`;
the preserved R9 frontend SHA-256 is
`0A3E587FF4D198A1916D1045634EF2EC7E6630BD71D8549FA1E0E10859D0885A`.
These are local consistency checks, not approval or installed-client provenance.
The first whitespace summary/wrapper assumed no-index exit 0. Explicit status
capture showed 1 with no whitespace diagnostics; the wrapper and documentation
were corrected without changing source. No runtime test failure/correction is
claimed in R10.

| Decision | Status after R10 / remaining evidence |
| --- | --- |
| D1 — fault/ownership model | **PENDING**. No adoption of broker deferral or universal ownership/recovery claims. |
| D2 — oversized retention/accounting | **PENDING**. Prefix amendment, distinct-content/physical-copy interpretation and new budgets not adopted. |
| D3 — independent approval/withdrawal | **PENDING**. No actual authenticated authority/channel; test-only continuation is not approval. |
| D4 — independent authenticated UTC | **PENDING**. No source operation or new time attestation; filesystem timestamps are not trusted UTC. |
| D5 — protected private storage | **PENDING**. No production ACL/path/quota/retention/durability qualification or changes. |
| D6 — installed client/launcher/sole route | **PENDING**. Operator packet supplies reported package/executable identity, hashes, resource/signature results (§2.5); final identity and build mapping/SDK/hooks/effective configuration/retirement remain unverified. Minimum fake-only evidence is §6.3. |

Gate A blockers remain: installed client contract and fake-only qualification;
exact real launcher/delegation/stdio/contained topology; independent authenticated
launch/review/withdrawal and protected one-shot replay; two-source UTC/expiry
verification; private bounded evidence/checkpoint/storage deployment; sole effective
route and stale-session retirement; approved D1–D6 dispositions and later complete
readiness review. Gate B remains separately blocked. Raw stdout retention before
parsing, evidence verification, inert startup, strict argument validation, genuine
test-only WAIT_REVIEW, digest-bound checkpoint and terminal one-shot uncertainty
semantics remain intact.

**Smallest next evidence step after packet review:** clarify §2.5's acquisition
stability/offline qualification, then supply §6.3's build binding, boundary contract
and selected config/hook profile. Core §6.1 output is received; no repeat installed
read or execution is requested. Only with enough evidence, conduct a later source-
attributed fake-client/contained-fixture qualification, with minimal supported
corrections and required regression suites if code changes. No live binding is
needed to fill this offline evidence gap.

### Current operator-packet resume verification

Only this report and `status.md` were edited. The submitted packet was preserved;
no denied installed-file read, installed OpenCode/Roblox executable invocation, network/vendor lookup, MCP
activation or synthetic process launch occurred. Packet review and current project
read/hash are new evidence; prior runtime and preservation results above remain
historical. Runtime suites/validators/compilation were not rerun.

| Operator-packet resume check | Actual result |
| --- | --- |
| Repository packet identity | `Get-Item` / `Get-FileHash -LiteralPath ... -Algorithm SHA256`: 6,365 bytes, digest in §2.5; preserved on recheck. No installed original accessed. |
| Reported digest / certificate syntax | Both supplied file digests are exactly 64 uppercase hexadecimal characters; signer thumbprint is exactly 40. This verifies transcription shape, not equality to installed bytes or certificate authenticity. |
| Before/after repository SHA-256 comparison | **PASS: 17/17 identical**: submitted packet plus project config, approved plan, six C2B source modules, five C2B test modules and R7/R8/R9 reports. Current config digest is §2.6's `6C26…BB32`, not the historical permission-edit digest. |
| `git diff --check` | **PASS, exit 0**, no whitespace diagnostics; LF→CRLF advisories only. |
| Report `git diff --no-index --check -- /dev/null docs/C1E_C2B_R10_OPENCODE_COMPATIBILITY.md` | No whitespace diagnostics; native exit **1** for nonempty untracked report versus empty, LF→CRLF advisory only; checking wrapper exits **0**. |
| Manual documentation reconciliation | Packet lines/values and §6.1 fields reviewed; historical unavailable facts distinguished from current operator evidence; disabled disk entries reconciled; §6.3 maps the minimum remaining static contract to all 14 investigation areas and §5 coverage. |
| Working-tree inventory versus entry | Same modified/untracked paths, including the already supplied packet and already untracked R10 report; only this report and `status.md` edited by the agent. No staging or new runtime artifact. |

**STOP after R10, including the operator-packet review; do not advance to R11.** The operator's
new configuration/permission change is explicitly disclosed in §2.4; the agent
made no such edit. No `mcp.bat`, `StudioMCP.exe` or installed OpenCode execution;
no real Roblox MCP call, frontend activation, agent configuration/permission change,
Luau/screenshot/Studio mutation/upload/save/publish, ComfyUI, human-approval or UTC
service operation, production evidence/ACL modification, dependency installation,
Git staging/commit/push or Swarm occurred. No permission broadening or live
execution approval is requested.

## 8. Pinned release-source continuation — current result

### 8.1 Acquisition and source attribution

**QUALIFIED fake-only compatibility. Gate A BLOCKED; D1–D6 PENDING.** The user
authorized public read-only retrieval of this exact official release and relevant
referenced MCP dependency source. Single agent; no Swarm or delegation. No denied
installed path was revisited, no installed executable run, and no retrieved vendor
source imported, installed, built or executed.

- Release: <https://github.com/anomalyco/opencode/releases/tag/v1.19.0>.
- Git ref API returned tag `v1.19.0` directly pointing to commit
  **`733b2c627e5aec39cb33cc22373bdce33053ef2c`**. The commit API message is
  `release: v1.19.0`; GitHub reports `verification.verified: false`, reason
  `unsigned`. This is HTTPS/API attribution, not a verified signed source release.
- Release API publication field: `2026-10-11T01:39:22Z`. Its `target_commitish`
  is parent `add9b4ba5adfb895934cb1bf46f590342cec68d2`; the actual resolved **tag
  ref**, not this release-creation field, is used as the source pin.
- OpenCode raw URL prefix (all source paths in manifests are exact commit URLs):
  `https://raw.githubusercontent.com/anomalyco/opencode/733b2c627e5aec39cb33cc22373bdce33053ef2c/`.
- SDK manifest/lock select **`@modelcontextprotocol/sdk@1.29.0`**. Its official
  `v1.29.0` Git ref resolves directly to
  **`e12cbd7078db388152f6e839abdbe09ba01f3f32`**. SDK prefix:
  `https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/e12cbd7078db388152f6e839abdbe09ba01f3f32/`.
- Repository `bun.lock:1061` selects
  `patches/@modelcontextprotocol%2Fsdk@1.29.0.patch`. The patch was retrieved at
  the OpenCode commit (URL encodes the literal percent as `%25`), reviewed as
  data, and included in the contract below. It patches published ESM/CJS JS and
  declarations, not the SDK tag's TypeScript files. Upstream SDK alone is not the
  complete release contract.

**Durable acquisition ledger:** `docs/evidence/r10-source/acquisition-01.json`
through `acquisition-04.json` record **38 successful unchanged response bodies**,
exact requested/final URLs, HTTP 200, byte lengths, SHA-256, ETag, method and
host-clock acquisition times. All downloaded source/metadata and both licenses
are retained beside those manifests. The helper uses standard-library HTTPS GET
and exclusive new-file writes; no package manager was invoked. Times are local
host observations, not authenticated UTC or external time-service measurements.
`SourcePacketTests` independently rereads/hashes all successful saved bodies.

The initial SDK ref candidate without `v` returned HTTP 404; that failure is
retained in batch 01 and the actual `v1.29.0` ref was acquired in batch 02. A tool
call attempting to create the local helper in the approved external temp area
was policy-denied; that path was not retried. The helper was created inside the
workspace. This did not access or retry any denied installed file.

Selected ledger entries (full paths/URLs and all other hashes are in manifests):

| Snapshot / source role | Bytes | SHA-256 of retrieved response body |
| --- | ---: | --- |
| `oc-mcp.ts` — `packages/opencode/src/mcp/index.ts` | 37745 | `82c459309dfd005d25daecfabc1007d807d4bee23f6078434974277938a1c026` |
| `oc-catalog.ts` — same package `src/mcp/catalog.ts` | 5834 | `1123ce304cd647e0945aa98743f411a69988f6dde63867aea78b74c72a5abe11` |
| `oc-lock.jsonc` — repository `bun.lock` | 875978 | `4e8ab76d77338a00de7cdf992f5c275d665902ae111d595074f3f143d4de0ac5` |
| `oc-sdk.patch` — selected repository SDK patch | 33172 | `a5524a398ff123038905ece3d7683fee949174b2fec169e97641348792ed0032` |
| `oc-config.ts` — `src/config/config.ts` | 27747 | `87a9071af1ddb04d65947dba49be3fb4c94ecf63e120f17ce46ee81ff25dd45a` |
| `oc-plugin.ts` — `src/plugin/index.ts` | 11339 | `47c62b7cfae891d268e6b239edb0f1c46df5cb35eb11ccfd8bd4186c156024e9` |
| `oc-tools.ts` — `src/session/tools.ts` | 23478 | `5ad3f44682fc8e2bacb2222157943de8ab7dd663a1e0ddf5e4a213539b1f67d7` |
| `sdk-client.ts` — SDK `src/client/index.ts` | 36290 | `3a0e484cd4521d77e022b781e82e9d6f11e64133ff104f17da9fa1b85658039a` |
| `sdk-protocol.ts` — SDK `src/shared/protocol.ts` | 68569 | `7b73185b8dc38563e6d494f08a3f340a09c9d60ff14ea4d784c3e3bf2432dc83` |
| `sdk-stdio.ts` — SDK `src/client/stdio.ts` | 7873 | `ca0ef8e9c3ff27dee9c77bc7371ffaafdbda63996a9b6c9f8639cf5f8ac5ed6a` |
| `sdk-framing.ts` — SDK `src/shared/stdio.ts` | 1040 | `37b67f01c554c94cd2de4726818f78a2a05f6030f56fe3afec53e2b8fdd119be` |
| `sdk-types.ts` — SDK `src/types.ts` | 90247 | `5a8ab1689ab69fa975c4dbb2aba7debda409872f1618383bc6a8f984625969aa` |
| `oc-publish.ts` — `packages/opencode/script/publish.ts` | 7916 | `a865f09f5d59e349dfacd3b96689caf9ceb29c0f019a2c4afbde85e6394fc5ce` |

### 8.2 Build/source correlation and resolved dependency qualification

Relevant source package is private workspace **`opencode@1.19.0`**, not the
generated npm wrapper. `oc-publish.ts:26–79` generates **`opencode-ai`**, version
from platform artifacts, `bin.opencode: ./bin/opencode.exe`, postinstall script,
platform optional dependencies and OS/CPU lists. These agree with the operator's
selected wrapper fields, without reconstructing or hashing its original bytes.
`oc-build.ts:101–113,145–201,223–238` includes Windows x64/baseline/arm64 targets,
names `opencode-windows-x64`, compiles with Bun and defines `OPENCODE_VERSION` from
the release script version. `oc-root-package.json:7` selects **Bun 1.3.14**,
consistent with the reported resource metadata. The installer was not executed;
its actual platform-selection/postinstall run and the installed hard-link history
remain UNKNOWN.

Resolved lock evidence (not just semver ranges):

- `oc-package.json:83` / `oc-lock.jsonc:598,1823`: MCP SDK **1.29.0**;
  lock integrity
  `sha512-zo37mZA9hJWpULgkRpowewez1y6ML5GsXJPY8FI0tBBCd77HEvza4jDqRKOXgHNn867PVGCyTdzqpz0izu5ZjQ==`;
  plus the repository patch at lock line 1061.
- `oc-lock.jsonc:3397`: transport dependency **cross-spawn 7.0.6**;
  `:1123,3045`: AI SDK **6.0.168**; `:5587`: top-level Zod **4.1.8**;
  `:5951`: SDK-scoped Zod **4.4.3**. SDK package exports/import conditions and
  source are retained. These are release lock resolutions, not an audit of the
  operator's embedded or loaded components. Transitive cross-spawn implementation,
  the full AI scheduler, and Zod/Ajv execution were not reproduced here.
- SDK source-tag version agrees with 1.29.0. Published npm tarball bytes were not
  fetched/rehash-checked against the lock's integrity, nor were compiled JS bytes
  regenerated. TypeScript + the explicit ESM/CJS patch support the static analysis;
  they do not prove byte-equivalence to the installed bundle.

**Executable mapping remains UNVERIFIED.** Nothing acquired binds operator SHA-256
`BB731F311416DF16691FA16763EB87657C4A5F5F3BCFF5202718C416E8F7AB1A` to a
signed build attestation or reproducible output of this commit. Release API gives
`opencode-windows-x64.zip`, 62,173,956 bytes, archive digest
`17108e9448c4fdad48eb8714c4ed6f5dfc9cf86c2eb8f2ce5d02043fef806eb5`;
that is an **archive** digest, not the installed executable digest. No archive or
executable was downloaded or run. Matching wrapper version, Bun metadata, package
names and publisher signature are correlation clues, not proof. §2.5's final-path,
stable-acquisition and offline-signature qualifications also remain explicit.

### 8.3 §6.3 expectation-to-source matrix — all 14 areas

Anchors below refer to the unchanged downloaded snapshots in §8.1, not working-tree
frontend line numbers. **Static release** means the selected local stdio, ordinary
non-task tool path, no modifying external hooks, fixed two-tool catalog and serial
calls under this fake driver. Installed binary and actual loaded session remain
UNKNOWN across this matrix. No unsupported fact is filled from R9's constants.

| Area | Source-derived expectation and anchors | R9 comparison / current qualification |
| --- | --- | --- |
| 1. Spawn / stdio | `oc-mcp.ts:340–369`: command array split into command/args; cwd is instance directory or resolved configured cwd; full `process.env`, optional `BUN_BE_BUN=1` only for literal command `opencode`, then configured environment; stderr pipe. `sdk-stdio.ts:112–162`: cross-spawn, stdin/stdout pipes, `shell:false`, `windowsHide:true`, cwd; default env merged before supplied env. | OpenCode's caller supplies full env, so the SDK's small default allowlist is not a full-environment restriction. R10 never uses this spawn for real. Windows cross-spawn quoting/PATH/helper details beyond this call are **UNKNOWN**. No creation-time Job Object assurance follows from ordinary client spawning; R6/R7 remains the synthetic child boundary. |
| 2. Framing / IDs / lifecycle | `sdk-framing.ts:9–25,33–38`: JSON.stringify + LF, UTF-8 buffering to LF, optional CR removed, JSON.parse/schema. `sdk-protocol.ts:322,1128–1143`: per-client numeric IDs start **0**, increment, no single-request mutex. | R9 accepts LF/CRLF and bounded nonnegative numeric IDs including 0; source does not establish R9's stricter size/duplicate/nonfinite policies as SDK limits. Fake emits the source key order/IDs independently; malformed/oversized input still refuses. SDK finite-frame/memory bounds are **UNKNOWN/not established** by this buffer implementation. |
| 3. Initialize / capabilities | `oc-mcp.ts:39–80`: `Client({name:"opencode",version:InstallationVersion}, capabilities:{roots:{}})` and roots handler. `sdk-types.ts:4–6`, `sdk-client.ts:483–534`, `oc-sdk.patch:414–494`: initial **2025-11-25**, supports replies 2025-11-25 / 2025-06-18 / 2025-03-26 / 2024-11-05 / 2024-10-07, validates reply and sends initialized. `oc-version.ts:6`; build defines version. | **Confirmed mismatch:** R9 accepted empty capabilities only. Added exact `opencode`/`1.19.0` roots profile. Initial protocol version was correct; no new negotiation/version acceptance needed for this profile. Reply still tools-only, no upstream launch or roots query. Actual build-defined version is **UNKNOWN**. |
| 4. Initialized notification | Same SDK connect/patch; `sdk-protocol.ts:1303–1308,1385–1410`: notification adds JSON-RPC envelope, no ID or params for initialized on this path. | R9's absent/empty initialized handling agrees. Fake sends absent params; initialization cannot inject launch/continuation. |
| 5. Catalog / schema / pagination | `oc-mcp.ts:391–405,457–473`: fetch tools only when advertised; notification-driven catalog refresh. `oc-catalog.ts:18–39,145–168`: first request params absent, follow nextCursor up to 1000 pages, repeated cursors fail; output-schema-validation-only fallback repeats catalog with tolerant schema. `sdk-client.ts:806–842`, patch `:498–520`: validator/task metadata cached across pages. `oc-catalog.ts:42–52`: force object/properties/additionalProperties:false for model schema. | Fixed R9 two-tool catalog has no nextCursor/outputSchema/listChanged. Ordinary first-page path works, no pagination correction needed. Cursor/task/dynamic catalog input still refuses. Fallback is catalog retry, not discovery/state authorization. Full provider-specific schema transformation is outside this fake profile. |
| 6. Names / aliases | `oc-catalog.ts:117–119`, `oc-mcp.ts:666–687`: model key = sanitized server + `_` + sanitized native tool name; non `[a-zA-Z0-9_-]` becomes `_`. `oc-catalog.ts:54–58` calls original native name. Map entries can collide/overwrite; no uniqueness guarantee is supplied. | Prefix is **model-facing**, not a wire prefix mismatch. Fake maps `roblox_studio_list_roblox_studios` back to `list_roblox_studios`. Frontend still refuses prefixed wire names and all other tools. Actual aliases/collisions in session are **UNKNOWN**. |
| 7. Arguments / metadata | `oc-catalog.ts:54–66`: `{name:native,arguments:args||{}}`; onprogress callback enabled. `sdk-protocol.ts:1128–1143`: adds `_meta:{progressToken:requestId}`. No task is requested on this path. | **Confirmed mismatch:** R9 rejected that extra params key. Release profile now requires exactly name/arguments/_meta and exactly one bounded integer token equal to numeric outer ID. Token is validated then stripped before existing policy. No generic `_meta`, extra args, task or authority input accepted. Legacy R9 profile remains unchanged. |
| 8. Response / errors | `sdk-types.ts:1444–1475`: content default [], optional structuredContent/isError; `sdk-client.ts:733–783`: outputSchema validation if advertised. `oc-catalog.ts:68–80`: isError throws joined nonblank text or default; empty content + structuredContent becomes text JSON. `sdk-protocol.ts:885–931,1189–1208`: correlated result schema or McpError rejection. `oc-tools.ts:420–486`: hooks/content extraction/truncation/model output. | R9 already returns the validated MCP content wrapper, not just decoded Studio payload; no wrapper fix needed. Fake checks selected text/structured/error conversion, not full Zod/Ajv or model behavior. Null-ID terminal/uncorrelatable refusals are connection failure, never accepted success for a pending tool. Actual model-visible hook/provider output **UNKNOWN**. |
| 9. Timeouts / cancellation | `oc-mcp.ts:38,227–243,359–369,661–682`: connect timeout configured or **30s**; failed acquisition closes transport. `oc-timeout.ts`: Promise.race is not a process deadline. Catalog timeout 30s default; tool timeout runtime override > configured > experimental fallback > SDK **60s** (`sdk-protocol.ts:106,1215–1218`). `oc-catalog.ts:61–65`: reset on progress, AbortSignal. SDK `:1165–1186,856–882`: cancellation notification `{requestId,reason:String(reason)}`, pending handlers removed; progress may reset timer, no supplied maxTotalTimeout. | Schema prose saying default 5s (`oc-mcp-schema.ts:20–22`) is not executable default evidence. R9 absolute watchdog/review expiry do not reset on client progress. Cancellation stays terminal and stops local contained work; it cannot prove real Studio cancellation. Synthetic windows are bounded test values, not installed deadlines. |
| 10. Retry / reconnect | `oc-mcp.ts:442–455`: local close marks failed/removes cached client/defs; no automatic local restart in this handler. `:648–659` explicit connect/disconnect recreates/closes. SDK patch `:523–647` adds **HTTP** expired-session recovery/reinitialize and one resend with active-request guard; catalog fallback noted above. | No source basis for claiming all transports never retry. Selected local stdio profile has no observed automatic tool resend path; model/hook retries and actual session controls **UNKNOWN**. Frontend stays terminal/new-only; reconnect/retry cannot replenish authority. HTTP is outside qualification. |
| 11. Scheduling / concurrency | SDK maintains independent response/progress maps and sends requests without per-server serialization (`sdk-protocol.ts:322–333,1098–1256`); OpenCode connects different servers unbounded (`oc-mcp.ts:497–528`) and list-change handlers can fetch asynchronously. `oc-tools.ts:398–409` adds no single-server mutex. | Client supports concurrency; R9 intentionally aborts a second in-flight frame instead of queueing. This remains a qualified **restricted-profile incompatibility**, not relaxed for convenience. No periodic ping loop found in selected MCP path; SDK exposes ping. Provider/model scheduling is **UNKNOWN**, not certified serial. Concurrent catalog/cancel tests prove refusal/no queued next tool. |
| 12. Size / transformations | SDK stdio buffer has no explicit byte cap in reviewed source. `oc-tools.ts:426–481`: text/content/attachments and model-facing output differ; `oc-truncate.ts:14–15,75–95,124–140`: defaults **2000 lines / 50 KiB**, configurable, saves full decoded text and returns preview/hint. | Display truncation is not original wire retention or evidence. R9 client 4096-byte frame / 64 frames / 262144 combined traffic and child original-byte limits remain unchanged. No SDK end-to-end bounded-memory or wire-limit equivalence claim; output larger than frontend limits intentionally fails. |
| 13. Config / precedence | `oc-config.ts:40–51,260–303,328–548,559–578`: deep merge in load order; global config.json → opencode.json → jsonc; remote wellknown first, then global/custom/project/directory/inline/active-org/managed layers; permission env override and legacy tools conversion. `oc-paths.ts`, `oc-variable.ts`, `oc-managed.ts`, `oc-global.ts`, `oc-flag.ts`; details §8.4. `oc-permission.ts:28–37` uses last matching rule with default ask. | Static loader semantics do not identify this session's sources/order/rules. Current project disk digest unchanged, both MCP entries false. Agent/session-approved rules, actual path normalization and effective ask/deny origin remain **UNKNOWN**. No global/managed/credential read or config command executed. |
| 14. Plugins / hooks | `oc-plugin.ts:66–85,170–253,284–297`: built-ins first unless disabled, then configured origins unless pure; external hook registration sequential; config hooks receive cfg; trigger loops in registration order. `oc-plugin-config.ts:18–29,42–76`: auto-discovery, path normalization, last identity wins. `oc-hooks.ts:225,266–281,332–334` defines config/tool hooks; `oc-tools.ts:402–424` invokes before/after around MCP call. | npm swarm inventory and absent project plugin field do not prove no hooks. Before may mutate args, after may mutate result; config hooks may affect shared cfg. Hook definitions alone do not prove every definition hook applies to MCP. Loaded set/entrypoint digests/order/effects remain **UNKNOWN**. Fake profile explicitly excludes modifying hooks and code mode; no plugin loaded. |

### 8.4 Static configuration versus this session

Release loader order is source evidence, not an effective-settings dump:

1. Auth-selected wellknown/remote config; then global `config.json`,
   `opencode.json`, `opencode.jsonc` (global loader cached indefinitely until
   invalidation); then custom `OPENCODE_CONFIG`.
2. Project ancestry files via `ConfigPaths.files(...).toReversed()` unless
   `OPENCODE_DISABLE_PROJECT_CONFIG`; config directories include global,
   discovered `.opencode`, home `.opencode`, then `OPENCODE_CONFIG_DIR`.
   Relevant directory JSON/JSONC, agent/command and auto-discovered plugin data merge.
   Exact FS helper enumeration/tie order is not independently reproduced here.
3. `OPENCODE_CONFIG_CONTENT`; active organization config; managed directory
   `opencode.json`/`jsonc` (Windows `%ProgramData%\opencode`, test override
   `OPENCODE_TEST_MANAGED_CONFIG_DIR`); macOS managed preferences only on macOS.
4. `OPENCODE_PERMISSION` is applied after those loads; legacy tools permissions
   are merged below explicitly selected permission values. Rules use last-match
   semantics in the reviewed evaluator; actual session/agent rules remain unknown.

`{env:NAME}` and `{file:path}` substitution occurs while loading text; percent
syntax in a configured `cmd.exe` argument is not expanded by this substitution
function. The configured shell/transport owns any later shell expansion. No real
command/launcher expansion or resolution was exercised. Source loading can also
write schema/default/dependency files or initiate background installs; no config
loader/debug command or plugin was run to derive effective state.

The project disk file remains SHA-256
`6C2656F8245444E0B169F1501E7312716615F409D90CC9AB04A76BC9E6E7BB32`,
with Roblox and ComfyUI entries disabled. Active global/custom/inline/org/managed
sources, environment/CLI flags, default-plugin runtime flags, agent permissions,
plugin identities and any in-memory routes remain **UNKNOWN**. No full environment,
argv, config, credential or provider dump was collected. Standalone qualification
does not require stale-session retirement proof; any later actual-session or live
deployment claim still does.

### 8.5 Confirmed corrections and fake-only coverage

Only `tool/c2b_restricted_frontend.py` runtime logic changed:

- Added a distinct front-facing `CLIENT_PROTOCOL` literal sourced from SDK types;
  the recorder/fake-child protocol was not changed. Initial version is unchanged.
- Added exact initialization profile `clientInfo:{name:"opencode",version:"1.19.0"}`
  with `capabilities:{roots:{}}`; existing R9 empty-capability tests stay supported.
- For that release profile only, require exact call metadata with one nonnegative
  integer `progressToken == requestId < 2**53`. Remove this inert metadata before
  the existing exact name/arguments/one-shot policy. No progress notification is
  necessary or emitted. Roots capability does not trigger any roots/Studio request.

No authorization, launch token, continuation, checkpoint, per-write verification,
single-outstanding rule, containment, raw-before-parse recording, timeout/review
budget, evidence verification or uncertainty assertion was relaxed. No aliases,
negotiation, queue, retry, generic metadata/control forwarding or new tool was added.
Existing R9 client/test files and recorder/containment/review source are unchanged.

New `tests/fixtures/c2b_r10_release_client.py` is an independently specified **Python
fake**, with source anchors and literal protocol/client/target values, numeric IDs
from zero, JavaScript-shaped envelopes, native-name reverse mapping and progress
metadata. It imports no frontend/recorder constants. Its text-result checker is a
declared subset of SDK/OpenCode conversion; it is not the JS SDK/Zod/Ajv or a
provider/plugin emulator. No downloaded source is executed.

`tests/test_c2b_r10_compatibility.py` adds **16 tests**: inert release lifecycle/
catalog/ping, source serializer/IDs, bounded exact metadata and authority rejection,
strict supported profile, aliases/schemas, selected result/error conversion,
actual contained discovery → verified WAIT_REVIEW → separate TEST-ONLY continuation
→ state, real frontend stream loop, missing continuation/wrong target/retry,
checkpoint tamper during intent with **zero state bytes**, cancellation/concurrent
catalog terminal refusal, and source body/hash/tag attribution checks. R9's existing
malformed/oversized/disconnect/reconnect/death/raw-before-parse/cleanup tests ran
unchanged alongside them. This provides positive serial-profile evidence and
intentional rejection evidence, not universal release-client compatibility.

### 8.6 New executed verification — not historical R9 totals

| Command / check | New result |
| --- | --- |
| `python -m unittest tests.test_c2b_r10_compatibility -v` | **16 passed, 0 skipped, 0.906s**; all contained Windows cases ran. |
| `python -m unittest tests.test_c2b_r10_compatibility tests.test_c2b_restricted_frontend tests.test_c2b_native_recorder tests.test_c2b_windows_containment tests.test_c2b_recording_supervisor tests.test_c2b_evidence` | **210 passed, 0 skipped, 25.635s** = 16 R10 + 194 existing boundary tests. |
| `python -m unittest discover -s tests -p "test_*.py"` | **415 run, 414 passed, 1 existing symlink skip, 37.381s**. Native Windows tests ran. Existing skip remains `test_asset_registry.RegistryTests.test_symlink_escape`. |
| `python tool/validate_art.py` | **PASS:** 2 metaschemas, 5 presets, 3 positive / 36 negative request fixtures; no files written. |
| `python tool/registry.py validate` | **PASS:** 0 unique assets, 0 events. |
| `python -m compileall -q tool tests docs/evidence/r10-source/acquire.py` | **PASS**, no diagnostics; output parents verified before command. No vendor TS source compiled or executed. |
| `python -m unittest tests.test_c2b_r10_compatibility.SourcePacketTests -v` after final publication-script retrieval | **2 passed, 0.013s**; all **38** successful saved response bodies rehashed. This targeted recheck includes batch 04 added after the full suite; no runtime code changed afterward. |
| Tracked `git diff --check` and six authored untracked no-index checks | **PASS**, no whitespace diagnostics; no-index statuses 1 denote differences from empty, checking wrapper 0; LF→CRLF advisories only. Covers frontend, new fixture/test, R10 report and source-packet README/helper. Downloaded response bodies are preserved byte-exact rather than normalized. |
| Preserved repository digest comparison | **16/16 match prior recorded digests**: project config, approved plan, operator packet, five unchanged recorder/containment/evidence/review source modules, five existing tests and R7/R8/R9 reports. R9 frontend is the sole changed runtime source. |
| Working-tree/diff review | Existing dirty/untracked work retained, including pre-existing config/R4 handoff edits. Added only source packet/local helper, release fake fixture and R10 tests; modified frontend, this report/status and additive implementation handoff. No staging or production evidence. |

Red/green development evidence: the first two-test probe against the unchanged R9
frontend rejected release initialize (one failure); the second case errored on a
subsequent null-ID terminal refusal. After adding the exact roots profile,
initialize passed and the metadata probe failed with `exact_tool_arguments_required`
instead of reaching the unchanged authorization refusal. Exact metadata adaptation
resolved that second mismatch. The final 16/210/415 runs include both corrections;
there was no relaxation of authority to turn the probes green. Post-terminal
null-ID failures are explicitly classified as failed delivery, not source-client
success. Final provenance, whitespace and preservation results are in the table
above. Tested current-source digests:

- Frontend: `ED7B5C2BCE21411CF5F4965CF9480C84494BB6FC9F78CF44D3C16F87FC92DDD4`.
- Release fake: `EECB6D512F0697941E616A68635C73B68308C38E24B916C4F2FF848F4B3880F2`.
- R10 tests: `1BC51D63768443907F9DC8997D39820FCE08CA0C4788C5F2E04A638B5BDFD411`.

### 8.7 Classification, remaining gates and next practical step

**QUALIFIED** applies only to the source-attributed serial stdio/text-result Python
fake profile tested here. It is neither installed-build VERIFIED nor BLOCKED merely
for lack of stale-session/live-deployment evidence. It excludes concurrent traffic,
HTTP/SSE recovery, task tools, arbitrary capabilities, provider/schema transformations,
modifying plugin hooks and full JS SDK/parser/spawn equivalence. Those limitations
are explicit; client concurrency/size-limit refusal remains intentional.

Smallest practical next implementation step: use this pinned expectation map for
the next narrow **offline** independent approval/withdrawal, authenticated-time
verifier interface and protected replay/evidence/checkpoint contract. Keep external
authority/time sources injected fakes until D1–D6 decisions and deployment evidence
exist. Do not promote current TEST-ONLY tokens to real approval. In parallel evidence
work, an already available build attestation/artifact-to-executable mapping and
credential-free actual loaded config/hook profile would narrow installed correlation;
another version slogan or generic website would not. No next milestone is started.

Gate A blockers remain: executable/build and actual effective client/launcher
correlation; exact real contained launch/delegation; independent authenticated
launch/review/withdrawal and protected one-shot replay; two-source trusted UTC/
expiry checks; private bounded NTFS storage, quotas/retention/recovery; sole-route
deployment and stale-session retirement; approved D1–D6 dispositions and complete
later readiness review. Gate B remains separately blocked. No production approval,
time, ACL or evidence deployment was attempted.

**STOP after R10. Gate A BLOCKED / NOT TECHNICALLY READY; D1–D6 PENDING.** No
installed OpenCode/Roblox executable or real launcher, Studio MCP/Luau/screenshot/
mutation/upload/save/publish, MCP registration activation, ComfyUI, authority
issuance, external time-service query, security permission/config edit, dependency
installation, Git staging/commit/push, Swarm or R11 advancement occurred.
