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
class IdentityConflict(PatcherError): pass

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
        self.is_rename: bool = False # Added

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
            elif l.startswith('rename from '):
                cur_f.old_path = l[12:]; cur_f.is_rename = True
            elif l.startswith('rename to '):
                cur_f.new_path = l[10:]
        return p_files

class IdentityMap:
    def __init__(self):
        self._map: Dict[str, str] = {}

    def _norm(self, p: str) -> str:
        if not p or p == "/dev/null": return p
        return os.path.normcase(os.path.normpath(p))

    def resolve_path(self, path: str) -> str:
        norm = self._norm(path)
        return self._map.get(norm, norm)

    def add_rename(self, old_path: str, new_path: str):
        norm_old, norm_new = self._norm(old_path), self._norm(new_path)
        if norm_old in self._map and self._map[norm_old] != norm_old:
            raise IdentityConflict(f"Path Identity Conflict: {old_path} moved.")
        self._map[norm_old] = norm_new

class Matcher:
    def find_match(self, buffer: List[str], hunk: Hunk, args: argparse.Namespace) -> List[int]:
        """Requirement ID: Search and Replace Logic (Sliding Window, Fuzz, and WS)"""
        search = [l[1:] for l in hunk.lines if l.startswith((' ', '-'))]
        if not search:
            return [len(buffer)] if hunk.old_start == 0 else []

        start_hint = max(0, hunk.old_start - 1)
        max_off = args.max_offset
        matches = []

        for i in range(len(buffer) - len(search) + 1):
            offset = abs(i - start_hint)
            if hunk.old_start != 0 and max_off == 0 and offset != 0: continue
            if max_off > 0 and offset > max_off: continue
            
            # SURGICAL FIX: Implement Fuzz and Indentation Relaxation
            mismatches = 0
            for j, s_line in enumerate(search):
                b_line = buffer[i + j]
                
                # Rule: Indentation Relaxation vs. Exact Match
                if args.ignore_leading_whitespace:
                    b = b_line.strip()
                    s = s_line.strip()
                else:
                    b = b_line.rstrip('\r\n')
                    s = s_line.rstrip('\r\n')
                
                if b != s:
                    mismatches += 1
            
            # Rule: Success if within Fuzz threshold
            if mismatches <= args.fuzz:
                matches.append(i)
                if len(matches) > 1: break
        return matches

class PatcherOrchestrator:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.matcher = Matcher()
        self.id_map = IdentityMap() # Added

    def _log(self, level: int, msg: str, is_err: bool = False):
        if self.args.verbose >= level:
            print(msg, file=sys.stderr if is_err else sys.stdout)

    # Update resolve_target_path to check IdentityMap
    def resolve_target_path(self, header_path: Optional[str]) -> str:
        base_dir = self.args.directory or os.getcwd()
        if self.args.target_file_override:
            return os.path.abspath(self.args.target_file_override)
        if not header_path:
            raise PatcherError("No target file specified.")
        
        # FIX: Check Session Identity Map
        mapped_path = self.id_map.resolve_path(header_path)
        
        norm_path = os.path.normpath(mapped_path.replace('/', os.sep))
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
        """Requirement ID: Execution Strategy and Order of Operations"""
        try:
            # 1. Parse the patch file into objects
            with open(self.args.patch_file, 'r', encoding='utf-8') as f:
                patch_files = PatchParser().parse_stream(f)
            
            # 2. Iterate through each file section in the patch
            for pf in patch_files:
                # Handle Identities and Renames before Application
                if pf.is_rename:
                    src = self.resolve_target_path(pf.old_path)
                    dst = self.resolve_target_path(pf.new_path)
                    
                    # Negative Scenario 3.1: Collision Check
                    if os.path.exists(dst) and src != dst:
                        self._log(1, f"FATAL: Destination already exists: {dst}", True)
                        return 2
                    
                    # Update the session-wide mapping
                    self.id_map.add_rename(pf.old_path, pf.new_path)
                    
                    if not self.args.dry_run:
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        os.replace(src, dst)
                
                # Resolve target (checking id_map) and read content
                resolved = self.resolve_target_path(pf.new_path)
                
                if not os.path.exists(resolved):
                    self._log(1, f"FATAL: Target file not found: {resolved}", True)
                    return 2

                # 3. Read content into buffer
                with open(resolved, 'r', encoding='utf-8') as f:
                    work_buf = f.readlines()
                
                # 4. Apply each hunk in this file section
                for h in pf.hunks:
                    idxs = self.matcher.find_match(work_buf, h, self.args)
                    if not idxs:
                        self._log(1, f"Hunk match failed for {resolved}", True)
                        return 2
                    
                    # Sprint 2/3/4: Apply first match found
                    idx = idxs[0]
                    del_c = len([l for l in h.lines if l.startswith(('-', ' '))])
                    
                    adds = []
                    for hunk_line in h.lines:
                        if hunk_line.startswith(('+', ' ')):
                            # Initial payload extraction
                            line_payload = hunk_line[1:].rstrip('\r\n')
                            
                            # SURGICAL FIX: Preserve original indentation if flag is set
                            if self.args.ignore_leading_whitespace and idx < len(work_buf):
                                original_line = work_buf[idx]
                                # Capture everything before the first non-whitespace character
                                indent = original_line[:len(original_line) - len(original_line.lstrip())]
                                # Reconstruct using original indent + patch content (stripped of its own leading WS)
                                final_line = indent + line_payload.lstrip() + '\n'
                            else:
                                final_line = line_payload + '\n'
                                
                            adds.append(final_line)
                    
                    # Update the buffer at the matched index
                    work_buf[idx : idx + del_c] = adds
                
                # 5. Commit changes to disk (Atomic Write)
                if not self.args.dry_run:
                    self.atomic_write(resolved, work_buf)
                
                self._log(1, f"Applied: {pf.new_path}")
                
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
    parser.add_argument("--fuzz", type=int, default=0)
    parser.add_argument("--ignore-leading-whitespace", action="store_true")
    args = parser.parse_args()
    if args.patch_file == "apply":
        args.patch_file = args.target_file_override
        args.target_file_override = None
    sys.exit(PatcherOrchestrator(args).run_session())

if __name__ == "__main__":
    main()
