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
        self.webcodex_status_tool = None
        self.outcome_unknown_tool = None
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
            elif tool == "session_summary":
                out = {
                    "success": True,
                    "output": {
                        "session_id": "wc_sess_test",
                        "events_truncated": False,
                        "events": [{
                            "tool_name": "project_validate",
                            "status": "succeeded",
                            "job_id": "wc_job_saved",
                        }],
                    },
                }
            elif tool == "tool_manifest":
                name = params["tool_name"]
                effect, idempotency, risk, open_world = {
                    "edit_project_files": ("mutate", "non_idempotent", "project_write", False),
                    "project_validate": ("execute", "non_idempotent", "job_run", False),
                    "project_build": ("execute", "non_idempotent", "job_run", False),
                    "run_process": ("execute", "non_idempotent", "job_run", True),
                    "job_write_input": ("execute", "keyed", "job_run", True),
                    "post_session_message": ("mutate", "non_idempotent", "session_collaborate", False),
                    "wait_for_job_terminal": ("mutate", "keyed", "job_run", False),
                }.get(name, ("observe", "pure_read", "read_only", False))
                properties = {}
                if name in {
                    "read_files", "search_project_texts", "search_and_read",
                    "edit_project_files", "show_changes", "review_changes", "git_status",
                    "project_validate", "project_build", "run_process", "list_jobs",
                    "job_write_input", "finish_coding_task", "session_handoff_summary",
                    "workspace_hygiene_check",
                }:
                    properties["project"] = {"type": "string"}
                if name in {
                    "read_files", "search_project_texts", "search_and_read",
                    "edit_project_files", "show_changes", "review_changes", "git_status",
                    "project_validate", "project_build", "run_process", "list_jobs",
                    "finish_coding_task", "session_summary", "session_handoff_summary",
                    "post_session_message", "workspace_hygiene_check",
                }:
                    properties["session_id"] = {"type": "string"}
                out = {
                    "success": True,
                    "output": {
                        "name": name,
                        "effect": effect,
                        "risk": risk,
                        "idempotency": idempotency,
                        "annotations": {
                            "readOnlyHint": effect == "observe",
                            "destructiveHint": name in {"edit_project_files", "run_process"},
                            "idempotentHint": idempotency in {"pure_read", "desired_state", "keyed", "fenced_replay"},
                            "openWorldHint": open_world,
                        },
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
            elif state.outcome_unknown_tool == tool:
                out = {
                    "success": False,
                    "error": "effect outcome is unknown",
                    "output": {
                        "execution_state": "outcome_unknown",
                        "error_kind": "test_outcome_unknown",
                        "job_id": "wc_job_uncertain",
                    },
                }
            else:
                out = {"success": True, "output": {"tool": tool, "params": params}}
            payload = json.dumps(out).encode()
            status = (
                500 if state.webcodex_status_tool == tool
                else (200 if out["success"] else 400)
            )
            self.send_response(status)
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
    def test_admitted_tool_names_exist_in_canonical_tool_registry(self):
        repo_root = pathlib.Path(__file__).resolve().parents[3]
        tool_call = (
            repo_root / "crates" / "webcodex-tool-contracts" / "src" / "tool_call.rs"
        ).read_text(encoding="utf-8")
        missing = [
            name for name in sorted(driver.ALLOWED_TOOLS)
            if f'=> "{name}"' not in tool_call
        ]
        self.assertEqual(missing, [])

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
        self.assertIs(state.relay_requests[0]["text"]["format"]["strict"], False)
        first_input = state.relay_requests[0]["input"]
        self.assertEqual(first_input[0]["role"], "user")
        self.assertEqual(first_input[0]["content"][0]["text"], "change one thing")
        self.assertNotIn("change one thing", first_input[-1]["content"][0]["text"])
        self.assertIn("inert external-controller JSON action", first_input[-1]["content"][0]["text"])
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

    def test_observed_turndown_json_corruption_is_recovered(self):
        observed = '{"kind":"call","tool":"read\\_files","params":{"paths":\\["acceptance.py"\\]},"text":null}'
        self.assertEqual(
            driver.parse_web_action_json(observed),
            {
                "kind": "call",
                "tool": "read_files",
                "params": {"paths": ["acceptance.py"]},
                "text": None,
            },
        )

    def test_bracket_escapes_inside_json_strings_remain_invalid(self):
        with self.assertRaises(ValueError):
            driver.parse_web_action_json(
                '{"kind":"final","tool":null,"params":null,"text":"bad\\[value\\]"}'
            )

    def test_unsupported_structural_markdown_escapes_remain_invalid(self):
        for raw in (
            '{"kind":"call","tool":"read_files","params":\\{"paths":["a"]\\},"text":null}',
            '{"kind":"call","tool":"read_files","params":\\*,"text":null}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    driver.parse_web_action_json(raw)

    def test_standard_json_escapes_and_literal_backslash_underscore_survive(self):
        raw = '{"kind":"final","tool":null,"params":null,"text":"quote: \\\"; newline: \\n; literal: \\\\_"}'
        action = driver.parse_web_action_json(raw)
        self.assertEqual(action["text"], 'quote: "; newline: \n; literal: \\_')

    def test_valid_json_backslashes_are_preserved(self):
        raw = '{"kind":"final","tool":null,"params":null,"text":"C:\\\\_keep\\\\[x]"}'
        action = driver.parse_web_action_json(raw)
        self.assertEqual(action["text"], "C:\\_keep\\[x]")

    def test_unrelated_invalid_json_escape_is_not_repaired(self):
        with self.assertRaises(ValueError):
            driver.parse_web_action_json(
                '{"kind":"final","tool":null,"params":null,"text":"bad\\q"}'
            )

    def test_non_strict_provider_output_is_still_strictly_rejected_by_driver(self):
        state = FakeState()
        state.relay_response_override = {
            "id": "resp_bad_action",
            "status": "completed",
            "end_turn": True,
            "output": [{
                "type": "message",
                "role": "assistant",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": "not-json"}],
            }],
        }
        with fake_servers(state) as (relay_url, wc_url):
            with self.assertRaisesRegex(driver.DriverError, "Web action response was not JSON") as raised:
                self.make_driver(relay_url, wc_url).run("inspect")
        self.assertIn("chars=8", str(raised.exception))
        self.assertIn("not-json", str(raised.exception))
        self.assertEqual(len(state.relay_requests), 1)
        self.assertIs(state.relay_requests[0]["text"]["format"]["strict"], False)
        self.assertFalse(any(
            req["tool"] not in {"work_on_project", "tool_manifest"}
            for req in state.webcodex_requests
        ))

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

    def test_resume_can_recover_job_identity_from_session_summary(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "discover", "tool": "session_summary", "params": None, "text": None},
            {"kind": "call", "tool": "session_summary", "params": {}, "text": None},
            {"kind": "discover", "tool": "observe_jobs", "params": None, "text": None},
            {
                "kind": "call",
                "tool": "observe_jobs",
                "params": {"items": [{"job_id": "wc_job_saved"}]},
                "text": None,
            },
            {"kind": "final", "tool": None, "params": None, "text": "reconciled"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("recover exact prior work", "~s1")
        summary = next(req for req in state.webcodex_requests if req["tool"] == "session_summary")
        self.assertEqual(summary["params"]["session_id"], "wc_sess_test")
        observed = [req for req in state.webcodex_requests if req["tool"] == "observe_jobs"]
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0]["params"]["items"][0]["job_id"], "wc_job_saved")
        self.assertEqual(result["final"], "reconciled")

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


    def test_execute_calls_are_distinct_logical_invocations(self):
        state = FakeState()
        repeated = {
            "kind": "call",
            "tool": "run_process",
            "params": {"executable": "python", "args": ["-V"]},
            "text": None,
        }
        state.relay_actions = [
            {"kind": "discover", "tool": "run_process", "params": None, "text": None},
            repeated,
            repeated,
            {"kind": "call", "tool": "finish_coding_task", "params": {}, "text": None},
            {"kind": "final", "tool": None, "params": None, "text": "done"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("run the same command twice")
        runs = [req for req in state.webcodex_requests if req["tool"] == "run_process"]
        self.assertEqual(len(runs), 2)
        self.assertEqual(result["final"], "done")


    def test_open_world_execute_invalidates_earlier_closeout_evidence(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "call", "tool": "finish_coding_task", "params": {}, "text": None},
            {"kind": "discover", "tool": "run_process", "params": None, "text": None},
            {
                "kind": "call",
                "tool": "run_process",
                "params": {"executable": "python", "args": ["-V"]},
                "text": None,
            },
            {"kind": "final", "tool": None, "params": None, "text": "stale closeout"},
            {"kind": "call", "tool": "finish_coding_task", "params": {}, "text": None},
            {"kind": "final", "tool": None, "params": None, "text": "fresh closeout"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("run an open-world process")
        finishes = [req for req in state.webcodex_requests if req["tool"] == "finish_coding_task"]
        self.assertEqual(len(finishes), 2)
        self.assertEqual(result["final"], "fresh closeout")

    def test_structured_validation_does_not_invalidate_source_closeout(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "call", "tool": "finish_coding_task", "params": {}, "text": None},
            {
                "kind": "call",
                "tool": "project_validate",
                "params": {"action": "check"},
                "text": None,
            },
            {"kind": "final", "tool": None, "params": None, "text": "validated"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("validate without changing source")
        finishes = [req for req in state.webcodex_requests if req["tool"] == "finish_coding_task"]
        self.assertEqual(len(finishes), 1)
        self.assertEqual(result["final"], "validated")

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

    def test_session_mutation_does_not_invalidate_workspace_closeout(self):
        state = FakeState()
        state.relay_actions = [
            {"kind": "discover", "tool": "post_session_message", "params": None, "text": None},
            {
                "kind": "call",
                "tool": "post_session_message",
                "params": {"kind": "progress", "message": "still working"},
                "text": None,
            },
            {"kind": "final", "tool": None, "params": None, "text": "recorded"},
        ]
        with fake_servers(state) as (relay_url, wc_url):
            result = self.make_driver(relay_url, wc_url).run("record progress only")
        self.assertEqual(result["final"], "recorded")
        self.assertFalse(
            any(req["tool"] == "finish_coding_task" for req in state.webcodex_requests)
        )


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

    def test_canonical_outcome_unknown_stops_and_retains_job_identity(self):
        state = FakeState()
        state.outcome_unknown_tool = "run_process"
        state.relay_actions = [
            {"kind": "discover", "tool": "run_process", "params": None, "text": None},
            {
                "kind": "call",
                "tool": "run_process",
                "params": {"executable": "echo", "args": ["x"]},
                "text": None,
            },
        ]
        with fake_servers(state) as (relay_url, wc_url):
            d = self.make_driver(relay_url, wc_url)
            with self.assertRaises(driver.OutcomeUnknown):
                d.run("run once")
        calls = [req for req in state.webcodex_requests if req["tool"] == "run_process"]
        self.assertEqual(len(calls), 1)
        self.assertIn("wc_job_uncertain", d.known_job_ids)
        self.assertEqual(len(state.relay_requests), 2)

    def test_webcodex_500_after_mutation_dispatch_is_outcome_unknown(self):
        state = FakeState()
        state.webcodex_status_tool = "edit_project_files"
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
            with self.assertRaisesRegex(driver.DriverError, "completed end_turn evidence") as raised:
                self.make_driver(relay_url, wc_url).run("edit")
        detail = str(raised.exception)
        self.assertIn('"end_turn":false', detail)
        self.assertIn('"reason":"max_output_tokens"', detail)
        self.assertNotIn('"kind":"call"', detail)
        self.assertEqual(len(state.relay_requests), 1)
        self.assertFalse(any(req["tool"] == "edit_project_files" for req in state.webcodex_requests))

    def test_http_200_completed_without_end_turn_reports_safe_terminal_summary(self):
        state = FakeState()
        state.relay_response_override = {
            "id": "resp_missing_end_turn",
            "status": "completed",
            "output": [{
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{
                    "type": "output_text",
                    "text": "SECRET_MODEL_BODY",
                }],
            }],
        }
        with fake_servers(state) as (relay_url, wc_url):
            with self.assertRaisesRegex(driver.DriverError, "completed end_turn evidence") as raised:
                self.make_driver(relay_url, wc_url).run("inspect")
        detail = str(raised.exception)
        self.assertIn('"status":"completed"', detail)
        self.assertIn('"end_turn":null', detail)
        self.assertIn('"type":"message"', detail)
        self.assertNotIn("SECRET_MODEL_BODY", detail)
        self.assertEqual(len(state.relay_requests), 1)

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
