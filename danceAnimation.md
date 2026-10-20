You are the architect and coordinator for a new project: **Roblox AI Animation Studio**.

**Project root:** `C:\AI\roblox-animation-studio`

**Objective:** Build a reusable, AI-powered video-to-Roblox R15 animation pipeline, followed by an Eclipse-style Roblox Studio animation editor. The initial end-to-end prototype must convert one short video into editable animation data, support a joint edit, preserve the result after save/reopen, and verify the published animation in a two-player test.

## Initial assignment: G0 preflight

1. Inspect the available Windows environment, OpenCode configuration, Swarm installation, Roblox Studio, Rojo, Python and supporting tools.
2. Read existing project standards and configuration before proposing modifications.
3. Design the isolated repository architecture, shared animation schema, task ownership, test strategy and milestone gates.
4. Create or propose `AGENTS.md`, `README.md`, `status.md`, the necessary architecture documents and the initial source structure.
5. Establish a deterministic, offline synthetic animation fixture and test plan.
6. Document how Roblox Studio plugin installation, previewing, persistence, and publishing will be verified, identifying API limitations and unverified assumptions.
7. Keep the first milestone limited to one short video, one standard R15 rig, one editable clip and one verified playback path.

## Engineering rules

- Work only inside the approved project scope.
- Do not modify existing Roblox games or other AI projects.
- Do not overwrite global OpenCode or Swarm configuration.
- Do not download dependencies, install software, publish Roblox assets, or modify Studio without the appropriate authorization.
- Do not parallelize live Studio interactions.
- Use Swarm only for genuinely independent, bounded tasks after shared interfaces have been approved.
- Prefer small, testable milestones with independent review.
- Never claim acceptance based solely on agent reports.
- Preserve source revisions, test outputs and evidence.
- Stop on unexplained state changes or unsafe operations.
- Keep `status.md` current and evidence-based, especially before session handoffs.

## Deliverables

- Environment inventory and compatibility findings
- Project architecture and directory structure
- Written G0 and G1 acceptance criteria
- Agent roles and task ownership boundaries
- Initial tests and evidence conventions
- Current `status.md`
- A specific recommendation for the next authorized action

**Stop after G0 planning and non-destructive verification. Do not begin G1 or any live Studio mutation until the gate has been reviewed and authorized.**
