#. REVISION CONTROL BLOCK:
	##. Document Title: Flexible Unified Diff Patcher - Technical Design Doc.
	##. Revision Number: 1.3.0.
	##. Status: Golden Source / Technical Blueprint.
	##. Format: HHMD (Hash Hierarchical Markdown).

#. Technical Stack & Environment:
	##. Runtime: Python 3.10+.
	##. Standard Library Dependency Policy: Restricted to Python Standard Library.
	##. CLI Presentation Layer:
		###. Rich Mode (Default): Uses ANSI escape sequences for color and progress.
		###. Monochrome Mode (Fallback): Automatically engaged if `sys.stdout.isatty()` is False or if the OS environment does not support ANSI.

#. Console UX & Visual Language:
	##. Semantic Indicators:
		###. SUCCESS [Bright Green]: Applied hunks/files.
		###. WARN [Yellow]: Fuzz used, offsets applied, or files skipped via glob.
		###. FATAL [Bright Red]: IO Errors, format errors, or aborted sessions.
		###. DEBUG [Dim Cyan]: Byte-level data and sliding window step-tracing.
	##. Progress Visualization:
		###. Multi-file patches: Shows a character-based progress bar `[###---] 50%` in Rich mode.
		###. Single-file patches: Simple hunk counter `(Hunk 2/10)`.

#. Error Handling & Exception Hierarchy:
	##. Internal Logic Class Tree:
		###. `PatcherError(Exception)`: Base class for all tool exceptions.
			####. `FormatError`: Triggered by invalid unified diff or binary patch headers.
			####. `IdentityConflict`: Triggered by rename/copy collisions in the Session Map.
			####. `MatchAmbiguity`: Triggered by multiple valid matches (Returns Code 127).
			####. `IOAbort`: Triggered by disk full, permissions, or read/write failures.
	##. Orchestrator Exit Code Mapping:
		###. `0`: Session completed with 100% success.
		###. `1`: Session completed with partial success (`--continue` mode).
		###. `2`: `PatcherError` or `OSError` (Fatal/Abort).
		###. `127`: `MatchAmbiguity` raised without `--global`.

#. System Architecture: Internal Data Structures:
	##. 1. `Hunk` (DataClass):
		###. Stores: Hint line numbers, exact context lines, +/- deltas, and binary Base85 blobs.
	##. 2. `PatchFile` (Object):
		###. Groups `Hunk` objects by their target path.
		###. Stores: Extended headers (renames, copies, similarity indices).
	##. 3. `Session` (Controller):
		###. State: Flags, Global Identity Map, and Path Normalizer.
		###. Method `validate()`: Performs the pre-scan for "Stop" mode.
		###. Method `commit()`: Executes the "Write-then-Rename" atomic loop.

#. Cross-Platform Compatibility Layer:
	##. Path Normalization: Uses `os.path.normpath` and `os.sep` for all identity map keys.
	##. Write Safety: Uses `os.replace()` for atomic overwrites to support Windows locking semantics.
