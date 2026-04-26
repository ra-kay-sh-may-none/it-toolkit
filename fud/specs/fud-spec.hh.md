#. REVISION CONTROL BLOCK:
	##. Document Title: Flexible Unified Diff Patcher Specification.
	##. Revision Number: 1.0.3.
	##. Status: Golden Source / Finalized.
	##. Format: HHMD (.WITH FILE EXTENSION .hh.md) (Hash Hierarchical Markdown).

#. Flexible Unified Diff Patcher Specification.
	##. This document outlines the structural requirements for a flexible patcher:
		###. The patcher must support standard unified diff headers and hunk markers.
		###. Implementation details focus on resilience against inaccurate line numbers.

	##. Core Specification for File Headers:
		###. A patch session begins with two identifying lines for the target files:
			####. The original file path is indicated by "--- " followed by the filename.
			####. The modified file path is indicated by "+++ " followed by the filename.
		###. Timestamps may follow the filenames but are considered optional for parsing.

	##. Input Scope and Target Resolution:
		###. The patcher processes a single patch file containing hunks for various files.
		###. Target file matching is governed by the following resolution hierarchy:
			####. 1. If an explicit <targetfile> is provided on the CLI, all hunks target that file.
			####. 2. If the --directory=DIR flag is present, all paths are resolved relative to DIR.
			####. 3. The --strip=N flag removes N leading components (slashes) from header paths.
		###. Glob filters restrict which files are eligible for patching:
			####. The --include=PATTERN and --exclude=PATTERN flags apply only to the resolved "+++" path.

	##. Session Path Mapping and Rename/Copy Logic:
		###. The tool maintains a session-wide path mapping table to track identities:
			####. It recognizes "rename from <path>" and "rename to <path>" extended headers.
			####. It supports "copy from <path>" and "copy to <path>" headers:
				#####. Copies do not delete the source file from the session map.
				#####. A new file identity is created using the content of the source path.
			####. Directory-level operations create virtual prefix mappings for all child files.
		###. Consistency is enforced to prevent split-identity conflicts:
			####. The tool throws a fatal error if a file is referred to by its old name after a rename.

	##. Sequential Patch Conflict Handling:
		###. The patcher manages conflicts when multiple patch files are applied in sequence:
			####. The tool verifies that each subsequent patch matches the file's current state on disk.
			####. If a previous patch moved the file, the next patch must acknowledge the new path.
			####. Failure to acknowledge a path change results in a "Path Identity Conflict" error.

	##. Execution Strategy and Order of Operations:
		###. The tool supports two primary modes for handling multi-hunk patch failures:
			####. The "Stop" mode (Default) prioritizes session-wide atomicity:
				#####. The tool performs a full pre-scan of all hunks against all target files.
				#####. It identifies every incorrect or ambiguous hunk discovered across the session.
				#####. If any failure is detected during this scan, no files are modified on the disk.
			####. The "Continue" mode (triggered by --continue) maximizes the application of valid changes:
				#####. Valid hunks are applied to the main file immediately as they are matched.
				#####. Failed or ambiguous hunks are logged as errors but do not block subsequent hunks.
		###. Partial Addition/Deletion Flags:
			####. The --no-add flag instructs the tool to skip all hunks containing additions (+).
			####. The --no-delete flag instructs the tool to skip all hunks containing deletions (-).

	##. Hunk Structure and Strict Matching Logic:
		###. Each hunk must start with a range header formatted as @@ -start,len +start,len @@:
			####. By default, the tool is strictly positional; the match must occur at the indicated line.
			####. If the content at the exact line does not match, the hunk application fails immediately.
		###. The specification permits the omission of the "@@" line entirely:
			####. If "@@" is missing, the patcher enters a full-file scanning mode.
			####. It performs a literal search for all provided context lines and deletion lines (-).

	##. Binary Data and Base85 Decoding:
		###. The tool supports Git-style Binary Data Encoding for non-text changes:
			####. It identifies "GIT binary patch" headers followed by a "literal" or "delta" hunk.
			####. Data blocks are decoded using the Ascii85 (Base85) Z-85 variant.
			####. Post-application hash verification ensures the binary file matches the expected state.

	##. File Creation, Deletion, and Directory Cleanup:
		###. The patcher recognizes standard markers for creating or removing files:
			####. A file creation is indicated by "--- /dev/null" in the header.
			####. A file deletion is indicated by "+++ /dev/null" in the header.
		###. The tool provides automatic filesystem management:
			####. For creations, parent directories are created automatically (mkdir -p).
			####. For deletions, once a file is removed, the tool checks if the parent directory is empty.
			####. Default Strictness (Option A): A directory is empty only if it contains zero items.
			####. Ignore List (Option C): The --cleanup-ignore=PATTERN flag allows specific files to be ignored during the emptiness check.
			####. If empty or only containing ignored items, the directory is recursively deleted.

	##. Symbolic Link Handling:
		###. The patcher handles symbolic links by transparently resolving them to their destinations:
			####. Matching and patching occur on the destination file pointed to by the link.
			####. The header name itself is used to identify the file in the session map.

	##. Search and Replace Logic for Hunk Application:
		###. Positional flexibility and content-based tolerance are disabled by default (Default: 0):
			####. The --max-offset=N flag sets the sliding window limit for line number hints.
			####. The --fuzz=N flag allows a match even if N context lines do not match perfectly.
		###. Similarity and Dissimilarity Indices:
			####. High similarity index scores (N%) can optionally increase the default search window.

	##. Line Ending and Whitespace Handling:
		###. The patcher auto-detects DOS (CRLF) or Unix (LF) formats from the target file.
		###. By default, all leading and trailing whitespace must match exactly.
		###. Specific flags (--ignore-leading-whitespace) allow relaxation of indentation rules.

	##. Encoding Detection and Adaptation:
		###. The patcher detects the encoding (e.g., UTF-8, UTF-16, Latin-1) of the main file.
		###. Input patch files are transcoded in memory to match the target file's encoding.

	##. File Write Safety:
		###. Modifications are written to the target path using an atomic "write-then-rename" strategy:
			####. Changes are first written to a temporary file (e.g., .patch.[filename].tmp).
			####. Upon success, the temporary file replaces the original.

	##. Backup and Safety Mechanisms:
		###. The --backup flag creates a ".orig" copy of the target file before modification.
		###. The --dry-run flag simulates the patching process without modifying any files.

	##. Logging and Verbosity Levels:
		###. Level 0 (Silent): Only returns the exit code.
		###. Level 1 (Default): Reports summary information and critical failures.
		###. Level 2 (Verbose): Includes detailed tracing for every hunk and filter skip.
		###. Level 3 (Debug): Displays byte-level comparison results and specific window offsets.

	##. Exit Codes and Error Handling:
		###. Code 0 indicates success.
		###. Code 1 indicates partial success or conflicts.
		###. Code 2 indicates a fatal error (missing file, invalid format).
		###. Code 127 indicates an ambiguous match in --strict mode.
