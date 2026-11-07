#!/usr/bin/env python3
"""Sample system memory every 0.25 s until a process exits: free, wired, purgeable, compressor and file-backed GiB,
page-in/out and compression counters, and the kernel's memory-pressure level.

    python3 speed-bench/residency/memsample.py <out.tsv> <pid>"""
import os
import re
import subprocess
import sys
import time

out, pid = sys.argv[1], int(sys.argv[2])
GIB_FIELDS = ['Pages free', 'Pages wired down', 'Pages purgeable', 'Pages occupied by compressor', 'File-backed pages']
COUNTERS = ['Pageins', 'Pageouts', 'Compressions', 'Decompressions', 'Swapouts']
page = int(re.search(r'page size of (\d+)', subprocess.run(['vm_stat'], capture_output=True, text=True).stdout)[1])
with open(out, 'w') as o:
    o.write('time\tfree_gib\twired_gib\tpurgeable_gib\tcompressor_gib\tfile_gib\t' +
            '\t'.join(c.lower() for c in COUNTERS) + '\tpressure\n')
    while True:
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            alive = False
        vm = subprocess.run(['vm_stat'], capture_output=True, text=True).stdout
        v = {k: int(re.search(re.escape(k) + r':\s+(\d+)', vm)[1]) for k in GIB_FIELDS + COUNTERS}
        level = subprocess.run(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'],
                               capture_output=True, text=True).stdout.strip()
        o.write(f'{time.time():.2f}\t' + '\t'.join(f'{v[k] * page / 2**30:.2f}' for k in GIB_FIELDS) + '\t' +
                '\t'.join(str(v[k]) for k in COUNTERS) + f'\t{level}\n')
        o.flush()
        if not alive:
            break
        time.sleep(0.25)
