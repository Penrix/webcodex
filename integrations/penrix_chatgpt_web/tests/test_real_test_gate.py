from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))


class RealTestGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "gate.json"
        self.now = 1000.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def gate(self):
        from real_test_driver import RealTestGate
        return RealTestGate(self.path, clock=lambda: self.now, sleep=self.sleep)

    def test_unknown_send_time_waits_thirty_seconds_without_sending(self):
        gate = self.gate()
        called = []
        gate.run(lambda: called.append(self.now))
        self.assertEqual(called, [1030.0])
        self.assertEqual(self.sleeps, [30.0])

    def test_completion_then_shared_cooldown_before_next_process(self):
        gate = self.gate()
        gate.run(lambda: setattr(self, "now", self.now + 75))
        called = []
        self.gate().run(lambda: called.append(self.now))
        self.assertEqual(called, [1135.0])
        self.assertEqual(self.sleeps, [30.0, 30.0])

    def test_fractional_completion_never_rounds_cooldown_below_thirty_seconds(self):
        self.now = 1000.0004
        gate = self.gate()
        gate.run(lambda: None)
        completed_at = self.now
        gate.run(lambda: None)
        self.assertGreaterEqual(self.now - completed_at, 30.0)

    def test_longer_existing_cooldown_and_fields_are_preserved(self):
        self.path.write_text(json.dumps({"nextAllowedAt": 1400000, "custom": "keep"}))
        self.gate().run(lambda: None)
        self.assertEqual(self.sleeps, [400.0])
        state = json.loads(self.path.read_text())
        self.assertEqual(state["custom"], "keep")
        self.assertGreaterEqual(state["nextAllowedAt"], 1430000)

    def test_rate_limit_or_uncertain_result_stops_all_later_sends(self):
        gate = self.gate()
        with self.assertRaisesRegex(RuntimeError, "429"):
            gate.run(lambda: (_ for _ in ()).throw(RuntimeError("429")))
        called = []
        with self.assertRaisesRegex(RuntimeError, "stopped"):
            self.gate().run(lambda: called.append(True))
        self.assertEqual(called, [])

    def test_concurrent_operator_is_rejected_before_any_send(self):
        from real_test_driver import RealTestGate
        called = []
        def outer():
            with self.assertRaisesRegex(RuntimeError, "active"):
                self.gate().run(lambda: called.append(True))
        self.gate().run(outer)
        self.assertEqual(called, [])

    def test_persisted_pending_turn_never_becomes_retry_permission(self):
        self.path.write_text(json.dumps({"blocked": "previous turn pending"}))
        called = []
        with self.assertRaisesRegex(RuntimeError, "stopped"):
            self.gate().run(lambda: called.append(True))
        self.assertEqual(called, [])

    def test_actual_model_http_path_is_paced_before_dispatch(self):
        from real_test_driver import TestWebModel
        from test_driver import FakeState, fake_servers
        state = FakeState()
        action = {"kind": "final", "tool": None, "params": None, "text": "OK"}
        state.relay_actions = [action, action]
        with fake_servers(state) as (relay_url, _):
            model = TestWebModel(relay_url, "test", "low", 5)
            model.gate = self.gate()
            self.assertEqual(model.next([], "one")[0], action)
            self.assertEqual(model.next([], "two")[0], action)
        self.assertEqual(len(state.relay_requests), 2)
        self.assertEqual(self.sleeps, [30.0, 30.0])

    def test_actual_model_429_cannot_dispatch_a_second_http_request(self):
        from real_test_driver import TestWebModel
        from test_driver import FakeState, fake_servers
        state = FakeState()
        state.relay_status = 429
        state.relay_response_override = {"error": {"code": "rate_limit_exceeded"}}
        with fake_servers(state) as (relay_url, _):
            model = TestWebModel(relay_url, "test", "low", 5)
            model.gate = self.gate()
            with self.assertRaisesRegex(RuntimeError, "429"):
                model.next([], "one")
            with self.assertRaisesRegex(RuntimeError, "stopped"):
                model.next([], "two")
        self.assertEqual(len(state.relay_requests), 1)


if __name__ == "__main__":
    unittest.main()
