import contextlib
import io
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import live_acceptance as live  # noqa: E402


VALID_TOKEN = "webcodex_" + ("a" * 64)
READY = {
    "server": {"url": "http://127.0.0.1:43123"},
    "connection": {
        "clipboard_contains": "bearer_credential",
        "clipboard_state": "copied",
    },
}


class LiveAcceptanceTests(unittest.TestCase):
    def test_driver_timeout_is_explicit_unknown_blocker(self):
        with mock.patch.object(
            live.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(["python", "driver.py"], live.DRIVER_TIMEOUT),
        ):
            with self.assertRaisesRegex(
                live.AcceptanceError,
                "outcome may be unknown.*Do not rerun automatically",
            ):
                live.run_driver(pathlib.Path("driver.py"), {}, ["--task", "x"])

    def test_primary_blocker_survives_cleanup_failure(self):
        repo = pathlib.Path(tempfile.mkdtemp(prefix="penrix-live-test-"))
        fake_share = object()
        stderr = io.StringIO()
        try:
            with (
                mock.patch.object(live, "make_repo", return_value=repo),
                mock.patch.object(
                    live,
                    "run_checked",
                    return_value="webcodex 0.4.4 (commit test, dirty=false, built_at=0)",
                ),
                mock.patch.object(live, "start_share", return_value=(fake_share, READY, [])),
                mock.patch.object(live.getpass, "getpass", return_value=VALID_TOKEN),
                mock.patch.object(live, "exact_project", return_value="agent:runner:repo"),
                mock.patch.object(
                    live,
                    "run_driver",
                    side_effect=live.AcceptanceError("primary blocker"),
                ),
                mock.patch.object(
                    live,
                    "stop_share",
                    side_effect=live.AcceptanceError("cleanup blocker"),
                ),
                mock.patch.object(live, "remove_state_dir"),
                contextlib.redirect_stderr(stderr),
            ):
                with self.assertRaisesRegex(live.AcceptanceError, "^primary blocker$"):
                    live.live_run(
                        pathlib.Path("webcodex.exe"),
                        pathlib.Path("driver.py"),
                        "http://127.0.0.1:17841/v1",
                    )
            self.assertIn(
                "Cleanup also failed after the primary blocker: cleanup blocker",
                stderr.getvalue(),
            )
        finally:
            live.shutil.rmtree(repo, ignore_errors=True)

    def test_cleanup_failure_still_fails_an_otherwise_successful_run(self):
        repo = pathlib.Path(tempfile.mkdtemp(prefix="penrix-live-test-"))
        fake_share = object()
        first = {"status": "completed", "session_ref": "~s1", "rounds": 2}
        second = {"status": "completed", "session_ref": "~s1", "rounds": 1}
        try:
            with (
                mock.patch.object(live, "make_repo", return_value=repo),
                mock.patch.object(
                    live,
                    "run_checked",
                    return_value="webcodex 0.4.4 (commit test, dirty=false, built_at=0)",
                ),
                mock.patch.object(live, "start_share", return_value=(fake_share, READY, [])),
                mock.patch.object(live.getpass, "getpass", return_value=VALID_TOKEN),
                mock.patch.object(live, "exact_project", return_value="agent:runner:repo"),
                mock.patch.object(live, "run_driver", side_effect=[first, second]),
                mock.patch.object(live, "verify_local_repo", side_effect=["same", "same"]),
                mock.patch.object(
                    live,
                    "stop_share",
                    side_effect=live.AcceptanceError("cleanup blocker"),
                ),
                mock.patch.object(live, "remove_state_dir"),
            ):
                with self.assertRaisesRegex(live.AcceptanceError, "^cleanup blocker$"):
                    live.live_run(
                        pathlib.Path("webcodex.exe"),
                        pathlib.Path("driver.py"),
                        "http://127.0.0.1:17841/v1",
                    )
        finally:
            live.shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
