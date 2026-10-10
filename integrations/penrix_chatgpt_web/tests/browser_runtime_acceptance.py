"""Real Windows Server/Runner with simulated browser replies; sends no ChatGPT messages."""
import json
import pathlib
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import browser_entry as browser
import driver
import live_acceptance as live

def call_action(tool, params):
    return {"kind": "call", "tool": tool, "params": params, "text": None}

def revision(value):
    for item in value.get('output', {}).get('items', []):
        if item.get('path') == 'acceptance.py':
            return item.get('output', {}).get('read_revision')
    return None

def serve_actions(entry, rpc, value):
    rpc('/start', {'task':'Offline transport acceptance: read, edit, review and finish only.'})
    phase = 0
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        status = rpc('/status', {})
        if status['state'] == 'completed':
            return status
        if status['state'] != 'running': raise RuntimeError(status['detail'])
        request = status['request']
        if not request:
            time.sleep(.05); continue
        prompt = request['prompt']
        if phase == 0:
            action = call_action('read_files', {'items':[{'path':'acceptance.py'}]})
        elif phase == 1:
            suffix = prompt.split('Controller data for this round:\n', 1)[1]
            messages, _ = json.JSONDecoder().raw_decode(suffix)
            text = next(m['content'][0]['text'] for m in reversed(messages) if 'Authoritative WebCodex result for read_files:' in m['content'][0]['text'])
            evidence = json.loads(text.split('\n', 1)[1])
            fence = revision(evidence)
            if fence is None: raise RuntimeError('No canonical read revision in real result: ' + driver.dump(evidence))
            old = 'BROKEN' if value == 'WEBCODEX_LIVE_OK' else 'WEBCODEX_LIVE_OK'
            action = call_action('edit_project_files', {'changes':[{'kind':'edit','path':'acceptance.py','expected_read_revision':fence,'edits':[{'kind':'replace_exact','old_text':old,'new_text':value}]}]})
        elif phase == 2:
            action = call_action('review_changes', {'scope':{'kind':'workspace'},'paths':['acceptance.py']})
        elif phase == 3:
            action = call_action('finish_coding_task', {})
        else:
            action = {'kind':'final','tool':None,'params':None,'text':'offline transport fixture completed'}
        rpc('/claim', {'id':request['id']})
        rpc('/reply', {'id':request['id'], 'text':json.dumps({'request_id':request['id'],'action':action})})
        phase += 1
    raise RuntimeError('Offline runtime acceptance timed out')

def main():
    repo = live.make_repo()
    binary = live.find_webcodex(sys.argv[1])
    share = server = None
    try:
        share, ready, _ = live.start_share(binary, repo, False)
        token = live.windows_clipboard_text().strip()
        if not live.TOKEN_RE.fullmatch(token): raise RuntimeError('Temporary WebCodex credential unavailable')
        url = ready['server']['url']
        project = live.exact_project(url, token)
        binding = live.state_dir_for(repo) / 'browser-binding.json'
        entry = browser.BrowserEntry(driver.WebCodex(url,token,90), project,binding)
        origin = browser.extension_origin()
        server = browser.make_server(entry,origin,('127.0.0.1',0))
        threading.Thread(target=server.serve_forever,daemon=True).start()
        local = 'http://127.0.0.1:' + str(server.server_port)
        auth = None
        def rpc(path, body):
            headers={'Origin':origin,'Content-Type':'application/json'}
            if auth: headers['Authorization']='Bearer '+auth
            req=urllib.request.Request(local+path,data=json.dumps({'conversation':'offline-chat',**body}).encode(),headers=headers)
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=20) as r: return json.load(r)
        auth=rpc('/pair',{})['token']
        first=serve_actions(entry,rpc,'WEBCODEX_LIVE_OK')
        live.verify_local_repo(repo)
        session=first['session_id']
        entry.worker.join(2)
        corrected=serve_actions(entry,rpc,'CORRECTED_BY_OWNER')
        assert corrected['session_id']==session
        assert 'CORRECTED_BY_OWNER' in (repo/'acceptance.py').read_text()
        entry.worker.join(2)
        moved=rpc('/transfer',{'conversation':'offline-chat-two'})
        assert moved['session_id']==session and moved['state']=='paused'
        try:
            rpc('/status',{})
            raise RuntimeError('Old conversation retained access after transfer')
        except urllib.error.HTTPError as exc:
            assert exc.code==409
            exc.close()
        def next_chat(path, body):
            return rpc(path,{'conversation':'offline-chat-two',**body})
        next_chat('/start',{'task':'Read acceptance.py on the original Session; make no changes.'})
        phase=0
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            current=next_chat('/status',{})
            if current['state']=='completed': break
            if current['state']!='running': raise RuntimeError(current['detail'])
            request=current['request']
            if not request:
                time.sleep(.05);continue
            if phase==0:
                assert 'resumed_explicitly' in request['prompt']
                action=call_action('read_files',{'items':[{'path':'acceptance.py'}]})
            else:
                assert 'CORRECTED_BY_OWNER' in request['prompt']
                action={'kind':'final','tool':None,'params':None,'text':'Transferred original Session read confirmed'}
            next_chat('/claim',{'id':request['id']})
            next_chat('/reply',{'id':request['id'],'text':json.dumps({'request_id':request['id'],'action':action})})
            phase+=1
        else:
            raise RuntimeError('Transferred Session acceptance timed out')
        entry.worker.join(2)
        assert current['session_id']==session and phase==2
        restored=browser.BrowserEntry(entry.wc,project,binding)
        assert restored.session_id==session and restored.state=='paused'
        assert restored.conversation=='offline-chat-two'
        assert 'CORRECTED_BY_OWNER' in (repo/'acceptance.py').read_text()
        print(json.dumps({'status':'passed','evidence':'real Windows canonical runtime, simulated browser transport, zero ChatGPT sends','session_id':session,'same_session_correction':True,'binding_restart':True,'explicit_conversation_transfer':True,'old_conversation_denied':True,'transferred_session_read':True,'repository':str(repo)},indent=2))
    finally:
        if server: server.shutdown();server.server_close()
        if share: live.stop_share(share)
        print('Fixture and canonical state retained: '+str(repo),file=sys.stderr)

if __name__=='__main__': main()
