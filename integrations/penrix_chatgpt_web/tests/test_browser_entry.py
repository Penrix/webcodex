import json
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import driver


class BrowserEntryTests(unittest.TestCase):
    def entry(self):
        import browser_entry
        return browser_entry.BrowserEntry(None, "project-one", None)

    def test_browser_transport_exists_without_relay(self):
        self.assertTrue((pathlib.Path(__file__).resolve().parents[1] / "browser_entry.py").is_file())

    def test_claim_once_and_exact_completed_reply(self):
        entry = self.entry()
        entry.conversation = "chat-one"
        entry.state = "running"
        got = []
        model = __import__("browser_entry").BoundModel(entry)
        t = threading.Thread(target=lambda: got.append(model.next([], "Read current files")))
        t.start()
        try:
            with entry.condition:
                self.assertTrue(entry.condition.wait_for(lambda: entry.pending is not None, 2))
            request = entry.snapshot()["request"]
            entry.claim("chat-one", request["id"])
            with self.assertRaises(driver.DriverError):
                entry.claim("chat-one", request["id"])
            with self.assertRaises(driver.DriverError):
                entry.reply("chat-one", "wrong", "{}")
            action = {"kind": "final", "tool": None, "params": None, "text": "confirmed"}
            entry.reply("chat-one", request["id"], json.dumps({"request_id": request["id"], "action": action}))
            t.join(2)
            self.assertFalse(t.is_alive())
            self.assertEqual(got[0][0], action)
            with self.assertRaises(driver.DriverError):
                entry.reply("chat-one", request["id"], "{}")
        finally:
            entry.pause()
            t.join(2)

    def test_pause_discards_waiting_proposal_without_execution(self):
        entry = self.entry()
        entry.state, entry.conversation = "running", "chat-one"
        errors = []
        def run():
            try:
                __import__("browser_entry").BoundModel(entry).next([], "next")
            except Exception as e:
                errors.append(e)
        t = threading.Thread(target=run)
        t.start()
        with entry.condition:
            self.assertTrue(entry.condition.wait_for(lambda: entry.pending is not None, 2))
        request = entry.snapshot()["request"]
        entry.pause()
        t.join(2)
        self.assertFalse(t.is_alive())
        self.assertEqual(type(errors[0]).__name__, "Paused")
        with self.assertRaises(driver.DriverError):
            entry.reply("chat-one", request["id"], "{}")

    def test_foreign_conversation_cannot_claim_request(self):
        entry = self.entry()
        entry.conversation = "chat-one"
        entry.pending = {"id": "r1", "delivery": "ready"}
        with self.assertRaises(driver.DriverError):
            entry.claim("another-chat", "r1")

    def test_native_continuation_carries_only_new_results(self):
        entry = self.entry()
        model = __import__("browser_entry").BoundModel(entry)
        seen = []
        entry.exchange = lambda prompt: seen.append(prompt) or '{"kind":"final","tool":null,"params":null,"text":"ok"}'
        first = [driver.msg("user", "owner task")]
        model.next(first, "first context")
        model.next(first + [driver.msg("user", "first context"), driver.msg("assistant", "old action"), driver.msg("developer", "new result")], "continue")
        self.assertIn("owner task", seen[0])
        self.assertNotIn("owner task", seen[1])
        self.assertIn("new result", seen[1])

    def test_binding_restores_only_exact_project(self):
        import browser_entry
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "binding.json"
            path.write_text(json.dumps({"project": "project-one", "conversation": "chat-one", "session_id": "wc_sess_saved"}))
            e = browser_entry.BrowserEntry(None, "project-one", path)
            self.assertEqual(e.session_id, "wc_sess_saved")
            self.assertEqual(e.state, "paused")
            with self.assertRaises(driver.DriverError):
                browser_entry.BrowserEntry(None, "different-project", path)

    def test_http_requires_exact_extension_origin_host_and_pairing_token(self):
        import browser_entry
        entry = self.entry()
        origin = "chrome-extension://" + "a" * 32
        server = browser_entry.make_server(entry, origin, ("127.0.0.1", 0))
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        url = "http://127.0.0.1:" + str(server.server_port)
        def post(path, body, headers):
            req = urllib.request.Request(url + path, data=json.dumps(body).encode(), headers=headers)
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req) as r:
                return json.load(r)
        try:
            with self.assertRaises(urllib.error.HTTPError) as bad:
                post("/pair", {}, {"Origin": "https://chatgpt.com"})
            self.assertEqual(bad.exception.code, 403)
            with self.assertRaises(urllib.error.HTTPError) as bad:
                post("/pair", {}, {"Origin": origin, "Host": "attacker.invalid"})
            self.assertEqual(bad.exception.code, 403)
            paired = post("/pair", {}, {"Origin": origin})
            self.assertEqual(paired["project"], "project-one")
            with self.assertRaises(urllib.error.HTTPError) as bad:
                post("/status", {}, {"Origin": origin})
            self.assertEqual(bad.exception.code, 401)
            status = post("/status", {}, {"Origin": origin, "Authorization": "Bearer " + paired["token"]})
            self.assertEqual(status["state"], "idle")
            stopped = post("/shutdown", {"conversation": "chat-one"}, {"Origin": origin, "Authorization": "Bearer " + paired["token"]})
            self.assertEqual(stopped["state"], "idle")
        finally:
            server.shutdown(); thread.join(2); server.server_close()


if __name__ == "__main__":
    unittest.main()
