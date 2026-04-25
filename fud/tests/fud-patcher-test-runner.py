import unittest
import os
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path

class TestSprint2Matching(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp()
        self.src_dir = os.path.join(self.test_root, "src")
        os.makedirs(self.src_dir)
        base_path = Path(__file__).parent.parent
        self.patcher_exe = os.path.abspath(base_path / "src" / "hud-patcher.py")

    def tearDown(self):
        shutil.rmtree(self.test_root)

    def run_p(self, args):
        cmd = [sys.executable, self.patcher_exe] + args
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_2_1_positive_exact_match(self):
        target = os.path.join(self.src_dir, "file1.py")
        with open(target, 'w', newline='') as f: f.write("line1\nline2\nline3\n")
        patch = os.path.join(self.test_root, "test.patch")
        with open(patch, 'w', newline='') as f:
            f.write("--- file1.py\n+++ file1.py\n@@ -2,1 +2,1 @@\n-line2\n+modified\n")
        res = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res.returncode, 0)
        with open(target, 'r') as f: 
            self.assertEqual(f.read(), "line1\nmodified\nline3\n")

    def test_2_2_positive_offset_match(self):
        target = os.path.join(self.src_dir, "file1.py")
        with open(target, 'w') as f: f.write("n1\nn2\nn3\ntarget\n")
        patch = os.path.join(self.test_root, "test.patch")
        with open(patch, 'w') as f:
            f.write("--- file1.py\n+++ file1.py\n@@ -1,1 +1,1 @@\n-target\n+found\n")
        res_fail = self.run_p([patch, "-d", self.src_dir])
        self.assertEqual(res_fail.returncode, 2)
        res_pass = self.run_p([patch, "-d", self.src_dir, "--max-offset", "10"])
        self.assertEqual(res_pass.returncode, 0)

if __name__ == "__main__":
    unittest.main()
