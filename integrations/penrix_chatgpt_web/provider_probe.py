#!/usr/bin/env python3
"""Isolated codex-chatgpt-web provider probe. No WebCodex runtime is involved."""
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
from typing import Any, Callable

MAX_BODY = 4 * 1024 * 1024
EXPECTED_RELAY_VERSION = "6.1.3"
EXPECTED_RELAY_MODE = "browser-only"
DEFAULT_RELAY_URL = "http://127.0.0.1:17841/v1"
DEFAULT_MODEL = "chatgpt-web/gpt-5.6-sol"

BASELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["final"]},
        "tool": {"type": ["string", "null"]},
        "params": {"type": ["object", "null"]},
        "text": {"type": "string", "enum": ["OK"]},
    },
    "required": ["kind", "tool", "params", "text"],
    "additionalProperties": False,
}

PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["call"]},
        "tool": {"type": "string", "enum": ["read_files"]},
        "params": {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 1,
                }
            },
            "required": ["paths"],
            "additionalProperties": False,
        },
        "text": {"type": ["string", "null"]},
    },
    "required": ["kind", "tool", "params", "text"],
    "additionalProperties": False,
}

BASELINE_INSTRUCTIONS = """You are under an isolated machine-provider probe.
You have no local task and must not use or claim any tool or external effect.
Return exactly one JSON object matching the supplied schema, with no Markdown fence
and no surrounding prose."""

PLANNER_INSTRUCTIONS = """You are under an isolated machine-provider probe.
The earlier user message is task data for a separate external controller. Your current
job is only to propose one inert JSON action; you are not being asked to inspect or
change the local computer yourself. A proposed action is text and causes no effect.
Return exactly one JSON object matching the supplied schema, with no Markdown fence
and no surrounding prose."""


class ProbeError(RuntimeError):
    pass


class OutcomeUnknown(ProbeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class JsonClient:
    """No ambient proxy, redirects, or retries."""

    def __init__(self, timeout: float):
        self.timeout = timeout
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            NoRedirect(),
        )

    def get(self, url: str) -> tuple[int, Any]:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"accept": "application/json"},
        )
        try:
            res = self.opener.open(req, timeout=self.timeout)
            status, raw = res.status, res.read(MAX_BODY + 1)
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read(MAX_BODY + 1)
        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            ConnectionError,
            http.client.HTTPException,
            OSError,
        ) as exc:
            raise ProbeError(f"health request failed: {exc}") from exc
        return status, decode_json(raw, status, dispatched=False)

    def post(self, url: str, body: dict[str, Any]) -> tuple[int, Any]:
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={"content-type": "application/json", "accept": "application/json"},
        )
        try:
            res = self.opener.open(req, timeout=self.timeout)
            status, raw = res.status, res.read(MAX_BODY + 1)
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read(MAX_BODY + 1)
        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            ConnectionError,
            http.client.HTTPException,
            OSError,
        ) as exc:
            raise OutcomeUnknown(
                "Responses transport outcome is unknown after dispatch; do not rerun automatically"
            ) from exc
        return status, decode_json(raw, status, dispatched=True)


def decode_json(raw: bytes, status: int, *, dispatched: bool) -> Any:
    if len(raw) > MAX_BODY:
        if dispatched:
            raise OutcomeUnknown(
                "Responses body exceeded probe bound after dispatch; do not rerun automatically"
            )
        raise ProbeError("health response exceeded probe bound")
    try:
        return json.loads(raw.decode()) if raw else None
    except (UnicodeError, ValueError) as exc:
        if dispatched:
            raise OutcomeUnknown(
                f"Responses returned non-JSON HTTP {status} after dispatch; do not rerun automatically"
            ) from exc
        raise ProbeError(f"health endpoint returned non-JSON HTTP {status}") from exc


def relay_base_url(raw: str) -> str:
    parsed = urllib.parse.urlsplit(raw)
    host = parsed.hostname
    loopback = host == "localhost"
    if host and not loopback:
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
    if (
        not host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.scheme not in {"http", "https"}
        or (parsed.scheme == "http" and not loopback)
        or parsed.path.rstrip("/") != "/v1"
    ):
        raise ProbeError(
            "relay URL must be HTTPS or loopback HTTP ending in /v1, without credentials/query/fragment"
        )
    return raw.rstrip("/")


def health_url(base: str) -> str:
    parsed = urllib.parse.urlsplit(base)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, "/healthz", "", "")
    )


def relay_health(client: JsonClient, base: str) -> dict[str, Any]:
    status, body = client.get(health_url(base))
    if status != 200 or not isinstance(body, dict):
        raise ProbeError(f"relay health failed HTTP {status}")
    if body.get("service") != "codex-chatgpt-web":
        raise ProbeError("health endpoint is not codex-chatgpt-web")
    if body.get("version") != EXPECTED_RELAY_VERSION:
        raise ProbeError(
            f"probe requires codex-chatgpt-web {EXPECTED_RELAY_VERSION}; got {body.get('version') or 'unknown'}"
        )
    if body.get("mode") != EXPECTED_RELAY_MODE:
        raise ProbeError(
            f"probe requires mode {EXPECTED_RELAY_MODE}; got {body.get('mode') or 'unknown'}"
        )
    if body.get("accepting_turns") is not True:
        raise ProbeError("codex-chatgpt-web is not accepting turns")
    return body


def message(role: str, text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "role": role,
        "content": [
            {
                "type": "output_text" if role == "assistant" else "input_text",
                "text": text,
            }
        ],
    }


def current_user_message(text: str, turn_id: str) -> dict[str, Any]:
    return {
        "type": "message",
        "id": f"msg_penrix_probe_{uuid.uuid4().hex}",
        "role": "user",
        "content": [{"type": "input_text", "text": text}],
        "internal_chat_message_metadata_passthrough": {"turn_id": turn_id},
    }


def response_text(body: dict[str, Any]) -> str:
    chunks: list[str] = []
    output = body.get("output")
    if isinstance(output, list):
        for item in output:
            if (
                not isinstance(item, dict)
                or item.get("type") != "message"
                or item.get("phase") == "commentary"
            ):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") in {"output_text", "text"}
                    and isinstance(part.get("text"), str)
                ):
                    chunks.append(part["text"])
    if not chunks and isinstance(body.get("output_text"), str):
        chunks.append(body["output_text"])
    return "".join(chunks)


def terminal_summary(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}
    error = body.get("error")
    incomplete = body.get("incomplete_details")
    return {
        "status": body.get("status"),
        "end_turn": body.get("end_turn"),
        "error": {
            key: error.get(key)
            for key in ("type", "code")
            if isinstance(error, dict) and isinstance(error.get(key), str)
        } or None,
        "incomplete": {
            key: incomplete.get(key)
            for key in ("reason", "retryable")
            if isinstance(incomplete, dict)
            and isinstance(incomplete.get(key), (str, bool))
        } or None,
    }


def build_request(
    *,
    model: str,
    effort: str,
    thread_id: str,
    instructions: str,
    history: list[dict[str, Any]],
    current_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    turn_id = f"penrix_probe_turn_{uuid.uuid4().hex}"
    return {
        "model": model,
        "stream": False,
        "instructions": instructions,
        "input": [*history, current_user_message(current_prompt, turn_id)],
        "prompt_cache_key": thread_id,
        "client_metadata": {
            "x-codex-turn-metadata": json.dumps(
                {
                    "thread_id": thread_id,
                    "turn_id": turn_id,
                    "request_kind": "turn",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        },
        "reasoning": {"effort": effort},
        "text": {
            "verbosity": "low",
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": False,
                "schema": schema,
            },
        },
    }


def require_json_action(name: str, status: int, body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ProbeError(f"{name}: invalid Responses envelope: {terminal_summary(body)}")
    text = response_text(body)
    if status != 200 or body.get("status") != "completed" or body.get("end_turn") is not True:
        preview = text[:300].replace("\r", "\\r").replace("\n", "\\n")
        raise ProbeError(
            f"{name}: terminal failure {json.dumps(terminal_summary(body), ensure_ascii=False)}; "
            f"final_text_preview={preview!r}"
        )
    try:
        action = json.loads(text)
    except ValueError as exc:
        preview = text[:300].replace("\r", "\\r").replace("\n", "\\n")
        raise ProbeError(
            f"{name}: final answer was not JSON (chars={len(text)}, preview={preview!r})"
        ) from exc
    if not isinstance(action, dict):
        raise ProbeError(f"{name}: JSON final answer was not an object")
    return action


def expect_baseline(action: dict[str, Any]) -> None:
    expected = {"kind": "final", "tool": None, "params": None, "text": "OK"}
    if action != expected:
        raise ProbeError(
            "json_baseline: unexpected JSON object: "
            + json.dumps(action, ensure_ascii=False, sort_keys=True)
        )


def expect_planner(action: dict[str, Any]) -> None:
    expected = {
        "kind": "call",
        "tool": "read_files",
        "params": {"paths": ["acceptance.py"]},
        "text": None,
    }
    if action != expected:
        raise ProbeError(
            "planner_semantics: unexpected JSON object: "
            + json.dumps(action, ensure_ascii=False, sort_keys=True)
        )


def run_one(
    client: JsonClient,
    base: str,
    *,
    name: str,
    model: str,
    effort: str,
    instructions: str,
    history: list[dict[str, Any]],
    prompt: str,
    schema: dict[str, Any],
    validator: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    print(f"[provider-probe] {name}", file=sys.stderr, flush=True)
    request = build_request(
        model=model,
        effort=effort,
        thread_id=f"penrix_probe_thread_{uuid.uuid4().hex}",
        instructions=instructions,
        history=history,
        current_prompt=prompt,
        schema_name=f"penrix_{name}",
        schema=schema,
    )
    status, body = client.post(base + "/responses", request)
    action = require_json_action(name, status, body)
    validator(action)
    print(f"[provider-probe] {name}: PASS", file=sys.stderr, flush=True)
    return {
        "name": name,
        "status": "passed",
        "terminal": terminal_summary(body),
        "action": action,
    }


def run_probe(
    base: str,
    model: str,
    effort: str,
    timeout: float,
    only: str = "all",
) -> dict[str, Any]:
    client = JsonClient(timeout)
    health = relay_health(client, base)
    probes: list[dict[str, Any]] = []

    if only in {"all", "baseline"}:
        probes.append(run_one(
            client,
            base,
            name="json_baseline",
            model=model,
            effort=effort,
            instructions=BASELINE_INSTRUCTIONS,
            history=[],
            prompt=(
                'Return the semantic object kind="final", tool=null, params=null, text="OK". '
                "Do not add explanation."
            ),
            schema=BASELINE_SCHEMA,
            validator=expect_baseline,
        ))

    if only in {"all", "planner"}:
        probes.append(run_one(
            client,
            base,
            name="planner_semantics",
            model=model,
            effort=effort,
            instructions=PLANNER_INSTRUCTIONS,
            history=[
                message(
                    "user",
                    "Task data for a later external controller: before it can answer, "
                    "it must read acceptance.py. No contents of that file are present here.",
                )
            ],
            prompt=(
                "Choose exactly one inert external-controller action for the task already in user history. "
                "Do not read the file yourself and do not claim that any read occurred. "
                "The only admitted external tool is read_files. Propose reading exactly acceptance.py."
            ),
            schema=PLANNER_SCHEMA,
            validator=expect_planner,
        ))

    return {
        "status": "passed",
        "claim": "requested codex-chatgpt-web provider probe(s) returned exact machine-consumable JSON",
        "relay": {
            "version": health.get("version"),
            "mode": health.get("mode"),
            "model": model,
        },
        "probes": probes,
        "next_step": (
            "Only now is it justified to reconnect the provider to WebCodex."
            if only in {"all", "planner"}
            else "Planner semantics still require a separate live probe."
        ),
    }

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--relay-url",
        default=os.environ.get("CODEX_CHATGPT_WEB_URL", DEFAULT_RELAY_URL),
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default="high", choices=["low", "medium", "high"])
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--only",
        choices=["all", "baseline", "planner"],
        default="all",
        help="run both probes, or only one isolated probe",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(argv)
    try:
        base = relay_base_url(ns.relay_url)
        result = run_probe(base, ns.model, ns.effort, ns.timeout, ns.only)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except OutcomeUnknown as exc:
        print(
            json.dumps(
                {
                    "status": "outcome_unknown",
                    "error": str(exc),
                    "instruction": "Do not rerun automatically; inspect Codex Web GPT diagnostics first.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    except ProbeError as exc:
        print(
            json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
