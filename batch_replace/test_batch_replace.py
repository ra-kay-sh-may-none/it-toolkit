import unittest
import os
import subprocess
import sys

class TestBatchReplace(unittest.TestCase):
    def setUp(self):
        self.target = "test_target.txt"
        self.mapping = "test_mapping.txt"
        with open(self.target, 'w') as f:
            f.write("Hello World")
        with open(self.mapping, 'w') as f:
            f.write("World\n---\nUniverse")

    def tearDown(self):
        for f in [self.target, self.mapping]:
            if os.path.exists(f): os.remove(f)
        if os.path.exists("error_dir.txt"):
            if os.path.isdir("error_dir.txt"): os.rmdir("error_dir.txt")
            else: os.remove("error_dir.txt")

    def test_full_execution_via_cli(self):
        result = subprocess.run(
            [sys.executable, "batch_replace.py", self.target, self.mapping],
            capture_output=True, text=True
        )
        self.assertIn("Successfully updated", result.stdout)

    def test_dry_run_via_cli(self):
        result = subprocess.run(
            [sys.executable, "batch_replace.py", self.target, self.mapping, "--dry-run"],
            capture_output=True, text=True
        )
        self.assertIn("--- DRY RUN OUTPUT ---", result.stdout)
        self.assertIn("Hello Universe", result.stdout)

    def test_file_not_found(self):
        result = subprocess.run(
            [sys.executable, "batch_replace.py", self.target, "missing.txt"],
            capture_output=True, text=True
        )
        self.assertIn("Error: Mapping file", result.stdout)

    def test_exception_branch(self):
        os.mkdir("error_dir.txt")
        result = subprocess.run(
            [sys.executable, "batch_replace.py", "error_dir.txt", self.mapping],
            capture_output=True, text=True
        )
        self.assertIn("An error occurred", result.stdout)

    def test_no_args_exit(self):
        result = subprocess.run(
            [sys.executable, "batch_replace.py"],
            capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0)

    def test_malformed_rule_skip(self):
        with open(self.mapping, 'w') as f:
            f.write("This rule has no separator")
        result = subprocess.run(
            [sys.executable, "batch_replace.py", self.target, self.mapping],
            capture_output=True, text=True
        )
        self.assertIn("Successfully updated", result.stdout)

if __name__ == "__main__":
    unittest.main()
