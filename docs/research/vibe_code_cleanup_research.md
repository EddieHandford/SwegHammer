## Vibe Code Cleanup: Research Report

### 1. The Term and the Problem

Andrej Karpathy coined "vibe coding" in a post on 2025-02-06, describing a mode of software development where the programmer "fully gives in to the vibes" — describing intent in natural language prompts, accepting AI-generated output without close review, and iterating on feel rather than reading the code ([Wikipedia](https://en.wikipedia.org/wiki/Vibe_coding)). The phrase spread immediately; by mid-2025, "vibe code cleanup" had become a distinct job description, with freelancers billing $100–$300 per hour to turn AI-generated prototypes into production-ready systems ([Metana](https://metana.io/blog/what-is-vibe-coding-cleanup/)).

What actually accumulates in a vibe-coded codebase:

- **Structural debt**: duplicated logic, oversized files (GitClear found duplicated code blocks grew 4–8x across 211 million lines of code analysed in 2024–25), inconsistent naming and abstraction layers, and architectural drift where each AI session adds its own pattern ([Undoing AI slop with AI](https://ericmjl.github.io/blog/2026/3/29/undoing-ai-vibe-coded-slop-with-ai/)).
- **Dead and unreachable code**: functions added for one experiment and never removed; feature gates left in after the experiment concluded.
- **Security gaps**: Veracode's 2025 analysis found nearly half of AI-generated code contained security flaws — exposed credentials, missing authentication, injection vulnerabilities ([Metana](https://metana.io/blog/what-is-vibe-coding-cleanup/)).
- **Missing tests**: AI-generated code almost never includes meaningful assertions; edge cases go dark.
- **Hallucinated or inflated dependencies**: packages added during generation that are never actually called.
- **Over-broad error handling**: bare `except Exception: pass` patterns that swallow failures silently — precisely the anti-pattern SwegHammer's own standing rule 13 prohibits.
- **Stale experiment gates**: feature flags left in the codebase past their experiment window become permanent technical debt ([Feature Flags Rot Your Codebase](https://stack-notes.com/blog/feature-flags-lifecycle-friday-deploys-technical-debt)).

---

### 2. Tooling Landscape (Python-focused)

**Dead-code detection**
- **vulture** (mature): scans for unused functions, classes, variables, and imports using static analysis. Assigns confidence 60–100%. For continuous integration use, `--min-confidence 100` filters to only genuinely unreachable code; lower thresholds are audit-only due to false positives from Python's dynamic nature. Supports whitelists (`--make-whitelist`) and `noqa` comments for exemptions ([vulture GitHub](https://github.com/jendrikseipp/vulture)).
- **deadcode** (newer): AST-based, claims to implement more detection rules than vulture, better for broad audits ([EuroPython 2024 session](https://ep2024.europython.eu/session/deadcode-a-tool-to-find-and-fix-unused-dead-python-code/)).
- Note: ruff intentionally does not detect globally dead code (only locally unused imports/variables per F401/F841) — it complements vulture rather than replacing it ([ruff issue #872](https://github.com/astral-sh/ruff/issues/872)).

**Unused-dependency checkers**
- **deptry**: scans `pyproject.toml`/`requirements.txt` against actual imports; detects unused, missing, and transitive-only dependencies. Suitable for CI.

**Duplication detection**
- **jscpd**: cross-language copy-paste detector with configurable minimum-token thresholds. Audit-only in practice; too noisy for blocking CI.
- **pylint** (duplicate-code checker): produces similarity reports but generates significant noise on large files.

**Lint, format, complexity**
- **ruff**: fast all-in-one Python linter and formatter; CI-grade from day one. Covers import hygiene, naming, complexity-adjacent rules, and autofix for many categories.
- **radon**: computes cyclomatic complexity and maintainability index per function; flag threshold CC &gt; 10 as audit candidates.
- **SonarQube**: full code-health platform including duplication, complexity, and security; heavier to set up but integrates with pull-request gates.

**Security**
- **bandit**: zero-configuration Python security scanner (~80 built-in tests); 40% lighter compute than integrated suites; CI-grade for known patterns but misses novel AI-generated anti-patterns ([bandit 2025](https://johal.in/application-security-testing-python-bandit-for-static-code-analysis-2025/)).
- **semgrep**: programmable, multi-language; 20,000+ rules; cross-file taint tracking; now ships an MCP server that scans files as an agent generates them. Better than bandit for AI-code patterns but heavier to configure ([Semgrep vs Bandit 2026](https://dev.to/rahulxsingh/semgrep-vs-bandit-python-security-scanning-compared-2026-5e5j)).

**AI-assisted refactoring**
- Practitioners in 2025–26 report using Claude Code / Cursor with an explicit architectural brief to drive the cleanup — the key lesson being that "AI can execute architecture, but it can't design it" ([ericmjl.github.io](https://ericmjl.github.io/blog/2026/3/29/undoing-ai-vibe-coded-slop-with-ai/)). Human judgment sets structure; the AI refactors to it.

---

### 3. Workflows That Work

**Characterisation tests before any refactor.** A characterisation (golden-master) test captures the existing behaviour of an untested piece of code and protects it from unintended change during refactoring. The recommended sequence: generate characterisation tests first (AI can help here), verify they pass on the current codebase, then refactor, keeping the tests green throughout ([Wikipedia: Characterization test](https://en.wikipedia.org/wiki/Characterization_test); [Medium: Golden Master Testing](https://chicio.medium.com/golden-master-testing-aka-characterization-test-a-powerful-tool-to-win-your-fight-against-legacy-1ca590f219a1)). For deterministic simulators like SwegHammer, a fixed-seed byte-comparison of game logs is the exact equivalent — it is already mandated by the project's standing rules for pure code-motion pull requests.

**Mechanical changes in separate pull requests from judgment changes.** Mixing a rename codemod with a logic change makes a pull request unreviable. Best practice: one pull request per type of change — formatter/codemod first (no logic delta), then logic changes on top ([Boy Scout Rule analysis](https://www.codewithjason.com/boy-scout-rule-insufficient/)). This maps exactly to SwegHammer's rule 14 (one self-contained change, 400-line soft cap).

**Boy Scout Rule for incremental improvement, cleanup sprints for concentrated debt.** Continuous improvement embedded in feature work avoids the "pause everything" cost of a dedicated sprint and prevents debt from compounding ([Boy Scout Rule](https://lawsofsoftwareengineering.com/laws/boy-scout-rule/)). However, for concentrated debt — like a gate-retirement pass — a focused sprint with behaviour-identity proofs is preferable to dribbling the work across unrelated waves.

**Feature gate retirement discipline.** The recommended lifecycle: (1) force the gate to always-on in production; (2) monitor for 24–48 hours; (3) if stable, delete both the gate check and the legacy code path in a single pull request; (4) confirm no remaining references ([Feature Flag Lifecycle](https://stack-notes.com/blog/feature-flags-lifecycle-friday-deploys-technical-debt)). Teams that skip step 1 (jump straight from conditional to deletion) introduce unnecessary risk. Quarterly "flag retirement parties" are cited as a sustainable cadence ([Octopus Deploy](https://octopus.com/devops/feature-flags/feature-flag-best-practices/)).

**Small, reviewable pull requests.** The research base that informed SwegHammer's own rule 14 (SmartBear/Cisco study; Google engineering practices) is the same literature practitioners cite in cleanup guides: defect-detection drops sharply past ~400 lines, and reviewers approving a 1,000-line diff are approving on trust, not review ([Google Engineering Practices](https://google.github.io/eng-practices/review/developer/small-cls.html)).

---

### 4. Applied to SwegHammer: Inventory and Recommendations

**Gate inventory.** The repo has **83 distinct `SWEG_*` environment gates** across `code/`. Of those, only 14 have an explicit default value baked into the `os.environ.get()` call:

- **Default-on (default "1"):** `SWEG_BOF_ASSAULT`, `SWEG_CHARGE_BASEEDGE`, `SWEG_CHARGE_PATH`, `SWEG_CSM_LEADERS`, `SWEG_DURCACHE`, `SWEG_FILL_SQUADS`, `SWEG_LOSCACHE`, `SWEG_OFFICER_FOLLOW`, `SWEG_PERMODEL`, `SWEG_SEED_LEADERS`, `SWEG_SITW_TEST`, `SWEG_TANKSHOCK_DICE`, `SWEG_TAU_CMD`
- **Explicit default-off (default "0"):** `SWEG_WARP_RIFTS`
- **Implicit false (no default string):** all remaining ~69 gates, including `SWEG_ROLLDMG`, `SWEG_SEEDMAX`, `SWEG_DISPLACE_FALLBACK`, `SWEG_DISPLACE_SWARM`, `SWEG_COLLISION`, `SWEG_PATHFIND`, `SWEG_RUINWALLS`, `SWEG_OCCGRID`, and many others — these evaluate falsy unless explicitly set in the environment.

Cross-referencing with auto-memory: `SWEG_DISPLACE_FALLBACK` is adopted default-on per project memory but has no "1" default in code (it is checked via `!= "0"` pattern). `SWEG_DISPLACE_SWARM` is parked/default-off. `SWEG_PATHFIND` and `SWEG_PATHFIND_STAGE0` are Stage 1 gated infrastructure (inert). Gates like `SWEG_ROLLDMG` are adopted (approved wave 93+) but carry no explicit code default.

**Eval artifact count.** `data/wf_*.txt`: 20 files, `data/wf_*.json`: 19 files, `data/wf_*.err`: 20 files. These are untracked (`.gitignore` excludes them from the repo). The `docs/` directory additionally holds ~100 `wf_wave*.log` files from earlier waves.

**Scripts inventory.** `scripts/` contains ~95 files. Notable categories: ~50 `diag_*.py` one-shot diagnostic scripts tied to specific waves (many now historical); ~15 `iter*.py` iteration-specific diagnostics; `loop_cleanup.py` (exists — the intended cleanup entry point); several `auto_loop_iter*.py` orchestration scripts that are superseded by the current loop procedure.

---

### Prioritised Cleanup Checklist for SwegHammer

1. **Gate-retirement pass — adopted levers with no code default (effort: medium).** Gates confirmed adopted in memory but lacking an explicit `"1"` default in code (`SWEG_DISPLACE_FALLBACK`, `SWEG_ROLLDMG`, and others) should have their defaults hardened. Rejected/parked gates (`SWEG_DISPLACE_SWARM`, `SWEG_WARP_RIFTS`, and any wave-experiment-only gates) should be deleted with the old code path. Each deletion = one small pull request with a fixed-seed game-log byte-comparison before and after (the project's existing behaviour-identity standard). Batch into groups of 3–5 gates per pull request to stay under the 400-line cap.

2. **vulture audit at `--min-confidence 80` — one-off sweep (effort: low).** Run `vulture code/ --min-confidence 80 --make-whitelist` and review the output. Expected signal: dead helper functions added during experiments and never called after the gate was removed. Do not hook into CI yet (too many dynamic dispatch patterns) — treat as an audit pass, then delete confirmed dead functions one small pull request at a time.

3. **Diag-script archive pass (effort: low).** Move `scripts/iter*.py`, `scripts/diag_*.py` tied to waves before wave 100, and superseded `scripts/auto_loop_iter*.py` into a `scripts/archive/` directory. These are historical artefacts; they add grep noise and inflate `vulture`'s false-positive rate. One pull request, pure code-motion, zero logic change — no behaviour-identity proof required beyond confirming `python run.py --cli` still exits cleanly.

4. **docs/wf_wave*.log archival policy (effort: low).** The ~100 `docs/wf_wave*.log` files pre-date the `data/` convention. Move them to `data/archive/` or delete (they are superseded by the corresponding `data/wf_*.txt` evals). Codify in `AUTO_LOOP_PROCEDURE.md`: eval logs older than the last 20 waves live in `data/archive/`, not `docs/`.
   **DONE 2026-06-12** — commit `e1ff37b`, pull request TBD (`claude/cleanup-evallog-archive` off `main`). One tracked file moved (`docs/wf_wave44_tson_n40.log` → `data/archive/`; the original ~100 files were already untracked and had not accumulated in the repo); `data/archive/README.md` created; `docs/AUTO_LOOP_PROCEDURE.md` prevention bullet expanded with named file patterns and `git mv` requirement; demonstration battle clean (exit 0).

5. **deptry dependency audit (effort: low).** Run `deptry .` against `requirements.txt` to surface any packages imported by removed experiment code but still listed as dependencies. Low risk; one-line removals from the requirements file.

6. **ruff baseline + pre-commit hook (effort: low).** `ruff check code/ --fix` for auto-fixable issues (unused imports F401, undefined names F821, complexity). Add as a pre-commit hook so new waves stay clean. The citation-audit hook already runs on rule-bearing commits; ruff would run on all commits.

7. **`SWEG_ROLLDMG` explicit default + doc sweep (effort: low).** This gate is approved (wave 93+) but reads `bool(os.environ.get("SWEG_ROLLDMG"))` — implicit false unless set. Hardening it to `os.environ.get("SWEG_ROLLDMG", "1") != "0"` makes the adoption permanent in code. Update `SIMULATION.md` to reflect that rolling damage is the production default.

8. **Complexity audit of `code/simulator.py` with radon (effort: medium, long-term).** At 10k+ lines this file is the dominant maintenance risk. Run `radon cc code/simulator.py -n B` to identify functions with cyclomatic complexity above 10. Document the top-10 offenders in `docs/STRUCTURAL_DEBT_REVIEW.md` (which already exists). Do not refactor now — extract only when a wave naturally touches the function, keeping the boy-scout rule rather than a disruptive sprint.

---

### Sources

- [Vibe coding — Wikipedia](https://en.wikipedia.org/wiki/Vibe_coding)
- [Semantic history of vibe coding — CodeRabbit](https://www.coderabbit.ai/blog/a-semantic-history-how-the-term-vibe-coding-went-from-a-tweet-to-prod)
- [What is vibe coding cleanup? — Metana](https://metana.io/blog/what-is-vibe-coding-cleanup/)
- [Undoing AI vibe-coded slop with AI — Eric Ma](https://ericmjl.github.io/blog/2026/3/29/undoing-ai-vibe-coded-slop-with-ai/)
- [vulture — GitHub](https://github.com/jendrikseipp/vulture)
- [Deadcode — EuroPython 2024](https://ep2024.europython.eu/session/deadcode-a-tool-to-find-and-fix-unused-dead-python-code/)
- [ruff dead-code issue — GitHub](https://github.com/astral-sh/ruff/issues/872)
- [Semgrep vs Bandit 2026 — DEV Community](https://dev.to/rahulxsingh/semgrep-vs-bandit-python-security-scanning-compared-2026-5e5j)
- [bandit for static analysis 2025 — johal.in](https://johal.in/application-security-testing-python-bandit-for-static-code-analysis-2025/)
- [Golden master / characterisation testing — Medium](https://chicio.medium.com/golden-master-testing-aka-characterization-test-a-powerful-tool-to-win-your-fight-against-legacy-1ca590f219a1)
- [Characterization test — Wikipedia](https://en.wikipedia.org/wiki/Characterization_test)
- [Feature flags rot your codebase — Stack Notes](https://stack-notes.com/blog/feature-flags-lifecycle-friday-deploys-technical-debt)
- [Feature flag retirement — CloudBees](https://www.cloudbees.com/blog/feature-flag-retirement)
- [Feature flag best practices 2025 — Octopus Deploy](https://octopus.com/devops/feature-flags/feature-flag-best-practices/)
- [Boy Scout Rule insufficiency — Code with Jason](https://www.codewithjason.com/boy-scout-rule-insufficient/)
- [Boy Scout Rule — Laws of Software Engineering](https://lawsofsoftwareengineering.com/laws/boy-scout-rule/)
- [Google Engineering Practices: small pull requests](https://google.github.io/eng-practices/review/developer/small-cls.html)
- [State of AI code quality 2025 — Qodo](https://www.qodo.ai/reports/state-of-ai-code-quality/)
