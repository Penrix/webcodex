import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import provider_probe as probe  # noqa: E402


class ProviderProbeTests(unittest.TestCase):
    def test_planner_request_keeps_owner_task_in_history_and_current_turn_planner_only(self):
        thread_id = "penrix_probe_thread_test"
        request = probe.build_request(
            model=probe.DEFAULT_MODEL,
            effort="high",
            thread_id=thread_id,
            instructions=probe.PLANNER_INSTRUCTIONS,
            history=[probe.message("user", "OWNER_TASK_NEEDS_LOCAL_READ")],
            current_prompt="CURRENT_PLANNER_ONLY",
            schema_name="planner",
            schema=probe.PLANNER_SCHEMA,
        )
        self.assertEqual(request["prompt_cache_key"], thread_id)
        self.assertEqual(request["input"][0]["role"], "user")
        self.assertEqual(
            request["input"][0]["content"][0]["text"],
            "OWNER_TASK_NEEDS_LOCAL_READ",
        )
        current = request["input"][-1]
        self.assertEqual(current["role"], "user")
        self.assertEqual(current["content"][0]["text"], "CURRENT_PLANNER_ONLY")
        self.assertEqual(
            current["internal_chat_message_metadata_passthrough"]["turn_id"],
            json.loads(request["client_metadata"]["x-codex-turn-metadata"])["turn_id"],
        )
        self.assertIs(request["text"]["format"]["strict"], False)
        self.assertEqual(request["text"]["format"]["schema"], probe.PLANNER_SCHEMA)

    def test_non_json_final_answer_reports_bounded_preview(self):
        body = {
            "status": "completed",
            "end_turn": True,
            "output": [{
                "type": "message",
                "role": "assistant",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": "I cannot access local files."}],
            }],
        }
        with self.assertRaisesRegex(
            probe.ProbeError,
            "final answer was not JSON.*I cannot access local files",
        ):
            probe.require_json_action("planner_semantics", 200, body)

    def test_baseline_and_planner_expectations_are_exact(self):
        probe.expect_baseline(
            {"kind": "final", "tool": None, "params": None, "text": "OK"}
        )
        probe.expect_planner(
            {
                "kind": "call",
                "tool": "read_files",
                "params": {"paths": ["acceptance.py"]},
                "text": None,
            }
        )
        with self.assertRaises(probe.ProbeError):
            probe.expect_planner(
                {"kind": "final", "tool": None, "params": None, "text": "no"}
            )

    def test_planner_only_runs_without_repeating_baseline(self):
        calls = []

        def fake_run_one(client, base, **kwargs):
            calls.append(kwargs["name"])
            return {"name": kwargs["name"], "status": "passed"}

        class FakeClient:
            pass

        original_client = probe.JsonClient
        original_health = probe.relay_health
        original_run_one = probe.run_one
        try:
            probe.JsonClient = lambda timeout: FakeClient()
            probe.relay_health = lambda client, base: {
                "version": "6.1.3",
                "mode": "browser-only",
            }
            probe.run_one = fake_run_one
            result = probe.run_probe(
                probe.DEFAULT_RELAY_URL,
                probe.DEFAULT_MODEL,
                "high",
                180.0,
                "planner",
            )
        finally:
            probe.JsonClient = original_client
            probe.relay_health = original_health
            probe.run_one = original_run_one

        self.assertEqual(calls, ["planner_semantics"])
        self.assertEqual(result["probes"][0]["name"], "planner_semantics")

    def test_terminal_failure_preserves_status_and_text_preview(self):
        body = {
            "status": "completed",
            "output": [{
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": '{"kind":"final"}'}],
            }],
        }
        with self.assertRaisesRegex(
            probe.ProbeError,
            "terminal failure.*end_turn.*final_text_preview",
        ):
            probe.require_json_action("json_baseline", 200, body)


if __name__ == "__main__":
    unittest.main()
