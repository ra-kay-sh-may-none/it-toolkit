#. FUD DEVELOPMENT PROTOCOL
	##. Status: Mandatory
	##. Application: Applies to all Agent-Human interactions for this project (Project FUD).

#. Core Rule: The Surgical Change Format
	##. Rule 1: No wholesale code regeneration unless explicitly requested.
	##. Rule 2: Changes MUST be presented in the "Search From / Replace To" format.
	##. Rule 3: Search blocks MUST include enough context (3-5 lines) to be unique.
	##. Rule 4: Zero tolerance for aesthetic changes (renaming variables, moving comments, changing white-space) unless technically required.

#. Protocol: Iterative Feature Sprints
	##. Phase 1: Requirements Sync - Extract specific logic from fud-spec.hh.md.
	##. Phase 2: Master Index Update - Advance the status and version (0.x.0).
	##. Phase 3: Design & Test Lock - Provide logic blueprint and character-exact test pairs.
	##. Phase 4: Surgical Implementation - Provide code updates using Rule 1 format.
	##. Phase 5: 100% Coverage Gate - Sprint cannot be marked DONE until all new branches (positive & negative) pass tests.

#. Versioning Strategy (0.x.0)
	##. x = Feature Increments (e.g., F5 Binary = 0.5.0).
	##. Final digit (0.0.x) reserved for hotfixes within a sprint.
	##. A version is marked DONE only when global test suite reports OK for all cumulative tests.

#. Diagnostic Standards
	##. Trace Logs: The `trace()` or `logger` infrastructure must remain intact.
	##. Log Format: MUST include the `[FUD_TRACE_ID]` marker from the environment.
	##. Test Runner: MUST dump stderr/stdout/logs automatically only on failure.

#. File Synchronisation
	##. master-index.hh.md: The single source of truth for current project state.
	##. hud-patcher.py: The production target.
	##. fud-patcher-test-runner.py: The verification target.
