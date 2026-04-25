#!/usr/bin/env python3
"""
FUD Patcher Test Runner
Filename: fud-patcher-test-runner.py
Revision: 1.6.0 (Full Suite)
Description: Exhaustive character-exact test suite for fud-patcher.py.
"""

import os
import sys
import shutil
import unittest
import subprocess
import tempfile
import re
from pathlib import Path

class TestFUDPPatcher(unittest.TestCase):
    def setUp(self):
        """Rule 1.5.0: Environmental Isolation"""
        # Locate the patcher relative to this script: project_root/src/fud-patcher.py
        base_path = Path(__file__).parent.parent
        self.patcher_exe = os.path.abspath(base_path / "src" / "fud-patcher.py")
        
        if not os.path.exists(self.patcher_exe):
            self.fail(f"Patcher executable not found at {self.patcher_exe}")

        # Execution Sandbox (Isolated from project folders)
        self.test_root = tempfile.mkdtemp()
        self.cwd_path = os.path.join(self.test_root, "workspace")
        self.src_path = os.path.join(self.test_root, "sources")
        self.patch_dir = os.path.join(self.test_root, "patches")

        for d in [self.cwd_path, self.src_path, self.patch_dir]:
            os.makedirs(d)

        self.init_standard_structure()

    def tearDown(self):
        shutil.rmtree(self.test_root)

    def init_standard_structure(self):
        """Standard Structure Rule: dir1/file1.py, dir2/file21.py, etc."""
        structure = [
            "dir1/file1.py", "dir2/file21.py", "dir2/file22.json",
            "dir3/file31.json", "dir3/file31.py", "dir3/file32.json",
            "dir3/file32.py", "dir4/file41.bin"
        ]
        for rel_path in structure:
            p = os.path.join(self.src_path, os.path.normpath(rel_path))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding='utf-8') as f:
                f.write("# Standard Base Content\n")

    def run_patcher(self, args, input_cwd=None):
        cwd = input_cwd or self.cwd_path
        # We REMOVE the "apply" string from the args list if it's there
        # to match our current hud-patcher positional arg logic
        if "apply" in args:
            args.remove("apply")
            
        cmd = [sys.executable, self.patcher_exe] + args
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8')
        
        # Clean ANSI escape sequences so assertions like self.assertIn work
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        res.stdout = ansi_escape.sub('', res.stdout)
        res.stderr = ansi_escape.sub('', res.stderr)
        return res

    def write_src(self, rel_path, content, encoding='utf-8', mode='w'):
        p = os.path.join(self.src_path, os.path.normpath(rel_path))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        
        if 'b' in mode:
            # If content is string, encode it to bytes for 'wb' mode
            if isinstance(content, str):
                content = content.encode(encoding)
            with open(p, mode) as f:
                f.write(content)
        else:
            with open(p, mode, newline='', encoding=encoding) as f:
                f.write(content)

    def write_patch(self, name, content):
        p = os.path.join(self.patch_dir, name)
        with open(p, "w", newline='', encoding='utf-8') as f:
            f.write(content)
        return p

    # --- FEATURE 1: POSITIONAL & SEARCH ---

    def test_F1_P1_StrictPos_Positive(self):
        self.write_src("dir1/file1.py", "Line 1\nLine 2\nLine 3\n")
        p = self.write_patch("p.patch", "--- dir1/file1.py\n+++ dir1/file1.py\n@@ -2,1 +2,1 @@\n-Line 2\n+Line 2 mod\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Line 2 mod", open(os.path.join(self.src_path, "dir1/file1.py")).read())

    def test_F1_P1_StrictPos_Negative(self):
        self.write_src("dir1/file1.py", "Line 1\nLine 2\n")
        p = self.write_patch("p.patch", "--- dir1/file1.py\n+++ dir1/file1.py\n@@ -10,1 +10,1 @@\n-Line 2\n+Line 2 mod\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 2)
        self.assertIn("Hunk 1 match failed", res.stderr)

    def test_F1_P2_Search_Positive(self):
        self.write_src("dir2/file21.py", "def start():\n    process()\n")
        p = self.write_patch("p.patch", "--- dir2/file21.py\n+++ dir2/file21.py\n def start():\n-    process()\n+    execute()\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Applied via full-file literal search", res.stdout)

    def test_F1_P2_Search_Negative(self):
        self.write_src("dir2/file21.py", "def stop(): pass\n")
        p = self.write_patch("p.patch", "--- dir2/file21.py\n+++ dir2/file21.py\n-def start()\n+def init()\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 2)
        self.assertIn("Literal context not found", res.stderr)

    # --- FEATURE 3: IDENTITY SHIFTS ---

    def test_F3_P7_Rename_Positive(self):
        self.write_src("dir1/file1.py", "print('A')\n")
        p = self.write_patch("p.patch", "--- rename from dir1/file1.py\n+++ rename to dir1/renamed.py\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.src_path, "dir1/file1.py")))
        self.assertTrue(os.path.exists(os.path.join(self.src_path, "dir1/renamed.py")))

    def test_F3_P7_Rename_Negative_Collision(self):
        self.write_src("dir1/file1.py", "A")
        self.write_src("dir1/existing.py", "B")
        p = self.write_patch("p.patch", "--- rename from dir1/file1.py\n+++ rename to dir1/existing.py\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 2)
        self.assertIn("Destination already exists", res.stderr)

    # --- FEATURE 4: RECURSIVE CLEANUP ---

    def test_F4_P10_Cleanup_Positive(self):
        self.write_src("dir1/file1.py", "# delete")
        # Ensure dir1 only has this file for strict removal
        for f in os.listdir(os.path.join(self.src_path, "dir1")):
            if f != "file1.py": os.remove(os.path.join(self.src_path, "dir1", f))
        p = self.write_patch("p.patch", "--- dir1/file1.py\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-# delete\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.src_path, "dir1")))

    def test_F4_P10_Cleanup_Negative_OptionA(self):
        self.write_src("dir1/file1.py", "# delete")
        self.write_src("dir1/untracked.txt", "stay")
        p = self.write_patch("p.patch", "--- dir1/file1.py\n+++ /dev/null\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.isdir(os.path.join(self.src_path, "dir1")))
        self.assertIn("Skipped directory removal", res.stdout)

    # --- FEATURE 9: BINARY BASE85 ---

    def test_F9_P19_Binary_Positive(self):
        self.write_src("dir4/file41.bin", "seed", mode='wb')
        p = self.write_patch("p.patch", "--- dir4/file41.bin\n+++ dir4/file41.bin\nGIT binary patch\nliteral 5\nzcmZ>V&OEpl\n\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 0)

    def test_F9_P20_Binary_Negative_CorruptB85(self):
        p = self.write_patch("p.patch", "--- /dev/null\n+++ dir4/corrupt.bin\nGIT binary patch\nliteral 5\nzcmZ_INVALID_!\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 2)
        self.assertIn("Invalid Base85 character", res.stderr)

    # --- FEATURE 11: SYMBOLIC LINKS ---

    def test_F11_P23_Symlink_Positive(self):
        if sys.platform == "win32": self.skipTest("Symlink test requires Unix/Admin on Win")
        self.write_src("dir2/file21.py", "x = 1")
        os.symlink("file21.py", os.path.join(self.src_path, "dir2/alias.py"))
        p = self.write_patch("p.patch", "--- dir2/alias.py\n+++ dir2/alias.py\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 0)
        self.assertIn("x = 2", open(os.path.join(self.src_path, "dir2/file21.py")).read())

    # --- FEATURE 14: AMBIGUITY ---

    def test_F14_P31_Ambiguity_Negative_127(self):
        self.write_src("dir2/file22.json", "active\nactive\n")
        p = self.write_patch("p.patch", "--- dir2/file22.json\n+++ dir2/file22.json\n-active\n+inactive\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path, "--strict"])
        self.assertEqual(res.returncode, 127)
        self.assertIn("Ambiguous match", res.stderr)

    def test_F14_P31_Ambiguity_Positive_Global(self):
        self.write_src("dir2/file22.json", "active\nactive\n")
        p = self.write_patch("ambig.patch", "--- dir2/file22.json\n+++ dir2/file22.json\n-active\n+inactive\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path, "--global"])
        self.assertEqual(res.returncode, 0)
        # FIX: Use Context Manager
        with open(os.path.join(self.src_path, "dir2/file22.json"), 'r') as f:
            content = f.read()
        self.assertEqual(content.count("inactive"), 2)

    def test_F1_P1_StrictPos_Positive(self):
        self.write_src("dir1/file1.py", "Line 1\nLine 2\n")
        p = self.write_patch("hit.patch", "--- dir1/file1.py\n+++ dir1/file1.py\n@@ -2,1 +2,1 @@\n-Line 2\n+Line 2 mod\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 0)

    def test_F3_P7_Rename_Positive(self):
        self.write_src("dir1/file1.py", "content")
        p = self.write_patch("ren.patch", "--- rename from dir1/file1.py\n+++ rename to dir1/new.py\n")
        res = self.run_patcher(["apply", p, "-d", self.src_path])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_path, "dir1/new.py")))

if __name__ == "__main__":
    unittest.main()