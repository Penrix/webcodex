from __future__ import annotations

import importlib.util
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
                            "observation_token": "b",
                        },
                        "error_kind": None,
                        "error": None,
                    },
                ]
            },
        }
        self.assertEqual(driver.terminal_job_ids(result), {"wc_job_done"})


class LiveAcceptanceJobEvidenceTests(unittest.TestCase):
    @staticmethod
    def stderr(
        *,
        handoff: str = "wc_job_slow",
        terminal: str | None = "wc_job_slow",
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
        return "\n".join(lines) + "\n"

    def test_exact_same_job_terminal_observation_passes(self):
        live.require_exact_run_process_job_observation(self.stderr())

    def test_mismatched_terminal_job_is_rejected(self):
        with self.assertRaisesRegex(
            live.AcceptanceError,
            "run_process durable Job was not terminal-observed",
        ):
            live.require_exact_run_process_job_observation(
                self.stderr(terminal="wc_job_other")
            )

    def test_missing_terminal_observation_is_rejected(self):
        with self.assertRaisesRegex(
            live.AcceptanceError,
            "run_process durable Job was not terminal-observed",
        ):
            live.require_exact_run_process_job_observation(
                self.stderr(terminal=None)
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
