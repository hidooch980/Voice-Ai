import importlib.util
import io
from pathlib import Path
import struct
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('signature_patch', Path(__file__).resolve().parents[1] / 'apk_signature_patch.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SignaturePatchTests(unittest.TestCase):
    def setUp(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('AndroidManifest.xml', 'test manifest')
        self.unsigned = output.getvalue()
        end, offset = m.directory(self.unsigned)
        block = struct.pack('<Q', 24) * 2 + b'APK Sig Block 42'
        signed = bytearray(self.unsigned[:offset] + block + self.unsigned[offset:])
        struct.pack_into('<I', signed, end + len(block) + 16, offset + len(block))
        self.signed = bytes(signed)
        self.patch = m.extract(self.unsigned, self.signed)

    def test_round_trip_matches_exact_bytes(self):
        self.assertEqual(m.reconstruct(self.unsigned, self.patch), self.signed)

    def test_zero_padding_before_signing_block(self):
        end, offset = m.directory(self.unsigned)
        block = b'\x00' * 920 + struct.pack('<Q', 24) * 2 + b'APK Sig Block 42'
        signed = bytearray(self.unsigned[:offset] + block + self.unsigned[offset:])
        struct.pack_into('<I', signed, end + len(block) + 16, offset + len(block))
        patch = m.extract(self.unsigned, bytes(signed))
        self.assertEqual(m.reconstruct(self.unsigned, patch), signed)

    def test_wrong_input_and_tampered_output_are_rejected(self):
        with self.assertRaises(ValueError):
            m.reconstruct(self.unsigned + b'tampered', self.patch)
        with self.assertRaises(ValueError):
            m.reconstruct(self.unsigned, dict(self.patch, signed_sha256='0' * 64))
        with self.assertRaises(ValueError):
            m.reconstruct(self.unsigned, dict(self.patch, central_directory_offset=0))

    def test_changed_zip_entry_cannot_be_exported(self):
        changed = self.signed.replace(b'test manifest', b'fake manifest')
        with self.assertRaises(ValueError):
            m.extract(self.unsigned, changed)

    def test_invalid_archives_rejected(self):
        for data in [b'', b'not an apk', self.unsigned[:-1]]:
            with self.assertRaises(ValueError):
                m.directory(data)
