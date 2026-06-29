# Context-management playbook — stop forgetting standing rules as context fills

The failure this prevents: across long sessions and after a compaction, the
orchestrator forgets a hard-won standing rule and acts against it — the concrete
case was a session that re-ran an expensive evaluation baseline that an existing
rule said never needed re-running, because that rule was not in context at the
moment of the action.

The root cause has one sentence: **a prompted "never" rule is not a guardrail.**
The model follows it most of the time, but fails exactly when the rule is not in
context — which is precisely after a compaction or deep into a long session. The
fix is three independent layers, because no single one is sufficient.

---

## The three layers of defence

**1. Survive the compaction (so the rule is still in context).** Claude Code
re-injects a fixed set of things from disk after it compacts; everything else is
summarised away and lost until a matching file is read again:

| Survives a compaction (re-injected from disk) | Lost until re-read |
|---|---|
| Project-root `CLAUDE.md` text + unscoped rules | Linked docs (`EVAL_PROTOCOL.md`, the ledger) |
| The auto-memory `MEMORY.md` **index** | Individual on-demand auto-memory entry files |
| (nothing else is guaranteed) | Rules with `paths:` frontmatter; nested `CLAUDE.md`; anything said only in conversation |

**Rule of thumb: if a rule must ALWAYS hold, its text lives in the body of root
`CLAUDE.md`, not only in a linked document.** A pointer to `EVAL_PROTOCOL.md`
survives, but the rule inside it does not — so the one-line rule itself is also in
`CLAUDE.md`.

**2. Fire at the moment of action (regardless of what is in context).** Where a
rule is a genuine hard "never", encode it as a `PreToolUse` hook that inspects the
tool call. A hook fires deterministically whether or not the governing rule is in
context. Two strengths:
- **Advisory** — print a reminder to stderr and exit 0. Right when the action is
  *sometimes* legitimate (re-running an OFF evaluation arm is valid for a true
  re-anchor, so a hard block would be wrong). This is what `eval_guard.py` does.
- **Blocking** — exit code 2 (or `permissionDecision: "deny"`). Right for an
  absolute never (`git_guard.py` blocks a push whose catalogue import is broken).
  Note: exit-2 blocking is reliable for the Bash tool but documented as flaky for
  Edit/Write and some tool paths — test it against the real invocation.

**3. Live on disk, not in the transcript.** State the orchestrator must not lose
goes into durable files it re-reads, plus git, so a fresh context reconstructs the
project without the lossy compaction summary: `CURRENT_STATE.md` (the live frame),
`DECISION_LEDGER.md` (what is landed / reverted / forbidden), the per-session
handover, and a commit after every wave. Write these *as the wave closes*, not only
at session end.

---

## What is wired up here (and how each layer is realised)

- **`eval_guard.py`** (`PreToolUse`, Bash + PowerShell) — prints the eval protocol
  headline whenever an `evaluate_vs_meta` / `paired_delta` command launches.
  Advisory, fail-open. This is layer 2 for the most-missed rule.
- **Root `CLAUDE.md`** — carries the OFF-anchor rule *text* (not just a link to
  `EVAL_PROTOCOL.md`) so it survives a compaction. This is layer 1.
- **`prompt_state.py`** (`UserPromptSubmit`) — re-injects a one-line guardrail
  (the OFF-anchor rule + "grep the ledger before re-running anything expensive")
  every prompt, placed last for recency. Reinforces layer 1 between compactions.
- **`session_state.py`** (`SessionStart`) — prints the `CURRENT_STATE.md` head on
  resume. Layer 3 re-entry.
- **`precompact_snapshot.py`** (`PreCompact`) — copies the transcript to
  `.claude/transcripts/` as a forensic audit trail. Note: `PreCompact` cannot
  inject context (no `additionalContext` support), so it does **not** carry facts
  into the post-compaction window — the survival burden is on layers 1 and 3, by
  design.
- **Sub-agent dispatch** — sub-agents start with a fresh isolated context and load
  `CLAUDE.md` / auto-memory, but never see the parent conversation; so every
  session-derived constraint (file scope, "do not re-run the OFF arm", no-push) is
  restated in each briefing. Offloading bulk reading and log-parsing to sub-agents
  keeps the orchestrator's context lean across many sequential waves.

---

## Ranked playbook (highest leverage first)

1. **Deterministic `PreToolUse` guard for each hard rule** — the only enforcement
   independent of context. (Done for the eval; advisory is correct for it.)
2. **Put always-true rules' text in root `CLAUDE.md`** (or drop a rule's `paths:`
   frontmatter) so they survive a compaction. (Done for the OFF-anchor rule.)
3. **Re-inject the small standing-rule set every turn** via `UserPromptSubmit` /
   `SessionStart` stdout and `PreToolUse` `additionalContext`. (Done — one line.)
4. **Restate session-derived constraints in every sub-agent briefing**, and keep
   offloading bulk work to sub-agents.
5. **Commit + append to the ledger/handover after every wave** so a fresh context
   recovers from disk, not from a summary.
6. **Write to durable memory as you go**, never only at session end.
7. **Treat a compaction as expected loss** — do not rely on its summary for
   anything critical.
8. **Retrieve before acting** — grep the ledger / current-state for the governing
   rule before a costly action, as defence-in-depth with layer 2.

---

## Open items (your judgement)

- **`CLAUDE.md` is ~330 lines, over Anthropic's ~200-line guidance.** A large
  standing-rules file dilutes adherence to all of it. The fix is to keep it lean
  and route hard rules to hooks — but trimming hard-won rules is an owner call, so
  it is flagged, not done. Candidate approach: keep the rule *statements* in
  `CLAUDE.md`, move the *rationale / examples* into the linked docs.
- **Does `UserPromptSubmit` fire on each programmatically-dispatched wave** in the
  fully autonomous loop? It fires per submitted prompt, not per internal tool turn.
  If a wave runs many tool turns without a new prompt, the per-prompt guardrail
  re-injects at wave dispatch but not before every tool call — which is exactly why
  the `PreToolUse` guard (layer 2) is the load-bearing one.

## Sources

Anthropic primary: "effective context engineering for AI agents", "effective
harnesses for long-running agents", the Claude Code context-window / memory /
sub-agents / hooks documentation, and the "steering Claude Code" blog; corroborated
by Chroma's context-rot study and practitioner write-ups. Researched 2026-06-27;
re-verify the survival table and hook behaviour against the current release before
relying on exact thresholds.
