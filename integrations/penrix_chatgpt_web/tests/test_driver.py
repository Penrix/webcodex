from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import pathlib
import socket
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DRIVER_PATH = pathlib.Path(__file__).parents[1] / "driver.py"
spec = importlib.util.spec_from_file_location("penrix_web_driver", DRIVER_PATH)
driver = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = driver
spec.loader.exec_module(driver)


def response_body(action):
    text = json.dumps(action, separators=(",", ":"))
    return {
        "id": "resp_test",
        "status": "completed",
        "end_turn": True,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "phase": "commentary",
                "content": [{"type": "output_text", "text": "browser-only local bridge unavailable"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": text}],
            },
        ],
    }


class FakeState:
    def __init__(self):
        self.relay_actions = []
        self.relay_requests = []
        self.webcodex_requests = []
        self.drop_relay = False
        self.drop_webcodex_tool = None
        self.relay_response_override = None
        self.relay_status = 200


@contextlib.contextmanager
def fake_servers(state: FakeState):
    class RelayHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(length))
            state.relay_requests.append(body)
            if state.drop_relay:
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            if state.relay_response_override is not None:
                envelope = state.relay_response_override
            else:
                action = state.relay_actions.pop(0)
                envelope = response_body(action)
            payload = json.dumps(envelope).encode()
            self.send_response(state.relay_status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    class WebCodexHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(length))
            state.webcodex_requests.append(body)
            tool = body["tool"]
            params = body.get("params") or {}
            if state.drop_webcodex_tool == tool:
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            if tool == "work_on_project":
                out = {"success": True, "output": {"session_id": "wc_sess_test", "session_ref": "~s1"}}
            elif tool == "session_handoff_summary":
                out = {"success": True, "output": {"session_id": "wc_sess_test", "brief": "saved"}}
            elif tool == "tool_manifest":
                name = params["tool_name"]
                effect = "mutate" if name in {"edit_project_files", "run_shell"} else "observe"
                properties = {}
                if name not in {
                    "observe_jobs", "wait_for_job_readiness", "wait_for_job_terminal"
                }:
                    properties["project"] = {"type": "string"}
                if name in {
                    "read_files", "edit_project_files", "finish_coding_task",
                    "run_shell", "list_jobs", "review_changes", "project_validate",
                    "project_build", "workspace_hygiene"
                }:
                    properties["session_id"] = {"type": "string"}
                out = {
                    "success": True,
                    "output": {
                        "name": name,
                        "effect": effect,
                        "idempotency": "non_idempotent" if effect == "mutate" else "pure_read",
                        "input_schema": {"type": "object", "properties": properties},
                    },
                }
            elif tool == "read_files":
                out = {"success": True, "output": {"text": "hello"}}
            elif tool == "edit_project_files":
                out = {"success": True, "output": {"state_changed": True}}
            elif tool == "project_validate":
                out = {
                    "success": True,
                    "output": {
                        "execution_state": "running",
                        "terminal": False,
                        "job_id": "wc_job_current",
                    },
                }
            elif tool == "observe_jobs":
                out = {
                    "success": True,
                    "output": {
                        "items": [{
                            "job_id": params["items"][0].get("job_id", "wc_job_current"),
                            "status": "completed",
                            "observation_ref": "~j1",
                        }]
                    },
                }
            elif tool == "finish_coding_task":
                out = {"success": True, "output": {"closed": True}}
            else:
                out = {"success": True, "output": {"tool": tool, "params": params}}
            payload = json.dumps(out).encode()
            self.send_response(200 if out["success"] else 400)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    relay = ThreadingHTTPServer(("127.0.0.1", 0), RelayHandler)
    wc = ThreadingHTTPServer(("127.0.0.1", 0), WebCodexHandler)
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in (relay, wc)]
    for thread in threads:
        thread.start()
    try:
        yield (
            f"http://127.0.0.1:{relay.server_address[1]}/v1",
            f"http://127.0.0.1:{wc.server_address[1]}",
        )
    finally:
        relay.shutdown()
        wc.shutdown()
        relay.server_close()
        wc.server_close()
        for thread in threads:
            thread.join(timeout=2)


class DriverTests(unittest.TestCase):
    def make_driver(self, relay_url, wc_url):
        return driver.Driver(
            driver.WebCodex(wc_url, "secret-test-token", 3),
            driver.WebModel(relay_url, "chatgpt-web/gpt-5.6-sol", "high", 3),
            project="agent:runner:repo",
            allowed=driver.ALLOWED_TOOLS,
            log=io.StringIO(),
        )

    def test_edit_requires_closeout_and_fixed_authority_is_injected(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "call", "tool": "read_files", "params": {"paths": ["README.md"]}, "text": None},
            {"kind": "call", "tool": "edit_project_files", "params": {"edits": []}, "text": None},
            {"kind": "final", "tool": None, "params": None, "text": "too early"},
            {"kind": "call", "tool": "finish_coding_task", "params": {}, "text": None},
            {"kind": "final", "tool": None, "params": None, "text": "done"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("change one thing")
        self.assertEqual(result["final"], "done")
        self.assertEqual(result["session_id"], "wc_sess_test")
        self.assertEqual(len(state.relay_requests), 5)
        self.assertEqual(state.relay_requests[0]["text"]["format"]["type"], "json_schema")
        first_meta = json.loads(
            state.relay_requests[0]["client_metadata"]["x-codex-turn-metadata"]
        )
        second_meta = json.loads(
            state.relay_requests[1]["client_metadata"]["x-codex-turn-metadata"]
        )
        self.assertEqual(
            state.relay_requests[0]["prompt_cache_key"], first_meta["thread_id"]
        )
        self.assertEqual(first_meta["thread_id"], second_meta["thread_id"])
        self.assertNotEqual(first_meta["turn_id"], second_meta["turn_id"])
        first_user = state.relay_requests[0]["input"][-1]
        second_user = state.relay_requests[1]["input"][-1]
        self.assertEqual(
            first_user["internal_chat_message_metadata_passthrough"]["turn_id"],
            first_meta["turn_id"],
        )
        self.assertEqual(
            second_user["internal_chat_message_metadata_passthrough"]["turn_id"],
            second_meta["turn_id"],
        )
        read = next(req for req in state.webcodex_requests if req["tool"] == "read_files")
        edit = next(req for req in state.webcodex_requests if req["tool"] == "edit_project_files")
        finish = next(req for req in state.webcodex_requests if req["tool"] == "finish_coding_task")
        for req in (read, edit, finish):
            self.assertEqual(req["params"]["project"], "agent:runner:repo")
            self.assertEqual(req["params"]["session_id"], "wc_sess_test")
            self.assertEqual(req["recording_session_id"], "wc_sess_test")
        self.assertIs(finish["params"]["summary_only"], True)
        manifests = {
            req["params"].get("tool_name")
            for req in state.webcodex_requests
            if req["tool"] == "tool_manifest"
        }
        self.assertIn("review_changes", manifests)

    def test_project_retarget_is_rejected_before_effect(self):
        state = FakeState()
        state.relay_actions = [
            {
                "kind": "call",
                "tool": "read_files",
                "params": {"project": "agent:other:repo", "paths": ["README.md"]},
                "text": None,
            },
            {"kind": "final", "tool": None, "params": None, "text": "stopped"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("inspect")
        self.assertEqual(result["final"], "stopped")
        self.assertFalse(any(req["tool"] == "read_files" for req in state.webcodex_requests))
        self.assertEqual(len(state.relay_requests), 2)

    def test_undiscovered_added_tool_is_not_called(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "call", "tool": "run_shell", "params": {"command": "echo no"}, "text": None},
            {"kind": "final", "tool": None, "params": None, "text": "no call"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("do not run")
        self.assertEqual(result["final"], "no call")
        self.assertFalse(any(req["tool"] == "run_shell" for req in state.webcodex_requests))

    def test_resume_reads_exact_handoff(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "final", "tool": None, "params": None, "text": "continued"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("continue", "~s1")
        work = next(req for req in state.webcodex_requests if req["tool"] == "work_on_project")
        self.assertEqual(work["params"]["session_id"], "~s1")
        self.assertTrue(any(req["tool"] == "session_handoff_summary" for req in state.webcodex_requests))
        self.assertEqual(result["final"], "continued")

    def test_non_idempotent_mutation_is_not_dispatched_twice(self):
        state = FakeState()
        repeated = {"kind": "call", "tool": "edit_project_files", "params": {"edits": []}, "text": None}
        state.relay_actions = [
            repeated,
            repeated,
            {"kind": "call", "tool": "finish_coding_task", "params": {}, "text": None},
            {"kind": "final", "tool": None, "params": None, "text": "done"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("edit once")
        edits = [req for req in state.webcodex_requests if req["tool"] == "edit_project_files"]
        self.assertEqual(len(edits), 1)
        self.assertEqual(result["final"], "done")


    def test_later_mutation_invalidates_earlier_closeout_evidence(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "call", "tool": "finish_coding_task", "params": {}, "text": None},
            {"kind": "call", "tool": "edit_project_files", "params": {"edits": []}, "text": None},
            {"kind": "final", "tool": None, "params": None, "text": "stale closeout"},
            {"kind": "call", "tool": "finish_coding_task", "params": {}, "text": None},
            {"kind": "final", "tool": None, "params": None, "text": "fresh closeout"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("edit after an early review")
        finishes = [
            req for req in state.webcodex_requests
            if req["tool"] == "finish_coding_task"
        ]
        self.assertEqual(len(finishes), 2)
        self.assertEqual(result["final"], "fresh closeout")


    def test_allowed_but_undiscovered_tool_is_rejected_until_manifest(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "call", "tool": "show_changes", "params": {}, "text": None},
            {"kind": "discover", "tool": "show_changes", "params": None, "text": None},
            {"kind": "call", "tool": "show_changes", "params": {}, "text": None},
            {"kind": "final", "tool": None, "params": None, "text": "done"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("inspect changes")
        calls = [req for req in state.webcodex_requests if req["tool"] == "show_changes"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["final"], "done")

    def test_unknown_job_identity_is_rejected_before_webcodex(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "discover", "tool": "observe_jobs", "params": None, "text": None},
            {
                "kind": "call",
                "tool": "observe_jobs",
                "params": {"items": [{"job_id": "wc_job_other"}]},
                "text": None,
            },
            {"kind": "final", "tool": None, "params": None, "text": "blocked"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("observe only this task")
        self.assertEqual(result["final"], "blocked")
        self.assertFalse(any(req["tool"] == "observe_jobs" for req in state.webcodex_requests))

    def test_current_project_job_identity_can_be_observed(self):
        state = FakeState()
        state.relay_actions = [
            {
                "kind": "call",
                "tool": "project_validate",
                "params": {"action": "check"},
                "text": None,
            },
            {"kind": "discover", "tool": "observe_jobs", "params": None, "text": None},
            {
                "kind": "call",
                "tool": "observe_jobs",
                "params": {"items": [{"job_id": "wc_job_current"}]},
                "text": None,
            },
            {"kind": "final", "tool": None, "params": None, "text": "observed"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("validate and observe")
        observations = [
            req for req in state.webcodex_requests if req["tool"] == "observe_jobs"
        ]
        self.assertEqual(len(observations), 1)
        self.assertEqual(result["final"], "observed")


    def test_webcodex_mutation_disconnect_is_not_retried(self):
        state = FakeState()
        state.drop_webcodex_tool = "edit_project_files"
        state.relay_actions = [
            {"kind": "call", "tool": "edit_project_files", "params": {"edits": []}, "text": None},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            with self.assertRaises(driver.OutcomeUnknown):
                self.make_driver(relay_url, wc_url).run("edit once")
        edits = [req for req in state.webcodex_requests if req["tool"] == "edit_project_files"]
        self.assertEqual(len(edits), 1)
        self.assertEqual(len(state.relay_requests), 1)

    def test_relay_disconnect_is_not_retried(self):
        state = FakeState()
        state.drop_relay = True
        with fake_servers(state) as (relay_url, wc_url):
            with self.assertRaises(driver.OutcomeUnknown):
                self.make_driver(relay_url, wc_url).run("inspect")
        self.assertEqual(len(state.relay_requests), 1)

    def test_http_200_incomplete_response_cannot_drive_an_effect(self):
        state = FakeState()
        state.relay_response_override = {
            "id": "resp_incomplete",
            "status": "incomplete",
            "end_turn": False,
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [{
                "type": "message",
                "role": "assistant",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps({
                        "kind": "call",
                        "tool": "edit_project_files",
                        "params": {"edits": []},
                        "text": None,
                    }, separators=(",", ":")),
                }],
            }],
        }
        with fake_servers(state) as (relay_url, wc_url):
            with self.assertRaisesRegex(driver.DriverError, "completed end_turn evidence"):
                self.make_driver(relay_url, wc_url).run("edit")
        self.assertEqual(len(state.relay_requests), 1)
        self.assertFalse(any(req["tool"] == "edit_project_files" for req in state.webcodex_requests))

    def test_relay_post_send_failure_codes_are_outcome_unknown(self):
        for status in (200, 502):
            for code in ("chatgpt_submission_ambiguous", "chatgpt_submitted_turn_failed"):
                with self.subTest(status=status, code=code):
                    state = FakeState()
                    state.relay_status = status
                    state.relay_response_override = {
                        "id": "resp_failed",
                        "status": "failed",
                        "end_turn": False,
                        "error": {
                            "type": "server_error",
                            "code": code,
                            "message": "delivery state is not safe to replay",
                        },
                        "output": [],
                    }
                    with fake_servers(state) as (relay_url, wc_url):
                        with self.assertRaises(driver.OutcomeUnknown):
                            self.make_driver(relay_url, wc_url).run("inspect")
                    self.assertEqual(len(state.relay_requests), 1)


if __name__ == "__main__":
    unittest.main()
