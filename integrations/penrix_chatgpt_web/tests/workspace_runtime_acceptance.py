"""Windows home-workspace proof using synthetic actions, with zero ChatGPT sends."""
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import driver
import live_acceptance as live
from workspace_runtime import WorkspaceRuntime


def main():
    root = pathlib.Path.home()
    # Both folders are disposable; no existing personal files are inspected.
    first = pathlib.Path(tempfile.mkdtemp(prefix='webcodex-proof-', dir=root / 'Documents'))
    second = pathlib.Path(tempfile.mkdtemp(prefix='webcodex-proof-', dir=root / 'Downloads'))
    a, b = first / 'proof.txt', second / 'proof.txt'
    a.write_text('BEFORE', encoding='utf-8'); b.write_text('SIBLING', encoding='utf-8')
    relative_a, relative_b = a.relative_to(root).as_posix(), b.relative_to(root).as_posix()
    state = pathlib.Path('C:/ProgramData/Penrix-WebCodex/acceptance-home')
    runtime = WorkspaceRuntime(live.find_webcodex(sys.argv[1]), root, state)
    try:
        url, token, project = runtime.start()
        wc = driver.WebCodex(url, token, 90)
        boot = wc.call('work_on_project', {'project': project, 'instruction': 'Synthetic home workspace acceptance; only disposable proof files.'})
        assert boot['success'], driver.dump(boot)
        session = boot['output']['session_id']
        run = driver.Driver(wc, None, project)
        def call(tool, params):
            run.manifest(tool, session)
            result = run.execute(tool, params, session)
            assert result['success'], driver.dump(result)
            return result
        read = call('read_files', {'items': [{'path': relative_a}, {'path': relative_b}]})
        items = read['output']['items']
        revision = next(i['output']['read_revision'] for i in items if i['path'] == relative_a)
        assert 'SIBLING' in driver.dump(read)
        call('edit_project_files', {'changes': [{'kind': 'edit', 'path': relative_a,
             'expected_read_revision': revision, 'edits': [{'kind': 'replace_exact', 'old_text': 'BEFORE', 'new_text': 'AFTER'}]}]})
        assert a.read_text(encoding='utf-8') == 'AFTER'
        outside = run.execute('read_files', {'items': [{'path': 'C:/Windows/win.ini'}]}, session)
        assert outside['output']['succeeded_count'] == 0 and outside['output']['failed_count'] == 1, driver.dump(outside)
        process = call('run_process', {'executable':sys.executable,
                       'args':['-c','from pathlib import Path; assert Path("proof.txt").read_text()=="SIBLING"; print("SIBLING_CWD_OK")'],
                       'cwd':second.relative_to(root).as_posix(),'purpose':'diagnostic'})
        assert 'SIBLING_CWD_OK' in driver.dump(process), driver.dump(process)
        finish = call('finish_coding_task', {})
        assert run.closeout_ok
        runtime.close()
        url, token, restored_project = runtime.start()
        assert restored_project == project
        restored = driver.WebCodex(url, token, 90).call('work_on_project',
                   {'project':project,'instruction':'Read-only recovery of exact synthetic session','session_id':session})
        assert restored['success'] and restored['output']['session_id'] == session
        print(json.dumps({'home':str(root),'project':project,'session':session,'sibling_read':True,
              'fenced_edit':True,'sibling_process_cwd':True,'outside_read_denied':True,'finish':finish['success'],'restart_session':True,
              'proof_files':[str(a),str(b)],'chatgpt_sends':0}))
    finally:
        runtime.close()


if __name__ == '__main__':
    main()
