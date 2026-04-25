import unittest
import os
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path

class TestFUDPPatcher(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp()
        self.src_dir = os.path.join(self.test_root, "src")
        os.makedirs(self.src_dir)
        # Anchor to the production script
        base_path = Path(__file__).parent.parent
        self.patcher_exe = os.path.abspath(base_path / "src" / "hud-patcher.py")

    def tearDown(self):
        shutil.rmtree(self.test_root)

    def write_file(self, path, content):
        """Helper to write source files to the sandbox."""
        p = os.path.join(self.src_dir, path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', newline='') as f: 
            f.write(content)
        return p

    def run_p(self, args):
        """Helper to execute the patcher CLI."""
        cmd = [sys.executable, self.patcher_exe] + args
        return subprocess.run(cmd, capture_output=True, text=True)

    # --- SPRINT 2: MATCHING TESTS ---

    # def test_2_1_positive_exact_match(self):
    #     target = self.write_file("file1.py", "line1\nline2\nline3\n")
    #     patch = os.path.join(self.test_root, "test.patch")
    #     with open(patch, 'w', newline='') as f:
    #         f.write("--- file1.py\n+++ file1.py\n@@ -2,1 +2,1 @@\n-line2\n+modified\n")
    #     res = self.run_p([patch, "-d", self.src_dir])
    #     self.assertEqual(res.returncode, 0)
    #     with open(target, 'r') as f: 
    #         self.assertEqual(f.read(), "line1\nmodified\nline3\n")

    # # --- SPRINT 3: RENAME TESTS ---

    # def test_3_1_positive_rename_and_edit(self):
    #     target = self.write_file("old.py", "line1\n")
    #     patch = os.path.join(self.test_root, "rename.patch")
    #     with open(patch, 'w', newline='') as f:
    #         f.write("--- old.py\n+++ new.py\nrename from old.py\nrename to new.py\n@@ -1,1 +1,1 @@\n-line1\n+line2\n")
    #     res = self.run_p([patch, "-d", self.src_dir])
    #     self.assertEqual(res.returncode, 0)
    #     self.assertFalse(os.path.exists(target))
    #     with open(os.path.join(self.src_dir, "new.py")) as f:
    #         self.assertEqual(f.read(), "line2\n")

    # def test_3_2_positive_identity_redirection(self):
    #     self.write_file("a.py", "content\n")
    #     patch = os.path.join(self.test_root, "multi.patch")
    #     with open(patch, 'w', newline='') as f:
    #         f.write("--- a.py\n+++ b.py\nrename from a.py\nrename to b.py\n"
    #                 "--- a.py\n+++ a.py\n@@ -1,1 +1,1 @@\n-content\n+updated\n")
    #     res = self.run_p([patch, "-d", self.src_dir])
    #     self.assertEqual(res.returncode, 0)
    #     with open(os.path.join(self.src_dir, "b.py")) as f:
    #         self.assertEqual(f.read(), "updated\n")

    # def test_4_1_positive_fuzz_factor(self):
    #     # Disk has v1.2, Patch has v1.0. Should pass with --fuzz=1
    #     self.write_file("app.cfg", "version=1.2\nstatus=ok\n")
    #     patch = os.path.join(self.test_root, "fuzz.patch")
    #     with open(patch, 'w', newline='') as f:
    #         f.write("--- app.cfg\n+++ app.cfg\n@@ -1,2 +1,2 @@\n-version=1.0\n+version=2.0\n status=ok\n")
        
    #     # Should fail with default fuzz 0
    #     res_fail = self.run_p([patch, "-d", self.src_dir])
    #     self.assertEqual(res_fail.returncode, 2)

    #     # Should pass with fuzz 1
    #     res_pass = self.run_p([patch, "-d", self.src_dir, "--fuzz", "1"])
    #     self.assertEqual(res_pass.returncode, 0)
    #     with open(os.path.join(self.src_dir, "app.cfg")) as f:
    #         self.assertIn("version=2.0", f.read())

    # def test_4_2_positive_ignore_whitespace(self):
    #     # Disk uses Tabs, Patch uses 4 Spaces
    #     self.write_file("code.py", "\tprint('hello')\n")
    #     patch = os.path.join(self.test_root, "ws.patch")
    #     with open(patch, 'w', newline='') as f:
    #         f.write("--- code.py\n+++ code.py\n@@ -1,1 +1,1 @@\n-    print('hello')\n+    print('world')\n")
        
    #     # Fail without flag
    #     res_fail = self.run_p([patch, "-d", self.src_dir])
    #     self.assertEqual(res_fail.returncode, 2)

    #     # Pass with --ignore-leading-whitespace
    #     res_pass = self.run_p([patch, "-d", self.src_dir, "--ignore-leading-whitespace"])
    #     self.assertEqual(res_pass.returncode, 0)
    #     with open(os.path.join(self.src_dir, "code.py")) as f:
    #         # Should preserve the original indentation style (Tab)
    #         self.assertEqual(f.read(), "\tprint('world')\n")


    def test_5_1_positive_binary_literal(self):
        target = os.path.join(self.src_dir, "file.bin")
        # Git binary patch for 5 bytes: "Hello"
        patch_content = (
            "--- file.bin\n+++ file.bin\n"
            "GIT binary patch\nliteral 5\nHcmZ>V&OEpl\n\n"
        )
        patch = os.path.join(self.test_root, "bin.patch")
        with open(patch, 'w') as f: f.write(patch_content)
        
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        with open(target, 'rb') as f:
            self.assertEqual(f.read(), b"Hello")

    def test_5_2_positive_binary_creation(self):
        patch_content = (
            "--- /dev/null\n+++ new.bin\n"
            "GIT binary patch\nliteral 4\nGcmZ>V&O\n\n"
        )
        patch = os.path.join(self.test_root, "create_bin.patch")
        with open(patch, 'w') as f: f.write(patch_content)
        
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.src_dir, "new.bin")))

if __name__ == "__main__":
    unittest.main()
