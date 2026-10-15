"""Integrity-checked public downloads and selective HTTP ZIP extraction."""
from __future__ import annotations

import hashlib
import io
import time
import urllib.request
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def fetch(url, start=None, end=None):
    headers = {"User-Agent": "aircraft-approach-practice/2"}
    if start is not None:
        headers["Range"] = f"bytes={start}-{end}"
        # Some intermediary caches key only on URL and ignore the Range header.
        # Make each byte range a stable URL variant, and still verify Content-Range.
        parts = urllib.parse.urlsplit(url)
        query = parts.query + ('&' if parts.query else '') + f'byte_range={start}-{end}'
        url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
                if start is not None and (response.status != 206 or
                        not response.headers.get("Content-Range", "").startswith(f"bytes {start}-{end}/")):
                    raise ValueError("Server did not honor the requested byte range")
                data = response.read()
                if start is not None and len(data) != end - start + 1:
                    raise ValueError("Incomplete HTTP range")
                return data
        except (OSError, ValueError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


class RemoteZip(io.RawIOBase):
    """Seekable HTTP reader. ZIP validates each extracted member's CRC32.

    Whole-archive MD5 cannot be verified when only selected members are fetched;
    retain member CRC and SHA256 rather than claiming the archive was verified.
    """
    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0
        self.cache_start, self.cache = 0, b""

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self.position = offset + (0 if whence == 0 else self.position if whence == 1 else self.size)
        if self.position < 0:
            raise ValueError("Negative offset")
        return self.position

    def read(self, size=-1):
        size = min(self.size - self.position, size if size >= 0 else self.size)
        if size <= 0:
            return b""
        start, stop = self.position, self.position + size
        if not (self.cache_start <= start and stop <= self.cache_start + len(self.cache)):
            self.cache_start = start
            self.cache = fetch(self.url, start, min(self.size, max(stop, start + 512 * 1024)) - 1)
        data = self.cache[start - self.cache_start:stop - self.cache_start]
        self.position = stop
        return data


def extract_member(url, size, member, target):
    target = Path(target)
    with zipfile.ZipFile(RemoteZip(url, size)) as archive:
        info = archive.getinfo(member)
        data = archive.read(info)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    temporary.write_bytes(data)
    temporary.replace(target)
    return {"archive_url": url, "member": member, "bytes": len(data),
            "zip_crc32_verified": f"{info.CRC:08x}",
            "sha256": hashlib.sha256(data).hexdigest(), "archive_md5_verified": False}


def download_archive(url, size, md5, target, workers=8):
    """Resume fixed byte chunks; publish only after checking publisher's MD5."""
    target = Path(target)
    if target.exists() and target.stat().st_size == size:
        with target.open('rb') as stream:
            if hashlib.file_digest(stream, 'md5').hexdigest() == md5:
                return target
    chunks = target.parent / (target.name + '.chunks')
    chunks.mkdir(parents=True, exist_ok=True)
    ranges = [(i, min(size, i + 16 * 1024 * 1024) - 1) for i in range(0, size, 16 * 1024 * 1024)]
    def part(bounds):
        a, b = bounds
        p = chunks / str(a)
        if not p.exists() or p.stat().st_size != b - a + 1:
            p.write_bytes(fetch(url, a, b))
        return p
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(part, bounds) for bounds in ranges]
        for count, future in enumerate(as_completed(futures), 1):
            future.result()
            if count % 10 == 0 or count == len(ranges):
                print(f'{target.name}: {count}/{len(ranges)} chunks', flush=True)
    temporary = target.with_suffix(target.suffix + '.part')
    digest = hashlib.md5()
    with temporary.open('wb') as output:
        for a, _ in ranges:
            data = (chunks / str(a)).read_bytes()
            output.write(data)
            digest.update(data)
    if digest.hexdigest() != md5:
        raise ValueError(f'Publisher MD5 mismatch for {target.name}')
    temporary.replace(target)
    # Exact known files only; no recursive or computed-directory deletion.
    for a, _ in ranges:
        (chunks / str(a)).unlink()
    chunks.rmdir()
    return target
