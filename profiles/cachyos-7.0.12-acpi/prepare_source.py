#!/usr/bin/env python3
"""Deterministic base substitutions before the separate ACPI overlay."""
import json
from pathlib import Path
import re

def prepare(root, identity):
    root = Path(root)
    facp = bytes.fromhex(identity['FACP'])
    paths = ('hw/ide/core.c', 'hw/nvme/ctrl.c', 'include/hw/acpi/aml-build.h', 'hw/acpi/aml-build.c')
    texts = {p: (root / p).read_text(encoding='utf-8') for p in paths}
    changes = {
        'hw/ide/core.c': [('"HL-DT-ST BD-RE WH16NS60"', '"Sony NEC Optiarc AD-7261S"'),
                          ('"Hitachi HMS360404D5CF00"', '"Transcend Ultimate microSDXC"'),
                          ('"Samsung SSD 980 500GB"', '"SanDisk Ultra 3D NAND SSD 1TB"')],
        'hw/nvme/ctrl.c': [('"NVMe Ctrl"', '"SanDisk Ultra 3D NAND SSD 1TB"')],
        'hw/acpi/aml-build.c': [('g_array_append_vals(array, "ACPI", 4);',
                               'g_array_append_vals(array, ' + json.dumps(facp[18:22].replace(b'\0', b' ').decode('ascii')) + ', 4);')],
    }
    for p, replacements in changes.items():
        for before, after in replacements:
            if texts[p].count(before) != 1:
                raise ValueError('Unexpected source token in ' + p + ': ' + before)
            texts[p] = texts[p].replace(before, after)
    p = 'include/hw/acpi/aml-build.h'
    for name, value in [('ACPI_BUILD_APPNAME6', facp[:6]), ('ACPI_BUILD_APPNAME8', facp[6:14])]:
        pattern = r'(#define ' + name + r' )"[^"\n]*"'
        replacement = json.dumps(value.replace(b'\0', b' ').decode('ascii'))
        texts[p], count = re.subn(pattern, lambda m: m[1] + replacement, texts[p])
        if count != 1:
            raise ValueError('Unexpected ACPI macro: ' + name)
    for p, text in texts.items():
        (root / p).write_bytes(text.encode())
