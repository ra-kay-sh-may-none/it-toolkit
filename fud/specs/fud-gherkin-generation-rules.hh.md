#. REVISION CONTROL BLOCK:
	##. Document Title: Grounding Rules with Universal Fencing and Paired Complexity.
	##. Revision Number: 1.5.0.
	##. Status: Active / Instructional.
	##. Format: HHMD (.WITH FILE EXTENSION .hh.md) (Hash Hierarchical Markdown).

#. Core Grounding Rules for Test Case Generation.
	##. Environmental Isolation Rule:
		###. Every test scenario must explicitly define four distinct paths to verify resolution logic:
			####. The absolute path of the patcher executable (e.g., /opt/bin/patcher).
			####. The Current Working Directory (CWD) from which the command is issued (e.g., /home/user/workspace).
			####. The Source Directory containing the target files to be patched (e.g., /mnt/data/sources).
			####. The Patch Directory containing the .patch or .diff files (e.g., /home/user/patches).
	##. Standardized Directory Structure Rule:
		###. All scenarios must assume the following base file tree exists in the Source Directory:
			####. dir1/file1.py
			####. dir2/file21.py
			####. dir2/file22.json
			####. dir3/file31.json
			####. dir3/file31.py
			####. dir3/file32.json
			####. dir3/file32.py
			####. dir4/file41.bin
	##. Universal Fencing Rule:
		###. EVERYTHING technical and character-exact must be enclosed in fenced code blocks.
		###. This includes: Main file content, Patch file content, CLI commands, STDOUT, and STDERR.
		###. Empty states must be represented as an empty fenced block.
	##. Paired Complexity Rule:
		###. Features must be presented in ascending order of complexity.
		###. Every scenario within a feature must be presented as a Pair:
			####. 1. Positive Scenario: Demonstrates successful execution of the specific logic.
			####. 2. Negative/Edge Scenario: Demonstrates the specific failure mode or boundary constraint.
	##. Exact Content Rule:
		###. All inputs and outputs must be character-exact, reflecting prefixes and headers.
	##. Explicit CLI Invocation Rule:
		###. The "When" step must show the literal command string inside a fenced block.
	##. Logging and Exit Code Rule:
		###. Verify exit codes (0, 1, 2, or 127) and log destinations (STDOUT/STDERR) in fenced blocks.
	##. Filesystem Integrity Rule:
		###. Verify (non)existence of files and recursive removal of empty parent directories.
	##. Permutation Rule:
		###. Test suites must cover 100% of the combinations in the Golden Source specification.
