import unittest
import os
import shutil
import tempfile
import subprocess
import sys
from pathlib import Path

class TestSprint1Resolution(unittest.TestCase):
    def setUp(self):
        self.test_root = tempfile.mkdtemp()
        self.src_dir = os.path.join(self.test_root, "src")
        os.makedirs(self.src_dir)
        
        # Point to the freshly generated src/hud-patcher.py
        base_path = Path(__file__).parent.parent
        self.patcher_exe = os.path.abspath(base_path / "src" / "hud-patcher.py")

    def tearDown(self):
        shutil.rmtree(self.test_root)

    def run_p(self, args):
        cmd = [sys.executable, self.patcher_exe] + args
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_pair_1_1_positive_strip_resolution(self):
        # Header is "a/dir1/file1.py", we use -p1, should hit self.src_dir/dir1/file1.py
        target = os.path.join(self.src_dir, "dir1", "file1.py")
        os.makedirs(os.path.dirname(target))
        with open(target, 'w') as f: f.write("test")
        
        # dummy.patch is required by CLI but not read yet in Sprint 1
        res = self.run_p(["dummy.patch", "-d", self.src_dir, "-p1"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Applied", res.stdout)
        self.assertTrue(os.path.exists(target))

    def test_pair_1_2_positive_override(self):
        override_file = os.path.join(self.test_root, "manual.txt")
        with open(override_file, 'w') as f: f.write("manual")
        
        res = self.run_p(["dummy.patch", override_file])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(override_file))

if __name__ == "__main__":
    unittest.main()
