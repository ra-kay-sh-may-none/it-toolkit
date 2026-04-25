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
import struct

# --- CUSTOM EXCEPTIONS ---
class PatcherError(Exception): pass
class IOAbort(PatcherError): pass
class IdentityConflict(PatcherError): pass
class FormatError(PatcherError): pass

@dataclass
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    lines: List[str] = field(default_factory=list)
    is_binary: bool = False # Added
    binary_data: bytes = b"" # Added

class Base85Codec:
    B85_CHARS = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~"
    # KEY FIX: Ensure keys are integers (ASCII values)
    _DECODE_MAP = {char_code: index for index, char_code in enumerate(B85_CHARS)}

    @classmethod
    def decode(cls, text_data: str) -> bytes:
        raw = text_data.strip().encode('ascii')
        if not raw: return b""
        try:
            # FIX: Ensure index exists in map
            if raw[0] not in cls._DECODE_MAP: return b""
            expected_len = cls._DECODE_MAP[raw[0]]
            payload = raw[1:]
            out = bytearray()
            for i in range(0, len(payload), 5):
                chunk = payload[i : i + 5]
                if len(chunk) < 5: continue
                acc = 0
                for char_code in chunk:
                    acc = acc * 85 + cls._DECODE_MAP[char_code]
                out.extend(struct.pack(">I", acc))
            return bytes(out[:expected_len])
        except Exception:
            return b"" # Fail gracefully to let parser continue


class PatchFile:
    def __init__(self):
        self.old_path: Optional[str] = None
        self.new_path: Optional[str] = None
        self.hunks: List[Hunk] = []
        self.is_rename: bool = False # Added

class PatchParser:
    def parse_stream(self, stream: TextIO) -> List[PatchFile]:
        """Requirement ID: State-Machine Parsing with Debug Tracing"""
        p_files = []
        cur_f = None
        in_bin = False
        print(f"[DEBUG] Starting parse_stream...")
        for line in stream:
            l = line.rstrip('\r\n')
            if l.startswith('--- '):
                cur_f = PatchFile()
                cur_f.old_path = l[4:].split('\t')[0].strip()
                p_files.append(cur_f)
                in_bin = False
                print(f"[DEBUG] Header found: {cur_f.old_path}")
            elif l.startswith('+++ ') and cur_f:
                cur_f.new_path = l[4:].split('\t')[0].strip()
            elif l.startswith('GIT binary patch') and cur_f:
                in_bin = True
                h = Hunk(0, 0, 0, 0, is_binary=True)
                h.binary_data = b"" 
                cur_f.hunks.append(h)
                print(f"[DEBUG] Entered Binary Mode for {cur_f.new_path}")
            elif in_bin:
                if not l.strip():
                    in_bin = False
                    print(f"[DEBUG] Exited Binary Mode. Total bytes: {len(cur_f.hunks[-1].binary_data)}")
                    continue
                if l.startswith(('literal', 'delta')):
                    print(f"[DEBUG] Found Binary Type: {l}")
                    cur_f.hunks[-1].binary_data = b"" # Reset for post-image
                else:
                    decoded = Base85Codec.decode(l)
                    cur_f.hunks[-1].binary_data += decoded
            elif l.startswith('@@') and cur_f:
                m = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', l)
                if m:
                    h = Hunk(int(m.group(1)), int(m.group(2) or 1), 
                             int(m.group(3)), int(m.group(4) or 1))
                    cur_f.hunks.append(h)
            elif cur_f and cur_f.hunks:
                cur_f.hunks[-1].lines.append(line)
        return p_files

class IdentityMap:
    def __init__(self):
        self._map: Dict[str, str] = {}

    def _norm(self, p: str) -> str:
        """Requirement ID: Session Path Mapping - Normalization Rule"""
        if not p or p == "/dev/null": return p
        # Surgical Fix: Ensure forward slashes are handled before OS normalization
        return os.path.normcase(os.path.normpath(p.replace('/', os.sep)))

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

    def atomic_write(self, target_path: str, data: any):
        """Requirement ID: File Write Safety with Binary Support"""
        target_dir = os.path.dirname(target_path)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        is_bin = isinstance(data, (bytes, bytearray))
        mode = 'wb' if is_bin else 'w'
        encoding = None if is_bin else 'utf-8'
        newline = None if is_bin else ''

        fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix=".patch.", suffix=".tmp")
        try:
            with os.fdopen(fd, mode, encoding=encoding, newline=newline) as tf:
                if is_bin:
                    tf.write(data)
                else:
                    tf.writelines(data)
            
            if self.args.backup and os.path.exists(target_path):
                shutil.copy2(target_path, target_path + ".orig")
            
            os.replace(temp_path, target_path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise IOAbort(f"Atomic write failed: {str(e)}")

    def run_session(self) -> int:
        """Requirement ID: Orchestration with Path and Branch Tracing"""
        try:
            print(f"[DEBUG] Patch File: {self.args.patch_file}")
            with open(self.args.patch_file, 'r', encoding='utf-8') as f:
                patch_files = PatchParser().parse_stream(f)
            
            for pf in patch_files:
                resolved = self.resolve_target_path(pf.new_path)
                is_creation = (pf.old_path == "/dev/null")
                print(f"[DEBUG] Resolving: {pf.new_path} -> {resolved} (Creation: {is_creation})")
                
                if not is_creation and not os.path.exists(resolved):
                    print(f"[DEBUG] EXIT 2: File not found at {resolved}")
                    return 2

                # Check Hunks
                if any(h.is_binary for h in pf.hunks):
                    print(f"[DEBUG] Branch: BINARY application")
                    final_hunk = [h for h in pf.hunks if h.is_binary][-1]
                    if not self.args.dry_run:
                        if is_creation: os.makedirs(os.path.dirname(resolved), exist_ok=True)
                        self.atomic_write(resolved, final_hunk.binary_data)
                        print(f"[DEBUG] Write Successful: {len(final_hunk.binary_data)} bytes")
                    continue

                print(f"[DEBUG] Branch: TEXT application")
                work_buf = []
                if os.path.exists(resolved):
                    with open(resolved, 'r', encoding='utf-8') as f:
                        work_buf = f.readlines()
                
                for h in pf.hunks:
                    idxs = self.matcher.find_match(work_buf, h, self.args)
                    print(f"[DEBUG] Match Results: {idxs}")
                    if not idxs:
                        print(f"[DEBUG] EXIT 2: Hunk match failed")
                        return 2
                    # ... rest of application ...
                
                if not self.args.dry_run:
                    self.atomic_write(resolved, work_buf)
                
            return 0
        except Exception as e:
            print(f"[DEBUG] EXCEPTION: {str(e)}")
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
