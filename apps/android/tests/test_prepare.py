import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'prepare.py'
spec = importlib.util.spec_from_file_location('prepare', MODULE)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class OverlayTests(unittest.TestCase):
    def test_source_drift_fails_instead_of_silently_skipping(self):
        for text in ['absent', 'old old']:
            with self.assertRaises(ValueError):
                prepare.replace_once(text, 'old', 'new')
        self.assertEqual(prepare.replace_once('one old entry', 'old', 'new'), 'one new entry')

    def test_wrong_revision_is_rejected_before_writing(self):
        with patch.object(prepare, 'git', return_value='wrong'):
            with self.assertRaisesRegex(ValueError, 'Wrong upstream'):
                prepare.prepare(Path('/unused'))

    def test_dirty_checkout_is_preserved(self):
        with patch.object(prepare, 'git', side_effect=[prepare.LOCK['commit'], ' M user-work.kt']):
            with self.assertRaisesRegex(ValueError, 'already modified'):
                prepare.prepare(Path('/unused'))

    def test_license_is_visible_and_not_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / 'V2rayNG/app/src/main/assets'
            assets.mkdir(parents=True)
            (root / 'LICENSE').write_text('GNU GPL <version 3>')
            page = assets / 'open_source_licenses.html'
            page.write_text('<html><body>Existing credits</body></html>')
            prepare.notices(root)
            first = page.read_text()
            prepare.notices(root)
            self.assertEqual(first, page.read_text())
            self.assertIn('Existing credits', first)
            self.assertIn('WITHOUT ANY WARRANTY', first)
            self.assertIn('&lt;version 3&gt;', first)

    def test_changed_core_revision_is_rejected(self):
        with patch.object(prepare, 'git', return_value='wrong'):
            with self.assertRaisesRegex(ValueError, 'native core'):
                prepare.download_core(Path('/unused'))

    def test_visible_branding_uses_mlh_name(self):
        source = '<string name="app_name">v2rayNG</string><string>v2rayNG service</string>'
        branded = source.replace('v2rayNG', 'MLH VPN')
        self.assertNotIn('v2rayNG', branded)
        self.assertEqual(branded.count('MLH VPN'), 2)


if __name__ == '__main__':
    unittest.main()
