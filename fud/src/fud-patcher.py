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
import zlib

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


import os
# --- ENV FORENSIC START ---
logger.debug("--- [FULL ENV TRACE] ---")
for key, val in sorted(os.environ.items()):
    logger.debug(f"TRACE-ENV: {key} = {val}")
logger.debug("--- [END ENV TRACE] ---")
# --- ENV FORENSIC END ---

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
            _, pos = get_size(pos) # Source Size
            _, pos = get_size(pos) # Target Size
        except IndexError: return b""

        while pos < len(delta_data):
            cmd = delta_data[pos]; pos += 1 
            if cmd & 0x80: # COPY from base 
                print(f"DEBUG_HIT: DELTA_COPY_CMD_{hex(cmd)}") # Marker 1
                off = size = 0 
                try: 
                    if cmd & 0x01: 
                        print("DEBUG_HIT: BIT_0x01_OFF") # Marker 2
                        off = delta_data[pos]; pos += 1 
                    if cmd & 0x02: off |= delta_data[pos] << 8; pos += 1 
                    if cmd & 0x04: off |= delta_data[pos] << 16; pos += 1 
                    if cmd & 0x08: off |= delta_data[pos] << 24; pos += 1 
                    if cmd & 0x10: 
                        print("DEBUG_HIT: BIT_0x10_SIZE") # Marker 3
                        size = delta_data[pos]; pos += 1 
                    if cmd & 0x20: size |= delta_data[pos] << 8; pos += 1 
                    if cmd & 0x40: size |= delta_data[pos] << 16; pos += 1 
                except IndexError: 
                    print("DEBUG_HIT: DELTA_INDEX_ERROR")
                    break 
                if size == 0: size = 0x10000
                # Ensure we don't copy more than available in base_data
                end_pos = off + size
                out.extend(base_data[off : min(len(base_data), end_pos)])
            elif cmd > 0: # INSERT literal (Standard Command)
                out.extend(delta_data[pos : pos + cmd])
                pos += cmd
        return bytes(out)

class Base85Codec:
    # F12: Immutable Integer Alphabet (0-9, A-Z, a-z, symbols)
    # This prevents Windows character mangling.
    B85_CHARS_INT = list(range(48, 58)) + list(range(65, 91)) + list(range(97, 123)) + \
                    [33, 35, 36, 37, 38, 40, 41, 42, 43, 45, 59, 60, 61, 62, 63, 64, 94, 95, 96, 123, 124, 125, 126]
    B85_CHARS = bytes(B85_CHARS_INT)
    _DECODE_MAP = {val: i for i, val in enumerate(B85_CHARS_INT)}
    @classmethod
    def decode(cls, text_data: str) -> bytes:
        raw = text_data.strip().encode('ascii')
        if not raw: return b""
        try:
            # Fix: Ensure we get the correct integer index for the length prefix
            expected_len = cls._DECODE_MAP[raw[0]]
            payload = raw[1:]
            out = bytearray()
            for i in range(0, len(payload), 5):
                chunk = payload[i:i+5]
                # Pad short blocks with the character mapping to index 0 (ASCII 48)
                if len(chunk) < 5:
                    chunk = chunk + bytes([cls.B85_CHARS_INT[0]]) * (5 - len(chunk))
                acc = 0
                for char_code in chunk:
                    # Rule: use the integer value directly for mapping
                    if char_code in cls._DECODE_MAP:
                        acc = acc * 85 + cls._DECODE_MAP[char_code]
                    else:
                        raise ValueError(f"Invalid B85 byte: {char_code}")
                out.extend(struct.pack(">I", acc))
            
            res = bytes(out[:expected_len])
            # SURGICAL FIX: Enforce Strict Git Binary Integrity.
            # If the decoded length doesn't match the header exactly, the patch is corrupt.
            if len(res) != expected_len:
                logger.error(f"Codec Integrity Fail: Got {len(res)}, Expected {expected_len}")
                return b""
            
            logger.debug(f"Codec Output: {res.hex()} (Expected: {expected_len})")
            return res
        except Exception as e:
            logger.error(f"Codec Error: {e}")
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
                # F10/Coverage: Allow finding at least 2 matches to trigger ambiguity check
                if not getattr(args, 'global_apply', False) and len(matches) > 1:
                    break
        
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
                path = l[12:].strip()
                if path: cur_f.old_path = path; cur_f.is_rename = True
            elif l.startswith('rename to ') and cur_f:
                path = l[10:].strip()
                if path: cur_f.new_path = path
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
        logger.debug(f"TRACE-START: Session Start: {self.args.patch_file}")
        session_status = 0
        try:
            with open(self.args.patch_file, 'r', encoding='utf-8') as f:
                patch_files = PatchParser().parse_stream(f)
            logger.debug(f"TRACE-PARSED: Found {len(patch_files)} files in patch")

            if getattr(self.args, 'reverse', False):
                logger.debug("TRACE-REVERSE: Reversing patch hunks")
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
                logger.debug(f"TRACE-FILE-START: Target: {pf.new_path or pf.old_path}")
                
                filter_target = pf.new_path if pf.new_path != "/dev/null" else pf.old_path
                if self.args.include and not fnmatch.fnmatch(filter_target, self.args.include): continue
                if self.args.exclude and fnmatch.fnmatch(filter_target, self.args.exclude): continue

                if pf.is_rename:
                    src, dst = self.resolve_target_path(pf.old_path), self.resolve_target_path(pf.new_path)
                    logger.debug(f"TRACE-RENAME: {src} -> {dst}")
                    if os.path.exists(dst) and src != dst: 
                        logger.error(f"TRACE-RENAME-FAIL: Target {dst} exists"); file_failed = True
                    else:
                        self.id_map.add_rename(pf.old_path, pf.new_path)
                        if not self.args.dry_run:
                            if not os.path.exists(src): 
                                logger.error(f"TRACE-RENAME-FAIL: Source {src} missing"); file_failed = True
                            else:
                                os.makedirs(os.path.dirname(dst), exist_ok=True)
                                os.replace(src, dst)
                
                if file_failed:
                    if self.args.continue_on_fail: session_status = 1; continue
                    else: return 2

                resolved = self.resolve_target_path(pf.new_path)
                exists_on_disk = os.path.exists(resolved)
                is_pending_dry_rename = self.args.dry_run and pf.is_rename
                logger.debug(f"TRACE-PATH: Resolved to {resolved} (Exists={exists_on_disk})")

                if pf.new_path == "/dev/null":
                    if not self.args.dry_run:
                        t = self.resolve_target_path(pf.old_path)
                        if os.path.exists(t):
                            os.remove(t)
                            DirectoryCleaner.cleanup(os.path.dirname(t), self.args.directory or os.getcwd(), self.args.cleanup_ignore)
                    self._log(1, f"Deleted: {pf.old_path}"); continue

                # Requirement: Identity of creation hunks (Path or Hunk line 0)
                is_creation = (pf.old_path == "/dev/null") or any(h.old_start == 0 for h in pf.hunks)
                is_c = is_creation or getattr(self.args, 'reverse', False)
                
                if not is_c and not exists_on_disk and not is_pending_dry_rename:
                    logger.error(f"TRACE-MISSING: File not found: {resolved}")
                    if self.args.continue_on_fail: session_status = 1; continue
                    else: return 2
                
                # --- BINARY BRANCH ---
                binary_hunks = [h for h in pf.hunks if h.is_binary]
                if binary_hunks:
                    h = binary_hunks[0]
                    # REQUIREMENT: F11/F12 - Binary data MUST exist and be complete
                    if not h.binary_data:
                        logger.error("TRACE-BIN-FAIL: Empty or corrupt binary data")
                        if self.args.continue_on_fail: session_status = 1; continue
                        else: return 2
                    
                    logger.debug(f"TRACE-BIN: Data size {len(h.binary_data)}, Delta={h.is_delta}")
                    if not self.args.dry_run:
                        try:
                            os.makedirs(os.path.dirname(resolved), exist_ok=True)
                            p_data = h.binary_data
                            try:
                                p_data = zlib.decompress(h.binary_data)
                                logger.debug("TRACE-BIN: Zlib Decompress SUCCESS")
                            except Exception as ze:
                                logger.debug(f"TRACE-BIN: Zlib Skip ({ze})")
                                
                            if h.is_delta:
                                # F11: Delta instructions must have Source and Target sizes (min 2 bytes)
                                if len(p_data) < 2:
                                    raise ValueError("Delta instruction too short")
                                b_data = b""
                                if os.path.exists(resolved):
                                    with open(resolved, 'rb') as f: b_data = f.read()
                                final_data = DeltaDecoder.apply(b_data, p_data)
                                logger.debug("TRACE-BIN: Delta applied")
                            else:
                                final_data = p_data
                                logger.debug("TRACE-BIN: Literal used")
                            
                            self.atomic_write(resolved, final_data)
                            logger.debug("TRACE-BIN: Write SUCCESS")
                        except Exception as be:
                            logger.error(f"TRACE-BIN-FATAL: {be}")
                            if self.args.continue_on_fail: session_status = 1; file_failed = True; break
                            else: return 2
                    
                    self._log(1, f"Applied binary: {pf.new_path}")
                    continue

                # --- TEXT BRANCH ---
                logger.debug(f"TRACE-TEXT: Processing {len(pf.hunks)} hunks")
                work_buf = []
                if os.path.exists(resolved):
                    with open(resolved, 'r', encoding='utf-8', errors='replace') as f: 
                        work_buf = f.readlines()
                elif is_c and not self.args.dry_run:
                    print("DEBUG_HIT: ENTERED NESTED MKDIR BRANCH") # Add this
                    os.makedirs(os.path.dirname(resolved), exist_ok=True)
                
                for h_idx, h in enumerate(pf.hunks):
                    logger.debug(f"TRACE-HUNK-{h_idx}: Searching...")
                    idxs = self.matcher.find_match(work_buf, h, self.args, file_offset)
                    if not idxs: 
                        logger.error(f"TRACE-HUNK-FAIL: No match for hunk {h_idx}"); file_failed = True; break
                    if len(idxs) > 1 and not getattr(self.args, 'global_apply', False):
                        logger.error("TRACE-HUNK-AMBIGUOUS: Multiple matches"); session_status = 127; file_failed = True; break
                    
                    if not is_c and h.old_start > 0:
                        file_offset = idxs[0] - (h.old_start - 1)
                        logger.debug(f"TRACE-OFFSET: New offset hint: {file_offset}")

                    for idx in reversed(idxs):
                        del_c = len([l for l in h.lines if l.startswith(('-', ' '))])
                        adds = []
                        for l in h.lines:
                            if l.startswith(('+', ' ')):
                                content = l[1:].rstrip('\r\n') + '\n'
                                if self.args.ignore_leading_whitespace and idx < len(work_buf):
                                    orig = work_buf[idx]
                                    indent = orig[:len(orig)-len(orig.lstrip())]
                                    adds.append(indent + content.lstrip())
                                else:
                                    adds.append(content)
                        work_buf[idx : idx + del_c] = adds
                
                if file_failed:
                    if self.args.continue_on_fail: session_status = 1; continue
                    else: return session_status or 2

                if not self.args.dry_run: 
                    self.atomic_write(resolved, work_buf)
                    logger.debug("TRACE-TEXT: Write SUCCESS")
                self._log(1, f"Applied: {pf.new_path}")
                
            return session_status
        except Exception as e:
            logger.error(f"TRACE-FATAL-SESSION: {str(e)}")
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

if __name__ == "__main__":
    try:
        main()
    finally:
        # F12: Force the tracker to save data on Windows
        try:
            import coverage
            c = coverage.Coverage.current()
            if c:
                c.stop()
                c.save()
        except:
            pass
