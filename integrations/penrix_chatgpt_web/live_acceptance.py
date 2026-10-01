#!/usr/bin/env python3
"""Windows live acceptance for Penrix ChatGPT Web -> WebCodex."""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import pathlib
import platform
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

READY_TIMEOUT = 75
DRIVER_TIMEOUT = 900
CLEANUP_TIMEOUT = 20
TOKEN_RE = re.compile(r"^webcodex_[0-9a-f]{64}$")
EXPECTED_WEBCODEX_VERSION = "0.4.4"
EXPECTED_WEB_MODEL = "chatgpt-web/gpt-5.6-sol"


class AcceptanceError(RuntimeError):
    pass


def run_checked(args: list[str], cwd: pathlib.Path) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit {completed.returncode}"
        raise AcceptanceError(f"command failed: {args[0]}: {detail}")
    return completed.stdout.strip()


def make_repo() -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp(prefix="penrix-webcodex-live-"))
    try:
        (root / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
        (root / "acceptance.py").write_text(
            'def expected_message():\n    return "BROKEN"\n',
            encoding="utf-8",
        )
        (root / "test_acceptance.py").write_text(
            "import unittest\n"
            "from acceptance import expected_message\n\n"
            "class AcceptanceTest(unittest.TestCase):\n"
            "    def test_expected_message(self):\n"
            '        self.assertEqual(expected_message(), "WEBCODEX_LIVE_OK")\n\n'
            'if __name__ == "__main__":\n'
            "    unittest.main()\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            "# Disposable WebCodex live acceptance\n\n"
            "This repository exists only for the Penrix ChatGPT Web -> WebCodex live test.\n",
            encoding="utf-8",
        )
        run_checked(["git", "init", "-b", "main"], root)
        run_checked(["git", "config", "user.name", "Penrix Live Acceptance"], root)
        run_checked(["git", "config", "user.email", "live-acceptance@invalid.local"], root)
        run_checked(["git", "add", "."], root)
        run_checked(["git", "commit", "-m", "test: seed disposable live acceptance"], root)
        return root
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise


def pump(stream, out: queue.Queue[str], capture: list[str]) -> None:
    try:
        for line in iter(stream.readline, ""):
            line = line.rstrip("\r\n")
            capture.append(line)
            if len(capture) > 200:
                del capture[:-200]
            out.put(line)
    finally:
        stream.close()


def start_share(
    webcodex: pathlib.Path,
    repo: pathlib.Path,
    probe_only: bool,
) -> tuple[subprocess.Popen[str], dict[str, Any], list[str]]:
    env = os.environ.copy()
    env["PATH"] = str(webcodex.parent) + os.pathsep + env.get("PATH", "")
    cmd = [
        str(webcodex),
        "share",
        "--tunnel",
        "none",
        "--json",
        "--stop-on-stdin-eof",
    ]
    if probe_only:
        cmd.append("--no-copy-url")
    proc = subprocess.Popen(
        cmd,
        cwd=repo,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None and proc.stderr is not None
    stdout_q: queue.Queue[str] = queue.Queue()
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    threading.Thread(target=pump, args=(proc.stdout, stdout_q, stdout_lines), daemon=True).start()
    threading.Thread(target=pump, args=(proc.stderr, queue.Queue(), stderr_lines), daemon=True).start()

    deadline = time.monotonic() + READY_TIMEOUT
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            detail = "\n".join(stderr_lines[-30:] or stdout_lines[-30:])
            raise AcceptanceError(
                f"webcodex share exited before ready ({proc.returncode}): {detail}"
            )
        try:
            line = stdout_q.get(timeout=0.25)
        except queue.Empty:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("event") == "ready":
            server = event.get("server")
            exposure = event.get("exposure")
            if not isinstance(server, dict) or not isinstance(server.get("url"), str):
                raise AcceptanceError("share ready event had no local Server URL")
            if not isinstance(exposure, dict) or exposure.get("state") != "local_ready":
                raise AcceptanceError(
                    f"share did not report local_ready: {json.dumps(event, ensure_ascii=False)}"
                )
            return proc, event, stderr_lines
    raise AcceptanceError("timed out waiting for webcodex share ready event")


def stop_share(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        if proc.returncode != 0:
            raise AcceptanceError(f"webcodex share exited unexpectedly with {proc.returncode}")
        return
    assert proc.stdin is not None
    proc.stdin.close()
    try:
        code = proc.wait(timeout=CLEANUP_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        raise AcceptanceError(
            "webcodex share did not stop after stdin EOF; process was killed"
        )
    if code != 0:
        raise AcceptanceError(f"webcodex share cleanup exited with {code}")


def json_request(
    url: str,
    token: str,
    body: dict[str, Any],
    timeout: float = 30,
) -> dict[str, Any]:
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "content-type": "application/json",
            "accept": "application/json",
            "authorization": f"Bearer {token}",
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as res:
            raw = res.read(4 * 1024 * 1024 + 1)
            status = res.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read(4 * 1024 * 1024 + 1)
    except OSError as exc:
        raise AcceptanceError(f"WebCodex request transport failed: {exc}") from exc
    if len(raw) > 4 * 1024 * 1024:
        raise AcceptanceError("WebCodex response exceeded live acceptance bound")
    try:
        data = json.loads(raw.decode()) if raw else {}
    except (UnicodeError, ValueError) as exc:
        raise AcceptanceError(f"WebCodex returned non-JSON HTTP {status}") from exc
    if status != 200 or not isinstance(data, dict):
        raise AcceptanceError(
            f"WebCodex HTTP {status}: {json.dumps(data, ensure_ascii=False)[:2000]}"
        )
    return data


def exact_project(server_url: str, token: str) -> str:
    result = json_request(
        server_url.rstrip("/") + "/api/tools/call",
        token,
        {"tool": "list_projects", "params": {"limit": 10, "summary_only": True}},
    )
    if result.get("success") is not True:
        raise AcceptanceError(
            "list_projects failed: " + json.dumps(result, ensure_ascii=False)[:2000]
        )
    output = result.get("output")
    projects = output.get("projects") if isinstance(output, dict) else None
    if not isinstance(projects, list):
        raise AcceptanceError("list_projects returned no project list")
    connected = [
        project
        for project in projects
        if isinstance(project, dict)
        and project.get("connected") is True
        and isinstance(project.get("id"), str)
    ]
    if len(connected) != 1:
        raise AcceptanceError(
            f"expected exactly one connected share Project, got {len(connected)}"
        )
    return connected[0]["id"]


def relay_catalog(relay_url: str) -> None:
    models_url = relay_url.rstrip("/") + "/models"
    req = urllib.request.Request(
        models_url,
        method="GET",
        headers={"accept": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=20) as res:
            raw = res.read(2 * 1024 * 1024 + 1)
            status = res.status
    except Exception as exc:
        raise AcceptanceError(
            f"codex-chatgpt-web model catalog unavailable at {models_url}: {exc}"
        ) from exc
    if status != 200 or len(raw) > 2 * 1024 * 1024:
        raise AcceptanceError(
            f"codex-chatgpt-web model catalog failed HTTP {status}"
        )
    try:
        body = json.loads(raw.decode())
    except (UnicodeError, ValueError) as exc:
        raise AcceptanceError(
            "codex-chatgpt-web model catalog was not JSON"
        ) from exc
    data = body.get("data") if isinstance(body, dict) else None
    ids = {
        item.get("id")
        for item in data
        if isinstance(data, list)
        and isinstance(item, dict)
        and isinstance(item.get("id"), str)
    }
    if EXPECTED_WEB_MODEL not in ids:
        raise AcceptanceError(
            f"relay does not expose {EXPECTED_WEB_MODEL}; "
            "upgrade/configure codex-chatgpt-web before live acceptance"
        )


def run_driver(
    driver: pathlib.Path,
    env: dict[str, str],
    args: list[str],
) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(driver), *args],
        env=env,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=DRIVER_TIMEOUT,
    )
    if proc.stderr.strip():
        print(proc.stderr.rstrip(), file=sys.stderr)
    if proc.returncode != 0:
        raise AcceptanceError(
            f"driver failed with exit {proc.returncode}: "
            f"{proc.stdout.strip() or proc.stderr.strip()}"
        )
    try:
        result = json.loads(proc.stdout)
    except ValueError as exc:
        raise AcceptanceError("driver stdout was not JSON") from exc
    if not isinstance(result, dict) or result.get("status") != "completed":
        raise AcceptanceError(
            "driver did not complete: "
            + json.dumps(result, ensure_ascii=False)[:2000]
        )
    return result


def verify_local_repo(repo: pathlib.Path) -> None:
    source = (repo / "acceptance.py").read_text(encoding="utf-8")
    if 'return "WEBCODEX_LIVE_OK"' not in source:
        raise AcceptanceError(
            "expected edit is not present in disposable repository"
        )
    run_checked([sys.executable, "-m", "unittest", "-v"], repo)


def live_run(
    webcodex: pathlib.Path,
    driver: pathlib.Path,
    relay_url: str,
) -> dict[str, Any]:
    repo = make_repo()
    share: subprocess.Popen[str] | None = None
    success = False
    try:
        version = run_checked([str(webcodex), "--version"], repo)
        if f" {EXPECTED_WEBCODEX_VERSION} " not in f" {version} ":
            raise AcceptanceError(
                f"live acceptance requires WebCodex {EXPECTED_WEBCODEX_VERSION}; "
                f"got: {version}"
            )

        relay_catalog(relay_url)
        share, ready, _stderr = start_share(webcodex, repo, probe_only=False)
        connection = ready.get("connection")
        if (
            not isinstance(connection, dict)
            or connection.get("clipboard_contains") != "bearer_credential"
        ):
            raise AcceptanceError(
                "share did not stage a temporary bearer credential for handoff"
            )
        if connection.get("clipboard_state") != "copied":
            raise AcceptanceError(
                "share could not copy the temporary bearer credential "
                "to the Windows clipboard"
            )

        token = getpass.getpass(
            "WebCodex 已把临时 token 放进剪贴板。"
            "按 Ctrl+V 粘贴后回车（输入不会显示）: "
        ).strip()
        if not TOKEN_RE.fullmatch(token):
            raise AcceptanceError(
                "pasted value is not the temporary WebCodex project credential"
            )

        server_url = ready["server"]["url"]
        project = exact_project(server_url, token)
        env = os.environ.copy()
        env.update(
            {
                "WEBCODEX_URL": server_url,
                "WEBCODEX_TOKEN": token,
                "WEBCODEX_PROJECT": project,
                "CODEX_CHATGPT_WEB_URL": relay_url,
            }
        )

        first = run_driver(
            driver,
            env,
            [
                "--task",
                (
                    "This is a disposable Windows live acceptance repository. "
                    "Read acceptance.py and test_acceptance.py. Change only "
                    "acceptance.py so expected_message() returns exactly "
                    "WEBCODEX_LIVE_OK. Run python -m unittest -v through canonical "
                    "WebCodex process execution. Review the actual change, obtain "
                    "finish_coding_task evidence, and report completion. "
                    "Do not modify any other file."
                ),
            ],
        )
        verify_local_repo(repo)
        session_ref = first.get("session_ref")
        if not isinstance(session_ref, str) or not session_ref.startswith("~s"):
            raise AcceptanceError(
                "first driver run returned no durable Session ref"
            )

        second = run_driver(
            driver,
            env,
            [
                "--session",
                session_ref,
                "--task",
                (
                    "Recovery acceptance only. Recover the exact saved handoff "
                    "and current Project state. Do not modify files. Confirm "
                    "acceptance.py still returns WEBCODEX_LIVE_OK and report the "
                    "prior validation state from durable/current evidence."
                ),
            ],
        )
        success = True
        return {
            "status": "passed",
            "evidence_class_candidate": "LIVE VERIFIED",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "windows": platform.platform(),
            "webcodex_version": version,
            "driver_sha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
            "relay_model": EXPECTED_WEB_MODEL,
            "first_session_ref": session_ref,
            "first_rounds": first.get("rounds"),
            "resume_rounds": second.get("rounds"),
            "flow": [
                "Windows temporary Git Project",
                "WebCodex share local Server+Runner+Project",
                "codex-chatgpt-web browser-only reasoning",
                "WebCodex read/edit/process validation/finish evidence",
                "local filesystem/test recheck",
                "fresh driver process exact Session resume",
            ],
        }
    finally:
        cleanup_error: Exception | None = None
        if share is not None:
            try:
                stop_share(share)
            except Exception as exc:
                cleanup_error = exc
        if success and cleanup_error is None:
            shutil.rmtree(repo, ignore_errors=True)
        else:
            print(
                f"Disposable acceptance repository retained for diagnosis: {repo}",
                file=sys.stderr,
            )
        if cleanup_error is not None:
            raise cleanup_error


def share_probe(webcodex: pathlib.Path) -> dict[str, Any]:
    repo = make_repo()
    share: subprocess.Popen[str] | None = None
    success = False
    try:
        version = run_checked([str(webcodex), "--version"], repo)
        if f" {EXPECTED_WEBCODEX_VERSION} " not in f" {version} ":
            raise AcceptanceError(
                f"share probe requires WebCodex {EXPECTED_WEBCODEX_VERSION}; "
                f"got: {version}"
            )
        share, ready, _stderr = start_share(
            webcodex,
            repo,
            probe_only=True,
        )
        success = True
        return {
            "status": "passed",
            "webcodex_version": version,
            "server_url_present": isinstance(
                ready.get("server", {}).get("url"), str
            ),
            "exposure_state": ready.get("exposure", {}).get("state"),
        }
    finally:
        cleanup_error: Exception | None = None
        if share is not None:
            try:
                stop_share(share)
            except Exception as exc:
                cleanup_error = exc
        if success and cleanup_error is None:
            shutil.rmtree(repo, ignore_errors=True)
        else:
            print(
                f"Disposable share-probe repository retained: {repo}",
                file=sys.stderr,
            )
        if cleanup_error is not None:
            raise cleanup_error


def find_webcodex(bin_dir: str | None) -> pathlib.Path:
    if bin_dir:
        candidate = (
            pathlib.Path(bin_dir).expanduser().resolve() / "webcodex.exe"
        )
    else:
        found = shutil.which("webcodex")
        if not found:
            raise AcceptanceError(
                "--webcodex-bin-dir is required when webcodex.exe is not on PATH"
            )
        candidate = pathlib.Path(found).resolve()
    if not candidate.is_file():
        raise AcceptanceError(f"webcodex.exe not found: {candidate}")
    for companion in ("webcodex-server.exe", "webcodex-runner.exe"):
        if not (candidate.parent / companion).is_file():
            raise AcceptanceError(
                f"missing companion binary: {candidate.parent / companion}"
            )
    return candidate


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--webcodex-bin-dir",
        default=os.environ.get("WEBCODEX_BIN_DIR"),
    )
    parser.add_argument(
        "--relay-url",
        default=os.environ.get(
            "CODEX_CHATGPT_WEB_URL",
            "http://127.0.0.1:17841/v1",
        ),
    )
    parser.add_argument("--share-probe-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if os.name != "nt":
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "error": "Windows live acceptance must run on Windows",
                }
            )
        )
        return 2
    ns = parse_args(argv)
    try:
        if not shutil.which("git"):
            raise AcceptanceError("Git for Windows is required")
        webcodex = find_webcodex(ns.webcodex_bin_dir)
        driver = pathlib.Path(__file__).with_name("driver.py").resolve()
        if not driver.is_file():
            raise AcceptanceError(
                f"driver.py not found beside live_acceptance.py: {driver}"
            )
        result = (
            share_probe(webcodex)
            if ns.share_probe_only
            else live_run(webcodex, driver, ns.relay_url)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except AcceptanceError as exc:
        print(
            json.dumps(
                {"status": "blocked", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
