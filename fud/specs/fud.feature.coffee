Feature: Basic Positional and Search Logic
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # SCENARIO 1: Simplest Hunk, Exact Match, Default Strict Mode
  Scenario: Exact Line Number Match on a Single File
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      import os
      print("Hello")
      exit(0)
      """
    And a patch file "/home/user/patches/simple.patch" with content:
      """
      --- dir1/file1.py
      +++ dir1/file1.py
      @@ -2,1 +2,1 @@
      -print("Hello")
      +print("World")
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/simple.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir1/file1.py" should exactly match:
      """
      import os
      print("World")
      exit(0)
      """
    And STDOUT should exactly match:
      """
      1 hunk applied successfully
      """
    And STDERR should exactly match:
      """
      """

  # SCENARIO 2: Search and Replace (Omitted @@) - Increasing complexity by removing hints
  Scenario: Context Matching without Line Number Hints
    Given a file "/mnt/data/sources/dir2/file22.json" with content:
      """
      {
        "status": "pending",
        "retries": 0
      }
      """
    And a patch file "/home/user/patches/search.patch" with content:
      """
      --- dir2/file22.json
      +++ dir2/file22.json
      -  "status": "pending"
      +  "status": "complete"
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/search.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir2/file22.json" should exactly match:
      """
      {
        "status": "complete",
        "retries": 0
      }
      """
    And STDOUT should exactly match:
      """
      Applied via full-file literal search
      """
    And STDERR should exactly match:
      """
      """

  # SCENARIO 3: Positional Failure (Strict Mode) - Increasing complexity by testing negative constraints
  Scenario: Strict Positional Match Failure
    Given a file "/mnt/data/sources/dir3/file31.py" with content:
      """
      def foo():
          return 1
      """
    And a patch file "/home/user/patches/wrong_line.patch" with content:
      """
      --- dir3/file31.py
      +++ dir3/file31.py
      @@ -10,1 +10,1 @@
      -    return 1
      +    return 2
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/wrong_line.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir3/file31.py" should exactly match:
      """
      def foo():
          return 1
      """
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      Hunk match failed at line 10
      """

  # SCENARIO 4: Sliding Window (Offset) - Increasing complexity by enabling positional tolerance
  Scenario: Flexible Positional Match with Max Offset
    Given a file "/mnt/data/sources/dir3/file32.py" with content:
      """
      # Comment
      # Comment
      # Comment
      # Comment
      v = 1
      """
    And a patch file "/home/user/patches/offset.patch" with content:
      """
      --- dir3/file32.py
      +++ dir3/file32.py
      @@ -1,1 +1,1 @@
      -v = 1
      +v = 2
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/offset.patch --directory=/mnt/data/sources --max-offset=10
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir3/file32.py" should exactly match:
      """
      # Comment
      # Comment
      # Comment
      # Comment
      v = 2
      """
    And STDOUT should exactly match:
      """
      1 hunk applied successfully at line 5 (offset 4)
      """
    And STDERR should exactly match:
      """
      """

Feature: Context-Based Matching Permutations
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)
  # Standard Structure Assumption: dir2/file21.py, dir3/file31.json, etc.

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # SCENARIO 5: Precise Context Matching (Multiple Lines)
  # Increasing complexity: Using surrounding context to anchor a search-and-replace.
  Scenario: Search and Replace using Multi-line Context Anchors
    Given a file "/mnt/data/sources/dir2/file21.py" with content:
      """
      import sys
      
      def execute():
          # Initial call
          do_work()
          return True
      """
    And a patch file "/home/user/patches/multi_context.patch" with content:
      """
      --- dir2/file21.py
      +++ dir2/file21.py
       def execute():
           # Initial call
      -    do_work()
      +    do_work_async()
           return True
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/multi_context.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir2/file21.py" should exactly match:
      """
      import sys
      
      def execute():
          # Initial call
          do_work_async()
          return True
      """
    And STDOUT should exactly match:
      """
      Applied via full-file literal search
      """
    And STDERR should exactly match:
      """
      """

  # SCENARIO 6: Fuzz Factor with Missing Context (Strictness Relaxation)
  # Increasing complexity: Some context lines in the patch do not match the main file.
  Scenario: Context Search with Fuzz Factor for Modified Surrounding Lines
    Given a file "/mnt/data/sources/dir3/file31.json" with content:
      """
      {
        "id": "101",
        "type": "standard",
        "active": true
      }
      """
    And a patch file "/home/user/patches/fuzz_context.patch" with content:
      """
      --- dir3/file31.json
      +++ dir3/file31.json
        "id": "101",
        "type": "outdated_type_string",
      -  "active": true
      +  "active": false
      """
    # Note: "outdated_type_string" does not match "standard" on disk.
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/fuzz_context.patch --directory=/mnt/data/sources --fuzz=1
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir3/file31.json" should exactly match:
      """
      {
        "id": "101",
        "type": "standard",
        "active": false
      }
      """
    And STDOUT should exactly match:
      """
      Applied with fuzz factor 1
      """
    And STDERR should exactly match:
      """
      """

  # SCENARIO 7: Ambiguous Context Search (Strictness Enforcement)
  # Increasing complexity: Context block appears twice; tool must identify ambiguity.
  Scenario: Ambiguous Match Detection in Search Mode
    Given a file "/mnt/data/sources/dir3/file32.json" with content:
      """
      {
        "item": "A",
        "tag": "test",
        "item": "B",
        "tag": "test"
      }
      """
    And a patch file "/home/user/patches/ambiguous.patch" with content:
      """
      --- dir3/file32.json
      +++ dir3/file32.json
       "tag": "test"
      - "tag": "test"
      + "tag": "prod"
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/ambiguous.patch --directory=/mnt/data/sources --strict
      """
    Then the exit code should be 127
    And the file "/mnt/data/sources/dir3/file32.json" should exactly match:
      """
      {
        "item": "A",
        "tag": "test",
        "item": "B",
        "tag": "test"
      }
      """
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      Ambiguous match: Context block found in multiple locations
      """

Feature: Multi-Hunk and Multi-File Permutations
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)
  # Strategy: Testing virtual offset tracking within a file and session atomicity across files.

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # SCENARIO 8: Multiple Hunks in One File (Virtual Offset Tracking)
  # Complexity: Hunk 1 adds lines, so Hunk 2 must be found at a new virtual position.
  Scenario: Sequential Hunks in One File with Downstream Line Shifts
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      def start():
          print("A")
      
      def end():
          print("B")
      """
    And a patch file "/home/user/patches/multi_hunk_shift.patch" with content:
      """
      --- dir1/file1.py
      +++ dir1/file1.py
      @@ -2,1 +2,3 @@
       def start():
      +    # Log start
      +    logger.info("Starting")
           print("A")
      @@ -5,1 +7,1 @@
       def end():
      -    print("B")
      +    print("C")
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/multi_hunk_shift.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir1/file1.py" should exactly match:
      """
      def start():
          # Log start
          logger.info("Starting")
          print("A")
      
      def end():
          print("C")
      """
    And STDOUT should exactly match:
      """
      Applied: 2 hunks to dir1/file1.py
      """
    And STDERR should exactly match:
      """
      """

  # SCENARIO 9: Multi-File Patch (Stop Mode - Default)
  # Complexity: One file fails, ensuring the whole session is aborted (Atomicity).
  Scenario: Atomic Multi-File Session Failure
    Given a file "/mnt/data/sources/dir2/file21.py" with content:
      """
      x = 1
      """
    And a file "/mnt/data/sources/dir2/file22.json" with content:
      """
      {"y": 1}
      """
    And a patch file "/home/user/patches/atomic_fail.patch" with content:
      """
      --- dir2/file21.py
      +++ dir2/file21.py
      @@ -1,1 +1,1 @@
      -x = 1
      +x = 2
      --- dir2/file22.json
      +++ dir2/file22.json
      @@ -1,1 +1,1 @@
      -{"y": 999}
      +{"y": 1}
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/atomic_fail.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir2/file21.py" should exactly match:
      """
      x = 1
      """
    And the file "/mnt/data/sources/dir2/file22.json" should exactly match:
      """
      {"y": 1}
      """
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      Hunk match failed for dir2/file22.json
      """

  # SCENARIO 10: Multi-File Patch (Continue Mode)
  # Complexity: Forcing partial success across multiple files.
  Scenario: Partial Success Across Multiple Files via Continue Flag
    Given a file "/mnt/data/sources/dir3/file31.py" with content:
      """
      a = 1
      """
    And a file "/mnt/data/sources/dir3/file31.json" with content:
      """
      b = 1
      """
    And a patch file "/home/user/patches/continue_partial.patch" with content:
      """
      --- dir3/file31.py
      +++ dir3/file31.py
      @@ -1,1 +1,1 @@
      -a = 1
      +a = 2
      --- dir3/file31.json
      +++ dir3/file31.json
      @@ -1,1 +1,1 @@
      -INVALID_CONTEXT
      +b = 2
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/continue_partial.patch --directory=/mnt/data/sources --continue
      """
    Then the exit code should be 1
    And the file "/mnt/data/sources/dir3/file31.py" should exactly match:
      """
      a = 2
      """
    And the file "/mnt/data/sources/dir3/file31.json" should exactly match:
      """
      b = 1
      """
    And STDOUT should exactly match:
      """
      Applied: dir3/file31.py
      """
    And STDERR should exactly match:
      """
      Failed: dir3/file31.json
      """

Feature: Exhaustive Negative Scenarios for Matching and Atomicity
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # NEGATIVE SCENARIO 1: Strict Context Mismatch (Single Line)
  Scenario: Strict Search Mode Context Mismatch
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      print("Old Line")
      """
    And a patch file "/home/user/patches/mismatch.patch" with content:
      """
      --- dir1/file1.py
      +++ dir1/file1.py
      -print("Mismatched Context")
      +print("New Line")
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/mismatch.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir1/file1.py" should exactly match:
      """
      print("Old Line")
      """
    And STDERR should exactly match:
      """
      Hunk match failed: Context not found
      """

  # NEGATIVE SCENARIO 2: Out-of-Bounds Sliding Window
  Scenario: Sliding Window Failure Outside Max Offset
    Given a file "/mnt/data/sources/dir3/file32.py" with content:
      """
      [100 lines of noise]
      target_line = true
      """
    And a patch file "/home/user/patches/out_of_bounds.patch" with content:
      """
      --- dir3/file32.py
      +++ dir3/file32.py
      @@ -1,1 +1,1 @@
      -target_line = true
      +target_line = false
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/out_of_bounds.patch --directory=/mnt/data/sources --max-offset=50
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir3/file32.py" should remain unchanged
    And STDERR should exactly match:
      """
      Hunk match failed: Target block found at offset 100 exceeds max-offset 50
      """

  # NEGATIVE SCENARIO 3: Ambiguous Context without Global Flag
  Scenario: Ambiguity Failure in Default Strict Mode
    Given a file "/mnt/data/sources/dir2/file21.py" with content:
      """
      option = 1
      option = 1
      """
    And a patch file "/home/user/patches/ambig_fail.patch" with content:
      """
      --- dir2/file21.py
      +++ dir2/file21.py
      -option = 1
      +option = 2
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/ambig_fail.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 127
    And STDERR should exactly match:
      """
      Ambiguous match: 2 occurrences found for the provided context block
      """

  # NEGATIVE SCENARIO 4: Session Rollback on Final Hunk Failure
  Scenario: Session Rollback for Multi-Hunk File in Stop Mode
    Given a file "/mnt/data/sources/dir3/file31.py" with content:
      """
      BLOCK_A
      BLOCK_B
      """
    And a patch file "/home/user/patches/hunk_rollback.patch" with content:
      """
      --- dir3/file31.py
      +++ dir3/file31.py
      @@ -1,1 +1,1 @@
      -BLOCK_A
      +BLOCK_A_MOD
      @@ -2,1 +2,1 @@
      -WRONG_BLOCK
      +BLOCK_B_MOD
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/hunk_rollback.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir3/file31.py" should exactly match:
      """
      BLOCK_A
      BLOCK_B
      """
    And STDERR should exactly match:
      """
      Hunk 2 match failed for dir3/file31.py
      """

  # NEGATIVE SCENARIO 5: Binary Patch Corruption Prevention
  Scenario: Binary Delta Hash Mismatch Abort
    Given a file "/mnt/data/sources/dir4/file41.bin" with corrupted raw binary
    And a patch file "/home/user/patches/binary_delta.patch" with content:
      """
      --- dir4/file41.bin
      +++ dir4/file41.bin
      GIT binary patch
      delta 10
      zcmZ>V&OEplzm`W_@9(0;A#)h!
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/binary_delta.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDERR should exactly match:
      """
      FATAL: Binary hash verification failed after delta application
      """

Feature: Identity Shifts - Rename and Copy Logic
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # SCENARIO 14: Atomic File Rename and Sequential Edit
  Scenario: Atomic File Rename and Sequential Edit
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      print("Old Path")
      """
    And a patch file "/home/user/patches/rename_v1.patch" with content:
      """
      --- rename from dir1/file1.py
      +++ rename to dir1/file1_new.py
      --- dir1/file1_new.py
      +++ dir1/file1_new.py
      @@ -1,1 +1,1 @@
      -print("Old Path")
      +print("New Path")
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/rename_v1.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir1/file1.py" should not exist
    And the file "/mnt/data/sources/dir1/file1_new.py" should exactly match:
      """
      print("New Path")
      """
    And STDOUT should exactly match:
      """
      Renamed: dir1/file1.py -> dir1/file1_new.py
      Applied: 1 hunk to dir1/file1_new.py
      """
    And STDERR should exactly match:
      """
      """

  # SCENARIO 15: File Copy and Independent Modification
  Scenario: Tracked Copy from Source to New Destination
    Given a file "/mnt/data/sources/dir2/file22.json" with content:
      """
      {"version": 1}
      """
    And a patch file "/home/user/patches/copy_test.patch" with content:
      """
      copy from dir2/file22.json
      copy to dir2/file22_backup.json
      --- dir2/file22_backup.json
      +++ dir2/file22_backup.json
      @@ -1,1 +1,1 @@
      -{"version": 1}
      +{"version": "backup"}
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/copy_test.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir2/file22.json" should exactly match:
      """
      {"version": 1}
      """
    And the file "/mnt/data/sources/dir2/file22_backup.json" should exactly match:
      """
      {"version": "backup"}
      """
    And STDOUT should exactly match:
      """
      Copied: dir2/file22.json -> dir2/file22_backup.json
      Applied: 1 hunk to dir2/file22_backup.json
      """
    And STDERR should exactly match:
      """
      """

  # SCENARIO 16: Path Identity Conflict (Rename Violation)
  Scenario: Fatal Error when Hunk refers to Deprecated Path after Rename
    Given a file "/mnt/data/sources/dir3/file31.py" with content:
      """
      # Original
      """
    And a patch file "/home/user/patches/ghost_conflict.patch" with content:
      """
      --- rename from dir3/file31.py
      +++ rename to dir3/file31_moved.py
      --- dir3/file31.py
      +++ dir3/file31.py
      - # Original
      + # Modified
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/ghost_conflict.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir3/file31.py" should exactly match:
      """
      # Original
      """
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      FATAL: Path Identity Conflict - dir3/file31.py was already renamed to dir3/file31_moved.py
      """

Feature: Negative Scenarios for Identity Shifts
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # NEGATIVE SCENARIO 6: Rename Source Missing
  Scenario: Failure when Rename Source File Does Not Exist
    Given the directory "/mnt/data/sources/dir1" is empty
    And a patch file "/home/user/patches/missing_source.patch" with content:
      """
      --- rename from dir1/missing.py
      +++ rename to dir1/found.py
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/missing_source.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      FATAL: Rename source not found: dir1/missing.py
      """

  # NEGATIVE SCENARIO 7: Rename Destination Collision
  Scenario: Failure when Rename Destination Already Exists
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      # File 1
      """
    And a file "/mnt/data/sources/dir1/existing.py" with content:
      """
      # I am already here
      """
    And a patch file "/home/user/patches/collision.patch" with content:
      """
      --- rename from dir1/file1.py
      +++ rename to dir1/existing.py
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/collision.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir1/file1.py" should still exist
    And STDERR should exactly match:
      """
      FATAL: Cannot rename to dir1/existing.py: Destination already exists
      """

  # NEGATIVE SCENARIO 8: Copy Source Missing
  Scenario: Failure when Copy Source File Does Not Exist
    Given the directory "/mnt/data/sources/dir2" is empty
    And a patch file "/home/user/patches/copy_fail.patch" with content:
      """
      copy from dir2/nonexistent.json
      copy to dir2/new.json
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/copy_fail.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDERR should exactly match:
      """
      FATAL: Copy source not found: dir2/nonexistent.json
      """

  # NEGATIVE SCENARIO 9: Circular Rename Detection
  Scenario: Failure on Circular Rename Chain in Single Session
    Given a file "/mnt/data/sources/dir1/file1.py"
    And a patch file "/home/user/patches/circular.patch" with content:
      """
      --- rename from dir1/file1.py
      +++ rename to dir1/temp.py
      --- rename from dir1/temp.py
      +++ rename to dir1/file1.py
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/circular.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDERR should exactly match:
      """
      FATAL: Circular rename detected for dir1/file1.py
      """

Feature: Feature 4 - Recursive Directory Cleanup and File Deletion
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # SCENARIO 17: Standard File Deletion with Directory Cleanup
  # Complexity: Deleting the only file in a directory triggers recursive removal of the parent folder.
  Scenario: Recursive Removal of Empty Parent Directories on File Deletion
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      # Sole content
      """
    And a patch file "/home/user/patches/delete_and_clean.patch" with content:
      """
      --- dir1/file1.py
      +++ /dev/null
      @@ -1,1 +0,0 @@
      -# Sole content
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/delete_and_clean.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir1/file1.py" should not exist
    And the directory "/mnt/data/sources/dir1" should not exist
    And STDOUT should exactly match:
      """
      Deleted file: dir1/file1.py
      Removed empty directory: dir1
      """
    And STDERR should exactly match:
      """
      """

  # SCENARIO 18: File Deletion with Persistent Sibling
  # Complexity: Verifying that cleanup stops if the directory is NOT empty.
  Scenario: File Deletion without Directory Removal when Siblings Exist
    Given a file "/mnt/data/sources/dir2/file21.py" with content:
      """
      # File 21
      """
    And a file "/mnt/data/sources/dir2/file22.json" with content:
      """
      {
        "id": 22
      }
      """
    And a patch file "/home/user/patches/delete_sibling.patch" with content:
      """
      --- dir2/file21.py
      +++ /dev/null
      @@ -1,1 +0,0 @@
      -# File 21
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/delete_sibling.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir2/file21.py" should not exist
    And the file "/mnt/data/sources/dir2/file22.json" should exactly match:
      """
      {
        "id": 22
      }
      """
    And the directory "/mnt/data/sources/dir2" should still exist
    And STDOUT should exactly match:
      """
      Deleted file: dir2/file21.py
      """
    And STDERR should exactly match:
      """
      """

  # NEGATIVE SCENARIO 10: Deletion Context Mismatch
  # Complexity: Ensuring safety by refusing to delete a file if its content doesn't match the deletion hunk.
  Scenario: Refusal to Delete File on Context Mismatch
    Given a file "/mnt/data/sources/dir3/file31.py" with content:
      """
      current_data = true
      """
    And a patch file "/home/user/patches/bad_delete.patch" with content:
      """
      --- dir3/file31.py
      +++ /dev/null
      @@ -1,1 +0,0 @@
      -outdated_data = false
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/bad_delete.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir3/file31.py" should exactly match:
      """
      current_data = true
      """
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      Hunk match failed for dir3/file31.py: Context mismatch
      """

  # NEGATIVE SCENARIO 11: Attempt to Delete Non-Existent File
  # Complexity: Handling missing files in a deletion patch.
  Scenario: Failure when Deleting a File that Does Not Exist
    Given the directory "/mnt/data/sources/dir3" is empty
    And a patch file "/home/user/patches/missing_delete.patch" with content:
      """
      --- dir3/file31.py
      +++ /dev/null
      @@ -1,1 +0,0 @@
      -void()
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/missing_delete.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      FATAL: Target file for deletion not found: dir3/file31.py
      """

Feature: Feature 4 - Recursive Directory Cleanup and File Deletion
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # POSITIVE SCENARIO 17: Standard File Deletion with Directory Cleanup (Already Defined)
  Scenario: Recursive Removal of Empty Parent Directories on File Deletion
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      # Sole content
      """
    And a patch file "/home/user/patches/delete_and_clean.patch" with content:
      """
      --- dir1/file1.py
      +++ /dev/null
      @@ -1,1 +0,0 @@
      -# Sole content
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/delete_and_clean.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir1/file1.py" should not exist
    And the directory "/mnt/data/sources/dir1" should not exist
    And STDOUT should exactly match:
      """
      Deleted file: dir1/file1.py
      Removed empty directory: dir1
      """
    And STDERR should exactly match:
      """
      """

  # NEGATIVE SCENARIO 17: Cleanup Failure due to Hidden Files or Permissions
  # Complexity: The file is deleted, but the directory cannot be removed because it contains 
  # an unlisted/untracked hidden file (e.g., .DS_Store), violating the "empty directory" rule.
  Scenario: Directory Removal Skips when Untracked Files are Present
    Given a directory "/mnt/data/sources/dir1/" containing "file1.py"
    And the directory "/mnt/data/sources/dir1/" also contains a hidden file ".DS_Store"
    And a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      # Sole content
      """
    And a patch file "/home/user/patches/delete_with_hidden.patch" with content:
      """
      --- dir1/file1.py
      +++ /dev/null
      @@ -1,1 +0,0 @@
      -# Sole content
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/delete_with_hidden.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir1/file1.py" should not exist
    And the directory "/mnt/data/sources/dir1" should still exist
    And STDOUT should exactly match:
      """
      Deleted file: dir1/file1.py
      Skipped directory removal: dir1 is not empty.
      """
    And STDERR should exactly match:
      """
      """

  # NEGATIVE SCENARIO 18: File Deletion Refusal on Path Collision
  # Complexity: Ensuring the patcher does not delete a file if the patch header path resolves
  # incorrectly due to an existing file where a directory was expected (Path Identity Conflict).
  Scenario: Failure when Deletion Target is Blocked by a Non-File Path
    Given a file "/mnt/data/sources/dir1" exists (where dir1 is a file, not a directory)
    And a patch file "/home/user/patches/path_collision.patch" with content:
      """
      --- dir1/file1.py
      +++ /dev/null
      @@ -1,1 +0,0 @@
      -content
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/path_collision.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDERR should exactly match:
      """
      FATAL: Cannot resolve path dir1/file1.py - /mnt/data/sources/dir1 is a file.
      """
    And STDOUT should exactly match:
      """
      """

Feature: Feature 5 - Binary Data and Base85 Decoding
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # POSITIVE SCENARIO 19: Valid Base85 Binary Delta
  # Complexity: Verifying the Ascii85 (Z-85 variant) decoding and binary application.
  Scenario: Successful Application of Git-Style Binary Delta
    Given a file "/mnt/data/sources/dir4/file41.bin" with raw binary content
    And a patch file "/home/user/patches/binary_valid.patch" with content:
      """
      --- dir4/file41.bin
      +++ dir4/file41.bin
      GIT binary patch
      delta 12
      zcmZ>V&OEplzm`W_@9(0;A#)h!A#)h!A#)h!
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/binary_valid.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir4/file41.bin" should be updated and pass hash verification
    And STDOUT should exactly match:
      """
      Applied binary delta to dir4/file41.bin
      """
    And STDERR should exactly match:
      """
      """

  # NEGATIVE SCENARIO 19: Invalid Base85 Encoding
  # Complexity: Ensuring the patcher rejects corrupted Base85 character sets.
  Scenario: Failure on Corrupted Base85 Alphabet in Binary Patch
    Given a file "/mnt/data/sources/dir4/file41.bin" with raw binary content
    And a patch file "/home/user/patches/binary_corrupt.patch" with content:
      """
      --- dir4/file41.bin
      +++ dir4/file41.bin
      GIT binary patch
      delta 12
      zcmZ>V&OEplzm_INVALID_CHARS_!!!
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/binary_corrupt.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir4/file41.bin" should remain unchanged
    And STDERR should exactly match:
      """
      FATAL: Invalid Base85 character encountered in binary hunk
      """

  # POSITIVE SCENARIO 20: Binary File Creation
  # Complexity: Creating a new binary file from a literal Base85 block.
  Scenario: Successful Creation of a New Binary File
    Given the directory "/mnt/data/sources/dir4" exists but is empty
    And a patch file "/home/user/patches/binary_create.patch" with content:
      """
      --- /dev/null
      +++ dir4/new_binary.bin
      GIT binary patch
      literal 5
      zcmZ>V&OEpl
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/binary_create.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir4/new_binary.bin" should exist
    And STDOUT should exactly match:
      """
      Created binary file: dir4/new_binary.bin
      """
    And STDERR should exactly match:
      """
      """

  # NEGATIVE SCENARIO 20: Post-Application Hash Mismatch
  # Complexity: Safety check failing when the resulting binary doesn't match the patch's expected hash.
  Scenario: Failure when Applied Binary Delta Results in Hash Mismatch
    Given a file "/mnt/data/sources/dir4/file41.bin" with non-matching seed data
    And a patch file "/home/user/patches/binary_hash_fail.patch" with content:
      """
      --- dir4/file41.bin
      +++ dir4/file41.bin
      GIT binary patch
      delta 10
      zcmZ>V&OEplzm`W_@9(0;A#)h!
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/binary_hash_fail.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir4/file41.bin" should remain unchanged
    And STDERR should exactly match:
      """
      FATAL: Binary hash verification failed for dir4/file41.bin
      """

Feature: Feature 6 - Symbolic Link Handling
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)
  # Standard Structure Assumption: dir1/file1.py, dir2/file21.py

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # POSITIVE SCENARIO 21: Patching Destination via Symlink
  # Complexity: Verifying that the patcher follows the link to modify the real file while keeping the link intact.
  Scenario: Successful Patching of Target File through a Symbolic Link
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      # Real File Content
      """
    And a symbolic link "/mnt/data/sources/dir1/link_to_file.py" pointing to "/mnt/data/sources/dir1/file1.py"
    And a patch file "/home/user/patches/symlink_patch.patch" with content:
      """
      --- dir1/link_to_file.py
      +++ dir1/link_to_file.py
      @@ -1,1 +1,1 @@
      -# Real File Content
      +# Patched via Symlink
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/symlink_patch.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir1/file1.py" should exactly match:
      """
      # Patched via Symlink
      """
    And the path "/mnt/data/sources/dir1/link_to_file.py" should still be a symbolic link
    And STDOUT should exactly match:
      """
      Resolved symlink: dir1/link_to_file.py -> dir1/file1.py
      Applied: 1 hunk to dir1/file1.py
      """
    And STDERR should exactly match:
      """
      """

  # NEGATIVE SCENARIO 21: Dangling Symbolic Link
  # Complexity: Handling a scenario where the symlink exists but its target file does not.
  Scenario: Failure when Patching via a Dangling Symbolic Link
    Given a symbolic link "/mnt/data/sources/dir1/broken_link" pointing to "/mnt/data/sources/nonexistent_file"
    And a patch file "/home/user/patches/broken_link.patch" with content:
      """
      --- dir1/broken_link
      +++ dir1/broken_link
      @@ -1,1 +1,1 @@
      -old
      +new
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/broken_link.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the path "/mnt/data/sources/dir1/broken_link" should still exist as a link
    And STDERR should exactly match:
      """
      FATAL: Symlink target not found: /mnt/data/sources/nonexistent_file
      """
    And STDOUT should exactly match:
      """
      """

  # POSITIVE SCENARIO 22: Symlink as Part of Rename Chain
  # Complexity: Renaming a symlink and ensuring it still points correctly.
  Scenario: Successful Rename of a Symbolic Link
    Given a file "/mnt/data/sources/dir2/file21.py" with content:
      """
      # Data
      """
    And a symbolic link "/mnt/data/sources/dir2/link_a" pointing to "/mnt/data/sources/dir2/file21.py"
    And a patch file "/home/user/patches/rename_link.patch" with content:
      """
      --- rename from dir2/link_a
      +++ rename to dir2/link_b
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/rename_link.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the path "/mnt/data/sources/dir2/link_a" should not exist
    And the path "/mnt/data/sources/dir2/link_b" should be a symbolic link pointing to "/mnt/data/sources/dir2/file21.py"
    And STDOUT should exactly match:
      """
      Renamed symlink: dir2/link_a -> dir2/link_b
      """

  # NEGATIVE SCENARIO 22: Binary Patching Attempt on a Symlink Path
  # Complexity: Ensuring the patcher rejects binary hunks if the target is a symlink and --no-follow-symlinks isn't used (not defined in spec yet, assuming follow).
  Scenario: Failure when Applying Binary Delta to a Symlink Target (Hash Check)
    Given a symbolic link "/mnt/data/sources/dir2/binary_link" pointing to "/mnt/data/sources/dir2/file21.py"
    And a patch file "/home/user/patches/binary_symlink.patch" with content:
      """
      --- dir2/binary_link
      +++ dir2/binary_link
      GIT binary patch
      delta 10
      zcmZ>V&OEplzm`W_@9(0;A#)h!
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/binary_symlink.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDERR should exactly match:
      """
      FATAL: Binary hash verification failed for dir2/file21.py
      """

Feature: Feature 7 - Line Ending and Whitespace Handling
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)
  # Standard Structure Assumption: dir3/file31.py, dir2/file21.py

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # POSITIVE SCENARIO 23: Line Ending Normalization (LF to CRLF)
  # Complexity: Verifying that the patcher auto-detects DOS format and normalizes the LF patch in-memory.
  Scenario: Successful Patching of a DOS File using a Unix Patch
    Given a file "/mnt/data/sources/dir3/file31.py" with content:
      """
      def main():\r\n    print("Start")\r\n
      """
    And a patch file "/home/user/patches/unix.patch" with Unix (LF) endings:
      """
      --- dir3/file31.py\n+++ dir3/file31.py\n@@ -2,1 +2,1 @@\n-    print("Start")\n+    print("End")\n
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/unix.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir3/file31.py" should exactly match:
      """
      def main():\r\n    print("End")\r\n
      """
    And STDOUT should exactly match:
      """
      Detected DOS line endings in dir3/file31.py.
      1 hunk applied successfully.
      """
    And STDERR should exactly match:
      """
      """

  # NEGATIVE SCENARIO 23: Strict Whitespace Mismatch
  # Complexity: Ensuring the patcher rejects a hunk if trailing spaces differ in default strict mode.
  Scenario: Failure on Trailing Whitespace Mismatch in Default Strict Mode
    Given a file "/mnt/data/sources/dir2/file21.py" with content:
      """
      value = 100  
      """
    # Note: Above line has 2 trailing spaces. Patch below has 0.
    And a patch file "/home/user/patches/ws_mismatch.patch" with content:
      """
      --- dir2/file21.py
      +++ dir2/file21.py
      @@ -1,1 +1,1 @@
      -value = 100
      +value = 200
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/ws_mismatch.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir2/file21.py" should exactly match:
      """
      value = 100  
      """
    And STDERR should exactly match:
      """
      Hunk match failed for dir2/file21.py: Whitespace mismatch at line 1.
      """
    And STDOUT should exactly match:
      """
      """

  # POSITIVE SCENARIO 24: Indentation Relaxation
  # Complexity: Using --ignore-leading-whitespace to patch code with different tab/space indentation.
  Scenario: Successful Patching with Leading Whitespace Relaxation
    Given a file "/mnt/data/sources/dir3/file31.py" with content:
      """
      \t\tlog.info("Process")
      """
    # Note: Main file uses tabs. Patch uses 8 spaces.
    And a patch file "/home/user/patches/indent.patch" with content:
      """
      --- dir3/file31.py
      +++ dir3/file31.py
      @@ -1,1 +1,1 @@
      -        log.info("Process")
      +        log.info("Complete")
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/indent.patch --directory=/mnt/data/sources --ignore-leading-whitespace
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir3/file31.py" should exactly match:
      """
      \t\tlog.info("Complete")
      """
    And STDOUT should exactly match:
      """
      1 hunk applied successfully (Ignoring leading whitespace).
      """

  # NEGATIVE SCENARIO 24: Inconsistent Line Endings in Patch
  # Complexity: Rejection of a patch file that mixes CRLF and LF internally, violating standard unified diff format.
  Scenario: Failure on Inconsistent Line Endings within Patch File
    Given a file "/mnt/data/sources/dir2/file21.py" with content:
      """
      content
      """
    And a patch file "/home/user/patches/mixed_patch.patch" with mixed endings:
      """
      --- dir2/file21.py\n+++ dir2/file21.py\r\n-content\n+new\n
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/mixed_patch.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDERR should exactly match:
      """
      FATAL: Invalid patch format - Inconsistent line endings detected in patch file.
      """

Feature: Feature 8 - Encoding Detection and Adaptation
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)
  # Standard Structure Assumption: dir3/file32.py, dir2/file21.py

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # POSITIVE SCENARIO 25: UTF-8 Patch to UTF-16 Target
  # Complexity: Verifying on-the-fly transcoding of patch content to match the target file's encoding.
  Scenario: Successful Patching of a UTF-16 File using a UTF-8 Patch
    Given a file "/mnt/data/sources/dir3/file32.py" encoded in "UTF-16BE" with content:
      """
      # International Logic
      print("你好")
      """
    And a patch file "/home/user/patches/utf8_to_utf16.patch" encoded in "UTF-8" with content:
      """
      --- dir3/file32.py
      +++ dir3/file32.py
      @@ -2,1 +2,1 @@
      -print("你好")
      +print("你好, 世界")
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/utf8_to_utf16.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir3/file32.py" should be encoded in "UTF-16BE"
    And the file "/mnt/data/sources/dir3/file32.py" should exactly match:
      """
      # International Logic
      print("你好, 世界")
      """
    And STDOUT should exactly match:
      """
      Detected encoding: UTF-16BE for dir3/file32.py
      Transcoded patch to match target encoding.
      1 hunk applied successfully.
      """
    And STDERR should exactly match:
      """
      """

  # NEGATIVE SCENARIO 25: Unsupported Encoding Detection
  # Complexity: Rejection of the operation if the file contains an encoding that cannot be reliably transcoded.
  Scenario: Failure when Target File Encoding is Unrecognized or Corrupted
    Given a file "/mnt/data/sources/dir2/file21.py" containing invalid byte sequences for any standard encoding
    And a patch file "/home/user/patches/standard.patch" with content:
      """
      --- dir2/file21.py
      +++ dir2/file21.py
      -old
      +new
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/standard.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDERR should exactly match:
      """
      FATAL: Could not detect character encoding for dir2/file21.py.
      """
    And STDOUT should exactly match:
      """
      """

  # POSITIVE SCENARIO 26: Preservation of Byte Order Mark (BOM)
  # Complexity: Ensuring that if the target file has a BOM, the patched output also includes it.
  Scenario: Successful Patching with BOM Preservation
    Given a file "/mnt/data/sources/dir3/file31.py" encoded in "UTF-8-SIG" (with BOM)
      """
      # BOM test
      """
    And a patch file "/home/user/patches/bom_preservation.patch"
      """
      --- dir3/file31.py
      +++ dir3/file31.py
      - # BOM test
      + # BOM preserved
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/bom_preservation.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir3/file31.py" should start with the UTF-8 BOM bytes
    And the file "/mnt/data/sources/dir3/file31.py" should exactly match:
      """
      # BOM preserved
      """
    And STDOUT should exactly match:
      """
      Detected UTF-8 BOM in dir3/file31.py.
      1 hunk applied successfully.
      """

  # NEGATIVE SCENARIO 26: Patch Transcoding Conflict
  # Complexity: Handling a scenario where the patch contains characters that cannot exist in the target file's encoding.
  Scenario: Failure when Patch Content is Incompatible with Target Encoding
    Given a file "/mnt/data/sources/dir2/file21.py" encoded in "ASCII"
      """
      # ASCII content
      """
    And a patch file "/home/user/patches/unicode.patch" encoded in "UTF-8" containing "emoji: 🚀"
      """
      --- dir2/file21.py
      +++ dir2/file21.py
      - # ASCII content
      + # ASCII content 🚀
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/unicode.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDERR should exactly match:
      """
      FATAL: Content in patch cannot be represented in target encoding (ASCII).
      """

Feature: Feature 9 - Backup and Safety Mechanisms
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)
  # Standard Structure Assumption: dir1/file1.py, dir2/file22.json

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # POSITIVE SCENARIO 27: Backup Creation Success
  # Complexity: Verifying that --backup creates a persistent .orig copy of the pre-patched file.
  Scenario: Successful Patching with Original File Backup
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      print("Version 1.0")
      """
    And a patch file "/home/user/patches/version_bump.patch" with content:
      """
      --- dir1/file1.py
      +++ dir1/file1.py
      @@ -1,1 +1,1 @@
      -print("Version 1.0")
      +print("Version 1.1")
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/version_bump.patch --directory=/mnt/data/sources --backup
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir1/file1.py" should exactly match:
      """
      print("Version 1.1")
      """
    And the file "/mnt/data/sources/dir1/file1.py.orig" should exist
    And the file "/mnt/data/sources/dir1/file1.py.orig" should exactly match:
      """
      print("Version 1.0")
      """
    And STDOUT should exactly match:
      """
      Created backup: dir1/file1.py.orig
      Applied: 1 hunk to dir1/file1.py
      """

  # NEGATIVE SCENARIO 27: Backup Write Failure
  # Complexity: Ensuring the patcher fails if it cannot write the backup file (e.g., read-only filesystem or permission error).
  Scenario: Failure when Backup File Cannot be Created
    Given a file "/mnt/data/sources/dir1/file1.py" exists
    And the directory "/mnt/data/sources/dir1" is read-only
    And a patch file "/home/user/patches/generic.patch" with content:
      """
      --- dir1/file1.py
      +++ dir1/file1.py
      -old
      +new
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/generic.patch --directory=/mnt/data/sources --backup
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir1/file1.py" should remain unchanged
    And STDERR should exactly match:
      """
      FATAL: Permission denied - Could not create backup file dir1/file1.py.orig
      """

  # POSITIVE SCENARIO 28: Dry-Run Simulation
  # Complexity: Verifying that --dry-run reports success but performs zero disk writes.
  Scenario: Successful Simulation of a Multi-file Patch
    Given a file "/mnt/data/sources/dir2/file22.json" with content:
      """
      {"active": true}
      """
    And a patch file "/home/user/patches/dry_run_test.patch" with content:
      """
      --- dir2/file22.json
      +++ dir2/file22.json
      @@ -1,1 +1,1 @@
      -{"active": true}
      +{"active": false}
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/dry_run_test.patch --directory=/mnt/data/sources --dry-run
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir2/file22.json" should exactly match:
      """
      {"active": true}
      """
    And STDOUT should exactly match:
      """
      [DRY-RUN] Hunk 1 for dir2/file22.json: Match found.
      Simulation complete: 1 hunk would be applied. No files modified.
      """

  # NEGATIVE SCENARIO 28: Dry-Run Failure Detection
  # Complexity: Ensuring --dry-run accurately predicts a failure without needing to touch the disk.
  Scenario: Simulation Correctly Identifies Hunk Failure
    Given a file "/mnt/data/sources/dir2/file22.json" with content:
      """
      {"active": true}
      """
    And a patch file "/home/user/patches/fail_predict.patch" with content:
      """
      --- dir2/file22.json
      +++ dir2/file22.json
      -{"active": MISSING_CONTEXT}
      +{"active": false}
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/fail_predict.patch --directory=/mnt/data/sources --dry-run
      """
    Then the exit code should be 2
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      [DRY-RUN] Hunk 1 for dir2/file22.json: Context mismatch.
      Simulation failed: 1 hunk would fail to apply.
      """

Feature: Feature 10 - Logging and Verbosity Levels
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)
  # Strategy: Verifying output granularity across defined levels (0 to 3).

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # POSITIVE SCENARIO 29: Level 0 (Silent Mode)
  # Complexity: Ensuring zero console output while returning a success code.
  Scenario: Successful Patching in Silent Mode
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      # Code
      """
    And a patch file "/home/user/patches/silent.patch" with content:
      """
      --- dir1/file1.py
      +++ dir1/file1.py
      @@ -1,1 +1,1 @@
      -# Code
      +# Updated
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/silent.patch --directory=/mnt/data/sources --verbose=0
      """
    Then the exit code should be 0
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      """
    And the file "/mnt/data/sources/dir1/file1.py" should contain "# Updated"

  # NEGATIVE SCENARIO 29: Level 1 (Default) Error Reporting
  # Complexity: Verifying that critical failures are reported to STDERR even at the lowest non-silent level.
  Scenario: Reporting Critical Failure at Default Logging Level
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      # Target
      """
    And a patch file "/home/user/patches/fail.patch" with content:
      """
      --- dir1/file1.py
      +++ dir1/file1.py
      @@ -1,1 +1,1 @@
      -# Mismatched_Context
      +# Updated
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/fail.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And STDOUT should exactly match:
      """
      """
    And STDERR should exactly match:
      """
      Hunk 1 failed for dir1/file1.py: Context mismatch.
      """

  # POSITIVE SCENARIO 30: Level 2 (Verbose) Tracing
  # Complexity: Verifying that filters and detected environmental factors are logged.
  Scenario: Detailed Tracing of Filters and Encodings at Level 2
    Given a file "/mnt/data/sources/dir2/file21.py" with content:
      """
      # Python Code
      """
    And a file "/mnt/data/sources/dir2/file22.json" with content:
      """
      {}
      """
    And a patch file "/home/user/patches/multi.patch" targeting both files.
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/multi.patch --directory=/mnt/data/sources --include="**/*.py" --verbose=2
      """
    Then the exit code should be 0
    And STDOUT should exactly match:
      """
      [INFO] Detected encoding: UTF-8 for dir2/file21.py
      [INFO] Detected line endings: LF for dir2/file21.py
      [INFO] Applied: 1 hunk to dir2/file21.py
      [SKIP] File dir2/file22.json excluded by glob filter
      """

  # POSITIVE SCENARIO 31: Level 3 (Debug) Byte-Level Output
  # Complexity: Verifying that exact sliding window offsets are reported.
  Scenario: Reporting Exact Window Offsets at Debug Level
    Given a file "/mnt/data/sources/dir3/file32.py" where target is shifted 5 lines
    And a patch file "/home/user/patches/shifted.patch"
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/shifted.patch --directory=/mnt/data/sources --max-offset=10 --verbose=3
      """
    Then the exit code should be 0
    And STDOUT should exactly match:
      """
      [DEBUG] Scanning for hunk context...
      [DEBUG] Match failed at line 1 (strict)
      [DEBUG] Attempting offset 1... fail
      [DEBUG] Attempting offset 2... fail
      [DEBUG] Attempting offset 3... fail
      [DEBUG] Attempting offset 4... fail
      [DEBUG] Attempting offset 5... SUCCESS
      [INFO] Applied hunk with offset 5.
      """

Feature: Feature 11 - Similarity and Dissimilarity Indices
  # Grounding: /opt/bin/patcher (EXE), /home/user/workspace (CWD), /mnt/data/sources (SRC), /home/user/patches (PATCH)
  # Strategy: Testing how similarity headers influence the search window and how dissimilarity triggers warnings.

  Background:
    Given the patcher executable is installed at "/opt/bin/patcher"
    And the current working directory is "/home/user/workspace"
    And the target source files are located in "/mnt/data/sources"
    And the patch files are located in "/home/user/patches"

  # POSITIVE SCENARIO 32: High Similarity Auto-Expansion
  # Complexity: Verifying that "similarity index 100%" automatically allows a vertical search even if --max-offset is not provided.
  Scenario: High Similarity Index Automatically Enables Sliding Window
    Given a file "/mnt/data/sources/dir1/file1.py" with content:
      """
      # Header
      # Noise
      print("Target")
      """
    And a patch file "/home/user/patches/high_sim.patch" with content:
      """
      --- dir1/file1.py
      +++ dir1/file1.py
      similarity index 100%
      @@ -1,1 +1,1 @@
      -print("Target")
      +print("Found")
      """
    # Note: "print" is at line 3, but hunk says line 1.
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/high_sim.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 0
    And the file "/mnt/data/sources/dir1/file1.py" should exactly match:
      """
      # Header
      # Noise
      print("Found")
      """
    And STDOUT should exactly match:
      """
      High similarity detected (100%).
      Applied: 1 hunk to dir1/file1.py at line 3 (offset 2).
      """
    And STDERR should exactly match:
      """
      """

  # NEGATIVE SCENARIO 32: Dissimilarity Warning/Abort
  # Complexity: Verifying that a low similarity index (or high dissimilarity) triggers a safety abort in default mode.
  Scenario: Low Similarity Index Triggers Safety Abort
    Given a file "/mnt/data/sources/dir2/file21.py" with content:
      """
      # Major refactor happened here
      # content is totally different
      """
    And a patch file "/home/user/patches/low_sim.patch" with content:
      """
      --- dir2/file21.py
      +++ dir2/file21.py
      similarity index 10%
      @@ -1,1 +1,1 @@
      -old_content
      +new_content
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/low_sim.patch --directory=/mnt/data/sources
      """
    Then the exit code should be 2
    And the file "/mnt/data/sources/dir2/file21.py" should remain unchanged
    And STDERR should exactly match:
      """
      FATAL: Similarity index too low (10%). Hunk application aborted for safety.
      """

  # POSITIVE SCENARIO 33: Forced Dissimilar Application
  # Complexity: Overriding the dissimilarity warning using a force or global flag.
  Scenario: Forced Application Despite High Dissimilarity
    Given a file "/mnt/data/sources/dir3/file31.json" with content:
      """
      {
        "meta": "changed"
      }
      """
    And a patch file "/home/user/patches/dissim.patch" with content:
      """
      --- dir3/file31.json
      +++ dir3/file31.json
      dissimilarity index 90%
      - {
      -   "meta": "old"
      - }
      + {
      +   "meta": "changed"
      + }
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/dissim.patch --directory=/mnt/data/sources --fuzz=5
      """
    Then the exit code should be 0
    And STDOUT should exactly match:
      """
      WARNING: High dissimilarity (90%).
      Applied: 1 hunk to dir3/file31.json (Forced via fuzz/offset).
      """

  # NEGATIVE SCENARIO 33: Conflict between Similarity and Strict Mode
  # Complexity: Ensuring that --strict flag overrides the automatic offset expansion of the similarity index.
  Scenario: Strict Mode Overrides Similarity Offset Expansion
    Given a file "/mnt/data/sources/dir1/file1.py" where "Target" is at line 3
    And a patch file "/home/user/patches/sim_strict.patch" with content:
      """
      --- dir1/file1.py
      +++ dir1/file1.py
      similarity index 100%
      @@ -1,1 +1,1 @@
      -print("Target")
      +print("Strict")
      """
    When I run the following command:
      """
      /opt/bin/patcher apply /home/user/patches/sim_strict.patch --directory=/mnt/data/sources --strict
      """
    Then the exit code should be 2
    And STDERR should exactly match:
      """
      Hunk match failed at line 1: Strict mode enabled (Offset expansion disabled).
      """
