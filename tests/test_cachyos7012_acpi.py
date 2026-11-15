import importlib.util
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'profiles/cachyos-7.0.12-acpi'
sys.path.insert(0, str(PROFILE))
import acpi_identity as acpi
import kernel
spec = importlib.util.spec_from_file_location('av_profile', PROFILE / 'profile.py')
av = importlib.util.module_from_spec(spec)
spec.loader.exec_module(av)

AML = '''/* base */
void acpi_table_begin(AcpiTable *desc, GArray *array)
{
    build_append_int_noprefix(array, 1, 4);                       /* Creator Revision */
}
void acpi_table_end(void) { /* original checksum */ }
'''
IVRS = '''void build_ivrs(void) {
    AcpiTable table = { .sig = "IVRS", .rev = 1, .oem_id = oem_id,
                         .oem_table_id = oem_table_id };
    uint64_t feature_report;
    /* IVinfo, MMIO, topology and feature bits remain unchanged */
}
'''
IDENTITY = {'FACP': bytes(range(26)).hex(), 'IVRS': bytes(range(26, 52)).hex()}

def table(sig):
    data = bytearray(48)
    data[:4] = sig.encode()
    struct.pack_into('<I', data, 4, len(data))
    data[8] = 1
    data[10:36] = bytes(range(26))
    data[9] = (-sum(data)) & 255
    return bytes(data)

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self):
        for name, text in [('hw/acpi/aml-build.c', AML), ('hw/i386/acpi-build.c', IVRS)]:
            p = self.root / 'source' / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode())
        return self.root / 'source'

    def test_capture_only_identity_not_body(self):
        for sig in ('FACP', 'IVRS'):
            (self.root / sig).write_bytes(table(sig))
        self.assertEqual(acpi.read_identity(self.root), {'FACP': bytes(range(26)).hex(), 'IVRS': bytes(range(26)).hex()})

    def test_bad_checksum_rejected(self):
        for sig in ('FACP', 'IVRS'):
            data = bytearray(table(sig))
            data[-1] ^= 1
            (self.root / sig).write_bytes(data)
        with self.assertRaises(ValueError):
            acpi.read_identity(self.root)

    def test_wrong_signature_rejected(self):
        (self.root / 'FACP').write_bytes(table('DSDT'))
        with self.assertRaises(ValueError):
            acpi.read_identity(self.root)

    def test_wrong_length_rejected(self):
        (self.root / 'FACP').write_bytes(table('FACP') + b'\0')
        with self.assertRaises(ValueError):
            acpi.read_identity(self.root)

    def test_missing_required_table_rejected(self):
        (self.root / 'FACP').write_bytes(table('FACP'))
        with self.assertRaises(ValueError):
            acpi.read_identity(self.root)

    def test_overlay_changes_only_ivrs_revision_in_body_builder(self):
        a, b = acpi.overlay(AML, IVRS, IDENTITY)
        self.assertEqual(b, IVRS.replace('.rev = 1', '.rev = 2'))
        self.assertIn('desc->table_offset + 10', a)
        self.assertIn('identity, 26', a)
        self.assertTrue(a.endswith('void acpi_table_end(void) { /* original checksum */ }\n'))
        self.assertNotIn('"HPET"', a)

    def test_duplicate_or_bad_inputs_do_not_patch(self):
        a, _ = acpi.overlay(AML, IVRS, IDENTITY)
        for bad_aml, bad_acpi, identity in [(a, IVRS, IDENTITY), (AML, 'wrong source', IDENTITY), (AML, IVRS, {'FACP': '00'})]:
            with self.assertRaises(ValueError):
                acpi.overlay(bad_aml, bad_acpi, identity)

    def test_restore_on_extra_copy_preserves_final_artifact(self):
        source = self.source()
        evidence = self.root / 'evidence'
        acpi.apply(source, IDENTITY, evidence)
        copy = self.root / 'restore-copy'
        shutil.copytree(source, copy)
        acpi.restore(copy, evidence)
        self.assertEqual((copy / 'hw/acpi/aml-build.c').read_bytes(), AML.encode())
        self.assertEqual((copy / 'hw/i386/acpi-build.c').read_bytes(), IVRS.encode())
        self.assertIn(acpi.MARKER, (source / 'hw/acpi/aml-build.c').read_text())

    def test_restore_refuses_later_edits(self):
        source = self.source()
        evidence = self.root / 'evidence'
        acpi.apply(source, IDENTITY, evidence)
        (source / 'hw/i386/acpi-build.c').write_bytes(b'later user edit')
        with self.assertRaises(ValueError):
            acpi.restore(source, evidence)

    def test_apply_prevalidates_both_files(self):
        source = self.source()
        (source / 'hw/i386/acpi-build.c').write_bytes(b'invalid')
        with self.assertRaises(ValueError):
            acpi.apply(source, IDENTITY, self.root / 'evidence')
        self.assertEqual((source / 'hw/acpi/aml-build.c').read_bytes(), AML.encode())

class KernelTests(unittest.TestCase):
    def test_pin_preserves_existing_packages_and_is_idempotent(self):
        text = '[options]\nIgnorePkg = other-package linux-cachyos # keep\n[core]\nServer = example\n'
        result = kernel.merge_pin(text)
        self.assertIn('IgnorePkg = other-package linux-cachyos # keep', result)
        self.assertIn('IgnorePkg = linux-cachyos-headers\n', result)
        self.assertEqual(result, kernel.merge_pin(result))
        self.assertEqual(result.split('[core]')[1], text.split('[core]')[1])

    def test_pin_rejects_missing_or_duplicate_options(self):
        for text in ('[core]\n', '[options]\n[options]\n'):
            with self.assertRaises(ValueError):
                kernel.merge_pin(text)

    def test_pin_restore_on_copy_and_later_edit_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p = root / 'pacman.conf'
            original = b'[options]\nIgnorePkg = unrelated\n[core]\n'
            p.write_bytes(original)
            kernel.pin_file(p, root / 'backup')
            copy = root / 'restore-copy'
            shutil.copy2(p, copy)
            kernel.restore_pin(copy, root / 'backup')
            self.assertEqual(copy.read_bytes(), original)
            self.assertNotEqual(p.read_bytes(), original)
            p.write_bytes(p.read_bytes() + b'# later edit\n')
            with self.assertRaises(ValueError):
                kernel.restore_pin(p, root / 'backup')

    def test_missing_package_never_invokes_pacman(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(kernel, 'run') as run:
            with self.assertRaises(ValueError):
                kernel.verify_packages(temp)
            run.assert_not_called()

    def test_headers_must_match(self):
        with patch.object(kernel, 'installed', return_value={'linux-cachyos': '7.0.12-1', 'linux-cachyos-headers': '7.3.1-1'}):
            with self.assertRaises(RuntimeError):
                kernel.require_kernel(running=False)

class BuildTests(unittest.TestCase):
    def test_locked_inputs_and_features(self):
        self.assertEqual(kernel.LOCK['kernel_release'], '7.0.12-1-cachyos')
        self.assertEqual(kernel.LOCK['qemu_commit'], 'aeec49e8170de7846f476124602cf7acd400c3df')
        self.assertIn('--enable-png', av.CONFIGURE)
        self.assertIn('--disable-vnc', av.CONFIGURE)
        self.assertIn('--disable-tcg', av.CONFIGURE)
        import hashlib
        content = (ROOT / 'patches/QEMU/AMD-v11.0.3.patch').read_text(encoding='utf-8').encode()
        self.assertEqual(hashlib.sha256(content).hexdigest(), kernel.LOCK['amd_patch_sha256'])

    def test_artifact_changes_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'binary'
            p.write_bytes(b'original')
            first = av.file_manifest(temp)
            p.write_bytes(b'changed')
            self.assertNotEqual(first, av.file_manifest(temp))

    def test_external_symlink_rejected(self):
        if sys.platform == 'win32':
            self.skipTest('Windows symlink privileges are not assumed')
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'escape').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):
                av.file_manifest(temp)

if __name__ == '__main__':
    unittest.main()
