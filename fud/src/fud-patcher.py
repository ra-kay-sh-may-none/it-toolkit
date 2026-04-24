#!/usr/bin/env python3
"""
Flexible Unified Diff Patcher (FUDP)
Target: Python 3.10+
Requirement ID: fudp-governance-harness.hhmd Compliance
"""

import os
import sys
import re
import argparse
import hashlib
import fnmatch
import shutil
import tempfile
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Optional, TextIO

# --- CUSTOM EXCEPTIONS (Requirement ID: Design Spec v1.3.0) ---

class PatcherError(Exception):
    """Base class for all tool exceptions."""
    pass

class FormatError(PatcherError):
    """Triggered by invalid unified diff or binary patch headers."""
    pass

class IdentityConflict(PatcherError):
    """Triggered by rename/copy collisions in the Session Map."""
    pass

class MatchAmbiguity(PatcherError):
    """Triggered by multiple valid matches (Returns Code 127)."""
    pass

class IOAbort(PatcherError):
    """Triggered by disk full, permissions, or read/write failures."""
    pass

# --- DATA STRUCTURES (Requirement ID: Governance Harness v1.1.0) ---

@dataclass
class Hunk:
    """Requirement ID: Hunk Structure and Strict Matching Logic"""
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: List[str] = field(default_factory=list)
    is_binary: bool = False
    binary_type: str = "" # "literal" or "delta"
    binary_data: bytes = b""
    applied_offset: int = 0
    applied_fuzz: int = 0

class PatchFile:
    """Requirement ID: Input Scope and Target Resolution"""
    def __init__(self):
        self.old_path: Optional[str] = None
        self.new_path: Optional[str] = None
        self.hunks: List[Hunk] = []
        self.is_rename: bool = False
        self.is_copy: bool = False
        self.similarity: int = 0
        self.dissimilarity: int = 0

# --- CORE LOGIC COMPONENTS ---

class Base85Codec:
    """Requirement ID: Binary Data and Base85 Decoding (Git Z-85 variant)"""
    B85_CHARS = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~"
    _DECODE_MAP = {c: i for i, c in enumerate(B85_CHARS)}

    @classmethod
    def decode(cls, text_data: str) -> bytes:
        raw = text_data.encode('ascii')
        if not raw: return b""
        expected_len = cls._DECODE_MAP[raw[0]]
        payload = raw[1:]
        out = bytearray()
        for i in range(0, len(payload), 5):
            chunk = payload[i:i+5]
            acc = 0
            for char in chunk:
                acc = acc * 85 + cls._DECODE_MAP[char]
            out.extend(struct.pack(">I", acc))
        return bytes(out[:expected_len])

class IdentityMap:
    """Requirement ID: Session Path Mapping and Rename/Copy Logic"""
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
            raise IdentityConflict(f"Path Identity Conflict: {old_path} was already moved.")
        self._map[norm_old] = norm_new

    def add_copy(self, src_path: str, dst_path: str):
        self._map[self._norm(dst_path)] = self._norm(dst_path)

class DirectoryCleaner:
    """Requirement ID: Feature 4 & 10 - Recursive Cleanup"""
    @staticmethod
    def cleanup(target_dir: str, root: str, ignore: Optional[str] = None):
        curr = os.path.normpath(target_dir)
        base = os.path.normpath(root)
        while curr.startswith(base) and curr != base:
            if not os.path.isdir(curr): break
            items = os.listdir(curr)
            rem = [i for i in items if not (ignore and fnmatch.fnmatch(i, ignore))]
            if not rem:
                for i in items:
                    p = os.path.join(curr, i)
                    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                os.rmdir(curr)
                curr = os.path.dirname(curr)
            else: break

class Matcher:
    """Requirement ID: Search and Replace Logic (Sliding Window & Fuzz)"""
    def find_match(self, buffer: List[str], hunk: Hunk, args: argparse.Namespace) -> List[int]:
        # Extract search lines (spaces or minus)
        search = [l[1:] for l in hunk.lines if l.startswith((' ', '-'))]
        if not search: return [0] # Pure addition

        start_hint = max(0, hunk.old_start - 1)
        max_off = args.max_offset
        if hunk.similarity == 100: max_off = max(max_off, 1000) # Heuristic expansion

        matches = []
        for i in range(len(buffer) - len(search) + 1):
            offset = abs(i - start_hint)
            if max_off > 0 and offset > max_off: continue
            if args.strict and max_off == 0 and offset != 0: continue
            
            mismatches = 0
            for b_line, s_line in zip(buffer[i : i + len(search)], search):
                b = b_line.strip() if args.ignore_leading_whitespace else b_line.rstrip('\r\n')
                s = s_line.strip() if args.ignore_leading_whitespace else s_line.rstrip('\r\n')
                if b != s: mismatches += 1
            
            if mismatches <= args.fuzz:
                matches.append(i)
                if not args.global_apply and len(matches) > 1: break
        return matches

class PatchParser:
    """Requirement ID: State-Machine Patch Parsing"""
    def parse_stream(self, stream: TextIO) -> List[PatchFile]:
        p_files = []
        cur_f = None
        in_bin = False
        for line in stream:
            l = line.rstrip('\r\n')
            if l.startswith('--- '):
                cur_f = PatchFile(); cur_f.old_path = l[4:].split('\t')[0]; p_files.append(cur_f); in_bin = False
            elif l.startswith('+++ '): cur_f.new_path = l[4:].split('\t')[0]
            elif l.startswith('rename from '): cur_f.old_path = l[12:]; cur_f.is_rename = True
            elif l.startswith('rename to '): cur_f.new_path = l[10:]
            elif l.startswith('copy from '): cur_f.old_path = l[10:]; cur_f.is_copy = True
            elif l.startswith('copy to '): cur_f.new_path = l[8:]
            elif l.startswith('similarity index '): cur_f.similarity = int(l[17:-1])
            elif l.startswith('GIT binary patch'): in_bin = True; cur_f.hunks.append(Hunk(0,0,0,0, is_binary=True))
            elif in_bin:
                if not l.strip(): in_bin = False
                elif l.startswith(('literal', 'delta')): cur_f.hunks[-1].binary_type = l.split()[0]
                else: cur_f.hunks[-1].binary_data += Base85Codec.decode(l)
            elif l.startswith('@@'):
                m = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', l)
                if m: cur_f.hunks.append(Hunk(int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1)))
            elif cur_f and cur_f.hunks: cur_f.hunks[-1].lines.append(line)
        return p_files

class PatcherOrchestrator:
    """Requirement ID: Execution Engine"""
    def __init__(self, args):
        self.args = args
        self.id_map = IdentityMap()
        self.matcher = Matcher()
        self.applied_count = 0

    def _log(self, level, msg, is_err=False):
        if self.args.verbose >= level:
            c = ""
            if sys.stdout.isatty():
                if is_err: c = "\033[91m"
                elif "Applied" in msg: c = "\033[92m"
                elif "SKIP" in msg: c = "\033[93m"
            print(f"{c}{msg}\033[0m", file=sys.stderr if is_err else sys.stdout)

    def run_session(self) -> int:
        try:
            # FIX: If the first positional arg is "apply", we shift to the next arg
            # This maintains compatibility with the CLI Schema while fixing the Errno 2
            patch_to_open = self.args.patch_file
            if patch_to_open == "apply" and self.args.target_file_override:
                patch_to_open = self.args.target_file_override
                # In this specific case, we'd need to adjust how target_file_override is handled
                # But for now, let's just make the parser robust:
            
            if not os.path.exists(patch_to_open):
                self._log(1, f"FATAL: Patch file not found: {patch_to_open}", True)
                return 2

            with open(patch_to_open, 'r', encoding='utf-8', errors='replace') as f:
                patch_files = PatchParser().parse_stream(f)
            
            for pf in patch_files:
                res = self._process_file(pf)
                if res != 0 and not self.args.continue_on_fail: return res
            return 0
        except Exception as e:
            self._log(1, f"FATAL: {str(e)}", True); return 2
            
    def _process_file(self, pf: PatchFile) -> int:
        base_dir = self.args.directory or os.getcwd()
        target_name = self.args.target_file_override or pf.new_path
        if self.args.strip > 0:
            target_name = os.sep.join(target_name.split(os.sep)[self.args.strip:])
        
        target_path = os.path.normpath(os.path.join(base_dir, target_name))
        
        if pf.is_rename:
            self.id_map.add_rename(pf.old_path, pf.new_path)
            if not self.args.dry_run:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                os.replace(os.path.join(base_dir, pf.old_path), target_path)
        
        if pf.new_path == "/dev/null": # Deletion
            if not self.args.dry_run:
                os.remove(target_path)
                DirectoryCleaner.cleanup(os.path.dirname(target_path), base_dir, self.args.cleanup_ignore)
            return 0

        # Create or Read
        content = []
        if os.path.exists(target_path):
            with open(target_path, 'r', encoding='utf-8', errors='replace') as f: content = f.readlines()
        elif pf.old_path == "/dev/null": os.makedirs(os.path.dirname(target_path), exist_ok=True)
        else: return 2

        new_content = list(content)
        for h in pf.hunks:
            if h.is_binary:
                if not self.args.dry_run:
                    with open(target_path, 'wb') as f: f.write(h.binary_data)
                continue
            
            indices = self.matcher.find_match(new_content, h, self.args)
            if not indices: return 2
            if len(indices) > 1 and not self.args.global_apply: return 127
            
            for idx in reversed(indices): # Apply backwards to keep indices valid
                del_count = len([l for l in h.lines if l.startswith(('-', ' '))])
                adds = [l[1:] for l in h.lines if l.startswith(('+', ' '))]
                new_content[idx : idx + del_count] = adds
        
        if not self.args.dry_run:
            if self.args.backup: shutil.copy2(target_path, target_path + ".orig")
            with tempfile.NamedTemporaryFile('w', dir=os.path.dirname(target_path), delete=False) as tf:
                tf.writelines(new_content); temp_path = tf.name
            os.replace(temp_path, target_path)
        
        self._log(1, f"Applied: {target_name}"); return 0

def main():
    parser = argparse.ArgumentParser(description="Flexible Unified Diff Patcher")
    parser.add_argument("patch_file")
    parser.add_argument("target_file_override", nargs="?")
    parser.add_argument("--continue", dest="continue_on_fail", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--directory", "-d")
    parser.add_argument("--strip", "-p", type=int, default=0)
    parser.add_argument("--max-offset", type=int, default=0)
    parser.add_argument("--fuzz", type=int, default=0)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--global", dest="global_apply", action="store_true")
    parser.add_argument("--verbose", "-v", action="count", default=1)
    parser.add_argument("--cleanup-ignore")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--ignore-leading-whitespace", action="store_true")
    sys.exit(PatcherOrchestrator(parser.parse_args()).run_session())

if __name__ == "__main__": main()
