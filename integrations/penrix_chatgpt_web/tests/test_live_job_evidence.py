from __future__ import annotations

import importlib.util
import io
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).parents[1]


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


driver = load_module("penrix_web_driver_job_evidence", "driver.py")
live = load_module("penrix_web_live_job_evidence", "live_acceptance.py")


def execute_manifest(*, open_world: bool) -> dict:
    return {
        "success": True,
        "output": {
            "input_schema": {"type": "object", "properties": {}},
            "effect": "execute",
            "idempotency": "non_idempotent",
            "risk": "job_run",
            "annotations": {"openWorldHint": open_world},
        },
    }


class FakeJobWebCodex:
    def call(self, tool, params, session=None):
        if tool == "run_process":
            return {
                "success": True,
                "output": {
                    "execution_state": "pending",
                    "continuation": {
                        "arguments": {
                            "items": [
                                {
                                    "job_id": "wc_job_slow",
                                    "after_observation_token": "token-1",
                                }
                            ]
                        }
                    },
                },
            }
        if tool == "observe_jobs":
            return {
                "success": True,
                "output": {
                    "items": [
                        {
                            "job_id": "wc_job_slow",
                            "status": "completed",
                            "terminal": True,
                            "exit_code": 0,
                            "observation_token": "token-2",
                        }
                    ]
                },
            }
        raise AssertionError(f"unexpected tool: {tool}")


class DriverJobEvidenceTests(unittest.TestCase):
    def test_job_ids_include_pending_continuation_identity(self):
        result = {
            "success": True,
            "output": {
                "execution_state": "pending",
                "continuation": {
                    "arguments": {
                        "items": [
                            {
                                "job_id": "wc_job_slow",
                                "after_observation_token": "token-1",
                            }
                        ]
                    }
                },
            },
        }
        self.assertEqual(driver.job_ids(result), {"wc_job_slow"})

    def test_terminal_job_ids_require_canonical_terminal_true(self):
        result = {
            "success": True,
            "output": {
                "items": [
                    {
                        "job_id": "wc_job_running",
                        "status": "running",
                        "terminal": False,
                        "observation_token": "a",
                    },
                    {
                        "index": 1,
                        "job_id": "wc_job_done",
                        "success": True,
                        "output": {
                            "job_id": "wc_job_done",
                            "status": "completed",
                            "terminal": True,
                            "exit_code": 0,
                            "observation_token": "b",
                        },
                        "error_kind": None,
                        "error": None,
                    },
                ]
            },
        }
        self.assertEqual(driver.terminal_job_ids(result), {"wc_job_done"})

    def test_successful_terminal_job_ids_require_completed_zero_exit(self):
        result = {
            "success": True,
            "output": {
                "items": [
                    {
                        "job_id": "wc_job_good",
                        "status": "completed",
                        "terminal": True,
                        "exit_code": 0,
                    },
                    {
                        "job_id": "wc_job_nonzero",
                        "status": "completed",
                        "terminal": True,
                        "exit_code": 1,
                    },
                    {
                        "job_id": "wc_job_failed",
                        "status": "failed",
                        "terminal": True,
                        "exit_code": 1,
                    },
                    {
                        "job_id": "wc_job_running",
                        "status": "running",
                        "terminal": False,
                        "exit_code": None,
                    },
                    {
                        "job_id": "wc_job_bool_exit",
                        "status": "completed",
                        "terminal": True,
                        "exit_code": False,
                    },
                ]
            },
        }
        self.assertEqual(driver.successful_terminal_job_ids(result), {"wc_job_good"})

    def test_execute_logs_canonical_handoff_terminal_and_success(self):
        log = io.StringIO()
        instance = driver.Driver(
            FakeJobWebCodex(),
            None,
            "wc_proj_test",
            allowed={"run_process", "observe_jobs"},
            log=log,
        )
        instance.contracts["run_process"] = execute_manifest(open_world=True)
        instance.contracts["observe_jobs"] = execute_manifest(open_world=False)

        instance.execute("run_process", {}, "wc_sess_test")
        instance.execute(
            "observe_jobs",
            {"items": [{"job_id": "wc_job_slow"}]},
            "wc_sess_test",
        )

        stderr = log.getvalue()
        self.assertIn(
            "[penrix-web] job_evidence event=handoff "
            "tool=run_process job_id=wc_job_slow",
            stderr,
        )
        self.assertIn(
            "[penrix-web] job_evidence event=terminal_observation "
            "tool=observe_jobs job_id=wc_job_slow",
            stderr,
        )
        self.assertIn(
            "[penrix-web] job_evidence event=terminal_success "
            "tool=observe_jobs job_id=wc_job_slow",
            stderr,
        )
        live.require_exact_run_process_job_observation(stderr)


class LiveAcceptanceJobEvidenceTests(unittest.TestCase):
    @staticmethod
    def stderr(
        *,
        handoff: str = "wc_job_slow",
        terminal: str | None = "wc_job_slow",
        successful: str | None = "wc_job_slow",
        run_process_calls: int = 1,
    ) -> str:
        lines = ["[penrix-web] WebCodex tool: run_process"] * run_process_calls
        lines.append(
            f"[penrix-web] job_evidence event=handoff tool=run_process job_id={handoff}"
        )
        lines.append("[penrix-web] WebCodex tool: observe_jobs")
        if terminal is not None:
            lines.append(
                "[penrix-web] job_evidence event=terminal_observation "
                f"tool=observe_jobs job_id={terminal}"
            )
        if successful is not None:
            lines.append(
                "[penrix-web] job_evidence event=terminal_success "
                f"tool=observe_jobs job_id={successful}"
            )
        return "\n".join(lines) + "\n"

    def test_exact_same_job_terminal_success_passes(self):
        live.require_exact_run_process_job_observation(self.stderr())

    def test_acceptance_does_not_invent_job_id_suffix_grammar(self):
        future_id = "wc_job_future.v2:opaque"
        live.require_exact_run_process_job_observation(
            self.stderr(
                handoff=future_id,
                terminal=future_id,
                successful=future_id,
            )
        )

    def test_mismatched_terminal_job_is_rejected(self):
        with self.assertRaisesRegex(
            live.AcceptanceError,
            "run_process durable Job was not terminal-observed",
        ):
            live.require_exact_run_process_job_observation(
                self.stderr(terminal="wc_job_other", successful=None)
            )

    def test_missing_terminal_observation_is_rejected(self):
        with self.assertRaisesRegex(
            live.AcceptanceError,
            "run_process durable Job was not terminal-observed",
        ):
            live.require_exact_run_process_job_observation(
                self.stderr(terminal=None, successful=None)
            )

    def test_failed_terminal_job_is_rejected(self):
        with self.assertRaisesRegex(
            live.AcceptanceError,
            "run_process durable Job did not report successful completion",
        ):
            live.require_exact_run_process_job_observation(
                self.stderr(successful=None)
            )

    def test_success_for_different_job_is_rejected(self):
        with self.assertRaisesRegex(
            live.AcceptanceError,
            "run_process durable Job did not report successful completion",
        ):
            live.require_exact_run_process_job_observation(
                self.stderr(successful="wc_job_other")
            )

    def test_duplicate_run_process_execution_is_rejected(self):
        with self.assertRaisesRegex(
            live.AcceptanceError,
            "expected exactly one run_process dispatch",
        ):
            live.require_exact_run_process_job_observation(
                self.stderr(run_process_calls=2)
            )

    def test_tool_names_alone_are_not_job_evidence(self):
        with self.assertRaisesRegex(
            live.AcceptanceError,
            "exactly one durable run_process Job handoff",
        ):
            live.require_exact_run_process_job_observation(
                "[penrix-web] WebCodex tool: run_process\n"
                "[penrix-web] WebCodex tool: observe_jobs\n"
            )


if __name__ == "__main__":
    unittest.main()
