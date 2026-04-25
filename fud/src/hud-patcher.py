#!/usr/bin/env python3
"""
Flexible Unified Diff Patcher (FUDP)
Target: Python 3.10+
Requirement ID: fudp-governance-harness.hhmd Compliance
Revision: 1.0.9 (Consolidated Iterative Build)
"""

import os
import sys
import argparse
import tempfile
import shutil
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, TextIO
import struct
import logging

# Setup persistent file logging
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patcher.log")
logging.basicConfig(
    filename=log_file,
    filemode='a',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FUDP")

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
    is_binary: bool = False
    binary_data: bytes = b""
    similarity: int = 0

class Base85Codec:
    B85_CHARS = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~"
    _DECODE_MAP = {char_code: index for index, char_code in enumerate(B85_CHARS)}

    @classmethod
    def decode(cls, text_data: str) -> bytes:
        raw = text_data.strip().encode('ascii')
        if not raw: return b""
        try:
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
            return b""

class PatchFile:
    def __init__(self):
        self.old_path: Optional[str] = None
        self.new_path: Optional[str] = None
        self.hunks: List[Hunk] = []
        self.is_rename: bool = False
        self.similarity: int = 0

class PatchParser:
    def parse_stream(self, stream: TextIO) -> List[PatchFile]:
        p_files = []
        cur_f = None
        in_bin = False
        for line in stream:
            l = line.rstrip('\r\n')
            if l.startswith('--- '):
                cur_f = PatchFile()
                path_parts = l[4:].split('\t')
                cur_f.old_path = path_parts[0].strip()
                p_files.append(cur_f); in_bin = False
            elif l.startswith('+++ ') and cur_f:
                path_parts = l[4:].split('\t')
                cur_f.new_path = path_parts[0].strip()
            elif l.startswith('rename from ') and cur_f:
                cur_f.old_path = l[12:].strip(); cur_f.is_rename = True
            elif l.startswith('rename to ') and cur_f:
                cur_f.new_path = l[10:].strip()
            elif l.startswith('similarity index ') and cur_f:
                cur_f.similarity = int(l[17:-1])
            elif l.startswith('GIT binary patch') and cur_f:
                in_bin = True
                h = Hunk(0, 0, 0, 0, is_binary=True)
                h.binary_data = b""; h.similarity = cur_f.similarity
                cur_f.hunks.append(h)
            elif in_bin:
                if not l.strip(): in_bin = False
                elif l.startswith(('literal', 'delta')):
                    cur_f.hunks[-1].binary_data = b""
                else:
                    cur_f.hunks[-1].binary_data += Base85Codec.decode(l)
            elif l.startswith('@@') and cur_f:
                m = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', l)
                if m:
                    h = Hunk(int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1))
                    h.similarity = cur_f.similarity
                    cur_f.hunks.append(h)
            elif cur_f and cur_f.hunks:
                cur_f.hunks[-1].lines.append(line)
        return p_files

class IdentityMap:
    def __init__(self):
        self._map: Dict[str, str] = {}

    def _norm(self, p: str) -> str:
        if not p or p == "/dev/null": return p
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
        search = [l[1:] for l in hunk.lines if l.startswith((' ', '-'))]
        if not search: return [len(buffer)] if hunk.old_start == 0 else []
        start_hint = max(0, hunk.old_start - 1)
        max_off = args.max_offset
        if hasattr(hunk, 'similarity') and hunk.similarity == 100: max_off = max(max_off, 1000)
        matches = []
        for i in range(len(buffer) - len(search) + 1):
            offset = abs(i - start_hint)
            if hunk.old_start != 0 and max_off == 0 and offset != 0: continue
            if max_off > 0 and offset > max_off: continue
            mismatches = 0
            for j, s_line in enumerate(search):
                b = buffer[i + j].rstrip('\r\n')
                s = s_line.rstrip('\r\n')
                if args.ignore_leading_whitespace:
                    if b.strip() != s.strip(): mismatches += 1
                elif b != s: mismatches += 1
            if mismatches <= args.fuzz:
                matches.append(i)
                if not getattr(args, 'global_apply', False) and len(matches) > 1: break
        return matches

class PatcherOrchestrator:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.matcher = Matcher()
        self.id_map = IdentityMap()

    def _log(self, level: int, msg: str, is_err: bool = False):
        if self.args.verbose >= level:
            print(msg, file=sys.stderr if is_err else sys.stdout)

    def resolve_target_path(self, header_path: Optional[str]) -> str:
        base_dir = self.args.directory or os.getcwd()
        if self.args.target_file_override: return os.path.abspath(self.args.target_file_override)
        if not header_path: raise PatcherError("No target file specified.")
        mapped_path = self.id_map.resolve_path(header_path)
        norm_path = os.path.normpath(mapped_path.replace('/', os.sep))
        parts = norm_path.split(os.sep)
        if self.args.strip > 0: parts = parts[self.args.strip:]
        return os.path.normpath(os.path.join(base_dir, os.sep.join(parts)))

    def atomic_write(self, target_path: str, data: any):
        target_dir = os.path.dirname(target_path)
        if not os.path.exists(target_dir): os.makedirs(target_dir, exist_ok=True)
        is_bin = isinstance(data, (bytes, bytearray))
        fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix=".patch.", suffix=".tmp")
        try:
            with os.fdopen(fd, 'wb' if is_bin else 'w', encoding=None if is_bin else 'utf-8', newline=None if is_bin else '') as tf:
                tf.write(data) if is_bin else tf.writelines(data)
            if self.args.backup and os.path.exists(target_path): shutil.copy2(target_path, target_path + ".orig")
            os.replace(temp_path, target_path)
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            raise IOAbort(str(e))

    def run_session(self) -> int:
        try:
            with open(self.args.patch_file, 'r', encoding='utf-8') as f:
                patch_files = PatchParser().parse_stream(f)
            session_status = 0
            for pf in patch_files:
                if pf.is_rename:
                    src = self.resolve_target_path(pf.old_path)
                    dst = self.resolve_target_path(pf.new_path)
                    if os.path.exists(dst) and src != dst:
                        self._log(1, f"FATAL: Destination exists: {dst}", True); return 2
                    self.id_map.add_rename(pf.old_path, pf.new_path)
                    if not self.args.dry_run:
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        os.replace(src, dst)
                
                resolved = self.resolve_target_path(pf.new_path)
                is_creation = (pf.old_path == "/dev/null")
                if not is_creation and not os.path.exists(resolved):
                    self._log(1, f"FATAL: File not found: {resolved}", True); return 2

                if any(h.is_binary for h in pf.hunks):
                    final_hunk = [h for h in pf.hunks if h.is_binary][-1]
                    if not self.args.dry_run:
                        if is_creation: os.makedirs(os.path.dirname(resolved), exist_ok=True)
                        self.atomic_write(resolved, final_hunk.binary_data)
                    self._log(1, f"Applied binary: {pf.new_path}"); continue

                work_buf = []
                if os.path.exists(resolved):
                    with open(resolved, 'r', encoding='utf-8', errors='replace') as f: work_buf = f.readlines()
                elif is_creation: os.makedirs(os.path.dirname(resolved), exist_ok=True)
                
                for h in pf.hunks:
                    idxs = self.matcher.find_match(work_buf, h, self.args)
                    if not idxs: self._log(1, f"FAIL: Hunk match failed", True); return 2
                    if len(idxs) > 1 and not getattr(self.args, 'global_apply', False):
                        self._log(1, "Ambiguous match", True); return 127
                    
                    for idx in reversed(idxs):
                        del_c = len([l for l in h.lines if l.startswith(('-', ' '))])
                        adds = []
                        for hunk_line in h.lines:
                            if hunk_line.startswith(('+', ' ')):
                                line_p = hunk_line[1:].rstrip('\r\n')
                                if self.args.ignore_leading_whitespace and idx < len(work_buf):
                                    orig = work_buf[idx]
                                    indent = orig[:len(orig) - len(orig.lstrip())]
                                    final = indent + line_p.lstrip() + '\n'
                                else: final = line_p + '\n'
                                adds.append(final)
                        work_buf[idx : idx + del_c] = adds
                
                if not self.args.dry_run: self.atomic_write(resolved, work_buf)
                msg = "Applied via full-file literal search" if all(h.old_start == 0 for h in pf.hunks) else "Applied"
                self._log(1, f"{msg}: {pf.new_path}")
            return session_status
        except Exception as e:
            self._log(1, f"FATAL: {str(e)}", True); return 2

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
    parser.add_argument("--global", dest="global_apply", action="store_true")
    parser.add_argument("--ignore-leading-whitespace", action="store_true")
    args = parser.parse_args()
    if args.patch_file == "apply":
        args.patch_file = args.target_file_override
        args.target_file_override = None
    sys.exit(PatcherOrchestrator(args).run_session())

if __name__ == "__main__": main()
