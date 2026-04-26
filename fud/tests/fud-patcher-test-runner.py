import unittest
import os
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path

class TestFUDPatcher(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp()
        self.src_dir = os.path.join(self.test_root, "src")
        os.makedirs(self.src_dir)
        base_path = Path(__file__).parent.parent
        self.patcher_exe = os.path.abspath(base_path / "src" / "fud-patcher.py")

    def tearDown(self):
        shutil.rmtree(self.test_root)
        # print(f"\n[INSPECT] Test files preserved at: {self.test_root}")

    def write_file(self, path, content, mode='w'):
        p = os.path.join(self.src_dir, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if 'b' in mode:
            with open(p, 'wb') as f: f.write(content)
        else:
            # Force UTF-8 and prevent Windows \r\n translation
            with open(p, 'w', newline='\n', encoding='utf-8') as f: 
                f.write(content)
        return p

    def run_p(self, args):
        test_name = self.id().split('.')[-1]
        env = dict(os.environ)
        env["FUD_TRACE_ID"] = test_name
        cmd = [sys.executable, self.patcher_exe] + args
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=env)
        
        if res.returncode != 0:
            # Persistent Failure Logging
            fail_log = os.path.join(os.path.dirname(__file__), "test_failures.log")
            with open(fail_log, "a", encoding="utf-8") as fl:
                fl.write(f"\n{'='*80}\n")
                fl.write(f"FAILURE IN: {test_name}\n")
                fl.write(f"COMMAND: {' '.join(args)}\n")
                fl.write(f"EXIT CODE: {res.returncode}\n")
                fl.write(f"{'-'*40}\nSTDERR:\n{res.stderr}\n")
                fl.write(f"{'-'*40}\nSTDOUT:\n{res.stdout}\n")
                
                # Pull the specific trace from patcher.log
                patcher_log = os.path.join(os.path.dirname(self.patcher_exe), "patcher.log")
                if os.path.exists(patcher_log):
                    with open(patcher_log, 'r', encoding='utf-8') as pl:
                        trace = [l for l in pl if f"[{test_name}]" in l]
                        fl.write(f"{'-'*40}\nPATCHER TRACE:\n{''.join(trace)}\n")

            print(f"\n--- [FAIL] {test_name} (Details written to test_failures.log) ---")
        return res

    # --- SPRINT 2: MATCHING ---
    def test_2_1_positive_exact_match(self):
        target = self.write_file("file1.py", "line1\nline2\nline3\n")
        patch = self.write_file("test.patch", "--- file1.py\n+++ file1.py\n@@ -2,1 +2,1 @@\n-line2\n+modified\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        with open(target, 'r') as f: self.assertEqual(f.read(), "line1\nmodified\nline3\n")

    # --- SPRINT 3: RENAMES ---
    def test_3_1_positive_rename_and_edit(self):
        target = self.write_file("old.py", "line1\n")
        patch = self.write_file("rename.patch", "--- old.py\n+++ new.py\nrename from old.py\nrename to new.py\n@@ -1,1 +1,1 @@\n-line1\n+line2\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "new.py")))

    def test_3_2_positive_identity_redirection(self):
        self.write_file("a.py", "content\n")
        patch = self.write_file("multi.patch", "--- a.py\n+++ b.py\nrename from a.py\nrename to b.py\n--- a.py\n+++ a.py\n@@ -1,1 +1,1 @@\n-content\n+updated\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        with open(os.path.join(self.src_dir, "b.py")) as f: self.assertEqual(f.read(), "updated\n")

    # --- SPRINT 4: TOLERANCE ---
    def test_4_1_positive_fuzz_factor(self):
        self.write_file("app.cfg", "version=1.2\nstatus=ok\n")
        patch = self.write_file("fuzz.patch", "--- app.cfg\n+++ app.cfg\n@@ -1,2 +1,2 @@\n-version=1.0\n+version=2.0\n status=ok\n")
        res_pass = self.run_p([patch, "-d", self.src_dir, "--fuzz", "1"])
        self.assertEqual(res_pass.returncode, 0)

    def test_4_2_positive_ignore_whitespace(self):
        self.write_file("code.py", "\tprint('hello')\n")
        patch = self.write_file("ws.patch", "--- code.py\n+++ code.py\n@@ -1,1 +1,1 @@\n-    print('hello')\n+    print('world')\n")
        res_pass = self.run_p([patch, "-d", self.src_dir, "--ignore-leading-whitespace"])
        self.assertEqual(res_pass.returncode, 0)
        with open(os.path.join(self.src_dir, "code.py")) as f: self.assertEqual(f.read(), "\tprint('world')\n")

    # --- SPRINT 5: BINARY ---
    def test_5_1_positive_binary_literal(self):
        target = self.write_file("file.bin", b"seed", mode='wb')
        patch = self.write_file("bin.patch", "--- file.bin\n+++ file.bin\nGIT binary patch\nliteral 5\nHcmZ>V&OEpl\n\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)

    def test_5_2_positive_binary_creation(self):
        patch = self.write_file("create_bin.patch", "--- /dev/null\n+++ new.bin\nGIT binary patch\nliteral 4\nGcmZ>V&O\n\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "new.bin")))

    # --- SPRINT 6: HARDENING (The Missing 6) ---
    def test_6_1_negative_strip_out_of_bounds(self):
        patch = self.write_file("test.patch", "--- a/b/file.txt\n+++ a/b/file.txt\n")
        res = self.run_p([patch, "-p99", "-d", self.src_dir])
        self.assertEqual(res.returncode, 2)
        self.assertIn("removed all path components", res.stderr)

    def test_6_2_positive_mkdir_on_demand(self):
        patch_path = self.write_file("new_dir.patch", "--- /dev/null\n+++ new/subdir/file.txt\n@@ -0,0 +1,1 @@\n+data\n")
        res = self.run_p([patch_path, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "new/subdir/file.txt")))

    def test_6_3_negative_strict_offset_failure(self):
        """Verify Exit 2 when a hunk is shifted but offset is 0."""
        self.write_file("strict.txt", "extra\ntarget\n")
        # Patch thinks target is at line 1, but it's at line 2.
        patch = self.write_file("strict.patch", "--- strict.txt\n+++ strict.txt\n@@ -1,1 +1,1 @@\n-target\n+done\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 2)

    def test_6_4_negative_ambiguity_code_127(self):
        self.write_file("dupe.txt", "common\ncommon\n")
        patch = self.write_file("ambig.patch", "--- dupe.txt\n+++ dupe.txt\n-common\n+unique\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 127)

    def test_6_5_positive_complex_rename_chain(self):
        self.write_file("f_a.txt", "start\n")
        content = "--- f_a.txt\n+++ f_b.txt\nrename from f_a.txt\nrename to f_b.txt\n" \
                  "--- f_b.txt\n+++ f_c.txt\nrename from f_b.txt\nrename to f_c.txt\n"
        patch = self.write_file("chain.patch", content)
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "f_c.txt")))

    def test_6_6_negative_rename_source_missing(self):
        patch = self.write_file("ghost.patch", "--- ghost.txt\n+++ new.txt\nrename from ghost.txt\nrename to new.txt\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 2)

    def test_7_1_positive_recursive_cleanup(self):
        """Verify parent directory is removed when last file is deleted."""
        target = self.write_file("deep/dir/file.txt", "content")
        patch = self.write_file("del.patch", "--- deep/dir/file.txt\n+++ /dev/null\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "deep")))

    def test_7_2_positive_exclude_filter(self):
        """Verify --exclude skips specific files in a multi-file patch."""
        self.write_file("keep.py", "v1\n")
        self.write_file("skip.log", "data\n")
        patch_content = (
            "--- keep.py\n+++ keep.py\n@@ -1,1 +1,1 @@\n-v1\n+v2\n"
            "--- skip.log\n+++ skip.log\n@@ -1,1 +1,1 @@\n-data\n+new\n"
        )
        patch = self.write_file("filter.patch", patch_content)
        res = self.run_p([patch, "-d", self.src_dir, "--exclude", "*.log"])
        self.assertEqual(res.returncode, 0)
        with open(os.path.join(self.src_dir, "keep.py")) as f: self.assertIn("v2", f.read())
        with open(os.path.join(self.src_dir, "skip.log")) as f: self.assertIn("data", f.read())

    def test_7_3_negative_include_filter(self):
        """Verify file is untouched if it doesn't match --include."""
        self.write_file("other.txt", "orig")
        patch = self.write_file("inc.patch", "--- other.txt\n+++ other.txt\n-orig\n+new\n")
        # Include only .py files
        res = self.run_p([patch, "-d", self.src_dir, "--include", "*.py"])
        self.assertEqual(res.returncode, 0)
        with open(os.path.join(self.src_dir, "other.txt")) as f: self.assertEqual(f.read(), "orig")

    def test_7_4_positive_cleanup_ignore(self):
        """Verify directory survives if it contains a 'cleanup-ignore' file."""
        self.write_file("keep_dir/file.txt", "content")
        self.write_file("keep_dir/.gitkeep", "") # This file should save the dir
        patch = self.write_file("del.patch", "--- keep_dir/file.txt\n+++ /dev/null\n")
        res = self.run_p([patch, "-d", self.src_dir, "--cleanup-ignore", ".*"])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.src_dir, "keep_dir")))

    def test_7_5_negative_identity_conflict(self):
        """Verify Exit 2 when a path is moved twice in one session."""
        self.write_file("orig.txt", "data")
        patch_content = (
            "--- orig.txt\n+++ first.txt\nrename from orig.txt\nrename to first.txt\n"
            "--- orig.txt\n+++ second.txt\nrename from orig.txt\nrename to second.txt\n"
        )
        patch = self.write_file("conflict.patch", patch_content)
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 2)
        self.assertIn("Conflict", res.stderr)

    def test_7_6_negative_read_only_file(self):
        """Verify Exit 2 when target file is read-only."""
        import stat
        target = self.write_file("readonly.txt", "locked")
        # Make file read-only
        os.chmod(target, stat.S_IREAD)
        patch = self.write_file("mod.patch", "--- readonly.txt\n+++ readonly.txt\n@@ -1,1 +1,1 @@\n-locked\n+unlocked\n")
        try:
            res = self.run_p([patch, "-d", self.src_dir])
            self.assertEqual(res.returncode, 2)
        finally:
            # Cleanup permissions so tearDown can delete the folder
            os.chmod(target, stat.S_IWRITE)

    def test_7_7_negative_malformed_binary_header(self):
        """Verify Exit 2 on malformed binary metadata."""
        patch = self.write_file("corrupt_bin.patch", "--- a.bin\n+++ a.bin\nGIT binary patch\nnot_literal 5\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 2)

    def test_8_1_positive_reverse_content(self):
        """Verify adding a line can be reversed (removed)."""
        target = self.write_file("rev.txt", "line1\nline2\n")
        # Patch that adds "line2"
        patch = self.write_file("add.patch", "--- rev.txt\n+++ rev.txt\n@@ -1,1 +1,2 @@\n line1\n+line2\n")
        res = self.run_p([patch, "-d", self.src_dir, "--reverse"])
        self.assertEqual(res.returncode, 0)
        with open(target, 'r') as f:
            self.assertEqual(f.read(), "line1\n")

    def test_8_2_positive_reverse_rename(self):
        """Verify a rename A->B can be reversed back to A."""
        self.write_file("file_b.py", "content")
        # Patch that says rename A to B
        patch = self.write_file("rev_ren.patch", "--- file_a.py\n+++ file_b.py\nrename from file_a.py\nrename to file_b.py\n")
        res = self.run_p([patch, "-d", self.src_dir, "-R"])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "file_a.py")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "file_b.py")))

    def test_8_3_positive_reverse_deletion_to_creation(self):
        """Verify reversing a deletion results in file creation."""
        # Patch says delete 'ghost.txt'
        patch = self.write_file("rev_del.patch", "--- ghost.txt\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-data\n")
        # Reverse it -> should create ghost.txt
        res = self.run_p([patch, "-d", self.src_dir, "--reverse"])
        self.assertEqual(res.returncode, 0)
        target = os.path.join(self.src_dir, "ghost.txt")
        self.assertTrue(os.path.exists(target))
        with open(target, 'r') as f:
            self.assertEqual(f.read(), "data\n")

    def test_8_4_positive_reverse_binary_literal(self):
        """Verify reversing a binary literal (swap old/new)."""
        # Note: Git binary patches for literal usually contain both pre- and post-image.
        # For our simplified logic, reversing binary swaps the headers.
        target = self.write_file("bin.dat", b"new_data", mode='wb')
        # Patch intended to change 'old' to 'new'
        patch = self.write_file("rev_bin.patch", "--- old.dat\n+++ bin.dat\nGIT binary patch\nliteral 8\nHcmZ>V&OExk\n\n")
        # Reverse it -> should restore 'old' (if old_path was mapped)
        # For Sprint 8 literal: this verifies the header swap logic doesn't crash binary IO.
        res = self.run_p([patch, "-d", self.src_dir, "-R"])
        self.assertEqual(res.returncode, 0)

    def test_8_5_positive_reverse_creation_to_deletion(self):
        """Verify reversing a file creation results in file deletion."""
        target = self.write_file("new_to_be_deleted.txt", "data\n")
        # Patch that would create this file
        patch = self.write_file("create.patch", "--- /dev/null\n+++ new_to_be_deleted.txt\n@@ -0,0 +1,1 @@\n+data\n")
        # Reverse it -> should delete the file
        res = self.run_p([patch, "-d", self.src_dir, "--reverse"])
        self.assertEqual(res.returncode, 0)
        self.assertFalse(os.path.exists(target))

    def test_9_1_positive_continue_on_fail(self):
        """Verify session moves to file 2 if file 1 fails with --continue."""
        self.write_file("file1.txt", "v1")
        self.write_file("file2.txt", "v1")
        # Patch where hunk 1 mismatches file1, but hunk 2 matches file2
        patch_content = (
            "--- file1.txt\n+++ file1.txt\n@@ -1,1 +1,1 @@\n-wrong\n+new\n"
            "--- file2.txt\n+++ file2.txt\n@@ -1,1 +1,1 @@\n-v1\n+v2\n"
        )
        patch = self.write_file("cont.patch", patch_content)
        res = self.run_p([patch, "-d", self.src_dir, "--continue"])
        self.assertEqual(res.returncode, 1) # Exit 1 for Partial Success
        with open(os.path.join(self.src_dir, "file2.txt")) as f:
            self.assertEqual(f.read(), "v2\n")

    def test_10_1_positive_sequential_offsets(self):
        """Verify Hunk 2 uses the offset found by Hunk 1."""
        # Content shifted by 1 line
        self.write_file("seq.txt", "extra_line\nline1\nline2\n")
        # Patch expects lines at 1 and 2
        patch_content = (
            "--- seq.txt\n+++ seq.txt\n"
            "@@ -1,1 +1,1 @@\n-line1\n+new1\n"
            "@@ -2,1 +2,1 @@\n-line2\n+new2\n"
        )
        patch = self.write_file("seq.patch", patch_content)
        # Offset 0 means strict positional matching
        # Without sequential tracking, Hunk 2 would fail at line 2.
        res = self.run_p([patch, "-d", self.src_dir, "--max-offset", "5"])
        self.assertEqual(res.returncode, 0)

    def test_9_2_positive_continue_on_ambiguity(self):
        """Verify --continue skips files that return Exit 127 (Ambiguity)."""
        self.write_file("ambig.txt", "common\ncommon\n")
        self.write_file("next.txt", "v1\n")
        # File 1 is ambiguous (should return 127 inside the loop)
        # File 2 is simple. With --continue, session should end with Exit 1.
        patch_content = (
            "--- ambig.txt\n+++ ambig.txt\n-common\n+unique\n"
            "--- next.txt\n+++ next.txt\n@@ -1,1 +1,1 @@\n-v1\n+v2\n"
        )
        patch = self.write_file("cont_ambig.patch", patch_content)
        res = self.run_p([patch, "-d", self.src_dir, "--continue"])
        self.assertEqual(res.returncode, 1)
        with open(os.path.join(self.src_dir, "next.txt")) as f:
            self.assertEqual(f.read(), "v2\n")

    def test_9_3_negative_continue_fatal_exception(self):
        """Verify --continue still returns Exit 2 on system/IO fatal errors."""
        # Provide a patch file that doesn't exist to trigger the outer catch
        res = self.run_p(["nonexistent.patch", "-d", self.src_dir, "--continue"])
        self.assertEqual(res.returncode, 2)

    def test_10_2_positive_sequential_creation(self):
        """Verify sequential offsets don't interfere with new file creation."""
        # Apply a shifted hunk to File 1 to set a file_offset
        self.write_file("f1.txt", "extra\ntarget\n")
        # File 2 is a creation (old_path is /dev/null)
        patch_content = (
            "--- f1.txt\n+++ f1.txt\n@@ -1,1 +1,1 @@\n-target\n+done\n"
            "--- /dev/null\n+++ f2.txt\n@@ -0,0 +1,1 @@\n+new\n"
        )
        patch = self.write_file("seq_create.patch", patch_content)
        res = self.run_p([patch, "-d", self.src_dir, "--max-offset", "5"])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "f2.txt")))


    def test_p1_rename_plus_fuzz(self):
        """P1: Combine Identity move with Tolerance drift."""
        target = self.write_file("old.py", "v1.2\nstatus=ok\n")
        patch = self.write_file("p1.patch", "--- old.py\n+++ new.py\nrename from old.py\nrename to new.py\n@@ -1,1 +1,1 @@\n-v1.0\n+v2.0\n")
        # Needs --fuzz 1 to match v1.2 vs v1.0
        res = self.run_p([patch, "-d", self.src_dir, "--fuzz", "1"])
        self.assertEqual(res.returncode, 0)
        with open(os.path.join(self.src_dir, "new.py")) as f:
            self.assertIn("v2.0", f.read())

    def test_p5_exclude_binary(self):
        """P5: Ensure filtering works on non-text headers."""
        self.write_file("data.bin", b"original", mode='wb')
        patch = self.write_file("p5.patch", "--- data.bin\n+++ data.bin\nGIT binary patch\nliteral 5\nHcmZ>V&OEpl\n\n")
        # Exclude the binary file
        res = self.run_p([patch, "-d", self.src_dir, "--exclude", "*.bin"])
        self.assertEqual(res.returncode, 0)
        with open(os.path.join(self.src_dir, "data.bin"), 'rb') as f:
            self.assertEqual(f.read(), b"original") # Untouched

    def test_p7_strip_depth_permutation(self):
        """P7: Verify high-depth path stripping."""
        self.write_file("deep/path/target.txt", "orig")
        # Patch uses 3 levels (a/b/c)
        patch = self.write_file("p7.patch", "--- a/b/target.txt\n+++ a/b/target.txt\n@@ -1,1 +1,1 @@\n-orig\n+new\n")
        # -p2 should strip 'a/b/' leaving 'target.txt'.
        # We target the 'deep/path' directory.
        res = self.run_p([patch, "-d", os.path.join(self.src_dir, "deep/path"), "-p2"])
        self.assertEqual(res.returncode, 0)
        with open(os.path.join(self.src_dir, "deep/path/target.txt")) as f:
            self.assertEqual(f.read(), "new\n")

    def test_p2_reverse_creation_existing(self):
        """P2: Reverse a creation patch on a file that already exists (results in deletion)."""
        target = self.write_file("exists.txt", "data\n")
        patch = self.write_file("p2.patch", "--- /dev/null\n+++ exists.txt\n@@ -0,0 +1,1 @@\n+data\n")
        res = self.run_p([patch, "-d", self.src_dir, "--reverse"])
        self.assertEqual(res.returncode, 0)
        self.assertFalse(os.path.exists(target))

    def test_p3_global_reverse(self):
        """P3: Reverse a global patch that added content to multiple lines."""
        content = "line\ntarget\nline\ntarget\n"
        target = self.write_file("multi.txt", content)
        # Patch that adds "!" to "target"
        patch = self.write_file("p3.patch", "--- multi.txt\n+++ multi.txt\n-target\n+target!\n")
        # First, apply forward (global)
        self.run_p([patch, "-d", self.src_dir, "--global"])
        # Now, reverse it (global)
        res = self.run_p([patch, "-d", self.src_dir, "--global", "--reverse"])
        self.assertEqual(res.returncode, 0)
        with open(target, 'r') as f:
            self.assertEqual(f.read(), content)

    def test_p4_ws_plus_fuzz(self):
        """P4: Match a line with both indentation difference and context drift."""
        # Disk has v1.2 with Tab, Patch has v1.0 with Spaces
        self.write_file("code.py", "\tversion=1.2\n")
        patch = self.write_file("p4.patch", "--- code.py\n+++ code.py\n@@ -1,1 +1,1 @@\n-    version=1.0\n+    version=2.0\n")
        # Needs both flags
        res = self.run_p([patch, "-d", self.src_dir, "--ignore-leading-whitespace", "--fuzz", "1"])
        self.assertEqual(res.returncode, 0)
        with open(os.path.join(self.src_dir, "code.py")) as f:
            self.assertEqual(f.read(), "\tversion=2.0\n")

    def test_p6_continue_rename_collision(self):
        """P6: File 1 rename fails (collision); verify File 2 still gets patched."""
        self.write_file("file1.txt", "v1")
        self.write_file("collision.txt", "blocked") # This blocks file1 -> collision.txt
        self.write_file("file2.txt", "old")
        patch_content = (
            "--- file1.txt\n+++ collision.txt\nrename from file1.txt\nrename to collision.txt\n"
            "--- file2.txt\n+++ file2.txt\n@@ -1,1 +1,1 @@\n-old\n+new\n"
        )
        patch = self.write_file("p6.patch", patch_content)
        res = self.run_p([patch, "-d", self.src_dir, "--continue"])
        self.assertEqual(res.returncode, 1) # Partial Success
        with open(os.path.join(self.src_dir, "file2.txt")) as f:
            self.assertEqual(f.read(), "new\n")

    def test_p8_include_plus_cleanup(self):
        """P8: Delete two files in different dirs, but include only one. Verify parent dir survival."""
        self.write_file("keep_dir/stay.txt", "data")
        self.write_file("del_dir/go.txt", "data")
        patch_content = (
            "--- keep_dir/stay.txt\n+++ /dev/null\n"
            "--- del_dir/go.txt\n+++ /dev/null\n"
        )
        patch = self.write_file("p8.patch", patch_content)
        # Only allow deletion in del_dir
        res = self.run_p([patch, "-d", self.src_dir, "--include", "del_dir/*"])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "keep_dir/stay.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "del_dir")))

    def test_p9_sequence_plus_reverse(self):
        """P9: Reverse a 2-hunk patch where both hunks were originally shifted."""
        original = "extra\nline1\nline2\n"
        self.write_file("seq.txt", "extra\nnew1\nnew2\n") # File currently has 'new' state
        patch_content = (
            "--- seq.txt\n+++ seq.txt\n"
            "@@ -1,1 +1,1 @@\n-line1\n+new1\n"
            "@@ -2,1 +2,1 @@\n-line2\n+new2\n"
        )
        patch = self.write_file("p9.patch", patch_content)
        # Reverse to restore 'line1/2' at the shifted position
        res = self.run_p([patch, "-d", self.src_dir, "--reverse", "--max-offset", "5"])
        self.assertEqual(res.returncode, 0)
        with open(os.path.join(self.src_dir, "seq.txt")) as f:
            self.assertEqual(f.read(), original)

    def test_p10_identity_plus_binary(self):
        """P10: Move a binary file and apply a new literal hunk to it in one session."""
        self.write_file("old.bin", b"seed", mode='wb')
        # SURGICAL ADDITION: Create a visible copy to inspect the "pre-patch" state
        # shutil.copy(os.path.join(self.src_dir, "old.bin"), os.path.join(self.src_dir, "old_backup.bin"))

        patch_content = (
            "--- old.bin\n"
            "+++ new.bin\n"
            "rename from old.bin\n"
            "rename to new.bin\n"
            "GIT binary patch\n"
            "literal 5\n"
            "50000000000\n\n"
        )
        patch = self.write_file("p10.patch", patch_content)
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        target = os.path.join(self.src_dir, "new.bin")
        self.assertTrue(os.path.exists(target))
        with open(target, 'rb') as f:
            # prefix '5' + 10 zeros decodes to 5 null bytes
            self.assertEqual(f.read(), b"\x00\x00\x00\x00\x00")

    def test_p11_negative_invalid_base85_char(self):
        """P11: Verify codec returns empty buffer on invalid Base85 alphabet char."""
        # '?' is not in the Git Base85 alphabet
        patch_content = (
            "--- a.bin\n+++ a.bin\n"
            "GIT binary patch\nliteral 1\n?cmZ>\n\n"
        )
        patch = self.write_file("bad_char.patch", patch_content)
        # Should return Exit 2 because application fails due to empty buffer
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 2)

    def test_p12_negative_empty_binary_block(self):
        """P12: Verify session handles binary header without any data blocks."""
        patch_content = (
            "--- a.bin\n+++ a.bin\n"
            "GIT binary patch\n\n"
        )
        patch = self.write_file("no_data.patch", patch_content)
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 2)

    # --- SPRINT 0.10.0: DRY-RUN SAFETY ---

    def test_12_1_safety_dry_run_edit(self):
        """Verify file content is NOT changed during dry-run."""
        target = self.write_file("f1.txt", "original\n")
        patch = self.write_file("edit.patch", "--- f1.txt\n+++ f1.txt\n@@ -1,1 +1,1 @@\n-original\n+changed\n")
        res = self.run_p([patch, "-d", self.src_dir, "--dry-run"])
        self.assertEqual(res.returncode, 0)
        with open(target, 'r') as f:
            self.assertEqual(f.read(), "original\n")

    def test_12_2_safety_dry_run_rename(self):
        """Verify renames are NOT executed during dry-run."""
        self.write_file("old.txt", "data")
        patch = self.write_file("rename.patch", "--- old.txt\n+++ new.txt\nrename from old.txt\nrename to new.txt\n")
        res = self.run_p([patch, "-d", self.src_dir, "--dry-run"])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "old.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.src_dir, "new.txt")))

    def test_12_3_safety_dry_run_cleanup(self):
        """Verify recursive cleanup is NOT executed during dry-run."""
        self.write_file("empty_me/file.txt", "data")
        patch = self.write_file("del.patch", "--- empty_me/file.txt\n+++ /dev/null\n")
        res = self.run_p([patch, "-d", self.src_dir, "--dry-run"])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "empty_me/file.txt")))

    def test_12_4_safety_dry_run_mkdir(self):
        """Verify new directories are NOT created during dry-run."""
        new_dir_path = os.path.join(self.src_dir, "ghost_dir")
        # Patch that would create a file in a new directory
        patch = self.write_file("mkdir.patch", "--- /dev/null\n+++ ghost_dir/new.txt\n@@ -0,0 +1,1 @@\n+data\n")
        res = self.run_p([patch, "-d", self.src_dir, "--dry-run"])
        self.assertEqual(res.returncode, 0)
        # The directory should not exist on disk
        self.assertFalse(os.path.exists(new_dir_path))

if __name__ == "__main__":
    unittest.main()
