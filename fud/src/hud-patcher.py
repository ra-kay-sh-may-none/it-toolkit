#!/usr/bin/env python3
"""
Flexible Unified Diff Patcher (FUD)
Revision: 1.0.14 (Full Logger Integration)
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

# --- LOGGING INFRASTRUCTURE (Harness v1.6.0) ---
class TraceFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = os.environ.get("FUD_TRACE_ID", "CLI")
        return True

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "patcher.log")
logger = logging.getLogger("FUD")
logger.setLevel(logging.DEBUG)
logger.propagate = False

# Handler 1: The Persistent File Log (All details + Trace ID)
fh = logging.FileHandler(log_path, mode='a', encoding='utf-8')
fh.addFilter(TraceFilter())
fh.setFormatter(logging.Formatter('%(asctime)s - [%(trace_id)s] - %(levelname)s - %(message)s'))
logger.addHandler(fh)

# Handler 2: The Console (User-facing only)
# We map self._log calls to this handler via the Orchestrator
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(ch)

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

class DirectoryCleaner:
    @staticmethod
    def cleanup(target_dir: str, root: str, ignore_pattern: Optional[str] = None):
        """Requirement ID: Feature 4 - Recursive Parent Removal (DIAGNOSTIC)"""
        import fnmatch
        curr = os.path.abspath(target_dir)
        base = os.path.abspath(root)
        
        logger.info(f"Cleanup Started: curr={curr}, base={base}")
        
        while curr != base:
            # DIAGNOSTIC: Check why the loop might exit
            if not curr.startswith(base):
                logger.error(f"Cleanup ABORT: curr no longer starts with base. curr={curr}")
                break
                
            if not os.path.isdir(curr):
                logger.error(f"Cleanup ABORT: {curr} is not a directory")
                break
            
            items = os.listdir(curr)
            
            # Logic: If any file matches the ignore pattern, the directory SURVIVES
            if ignore_pattern and any(fnmatch.fnmatch(i, ignore_pattern) for i in items):
                break

            if not items:
                try:
                    for i in items:
                        p = os.path.join(curr, i)
                        if os.path.isdir(p): shutil.rmtree(p)
                        else: os.remove(p)
                    
                    os.rmdir(curr)
                    logger.info(f"Cleanup SUCCESS: Removed {curr}")
                    
                    # Move to parent
                    old_curr = curr
                    curr = os.path.dirname(curr)
                    if curr == old_curr: # Root reached
                        break
                except OSError as e:
                    logger.error(f"Cleanup OSError at {curr}: {str(e)}")
                    break
            else:
                logger.info(f"Cleanup STOP: {curr} is not empty (remaining={remaining})")
                break

class Base85Codec:
    B85_CHARS = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~"
    _DECODE_MAP = {char_code: index for index, char_code in enumerate(B85_CHARS)}

    @classmethod
    def decode(cls, text_data: str) -> bytes:
        raw = text_data.strip().encode('ascii')
        if not raw: return b""
        try:
            expected_len = cls._DECODE_MAP[raw[0]]
            payload, out = raw[1:], bytearray()
            for i in range(0, len(payload), 5):
                chunk = payload[i:i+5]
                if len(chunk) < 5: continue
                acc = 0
                for char_code in chunk:
                    acc = acc * 85 + cls._DECODE_MAP[char_code]
                out.extend(struct.pack(">I", acc))
            return bytes(out[:expected_len])
        except Exception as e:
            logger.debug(f"Codec Error: {str(e)}")
            return b""

class IdentityMap:
    def __init__(self):
        self._map: Dict[str, str] = {}

    def _norm(self, p: str) -> str:
        if not p or p == "/dev/null": return p
        return os.path.normcase(os.path.normpath(p.replace('/', os.sep)))

    def resolve_path(self, path: str) -> str:
        norm = self._norm(path)
        visited = set()
        while norm in self._map and norm not in visited:
            visited.add(norm); norm = self._map[norm]
        return norm

    def add_rename(self, old_path: str, new_path: str):
        norm_old, norm_new = self._norm(old_path), self._norm(new_path)
        if norm_old in self._map and self._map[norm_old] != norm_old:
            raise IdentityConflict(f"Path Conflict: {old_path}")
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
            if hunk.old_start != 0:
                if max_off == 0 and offset != 0: continue
                if max_off > 0 and offset > max_off: continue
            
            mismatches = 0
            for j, s_line in enumerate(search):
                b, s = buffer[i + j].rstrip('\r\n'), s_line.rstrip('\r\n')
                if args.ignore_leading_whitespace:
                    if b.strip() != s.strip(): mismatches += 1
                elif b != s: mismatches += 1
            
            if mismatches <= args.fuzz:
                matches.append(i)
                if not getattr(args, 'global_apply', False) and len(matches) > 1: break
        
        logger.debug(f"Matcher: Found {len(matches)} hits for {hunk.old_start}")
        return matches

class PatchParser:
    def parse_stream(self, stream: TextIO) -> List[PatchFile]:
        p_files, cur_f, in_bin = [], None, False
        for line in stream:
            l = line.rstrip('\r\n')
            if l.startswith('--- '):
                cur_f = PatchFile()
                cur_f.old_path = l[4:].split('\t')[0].strip()
                p_files.append(cur_f); in_bin = False
            elif l.startswith('+++ ') and cur_f:
                cur_f.new_path = l[4:].split('\t')[0].strip()
            elif l.startswith('rename from ') and cur_f:
                cur_f.old_path = l[12:].strip(); cur_f.is_rename = True
            elif l.startswith('rename to ') and cur_f:
                cur_f.new_path = l[10:].strip()
            elif l.startswith('similarity index ') and cur_f:
                cur_f.similarity = int(l[17:-1])
            elif l.startswith('GIT binary patch') and cur_f:
                in_bin = True
                h = Hunk(0, 0, 0, 0, is_binary=True, similarity=cur_f.similarity)
                h.binary_data = b""; cur_f.hunks.append(h)
            elif in_bin:
                if not l.strip(): in_bin = False
                elif l.startswith(('literal', 'delta')): cur_f.hunks[-1].binary_data = b""
                else: cur_f.hunks[-1].binary_data += Base85Codec.decode(l)
            elif l.startswith('@@') and cur_f:
                m = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', l)
                if m:
                    h = Hunk(int(m.group(1)), int(m.group(2) or 1), int(m.group(3)), int(m.group(4) or 1), similarity=cur_f.similarity)
                    cur_f.hunks.append(h)
            elif cur_f:
                if l.startswith(('+', '-', ' ')):
                    if not cur_f.hunks: cur_f.hunks.append(Hunk(0, 0, 0, 0, similarity=cur_f.similarity))
                    cur_f.hunks[-1].lines.append(line)
        return p_files

class PatchFile:
    def __init__(self):
        self.old_path, self.new_path, self.hunks = None, None, []
        self.is_rename, self.similarity = False, 0

class PatcherOrchestrator:
    def __init__(self, args):
        self.args, self.matcher, self.id_map = args, Matcher(), IdentityMap()

    def _log(self, level, msg, is_err=False):
        if self.args.verbose >= level:
            # We print to stderr for FATAL/FAIL to satisfy test runner expectations
            print(msg, file=sys.stderr if is_err else sys.stdout)

    def resolve_target_path(self, header_path: str) -> str:
        base_dir = self.args.directory or os.getcwd()
        if self.args.target_file_override: return os.path.abspath(self.args.target_file_override)
        mapped = self.id_map.resolve_path(header_path)
        norm = os.path.normpath(mapped.replace('/', os.sep))
        parts = norm.split(os.sep)
        if self.args.strip > 0:
            if self.args.strip >= len(parts): raise PatcherError("removed all path components")
            parts = parts[self.args.strip:]
        return os.path.normpath(os.path.join(base_dir, os.sep.join(parts)))

    def atomic_write(self, target_path: str, data: any):
        target_dir = os.path.dirname(target_path)
        if not os.path.exists(target_dir): os.makedirs(target_dir, exist_ok=True)
        is_bin = isinstance(data, (bytes, bytearray))
        fd, temp = tempfile.mkstemp(dir=target_dir, prefix=".patch.", suffix=".tmp")
        try:
            with os.fdopen(fd, 'wb' if is_bin else 'w', encoding=None if is_bin else 'utf-8', newline=None if is_bin else '') as tf:
                tf.write(data) if is_bin else tf.writelines(data)
            if self.args.backup and os.path.exists(target_path): shutil.copy2(target_path, target_path + ".orig")
            os.replace(temp, target_path)
        except Exception as e:
            if os.path.exists(temp): os.remove(temp)
            raise IOAbort(str(e))

    def run_session(self) -> int:
        import fnmatch
        logger.info(f"Session Start: {self.args.patch_file}")
        try:
            with open(self.args.patch_file, 'r', encoding='utf-8') as f:
                patch_files = PatchParser().parse_stream(f)
            for pf in patch_files:
                # --- SURGICAL ADDITION: GLOB FILTERING ---
                target_raw = pf.new_path or pf.old_path
                if self.args.include and not fnmatch.fnmatch(target_raw, self.args.include):
                    continue
                if self.args.exclude and fnmatch.fnmatch(target_raw, self.args.exclude):
                    continue

                if pf.is_rename:
                    src, dst = self.resolve_target_path(pf.old_path), self.resolve_target_path(pf.new_path)
                    if os.path.exists(dst) and src != dst: return 2
                    self.id_map.add_rename(pf.old_path, pf.new_path)
                    if not self.args.dry_run:
                        if not os.path.exists(src): return 2
                        os.makedirs(os.path.dirname(dst), exist_ok=True); os.replace(src, dst)
                
                resolved = self.resolve_target_path(pf.new_path)
                if os.path.isdir(resolved): return 2                
                # --- FEATURE 4: DELETION & CLEANUP ---
                if pf.new_path == "/dev/null":
                    if not self.args.dry_run:
                        # Use pf.old_path to find the file that actually exists on disk
                        target_to_del = self.resolve_target_path(pf.old_path)
                        if os.path.exists(target_to_del):
                            os.remove(target_to_del)
                            # Anchor cleanup to the directory of the file we just deleted
                            base_anchor = self.args.directory or os.getcwd()
                            DirectoryCleaner.cleanup(os.path.dirname(target_to_del), base_anchor, self.args.cleanup_ignore)
                    self._log(1, f"Deleted: {pf.old_path}")
                    continue
                is_creation = (pf.old_path == "/dev/null")
                if not is_creation and not os.path.exists(resolved): return 2
                
                if any(h.is_binary for h in pf.hunks):
                    final_hunk = [h for h in pf.hunks if h.is_binary][-1]
                    if not self.args.dry_run:
                        os.makedirs(os.path.dirname(resolved), exist_ok=True)
                        self.atomic_write(resolved, final_hunk.binary_data)
                    self._log(1, f"Applied binary: {pf.new_path}"); continue

                work_buf = []
                if os.path.exists(resolved):
                    with open(resolved, 'r', encoding='utf-8', errors='replace') as f: work_buf = f.readlines()
                elif is_creation: os.makedirs(os.path.dirname(resolved), exist_ok=True)
                
                for h in pf.hunks:
                    idxs = self.matcher.find_match(work_buf, h, self.args)
                    if not idxs: self._log(1, "FAIL: Hunk match failed", True); return 2
                    if len(idxs) > 1 and not getattr(self.args, 'global_apply', False): return 127
                    for idx in reversed(idxs):
                        del_c = len([l for l in h.lines if l.startswith(('-', ' '))])
                        adds = []
                        for hunk_l in h.lines:
                            if hunk_l.startswith(('+', ' ')):
                                p = hunk_l[1:].rstrip('\r\n')
                                if self.args.ignore_leading_whitespace and idx < len(work_buf):
                                    orig = work_buf[idx]
                                    indent = orig[:len(orig)-len(orig.lstrip())]
                                    adds.append(indent + p.lstrip() + '\n')
                                else: adds.append(p + '\n')
                        work_buf[idx : idx + del_c] = adds
                if not self.args.dry_run: self.atomic_write(resolved, work_buf)
                msg = "Applied via full-file literal search" if any(h.old_start == 0 and not h.is_binary for h in pf.hunks) else "Applied"
                self._log(1, f"{msg}: {pf.new_path}")
            return 0
        except Exception as e:
            logger.error(f"Fatal: {str(e)}")
            self._log(1, f"FATAL: {str(e)}", True)
            return 2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("patch_file")
    parser.add_argument("target_file_override", nargs="?")
    parser.add_argument("--directory", "-d", type=str)
    parser.add_argument("--strip", "-p", type=int, default=0)
    parser.add_argument("--max-offset", type=int, default=0)
    parser.add_argument("--fuzz", type=int, default=0)
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="count", default=1)
    parser.add_argument("--global", dest="global_apply", action="store_true")
    parser.add_argument("--ignore-leading-whitespace", action="store_true")
    parser.add_argument("--include", type=str)
    parser.add_argument("--exclude", type=str)
    parser.add_argument("--cleanup-ignore", type=str)
    args = parser.parse_args()
    if args.patch_file == "apply":
        args.patch_file = args.target_file_override
        args.target_file_override = None
    sys.exit(PatcherOrchestrator(args).run_session())

if __name__ == "__main__": main()
