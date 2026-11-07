"""Byte ranges of the tensors in a GGUF file, and the page-cache helpers the residency tools share."""
import ctypes
import mmap
import os
import re
import struct

SCALARS = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i', 6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}
STATIC = re.compile(r'^(?!.*(_exps\.|engram_embd))')  # every tensor but the routed experts and the Engram tables
PAGE = mmap.PAGESIZE
_ONES = bytes(i & 1 for i in range(256))


def tensors(path):
    """[(name, start, end)] in file order; end is the next tensor's start (alignment padding included)."""
    with open(path, 'rb') as f:
        def rd(fmt):
            return struct.unpack('<' + fmt, f.read(struct.calcsize('<' + fmt)))[0]

        def string():
            return f.read(rd('Q')).decode('utf-8', 'replace')

        def value(t):
            if t == 8:
                return string()
            if t == 9:
                et, n = rd('I'), rd('Q')
                return [value(et) for _ in range(n)]
            return rd(SCALARS[t])

        if f.read(4) != b'GGUF':
            raise ValueError(f'{path}: not a GGUF file')
        rd('I')
        n_tensors, n_kv = rd('Q'), rd('Q')
        align = 32
        for _ in range(n_kv):
            key, t = string(), rd('I')
            v = value(t)
            if key == 'general.alignment':
                align = v
        infos = []
        for _ in range(n_tensors):
            name = string()
            for _ in range(rd('I')):
                rd('Q')
            rd('I')
            infos.append((name, rd('Q')))
        data = (f.tell() + align - 1) // align * align
    size = os.path.getsize(path)
    infos.sort(key=lambda x: x[1])
    return [(name, data + off, data + infos[i + 1][1] if i + 1 < len(infos) else size)
            for i, (name, off) in enumerate(infos)]


def group(name):
    """Tensor kind and layer band: 'attn_output_b L20-42'."""
    m = re.match(r'blk\.(\d+)\.(.*?)(\.weight|\.bias)?$', name)
    if not m:
        return 'other'
    return f'{m[2]} L{"00-19" if int(m[1]) < 20 else "20-42"}'


class Mapping:
    """A read-only shared mapping of the whole file: mincore sees the same unified buffer cache as the engine."""

    def __init__(self, path):
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.mmap.restype = ctypes.c_void_p
        self.libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_longlong]
        self.libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        self.libc.mincore.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p]
        self.libc.msync.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
        self.fd = os.open(path, os.O_RDONLY)
        self.size = os.fstat(self.fd).st_size
        self.base = self.libc.mmap(None, self.size, mmap.PROT_READ, mmap.MAP_SHARED, self.fd, 0)
        if self.base in (None, ctypes.c_void_p(-1).value):
            raise OSError(ctypes.get_errno(), 'mmap')

    def resident(self, start, end):
        """Bytes of [start, end) in the page cache."""
        a = start - start % PAGE
        n = (end - a + PAGE - 1) // PAGE
        vec = ctypes.create_string_buffer(n)
        if self.libc.mincore(self.base + a, n * PAGE, vec) != 0:
            raise OSError(ctypes.get_errno(), 'mincore')
        return vec.raw[:n].translate(_ONES).count(1) * PAGE

    def evict(self, start, end):
        a = start - start % PAGE
        if self.libc.msync(self.base + a, end - a, 0x2) != 0:  # MS_INVALIDATE
            raise OSError(ctypes.get_errno(), 'msync')

    def close(self):
        self.libc.munmap(self.base, self.size)
        os.close(self.fd)
