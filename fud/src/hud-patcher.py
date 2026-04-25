#!/usr/bin/env python3
"""
Flexible Unified Diff Patcher (FUDP)
Sprint 1: Path Resolution & Atomicity
Version: v0.1.0
"""

import os
import sys
import argparse
import tempfile
import shutil
from typing import List, Optional

# --- CUSTOM EXCEPTIONS (Requirement ID: Design Spec v1.3.0) ---
class PatcherError(Exception): pass
class IOAbort(PatcherError): pass

class PatcherOrchestrator:
    def __init__(self, args: argparse.Namespace):
        self.args = args

    def _log(self, level: int, msg: str, is_err: bool = False):
        if self.args.verbose >= level:
            print(msg, file=sys.stderr if is_err else sys.stdout)

    def resolve_target_path(self, header_path: Optional[str]) -> str:
        """Requirement ID: Target Resolution & Strip Logic"""
        base_dir = self.args.directory or os.getcwd()
        
        # 1. CLI Override Logic
        if self.args.target_file_override:
            return os.path.abspath(self.args.target_file_override)

        # 2. Header Path Logic
        if not header_path:
            raise PatcherError("No target file specified in CLI or Patch Headers.")

        # Normalize slashes and strip components
        norm_path = os.path.normpath(header_path.replace('/', os.sep))
        parts = norm_path.split(os.sep)
        
        if self.args.strip > 0:
            parts = parts[self.args.strip:]
            if not parts:
                raise PatcherError(f"Strip level -p{self.args.strip} removed all path components.")
        
        final_rel_path = os.sep.join(parts)
        return os.path.normpath(os.path.join(base_dir, final_rel_path))

    def atomic_write(self, target_path: str, lines: List[str]):
        """Requirement ID: File Write Safety (Atomic Write-then-Rename)"""
        target_dir = os.path.dirname(target_path)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        # Use sibling temp file for atomic rename compatibility
        fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix=".patch.", suffix=".tmp", text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as tf:
                tf.writelines(lines)
            
            if self.args.backup and os.path.exists(target_path):
                shutil.copy2(target_path, target_path + ".orig")
            
            os.replace(temp_path, target_path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise IOAbort(f"Atomic write failed: {str(e)}")

    def run_session(self) -> int:
        """Sprint 1 entry point: Just tests resolution and writing."""
        try:
            # For Sprint 1, we simulate a 'dummy' hunk for path testing
            # In a real patch, header_path would come from PatchParser
            dummy_header_path = "a/dir1/file1.py" 
            resolved = self.resolve_target_path(dummy_header_path)
            
            if not self.args.dry_run:
                # Test the write logic with current content
                content = []
                if os.path.exists(resolved):
                    with open(resolved, 'r', encoding='utf-8') as f:
                        content = f.readlines()
                self.atomic_write(resolved, content)
                self._log(1, f"Applied: {resolved}")
            
            return 0
        except Exception as e:
            self._log(1, f"FATAL: {str(e)}", True)
            return 2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("patch_file")
    parser.add_argument("target_file_override", nargs="?")
    parser.add_argument("--directory", "-d", type=str)
    parser.add_argument("--strip", "-p", type=int, default=0)
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="count", default=1)
    
    args = parser.parse_args()
    # Compatibility shim for 'patcher apply'
    if args.patch_file == "apply":
        args.patch_file = args.target_file_override
        args.target_file_override = None

    sys.exit(PatcherOrchestrator(args).run_session())

if __name__ == "__main__":
    main()
