#!/usr/bin/env python3
"""Chrome transport with explicit Session transfer for the canonical Driver."""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import pathlib
import re
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import driver
import live_acceptance as live

ROOT = pathlib.Path(__file__).resolve().parent
CHAT_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
PORT = 17842


class Paused(RuntimeError):
    pass


def extension_origin():
    manifest = json.loads((ROOT / "browser_extension/manifest.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(base64.b64decode(manifest["key"], validate=True)).hexdigest()[:32]
    return "chrome-extension://" + "".join(chr(ord("a") + int(c, 16)) for c in digest)


class BrowserEntry:
    def __init__(self, wc, project, binding_path, *, real_test=False):
        self.wc, self.project, self.binding_path = wc, project, binding_path
        self.condition = threading.Condition()
        self.pending = None
        self.worker = None
        self.state, self.detail = "idle", "本地项目已就绪"
        self.conversation, self.session_id = None, None
        self.real_test = real_test
        self.in_tool = False
        self.final = ""
        if binding_path and binding_path.exists():
            binding = json.loads(binding_path.read_text(encoding="utf-8"))
            if binding.get("project") != project:
                raise driver.DriverError("Saved browser binding belongs to a different Project")
            self.conversation, self.session_id = binding["conversation"], binding["session_id"]
            if not CHAT_ID.fullmatch(self.conversation) or not self.session_id.startswith("wc_sess_"):
                raise driver.DriverError("Invalid saved canonical browser binding")
            self.state, self.detail = "paused", "已恢复绑定；点击恢复，先读取原 Session"

    def save_binding(self):
        if self.binding_path and self.session_id:
            self.binding_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.binding_path.with_suffix(".tmp")
            temp.write_text(json.dumps({"project": self.project, "conversation": self.conversation,
                                        "session_id": self.session_id}), encoding="utf-8")
            temp.replace(self.binding_path)

    def check_chat(self, chat):
        if chat != self.conversation:
            raise driver.DriverError("项目已绑定其他聊天；请先停止旧执行，再点击转移到本聊天")

    def transfer(self, chat):
        if not CHAT_ID.fullmatch(chat or ""):
            raise driver.DriverError("请在一个已有的 ChatGPT 对话中转移")
        with self.condition:
            if (self.state not in {"paused", "completed"} or self.in_tool or self.pending
                    or (self.worker and self.worker.is_alive())):
                raise driver.DriverError("请先在旧聊天暂停，并等待当前执行结束后再转移")
            if not self.session_id:
                raise driver.DriverError("尚无可续接的 Session；请直接连接项目")
            previous = self.conversation
            self.conversation = chat
            try:
                self.save_binding()
            except OSError as exc:
                self.conversation = previous
                raise driver.DriverError("无法保存转移绑定；仍保留原聊天") from exc
            self.state, self.final = "paused", ""
            self.detail = "已转移到本聊天；点击恢复，先读取原 Session"

    def snapshot(self):
        with self.condition:
            return {"state": self.state, "detail": self.detail, "project": self.project,
                    "conversation": self.conversation, "session_id": self.session_id,
                    "final": self.final, "real_test": self.real_test,
                    "request": dict(self.pending) if self.pending else None}

    def claim(self, chat, request_id):
        with self.condition:
            self.check_chat(chat)
            if not self.pending or self.pending["id"] != request_id or self.pending["delivery"] != "ready":
                raise driver.DriverError("Request already claimed or no longer active; never resend")
            self.pending["delivery"] = "claimed"

    def reply(self, chat, request_id, text):
        with self.condition:
            self.check_chat(chat)
            if (self.state != "running" or not self.pending or self.pending["id"] != request_id
                    or self.pending["delivery"] != "claimed"):
                raise driver.DriverError("Reply is stale or already received")
            envelope = json.loads(text)
            if (not isinstance(envelope, dict) or set(envelope) != {"request_id", "action"}
                    or envelope["request_id"] != request_id or not isinstance(envelope["action"], dict)):
                raise driver.DriverError("Reply did not match the exact browser request")
            driver.action_parts(envelope["action"])
            self.pending["reply"] = driver.dump(envelope["action"])
            self.pending["delivery"] = "replied"
            self.condition.notify_all()

    def pause(self, reason="已暂停；正在运行的 Job 保留在 WebCodex 中"):
        with self.condition:
            self.state = "pausing" if self.in_tool else "paused"
            self.detail = reason
            self.pending = None
            self.condition.notify_all()

    def exchange(self, prompt):
        with self.condition:
            if self.state != "running":
                raise Paused(self.detail)
            request_id = secrets.token_hex(16)
            envelope_rule = ("\nBrowser delivery envelope overrides the action's outer format only. "
                             "Return exactly one JSON code block containing "
                             + json.dumps({"request_id": request_id, "action": {"kind": "call | discover | final", "tool": None, "params": None, "text": None}})
                             + ". Use this exact request_id; action must match the supplied action schema. No surrounding prose.")
            self.pending = {"id": request_id, "prompt": "[WebCodex controller request:" + request_id + "]\n" + prompt + envelope_rule, "delivery": "ready"}
            self.detail = "等待当前聊天的完整回复"
            self.condition.notify_all()
            ready = self.condition.wait_for(lambda: self.state != "running" or (self.pending and "reply" in self.pending), 600)
            if self.state != "running":
                raise Paused(self.detail)
            if not ready:
                self.pending = None
                raise driver.OutcomeUnknown("Browser reply timed out; inspect the same chat before recovery")
            reply = self.pending["reply"]
            self.pending = None
            return reply

    def start(self, chat, task):
        if not CHAT_ID.fullmatch(chat or "") or not isinstance(task, str) or not task.strip() or len(task) > 32000:
            raise driver.DriverError("An existing conversation and a nonempty task are required")
        with self.condition:
            if self.worker and self.worker.is_alive():
                raise driver.DriverError("Previous worker is still active; pause and wait before recovery")
            if self.conversation and self.conversation != chat:
                raise driver.DriverError("Project is bound to another conversation; do not silently retarget")
            self.conversation, self.state, self.final = chat, "running", ""
            self.detail = "读取项目和原 Session"
            self.worker = threading.Thread(target=self.run, args=(task,), daemon=True)
            self.worker.start()

    def run(self, task):
        entry = self
        class FixedRuntime:
            def call(self, tool, params, session=None):
                with entry.condition:
                    if entry.state != "running":
                        raise Paused(entry.detail)
                    entry.in_tool = True
                    entry.detail = "WebCodex 正在执行：" + tool
                try:
                    result = entry.wc.call(tool, params, session)
                    if tool == "work_on_project" and result.get("success") is True:
                        canonical = result.get("output", {}).get("session_id")
                        if not isinstance(canonical, str) or not canonical.startswith("wc_sess_"):
                            raise driver.DriverError("Bootstrap did not return canonical Session identity")
                        if entry.session_id and canonical != entry.session_id:
                            raise driver.DriverError("Recovery changed exact canonical Session")
                        entry.session_id = canonical
                        entry.save_binding()
                    return result
                finally:
                    with entry.condition:
                        entry.in_tool = False
                        if entry.state == "pausing":
                            entry.state = "paused"
        try:
            result = driver.Driver(FixedRuntime(), BoundModel(self), self.project).run(task, self.session_id)
            with self.condition:
                if self.state == "running":
                    self.state, self.detail, self.final = "completed", "任务已完成", result["final"]
        except Paused:
            pass
        except Exception as exc:
            self.pause("执行已停止，需核对后恢复：" + str(exc)[:1500])


class BoundModel:
    def __init__(self, entry):
        self.entry, self.sent = entry, 0
        self.gate = None
        if entry.real_test:
            from real_test_driver import RealTestGate
            self.gate = RealTestGate()

    def next(self, history, current_prompt):
        def operation():
            current = driver.msg("user", current_prompt)
            suffix = history[self.sent:]
            # Existing native conversation keeps discussion; do not replay all earlier rounds.
            prompt = driver.INSTRUCTIONS + "\nController data for this round:\n" + driver.dump(suffix) + "\n" + current_prompt
            if len(prompt.encode("utf-8")) > driver.MAX_BODY:
                raise driver.DriverError("Browser controller prompt exceeded transport limit")
            raw = self.entry.exchange(prompt)
            action = driver.parse_web_action_json(raw)
            driver.action_parts(action)
            self.sent = len(history) + 2  # current user + canonical assistant added by Driver
            return action, raw, current
        return self.gate.run(operation) if self.gate else operation()


def make_server(entry, origin, address=("127.0.0.1", PORT)):
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never put pairing credentials or prompt bodies in access logs.

        def send_json(self, status, value):
            payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            if self.headers.get("Origin") == origin:
                self.send_header("Access-Control-Allow-Origin", origin)
            self.end_headers()
            self.wfile.write(payload)

        def admitted_origin(self):
            expected = "127.0.0.1:" + str(self.server.server_port)
            return self.headers.get("Host") == expected and self.headers.get("Origin") == origin

        def do_OPTIONS(self):
            if not self.admitted_origin():
                self.send_json(403, {"error": "Origin denied"})
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "authorization,content-type")
            self.send_header("Access-Control-Allow-Methods", "POST")
            self.end_headers()

        def do_POST(self):
            if not self.admitted_origin():
                self.send_json(403, {"error": "Origin denied"})
                return
            if self.path != "/pair" and not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token):
                self.send_json(401, {"error": "Connect to the local project first"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= driver.MAX_BODY:
                    raise driver.DriverError("Invalid request size")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise driver.DriverError("Request must be an object")
                chat = body.get("conversation")
                if self.path == "/pair":
                    self.send_json(200, {"token": token, "project": entry.project})
                    return
                with entry.condition:
                    if self.path == "/start":
                        entry.start(chat, body.get("task"))
                    elif self.path == "/transfer":
                        entry.transfer(chat)
                    elif self.path == "/status":
                        if entry.conversation:
                            entry.check_chat(chat)
                    elif self.path == "/claim":
                        entry.claim(chat, body.get("id"))
                    elif self.path == "/reply":
                        entry.reply(chat, body.get("id"), body.get("text"))
                    elif self.path == "/pause":
                        entry.check_chat(chat)
                        entry.pause(body.get("reason") or "已暂停；可补充纠正后恢复")
                    elif self.path == "/shutdown":
                        if entry.conversation:
                            entry.check_chat(chat)
                        if entry.worker and entry.worker.is_alive():
                            raise driver.DriverError("Pause and wait for the current worker before closing the service")
                        threading.Thread(target=self.server.shutdown, daemon=True).start()
                    else:
                        self.send_json(404, {"error": "Unknown operation"})
                        return
                    snapshot = entry.snapshot()
                self.send_json(200, snapshot)
            except (driver.DriverError, ValueError, TypeError) as exc:
                self.send_json(409, {"error": str(exc)[:1500]})
    return ThreadingHTTPServer(address, Handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--webcodex-bin-dir", required=True)
    parser.add_argument("--real-test", action="store_true")
    ns = parser.parse_args(argv)
    repo = pathlib.Path(ns.project_dir).resolve(strict=True)
    live.run_checked(["git", "rev-parse", "--show-toplevel"], repo)
    webcodex = live.find_webcodex(ns.webcodex_bin_dir)
    version = live.run_checked([str(webcodex), "--version"], repo).strip()
    if not version.startswith("webcodex 0.4.4 "):
        raise driver.DriverError("Browser entry requires the reviewed WebCodex 0.4.4 candidate")
    state_dir = pathlib.Path.home() / ".codex" / "webcodex-browser-state" / hashlib.sha256(str(repo).casefold().encode()).hexdigest()[:16]
    share, ready, _ = live.start_share(webcodex, repo, False, state_dir)
    service = None
    try:
        token = live.windows_clipboard_text().strip()
        if not live.TOKEN_RE.fullmatch(token):
            raise driver.DriverError("WebCodex temporary credential unavailable")
        url = ready["server"]["url"]
        project = live.exact_project(url, token)
        entry = BrowserEntry(driver.WebCodex(url, token, 90), project,
                             state_dir / "browser-binding.json", real_test=ns.real_test)
        service = make_server(entry, extension_origin())
        print("WebCodex browser entry ready on 127.0.0.1:17842; connect from the Chrome panel", flush=True)
        service.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if service:
            entry.pause("本地服务正在关闭；恢复时读取原 Session")
            if entry.worker:
                entry.worker.join(100)
            service.server_close()
        live.stop_share(share)


if __name__ == "__main__":
    main()
