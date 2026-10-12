import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import browser_entry


class WorkspaceTests(unittest.TestCase):
    def test_workspace_snapshot_exposes_exact_authorized_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            entry = browser_entry.BrowserEntry(None, 'home-project', None, workspace_root=folder)
            self.assertEqual(entry.snapshot()['workspace_root'], str(pathlib.Path(folder).resolve()))

    def test_state_must_stay_outside_authorized_workspace(self):
        import workspace_runtime
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            with self.assertRaisesRegex(Exception, 'outside'):
                workspace_runtime.validate_state(root, root / 'private-state')
            workspace_runtime.validate_state(root / 'workspace', root / 'private-state')

    def test_launcher_defaults_to_home_without_git_initialization(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / 'Start-WebCodex.ps1').read_text(encoding='utf-8')
        self.assertIn('--workspace-dir', source)
        self.assertIn('$env:USERPROFILE', source)
        self.assertNotIn('git init', source)
