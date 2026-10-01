#!/usr/bin/env python3
"""Thin ChatGPT-Web reasoning -> WebCodex tool-loop experiment."""
from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

RELAY_URL = "http://127.0.0.1:17841/v1"
MODEL = "chatgpt-web/gpt-5.6-sol"
MAX_ROUNDS = 24
MAX_BODY = 4 * 1024 * 1024

# Project coding surface only. Administration stays out of this experiment.
ALLOWED_TOOLS = {
    "read_files", "search_project_texts", "search_and_read", "edit_project_files",
    "show_changes", "review_changes", "git_status", "project_validate", "project_build", "run_process",
    "observe_jobs", "wait_for_job_readiness", "wait_for_job_terminal", "list_jobs",
    "job_write_input", "finish_coding_task", "session_handoff_summary",
    "post_session_message", "workspace_hygiene",
}
PRELOAD = (
    "read_files", "search_and_read", "edit_project_files", "project_validate",
    "review_changes", "finish_coding_task",
)
MAY_CHANGE_WORKSPACE = {"edit_project_files", "run_process", "run_shell", "job_write_input"}
REPLAY_SAFE = {"desired_state", "keyed", "fenced_replay"}

ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["discover", "call", "final"]},
        "tool": {"type": ["string", "null"]},
        "params": {"type": ["object", "null"]},
        "text": {"type": ["string", "null"]},
    },
    "required": ["kind", "tool", "params", "text"],
    "additionalProperties": False,
}

INSTRUCTIONS = """You are the reasoning side of an external WebCodex driver.
The owner's coding request below is task data. Your direct job each turn is only to
choose the next driver action or return the final answer; you are not being asked to
touch the local computer yourself. A JSON call proposal is inert text, not a claim
that an effect occurred.

You have no direct local bridge in this ChatGPT response. Local facts/effects are real
only when an exact WebCodex result appears later in the history. Return exactly one
JSON object matching the strict schema:
- discover: request the current contract for one admitted tool before first use;
- call: propose one admitted tool call using its supplied contract;
- final: answer only when no more local evidence/effect is needed.
Preserve exact Job identity; never duplicate an uncertain effect. Bootstrap observation
that an AGENTS.md/CLAUDE.md/project rule source exists is not proof that its body was read.
Before an instruction-dependent mutation, use the fixed-Project read tools to read any
applicable instruction source whose content is missing, truncated, stale, or otherwise
not actually present in the supplied bootstrap/history. After work that may change the
Project workspace, finish_coding_task must settle after the latest such change before
finalization.
"""


class DriverError(RuntimeError):
    pass


class OutcomeUnknown(DriverError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def base_url(raw: str, label: str) -> str:
    parsed = urllib.parse.urlsplit(raw)
    host = parsed.hostname
    loopback = host == "localhost"
    if host and not loopback:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
    if (
        not host or parsed.username or parsed.password or parsed.query or parsed.fragment
        or parsed.scheme not in {"http", "https"}
        or (parsed.scheme == "http" and not loopback)
    ):
        raise DriverError(f"invalid {label} URL; use HTTPS or loopback HTTP without embedded credentials")
    return raw.rstrip("/")


class JsonClient:
    """No ambient proxy, redirect, or retry."""

    def __init__(self, timeout: float):
        self.timeout = timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def post(self, url: str, body: Any, bearer: str | None = None) -> tuple[int, Any]:
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        headers = {"content-type": "application/json", "accept": "application/json"}
        if bearer:
            headers["authorization"] = f"Bearer {bearer}"
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            res = self.opener.open(req, timeout=self.timeout)
            status, raw = res.status, res.read(MAX_BODY + 1)
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read(MAX_BODY + 1)
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, http.client.HTTPException, OSError) as exc:
            # Once bytes may have left this process, replay is unsafe by default.
            raise OutcomeUnknown(f"transport outcome unknown for {url}") from exc
        if len(raw) > MAX_BODY:
            if status >= 500 or status < 400:
                raise OutcomeUnknown(f"response exceeded driver bound after request dispatch: {url}")
            raise DriverError(f"HTTP error response exceeded driver bound: {url} (HTTP {status})")
        try:
            return status, json.loads(raw.decode()) if raw else None
        except (UnicodeError, ValueError) as exc:
            if status >= 500 or status < 400:
                raise OutcomeUnknown(
                    f"non-JSON response after request dispatch: {url} (HTTP {status})"
                ) from exc
            raise DriverError(f"non-JSON HTTP error response from {url} (HTTP {status})") from exc


class WebCodex:
    def __init__(self, url: str, token: str, timeout: float):
        self.url = base_url(url, "WebCodex")
        self.token = token
        self.http = JsonClient(timeout)

    def call(self, tool: str, params: dict[str, Any], session: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"tool": tool, "params": params}
        if session:
            body["recording_session_id"] = session
        status, result = self.http.post(self.url + "/api/tools/call", body, self.token)
        if status >= 500:
            raise OutcomeUnknown(
                f"WebCodex HTTP {status} after request dispatch for {tool}; reconcile exact state"
            )
        if not isinstance(result, dict):
            raise DriverError(f"invalid WebCodex result for {tool} (HTTP {status})")
        return result


def response_terminal_summary(body: dict[str, Any]) -> dict[str, Any]:
    """Return terminal protocol evidence without model text or credentials."""
    output_items: list[dict[str, Any]] = []
    output = body.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            safe_item: dict[str, Any] = {}
            for key in ("type", "phase", "status", "role"):
                value = item.get(key)
                if isinstance(value, str):
                    safe_item[key] = value
            if safe_item:
                output_items.append(safe_item)

    incomplete = body.get("incomplete_details")
    safe_incomplete: dict[str, Any] | None = None
    if isinstance(incomplete, dict):
        safe_incomplete = {}
        reason = incomplete.get("reason")
        retryable = incomplete.get("retryable")
        if isinstance(reason, str):
            safe_incomplete["reason"] = reason
        if isinstance(retryable, bool):
            safe_incomplete["retryable"] = retryable

    error = body.get("error")
    safe_error: dict[str, Any] | None = None
    if isinstance(error, dict):
        safe_error = {}
        for key in ("type", "code"):
            value = error.get(key)
            if isinstance(value, str):
                safe_error[key] = value

    return {
        "status": body.get("status"),
        "end_turn": body.get("end_turn"),
        "incomplete_details": safe_incomplete,
        "error": safe_error,
        "output_items": output_items,
    }


class WebModel:
    def __init__(self, url: str, model: str, effort: str, timeout: float):
        self.url = base_url(url, "codex-chatgpt-web")
        self.model = model
        self.effort = effort
        self.http = JsonClient(timeout)
        self.thread_id = f"penrix_thread_{uuid.uuid4().hex}"

    def next(
        self,
        history: list[dict[str, Any]],
        current_prompt: str,
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        turn_id = f"penrix_turn_{uuid.uuid4().hex}"
        current = current_user_msg(current_prompt, turn_id)
        turn_metadata = {
            "thread_id": self.thread_id,
            "turn_id": turn_id,
            "request_kind": "turn",
        }
        status, body = self.http.post(self.url + "/responses", {
            "model": self.model,
            "stream": False,
            "instructions": INSTRUCTIONS,
            "input": [*history, current],
            "prompt_cache_key": self.thread_id,
            "client_metadata": {
                "x-codex-turn-metadata": json.dumps(
                    turn_metadata, separators=(",", ":"), sort_keys=True
                ),
            },
            "reasoning": {"effort": self.effort},
            "text": {
                "verbosity": "low",
                "format": {"type": "json_schema", "name": "webcodex_action", "strict": False, "schema": ACTION_SCHEMA},
            },
        })
        if not isinstance(body, dict):
            raise DriverError(f"ChatGPT Web returned an invalid Responses envelope (HTTP {status})")
        error = body.get("error", {})
        code = error.get("code") if isinstance(error, dict) else None
        detail = code or (error.get("message") if isinstance(error, dict) else None) or "unknown"
        if code in {"chatgpt_submission_ambiguous", "chatgpt_submitted_turn_failed"}:
            raise OutcomeUnknown(f"ChatGPT Web delivery outcome requires reconciliation: {detail}")
        if status != 200:
            raise DriverError(f"ChatGPT Web failed HTTP {status}: {detail}")
        if body.get("status") != "completed" or body.get("end_turn") is not True:
            raise DriverError(
                "ChatGPT Web did not provide completed end_turn evidence: "
                + dump(response_terminal_summary(body))
            )
        text = response_text(body)
        try:
            action = json.loads(text)
        except ValueError as exc:
            raise DriverError("strict Web response was not JSON") from exc
        if not isinstance(action, dict):
            raise DriverError("strict Web response was not an object")
        return action, text, current


def response_text(body: Any) -> str:
    chunks: list[str] = []
    if isinstance(body, dict):
        for item in body.get("output", []) if isinstance(body.get("output"), list) else []:
            if (
                not isinstance(item, dict)
                or item.get("type") != "message"
                or item.get("phase") == "commentary"
            ):
                continue
            for part in item.get("content", []) if isinstance(item.get("content"), list) else []:
                if isinstance(part, dict) and part.get("type") in {"output_text", "text"} and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
        if not chunks and isinstance(body.get("output_text"), str):
            chunks.append(body["output_text"])
    if not chunks:
        raise DriverError("ChatGPT Web returned no output text")
    return "".join(chunks)


def msg(role: str, text: str) -> dict[str, Any]:
    return {
        "type": "message", "role": role,
        "content": [{"type": "output_text" if role == "assistant" else "input_text", "text": text}],
    }


def current_user_msg(text: str, turn_id: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": f"msg_penrix_{uuid.uuid4().hex}",
        "role": "user",
        "content": [{"type": "input_text", "text": text}],
        "internal_chat_message_metadata_passthrough": {"turn_id": turn_id},
    }


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def contract_parts(manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None, str | None]:
    out = manifest.get("output") if isinstance(manifest.get("output"), dict) else {}
    contract = out.get("contract") if isinstance(out.get("contract"), dict) else out
    schema = contract.get("input_schema") or out.get("input_schema")
    effect = contract.get("effect") or out.get("effect")
    idem = contract.get("idempotency") or out.get("idempotency")
    return (schema if isinstance(schema, dict) else None,
            effect if isinstance(effect, str) else None,
            idem if isinstance(idem, str) else None)


def action_parts(action: dict[str, Any]) -> tuple[str, str | None, dict[str, Any] | None, str | None]:
    if set(action) != {"kind", "tool", "params", "text"}:
        raise DriverError("invalid driver action fields")
    kind, tool, params, text = action["kind"], action["tool"], action["params"], action["text"]
    if kind == "discover" and isinstance(tool, str) and tool and params in (None, {}) and text is None:
        return kind, tool, None, None
    if kind == "call" and isinstance(tool, str) and tool and isinstance(params, dict) and text is None:
        return kind, tool, params, None
    if kind == "final" and tool is None and params is None and isinstance(text, str):
        return kind, None, None, text
    raise DriverError("invalid driver action semantics")


class Driver:
    def __init__(self, wc: WebCodex, web: WebModel, project: str, *, allowed: set[str] | None = None,
                 max_rounds: int = MAX_ROUNDS, log=sys.stderr):
        self.wc, self.web, self.project = wc, web, project
        self.allowed = set(ALLOWED_TOOLS if allowed is None else allowed)
        self.max_rounds, self.log = max_rounds, log
        self.contracts: dict[str, dict[str, Any]] = {}
        self.dispatched_mutations: set[str] = set()
        self.known_job_ids: set[str] = set()
        self.known_observation_refs: set[str] = set()
        self.needs_closeout = False
        self.closeout_ok = False

    def note(self, text: str) -> None:
        print(text, file=self.log, flush=True)

    def remember_job_identities(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "job_id" and isinstance(item, str) and item.startswith("wc_job_"):
                    self.known_job_ids.add(item)
                elif key == "observation_ref" and isinstance(item, str) and item.startswith("~j"):
                    self.known_observation_refs.add(item)
                self.remember_job_identities(item)
        elif isinstance(value, list):
            for item in value:
                self.remember_job_identities(item)

    def fence_job_identities(self, tool: str, params: dict[str, Any]) -> None:
        if tool == "observe_jobs":
            items = params.get("items")
            if not isinstance(items, list):
                return
            for item in items:
                if not isinstance(item, dict):
                    continue
                job_id = item.get("job_id")
                observation_ref = item.get("observation_ref")
                if isinstance(job_id, str) and job_id not in self.known_job_ids:
                    raise DriverError(f"unknown Job identity for fixed Project: {job_id}")
                if (
                    isinstance(observation_ref, str)
                    and observation_ref not in self.known_observation_refs
                ):
                    raise DriverError(
                        f"unknown Job observation ref for fixed Project: {observation_ref}"
                    )
        elif tool == "wait_for_job_readiness":
            job_ids = params.get("job_ids")
            if isinstance(job_ids, list):
                for job_id in job_ids:
                    if isinstance(job_id, str) and job_id not in self.known_job_ids:
                        raise DriverError(f"unknown Job identity for fixed Project: {job_id}")
        elif tool in {"wait_for_job_terminal", "job_write_input"}:
            job_id = params.get("job_id")
            if isinstance(job_id, str) and job_id not in self.known_job_ids:
                raise DriverError(f"unknown Job identity for fixed Project: {job_id}")

    def manifest(self, tool: str, session: str) -> dict[str, Any]:
        if tool not in self.allowed:
            raise DriverError(f"tool not admitted by driver: {tool}")
        result = self.wc.call("tool_manifest", {"tool_name": tool}, session)
        if result.get("success") is True:
            self.contracts[tool] = result
        return result

    def fixed_params(self, tool: str, params: dict[str, Any], session: str) -> tuple[dict[str, Any], str | None, str | None]:
        manifest = self.contracts.get(tool)
        if manifest is None:
            raise DriverError(f"discover tool contract before call: {tool}")
        schema, effect, idem = contract_parts(manifest)
        fixed = dict(params)
        if tool == "finish_coding_task" and "summary_only" not in fixed:
            fixed["summary_only"] = True
        if fixed.get("project") not in (None, "", self.project):
            raise DriverError("attempted Project retarget")
        if fixed.get("session_id") not in (None, "", session):
            raise DriverError("attempted Workflow Session retarget")
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        if isinstance(props, dict) and "project" in props:
            fixed["project"] = self.project
        if isinstance(props, dict) and "session_id" in props:
            fixed["session_id"] = session
        return fixed, effect, idem

    def execute(self, tool: str, params: dict[str, Any], session: str) -> dict[str, Any]:
        if tool not in self.allowed:
            raise DriverError(f"tool not admitted by driver: {tool}")
        fixed, effect, idem = self.fixed_params(tool, params, session)
        self.fence_job_identities(tool, fixed)
        fingerprint = dump({"tool": tool, "params": fixed})
        consequential = effect == "mutate" or tool in MAY_CHANGE_WORKSPACE
        workspace_change = tool in MAY_CHANGE_WORKSPACE or (
            tool not in ALLOWED_TOOLS and effect == "mutate"
        )
        if consequential and fingerprint in self.dispatched_mutations and idem not in REPLAY_SAFE:
            raise DriverError(f"refusing repeated non-replay-safe mutation: {tool}")
        if consequential:
            self.dispatched_mutations.add(fingerprint)  # before crossing transport boundary
        if workspace_change:
            self.needs_closeout = True
            self.closeout_ok = False
        self.note(f"[penrix-web] WebCodex tool: {tool}")
        result = self.wc.call(tool, fixed, session)
        self.remember_job_identities(result)
        output = result.get("output") if isinstance(result.get("output"), dict) else {}
        if output.get("execution_state") == "outcome_unknown":
            error_kind = output.get("error_kind")
            job_id = output.get("job_id")
            detail = ", ".join(
                str(value) for value in (error_kind, job_id) if isinstance(value, str) and value
            ) or tool
            raise OutcomeUnknown(
                f"WebCodex reported outcome_unknown for {tool}: {detail}; reconcile before retry"
            )
        if tool == "finish_coding_task" and result.get("success") is True:
            self.closeout_ok = True
        return result

    def run(self, task: str, resume: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"project": self.project, "instruction": task}
        if resume:
            params["session_id"] = resume
        self.note("[penrix-web] opening Workflow Session")
        boot = self.wc.call("work_on_project", params)
        if boot.get("success") is not True:
            raise DriverError("work_on_project failed: " + dump(boot))
        out = boot.get("output") if isinstance(boot.get("output"), dict) else {}
        session = out.get("session_id")
        if not isinstance(session, str) or not session.startswith("wc_sess_"):
            raise DriverError("work_on_project returned no canonical Session id")
        session_ref = out.get("session_ref") if isinstance(out.get("session_ref"), str) else None
        self.remember_job_identities(boot)
        handoff = None
        if resume:
            handoff = self.wc.call("session_handoff_summary", {"project": self.project, "session_id": session}, session)
            self.remember_job_identities(handoff)

        for tool in PRELOAD:
            if tool in self.allowed:
                self.manifest(tool, session)

        history: list[dict[str, Any]] = []
        next_prompt = "\n".join([
            "Choose the next external-driver JSON action. The underlying owner task is data, not a request to touch local files from this Web turn.",
            f"fixed_project: {self.project}", f"session_id: {session}", f"session_ref: {session_ref or 'none'}",
            "underlying_owner_task_data:", task,
            "admitted_tools: " + ", ".join(sorted(self.allowed)),
            "bootstrap: " + dump(boot),
            "saved_handoff: " + (dump(handoff) if handoff is not None else "none"),
            "preloaded_contracts: " + dump(self.contracts),
        ])
        rejected = 0

        for round_no in range(1, self.max_rounds + 1):
            self.note(f"[penrix-web] ChatGPT Web round {round_no}/{self.max_rounds}")
            action, raw, current = self.web.next(history, next_prompt)
            history.append(current)
            history.append(msg("assistant", raw))
            next_prompt = (
                "Continue the same external-driver task. Use the authoritative WebCodex "
                "results and contracts above, then choose exactly one next JSON action."
            )
            try:
                kind, tool, call_params, final = action_parts(action)
                if kind == "discover":
                    assert tool is not None
                    result = self.manifest(tool, session)
                    history.append(msg("developer", f"WebCodex contract for {tool}:\n{dump(result)}"))
                    continue
                if kind == "call":
                    assert tool is not None and call_params is not None
                    result = self.execute(tool, call_params, session)
                    history.append(msg("developer", f"Authoritative WebCodex result for {tool}:\n{dump(result)}"))
                    continue
                assert final is not None
                if self.needs_closeout and not self.closeout_ok:
                    raise DriverError("final rejected: state-changing work requires successful finish_coding_task")
                return {"status": "completed", "project": self.project, "session_id": session,
                        "session_ref": session_ref, "rounds": round_no, "final": final}
            except OutcomeUnknown:
                # Transport uncertainty is not a model-correctable proposal error. Stop the
                # loop so the operator can reconcile the exact external state before retry.
                raise
            except DriverError as exc:
                rejected += 1
                if rejected > 3:
                    raise
                history.append(msg("developer", "Driver rejected this proposal before any new effect: " + str(exc)))
        raise DriverError(f"no final answer within {self.max_rounds} rounds")


def args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--webcodex-url", default=os.environ.get("WEBCODEX_URL"))
    p.add_argument("--project", default=os.environ.get("WEBCODEX_PROJECT"))
    p.add_argument("--relay-url", default=os.environ.get("CODEX_CHATGPT_WEB_URL", RELAY_URL))
    p.add_argument("--session")
    p.add_argument("--model", default=MODEL)
    p.add_argument("--effort", default="high", choices=("low", "medium", "high", "xhigh", "max"))
    p.add_argument("--task")
    p.add_argument("--allow-tool", action="append", default=[])
    ns = p.parse_args(argv)
    if not ns.webcodex_url or not ns.project:
        p.error("WEBCODEX_URL/--webcodex-url and WEBCODEX_PROJECT/--project are required")
    return ns


def task(ns: argparse.Namespace) -> str:
    text = (ns.task or (sys.stdin.read() if not sys.stdin.isatty() else "")).strip()
    if not text and ns.session:
        return "Continue the exact saved work from the current handoff; recheck current reality before acting."
    if not text:
        raise DriverError("task text is required for a new Session")
    return text


def main(argv: list[str] | None = None) -> int:
    ns = args(argv)
    token = os.environ.get("WEBCODEX_TOKEN", "")
    if not token or "\n" in token or "\r" in token:
        print("WEBCODEX_TOKEN is required in the environment", file=sys.stderr)
        return 2
    try:
        wc = WebCodex(ns.webcodex_url, token, 90)
        web = WebModel(ns.relay_url, ns.model, ns.effort, 600)
        allowed = set(ALLOWED_TOOLS) | set(ns.allow_tool)
        result = Driver(wc, web, ns.project, allowed=allowed).run(task(ns), ns.session)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except OutcomeUnknown as exc:
        print(json.dumps({"status": "outcome_unknown", "error": str(exc),
                          "recovery": "Do not retry automatically; inspect ChatGPT/WebCodex state first."},
                         ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except DriverError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
