#. REVISION CONTROL BLOCK:
	##. Document Title: FUDP - AI Development Governance Harness.
	##. Status: Mandatory Framework / Integrated Interface Lock.
	##. Format: HHMD (Hash Hierarchical Markdown).

#. Pillar Document References:
	##. Functional Spec: `fud-spec.hh.md`
	##. Test Suite: `fud-cucumber.gherkin`
	##. Technical Design: `fud-tech-design.hh.md`
	##. Governance: `fud-governance-harness.hh.md` (This file)

#. CLI Command & Argument Schema (The External Lock):
	##. Positional Arguments:
		###. `patch_file`: [Required, String] Path to the input .patch or .diff file.
		###. `target_file_override`: [Optional, String] Explicit target file path (Overrides patch headers).
	##. Operational Flag Details:
		###. Strategy Flags:
			####. `--continue`: [Action: store_true] Enable best-effort application (Default is Stop Mode).
			####. `--dry-run`: [Action: store_true] Simulate process without disk writes.
			####. `--reverse`, `-R`: [Action: store_true] Apply the patch in reverse (Swap +/- and headers).
		###. Path & Resolution Flags:
			####. `--directory`, `-d`: [Type: str, Default: None] Set base directory for target file resolution.
			####. `--strip`, `-p`: [Type: int, Default: 0] Number of leading path components to strip from headers.
			####. `--include`: [Type: str, Default: None] Glob pattern for files to include in patching.
			####. `--exclude`: [Type: str, Default: None] Glob pattern for files to exclude from patching.
		###. Matching & Tolerance Flags:
			####. `--max-offset`: [Type: int, Default: 0] Max vertical lines to search from hint line.
			####. `--fuzz`: [Type: int, Default: 0] Max number of context lines allowed to mismatch.
			####. `--strict`: [Action: store_true] Abort on any ambiguity (Triggers Exit Code 127).
			####. `--global`: [Action: store_true] Apply hunks to all matching occurrences in search mode.
		###. Filesystem & Safety Flags:
			####. `--backup`: [Action: store_true] Create .orig backup files before modification.
			####. `--no-add`: [Action: store_true] Skip hunks containing additions (+).
			####. `--no-delete`: [Action: store_true] Skip hunks containing deletions (-).
			####. `--cleanup-ignore`: [Type: str, Default: None] Pattern of files to ignore during recursive rmdir.
			####. `--ignore-leading-whitespace`: [Action: store_true] Ignore indentation differences in matching.
		###. Feedback Flags:
			####. `--verbose`, `-v`: [Action: count, Default: 1] Increment logging level (0=Silent, 1=Default, 2=Info, 3=Debug).

#. Core Class & Method Signatures (The Internal Lock):
	##. 1. Class `PatcherOrchestrator`:
		###. `__init__(self, args: argparse.Namespace)`
		###. `run_session(self) -> int`: Main loop returning the session exit code.
		###. `_pre_scan(self) -> bool`: The "Stop Mode" validation pass across all files.
	##. 2. Class `PatchParser`:
		###. `parse_stream(self, stream: TextIO) -> List[PatchFile]`
		###. `_parse_hunk(self, lines: List[str]) -> Hunk`
	##. 3. Class `Matcher`:
		###. `find_match(self, target_lines: List[str], hunk: Hunk) -> List[int]`: Returns list of zero-based line indices.
	##. 4. Class `IdentityMap`:
		###. `resolve_path(self, path: str) -> str`: Returns the normalized current filesystem path.
		###. `add_rename(self, old_path: str, new_path: str)`
		###. `add_copy(self, src_path: str, dst_path: str)`

#. Identity Map Schema:
	##. Implementation: Flat dictionary `{ "normalized_original_path": "normalized_current_path" }`.
	##. Normalization: All keys/values MUST pass through `os.path.normcase(os.path.normpath(path))`.

#. Mandatory Variable Naming Conventions:
	##. Paths: `target_path`, `patch_path`, `temp_path`, `base_dir_path`.
	##. Buffers: `content_buffer`, `hunk_buffer`.
	##. Counters: `applied_count`, `skipped_count`, `failed_count`.

#. Code Generation Directives for Agents:
	##. Directive 1: Use Python Standard Library only.
	##. Directive 2: Maintain character-exact CLI behavior as defined in this Harness.
	##. Directive 3: Explicitly map code blocks to Requirement IDs in comments.
