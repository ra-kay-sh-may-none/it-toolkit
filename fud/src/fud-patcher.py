#!/usr/bin/env python3
"""
Flexible Unified Diff Patcher (FUD)
Revision: 1.0.15 (Sprint 9: Strategy & Sequential Intelligence)
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

fh = logging.FileHandler(log_path, mode='a', encoding='utf-8')
fh.addFilter(TraceFilter())
fh.setFormatter(logging.Formatter('%(asctime)s - [%(trace_id)s] - %(levelname)s - %(message)s'))
logger.addHandler(fh)

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
    is_delta: bool = False
    binary_data: bytes = b""
    similarity: int = 0

class DeltaDecoder:
    @staticmethod
    def apply(base_data: bytes, delta_data: bytes) -> bytes:
        """Requirement ID: F11 - Git Delta Instruction Decoder"""
        out = bytearray()
        pos = 0
        # Git Delta Header: Source size and Target size (ignored for literal-lite)
        def get_size(p):
            res, shift = 0, 0
            while p < len(delta_data):
                b = delta_data[p]; p += 1
                res |= (b & 0x7f) << shift
                shift += 7
                if not (b & 0x80): break
            return res, p
        
        if not delta_data: return b""
        try:
            source_size, pos = get_size(pos)
            target_size, pos = get_size(pos)
        except (IndexError, struct.error): return b""

        while pos < len(delta_data):
            cmd = delta_data[pos]; pos += 1
            if cmd & 0x80: # COPY from base
                off = size = 0
                if cmd & 0x01: off = delta_data[pos]; pos += 1
                if cmd & 0x02: off |= delta_data[pos] << 8; pos += 1
                if cmd & 0x04: off |= delta_data[pos] << 16; pos += 1
                if cmd & 0x08: off |= delta_data[pos] << 24; pos += 1
                if cmd & 0x10: size = delta_data[pos]; pos += 1
                if cmd & 0x20: size |= delta_data[pos] << 8; pos += 1
                if cmd & 0x40: size |= delta_data[pos] << 16; pos += 1
                if size == 0: size = 0x10000
                out.extend(base_data[off : off + size])
            elif cmd > 0: # INSERT literal
                out.extend(delta_data[pos : pos + cmd]); pos += cmd
        return bytes(out)

class Base85Codec:
    B85_CHARS = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~"
    _DECODE_MAP = {char_code: index for index, char_code in enumerate(B85_CHARS)}

    @classmethod
    def decode(cls, text_data: str) -> bytes:
        # SURGICAL FIX: We must strip leading/trailing whitespace 
        # before identifying the length character.
        raw = text_data.strip().encode('ascii')
        if not raw: return b""
        
        # DIAGNOSTIC: Log the raw input string
        logger.debug(f"Codec Input: {text_data.strip()}")
        try:
            # FIX: Ensure we use the integer ASCII value of the first character
            length_char = raw[0]
            if length_char not in cls._DECODE_MAP:
                return b""
            expected_len = cls._DECODE_MAP[length_char]
            payload, out = raw[1:], bytearray()
            for i in range(0, len(payload), 5):
                chunk = payload[i:i+5]
                if len(chunk) < 5:
                    chunk = chunk + b"0" * (5 - len(chunk))
                acc = 0
                for char_code in chunk:
                    acc = acc * 85 + cls._DECODE_MAP[char_code]
                out.extend(struct.pack(">I", acc))
            
            # SURGICAL FIX: Force exact length truncation
            res = bytes(out[:expected_len])

            logger.debug(f"Codec Output: {res.hex()} (Expected: {expected_len})")
            return res
        except Exception as e:
            logger.error(f"Codec Exception: {str(e)}")
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

class DirectoryCleaner:
    @staticmethod
    def cleanup(target_dir: str, root: str, ignore_pattern: Optional[str] = None):
        import fnmatch
        curr = os.path.abspath(target_dir)
        base = os.path.abspath(root)
        while curr != base and curr.startswith(base):
            if not os.path.isdir(curr): break
            items = os.listdir(curr)
            if ignore_pattern and any(fnmatch.fnmatch(i, ignore_pattern) for i in items): break
            if not items:
                try:
                    os.rmdir(curr)
                    curr = os.path.dirname(curr)
                except OSError: break
            else: break

class Matcher:
    def find_match(self, buffer: List[str], hunk: Hunk, args: argparse.Namespace, current_offset: int = 0) -> List[int]:
        """Requirement ID: F10 - Search with cumulative session offset"""
        search = [l[1:] for l in hunk.lines if l.startswith((' ', '-'))]
        if not search: return [len(buffer)] if hunk.old_start == 0 else []
        
        # Apply sequential offset to the starting hint
        start_hint = max(0, (hunk.old_start + current_offset) - 1)
        max_off = args.max_offset
        if hasattr(hunk, 'similarity') and hunk.similarity == 100: max_off = max(max_off, 1000)

        matches = []
        for i in range(len(buffer) - len(search) + 1):
            offset = abs(i - start_hint)
            if hunk.old_start != 0:
                # Rule: If max_off is 0 (strict mode), only allow matches where offset is 0.
                # If max_off > 0, allow matches within that distance from the start_hint.
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
                logger.debug(f"Matcher SUCCESS: Match found at index {i} with offset {offset}")
                if not getattr(args, 'global_apply', False) and len(matches) > 1: break
        
        logger.debug(f"Matcher FINAL: Found {len(matches)} total hits for target line {hunk.old_start}")
        return matches

class PatchParser:
    def parse_stream(self, stream: TextIO) -> List[PatchFile]:
        p_files, cur_f, in_bin = [], None, False
        for line in stream:
            l = line.rstrip('\r\n')
            
            # --- STATE TRANSITIONS (Exit Binary Mode) ---
            if l.startswith(('--- ', '@@ ')) and in_bin:
                in_bin = False

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
                if not any(h.is_binary for h in cur_f.hunks):
                    cur_f.hunks.append(Hunk(0, 0, 0, 0, is_binary=True, similarity=cur_f.similarity))
                logger.debug("Parser: Entered Binary Block")
                continue # SURGICAL FIX: Do not process this line as data
            elif in_bin:
                if not l.strip(): continue
                if l.startswith(('--- ', '+++ ', '@@ ')): 
                    in_bin = False; continue

                # SURGICAL FIX: Identify if this is an incremental delta patch
                clean_line = l.strip()
                if clean_line.startswith(('literal ', 'delta ')):
                    cur_f.hunks[-1].is_delta = clean_line.startswith('delta ')
                    if cur_f.hunks[-1].binary_data:
                        in_bin = False
                    else:
                        # First block: clear any accidental noise and skip this header line
                        cur_f.hunks[-1].binary_data = b""
                    continue
                
                # Only decode lines that are not headers
                if not l.startswith('GIT binary patch'):
                    decoded_chunk = Base85Codec.decode(l)
                    if decoded_chunk:
                        cur_f.hunks[-1].binary_data += decoded_chunk

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
        session_status = 0
        try:
            with open(self.args.patch_file, 'r', encoding='utf-8') as f:
                patch_files = PatchParser().parse_stream(f)

            if getattr(self.args, 'reverse', False):
                for pf in patch_files:
                    pf.old_path, pf.new_path = pf.new_path, pf.old_path
                    for h in pf.hunks:
                        h.old_start, h.new_start = h.new_start, h.old_start
                        h.old_len, h.new_len = h.new_len, h.old_len
                        new_lines = []
                        for line in h.lines:
                            if line.startswith('+'): new_lines.append('-' + line[1:])
                            elif line.startswith('-'): new_lines.append('+' + line[1:])
                            else: new_lines.append(line)
                        h.lines = new_lines

            for pf in patch_files:
                file_offset, file_failed = 0, False
                # Glob filtering must use the non-null path for matching
                filter_target = pf.new_path if pf.new_path != "/dev/null" else pf.old_path
                if self.args.include and not fnmatch.fnmatch(filter_target, self.args.include): continue
                if self.args.exclude and fnmatch.fnmatch(filter_target, self.args.exclude): continue

                if pf.is_rename:
                    src, dst = self.resolve_target_path(pf.old_path), self.resolve_target_path(pf.new_path)
                    if os.path.exists(dst) and src != dst: file_failed = True
                    else:
                        self.id_map.add_rename(pf.old_path, pf.new_path)
                        if not self.args.dry_run:
                            if not os.path.exists(src): file_failed = True
                            else: os.makedirs(os.path.dirname(dst), exist_ok=True); os.replace(src, dst)
                
                if file_failed:
                    if self.args.continue_on_fail: session_status = 1; continue
                    else: return 2

                resolved = self.resolve_target_path(pf.new_path)
                if os.path.isdir(resolved):
                    if self.args.continue_on_fail: session_status = 1; continue
                    else: return 2

                # FIX: In dry-run, if the file was supposed to be renamed, it won't exist 
                # at 'resolved' yet. We must acknowledge it is a "pending" dry move.
                exists_on_disk = os.path.exists(resolved)
                is_pending_dry_rename = self.args.dry_run and pf.is_rename

                if pf.new_path == "/dev/null":

                    if not self.args.dry_run:
                        t = self.resolve_target_path(pf.old_path)
                        if os.path.exists(t):
                            os.remove(t)
                            DirectoryCleaner.cleanup(os.path.dirname(t), self.args.directory or os.getcwd(), self.args.cleanup_ignore)
                    self._log(1, f"Deleted: {pf.old_path}"); continue

                is_c = (pf.old_path == "/dev/null") or getattr(self.args, 'reverse', False)
                if not is_c and not exists_on_disk and not is_pending_dry_rename:
                    if self.args.continue_on_fail: session_status = 1; continue
                    else: return 2
                
                if any(h.is_binary for h in pf.hunks):
                    # F11: Support both 'literal' and 'delta' binary hunks
                    # Rule: Take the first binary hunk (index 0) as the post-image
                    binary_hunks = [h for h in pf.hunks if h.is_binary]
                    target_hunk = binary_hunks[0]
                    
                    if not self.args.dry_run:
                        # Ensure directory exists for binary creations
                        dir_to_make = os.path.dirname(resolved)
                        if dir_to_make and not os.path.exists(dir_to_make):
                            os.makedirs(dir_to_make, exist_ok=True)                        
                        # Logic: Handle incremental delta vs full literal replacement
                        try:
                            if target_hunk.is_delta:
                                base_data = b""
                                if os.path.exists(resolved):
                                    with open(resolved, 'rb') as f: base_data = f.read()
                                final_data = DeltaDecoder.apply(base_data, target_hunk.binary_data)
                            else:
                                final_data = target_hunk.binary_data
                            
                            self.atomic_write(resolved, final_data)
                        except Exception as e:
                            logger.error(f"Binary application error: {e}")
                            file_failed = True; break
                    self._log(1, f"Applied binary: {pf.new_path}"); continue

                work_buf = []
                if os.path.exists(resolved):
                    with open(resolved, 'r', encoding='utf-8', errors='replace') as f: work_buf = f.readlines()
                elif is_c and not self.args.dry_run:
                    os.makedirs(os.path.dirname(resolved), exist_ok=True)
                
                for h in pf.hunks:

                    idxs = self.matcher.find_match(work_buf, h, self.args, file_offset)
                    if not idxs: file_failed = True; break
                    if len(idxs) > 1 and not getattr(self.args, 'global_apply', False): session_status = 127; file_failed = True; break
                    
                    # Update offset for next hunk using the first integer match in the list
                    if not is_c and h.old_start > 0 and idxs:
                        # Logic: Extract the first match to calculate the cumulative shift
                        file_offset = idxs[0] - (h.old_start - 1)

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
                
                if file_failed:
                    if self.args.continue_on_fail: session_status = 1; continue
                    else: return session_status or 2

                if not self.args.dry_run: self.atomic_write(resolved, work_buf)
                msg = "Applied via full-file literal search" if any(h.old_start == 0 and not h.is_binary for h in pf.hunks) else "Applied"
                self._log(1, f"{msg}: {pf.new_path}")
            return session_status
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
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="count", default=1)
    parser.add_argument("--fuzz", type=int, default=0)
    parser.add_argument("--global", dest="global_apply", action="store_true")
    parser.add_argument("--reverse", "-R", action="store_true")
    parser.add_argument("--continue", dest="continue_on_fail", action="store_true")
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
