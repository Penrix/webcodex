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


class FakeHttpResponse:
    def __init__(self, body, status=200):
        self.status = status
        self._raw = live.json.dumps(body).encode()

    def read(self, _limit):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, req, timeout):
        self.requests.append((req, timeout))
        return self.response


class LiveAcceptanceTests(unittest.TestCase):
    def test_real_git_porcelain_columns_survive_local_verification(self):
        temporary = tempfile.TemporaryDirectory(prefix="penrix-webcodex-live-")
        self.addCleanup(temporary.cleanup)
        with mock.patch.object(live.tempfile, "mkdtemp", return_value=temporary.name):
            repo = live.make_repo()
        (repo / "acceptance.py").write_text('def expected_message():\n    return "WEBCODEX_LIVE_OK"\n', encoding="utf-8")
        status = live.run_checked(["git", "status", "--porcelain"], repo)
        self.assertEqual(status.splitlines(), [" M acceptance.py"])
        self.assertIn("WEBCODEX_LIVE_OK", live.verify_local_repo(repo))

    def test_live_carrier_uses_paced_test_entry_not_unpaced_production_driver(self):
        completed = subprocess.CompletedProcess([], 0, stdout='{"status":"completed"}', stderr="")
        with mock.patch.object(live.subprocess, "run", return_value=completed) as run:
            live.run_driver(ROOT / "driver.py", {}, ["--task", "x"])
        self.assertEqual(pathlib.Path(run.call_args.args[0][1]).name, "real_test_driver.py")

    def test_relay_health_requires_exact_6_1_7_browser_only_contract(self):
        opener = FakeOpener(
            FakeHttpResponse(
                {
                    "status": "ok",
                    "service": "codex-chatgpt-web",
                    "version": "6.1.7",
                    "mode": "browser-only",
                    "accepting_turns": True,
                }
            )
        )
        with mock.patch.object(live.urllib.request, "build_opener", return_value=opener):
            result = live.relay_health("http://127.0.0.1:17841/v1")
        self.assertEqual(result["version"], "6.1.7")
        self.assertEqual(opener.requests[0][0].full_url, "http://127.0.0.1:17841/healthz")

    def test_relay_health_rejects_stale_relay_before_effects(self):
        opener = FakeOpener(
            FakeHttpResponse(
                {
                    "status": "ok",
                    "service": "codex-chatgpt-web",
                    "version": "5.0.8",
                    "mode": "browser-only",
                    "accepting_turns": True,
                }
            )
        )
        with mock.patch.object(live.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(
                live.AcceptanceError,
                "requires codex-chatgpt-web 6.1.7; got: 5.0.8",
            ):
                live.relay_health("http://127.0.0.1:17841/v1")

    def test_invalid_clipboard_credential_stops_before_project_or_driver(self):
        repo = pathlib.Path(tempfile.mkdtemp(prefix="penrix-live-test-"))
        fake_share = object()
        try:
            with (
                mock.patch.object(live, "make_repo", return_value=repo),
                mock.patch.object(
                    live,
                    "run_checked",
                    return_value="webcodex 0.4.4 (commit test, dirty=false, built_at=0)",
                ),
                mock.patch.object(
                    live,
                    "relay_health",
                    return_value={"version": "6.1.7", "mode": "browser-only"},
                ),
                mock.patch.object(live, "start_share", return_value=(fake_share, READY, [])),
                mock.patch.object(live, "windows_clipboard_text", return_value="not-a-token"),
                mock.patch.object(live, "exact_project") as exact_project,
                mock.patch.object(live, "run_driver") as run_driver,
                mock.patch.object(live, "stop_share"),
                mock.patch.object(live, "remove_state_dir") as remove_state,
            ):
                with self.assertRaisesRegex(
                    live.AcceptanceError,
                    "Windows clipboard does not contain the temporary WebCodex project credential",
                ):
                    live.live_run(
                        pathlib.Path("webcodex.exe"),
                        ROOT / "driver.py",
                        "http://127.0.0.1:17841/v1",
                    )
            exact_project.assert_not_called()
            run_driver.assert_not_called()
            remove_state.assert_not_called()
        finally:
            live.shutil.rmtree(repo, ignore_errors=True)

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

    def test_driver_requires_requested_live_evidence_markers(self):
        completed = subprocess.CompletedProcess(
            ["python", "driver.py"],
            0,
            stdout='{"status":"completed"}',
            stderr="[penrix-web] WebCodex tool: run_process\n",
        )
        with mock.patch.object(live.subprocess, "run", return_value=completed):
            with self.assertRaisesRegex(
                live.AcceptanceError,
                "without required live evidence: WebCodex tool: observe_jobs",
            ):
                live.run_driver(
                    pathlib.Path("driver.py"),
                    {},
                    ["--task", "x"],
                    required_stderr_markers=(
                        "WebCodex tool: run_process",
                        "WebCodex tool: observe_jobs",
                    ),
                )

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
                mock.patch.object(live, "relay_health", return_value={"version": "6.1.7", "mode": "browser-only"}),
                mock.patch.object(live, "start_share", return_value=(fake_share, READY, [])),
                mock.patch.object(live, "windows_clipboard_text", return_value=VALID_TOKEN),
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
                        ROOT / "driver.py",
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
                mock.patch.object(
                    live,
                    "relay_health",
                    return_value={"version": "6.1.7", "mode": "browser-only"},
                ),
                mock.patch.object(live, "start_share", return_value=(fake_share, READY, [])),
                mock.patch.object(live, "windows_clipboard_text", return_value=VALID_TOKEN),
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
                        ROOT / "driver.py",
                        "http://127.0.0.1:17841/v1",
                    )
        finally:
            live.shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
