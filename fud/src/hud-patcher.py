#!/usr/bin/env python3
"""
Flexible Unified Diff Patcher (FUDP)
Sprint 1: Path Resolution & Atomicity
Version: v0.2.0
"""

import os
import sys
import argparse
import tempfile
import shutil
import re
from dataclasses import dataclass, field
from typing import List, Optional, TextIO

# --- CUSTOM EXCEPTIONS ---
class PatcherError(Exception): pass
class IOAbort(PatcherError): pass

@dataclass
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: List[str] = field(default_factory=list)

class PatchFile:
    def __init__(self):
        self.old_path: Optional[str] = None
        self.new_path: Optional[str] = None
        self.hunks: List[Hunk] = []

class PatchParser:
    def parse_stream(self, stream: TextIO) -> List[PatchFile]:
        p_files = []
        cur_f = None
        for line in stream:
            l = line.rstrip('\r\n')
            if l.startswith('--- '):
                cur_f = PatchFile()
                cur_f.old_path = l[4:].split('\t')[0].strip()
                p_files.append(cur_f)
            elif l.startswith('+++ ') and cur_f:
                cur_f.new_path = l[4:].split('\t')[0].strip()
            elif l.startswith('@@') and cur_f:
                m = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', l)
                if m:
                    h = Hunk(int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1))
                    cur_f.hunks.append(h)
            elif cur_f and cur_f.hunks:
                cur_f.hunks[-1].lines.append(line)
        return p_files

class Matcher:
    def find_match(self, buffer: List[str], hunk: Hunk, args: argparse.Namespace) -> List[int]:
        search = [l[1:] for l in hunk.lines if l.startswith((' ', '-'))]
        if not search: return [len(buffer)] if hunk.old_start == 0 else []
        start_hint = max(0, hunk.old_start - 1)
        matches = []
        for i in range(len(buffer) - len(search) + 1):
            offset = abs(i - start_hint)
            if hunk.old_start != 0 and args.max_offset == 0 and offset != 0: continue
            if args.max_offset > 0 and offset > args.max_offset: continue
            if all(buffer[i+j].rstrip('\r\n') == search[j].rstrip('\r\n') for j in range(len(search))):
                matches.append(i)
                if len(matches) > 1: break
        return matches

class PatcherOrchestrator:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.matcher = Matcher()

    def _log(self, level: int, msg: str, is_err: bool = False):
        if self.args.verbose >= level:
            print(msg, file=sys.stderr if is_err else sys.stdout)

    def resolve_target_path(self, header_path: Optional[str]) -> str:
        base_dir = self.args.directory or os.getcwd()
        if self.args.target_file_override:
            return os.path.abspath(self.args.target_file_override)
        if not header_path:
            raise PatcherError("No target file specified.")
        norm_path = os.path.normpath(header_path.replace('/', os.sep))
        parts = norm_path.split(os.sep)
        if self.args.strip > 0:
            parts = parts[self.args.strip:]
        return os.path.normpath(os.path.join(base_dir, os.sep.join(parts)))

    def atomic_write(self, target_path: str, lines: List[str]):
        target_dir = os.path.dirname(target_path)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix=".patch.", suffix=".tmp", text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as tf:
                tf.writelines(lines)
            if self.args.backup and os.path.exists(target_path):
                shutil.copy2(target_path, target_path + ".orig")
            os.replace(temp_path, target_path)
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            raise IOAbort(f"Atomic write failed: {str(e)}")

    def run_session(self) -> int:
        try:
            with open(self.args.patch_file, 'r', encoding='utf-8') as f:
                patch_files = PatchParser().parse_stream(f)
            for pf in patch_files:
                resolved = self.resolve_target_path(pf.new_path)
                with open(resolved, 'r', encoding='utf-8') as f:
                    work_buf = f.readlines()
                for h in pf.hunks:
                    idxs = self.matcher.find_match(work_buf, h, self.args)
                    if not idxs: return 2
                    idx = idxs[0]
                    del_c = len([l for l in h.lines if l.startswith(('-', ' '))])
                    # Fix: Ensure added lines only have one newline
                    adds = [l[1:].rstrip('\r\n') + '\n' for l in h.lines if l.startswith(('+', ' '))]
                    work_buf[idx : idx + del_c] = adds
                if not self.args.dry_run:
                    self.atomic_write(resolved, work_buf)
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
    parser.add_argument("--max-offset", type=int, default=0)
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="count", default=1)
    args = parser.parse_args()
    if args.patch_file == "apply":
        args.patch_file = args.target_file_override
        args.target_file_override = None
    sys.exit(PatcherOrchestrator(args).run_session())

if __name__ == "__main__":
    main()
