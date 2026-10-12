"""Local non-Git workspace using canonical Server/Runner init and registration."""
from __future__ import annotations

import json
import os
import pathlib
import socket
import subprocess
import time
import tomllib

import driver
import live_acceptance as live


def validate_state(root, state):
    root, state = pathlib.Path(root).resolve(), pathlib.Path(state).resolve()
    if state == root or state.is_relative_to(root):
        raise driver.DriverError('Private runtime state must be outside the authorized workspace')


def private_directory(path):
    # No credentials exist until the protected inheritable DACL has been installed.
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.is_junction():
        raise driver.DriverError('Private runtime state cannot be a reparse point')
    script = """$ErrorActionPreference='Stop';
$p=[Console]::In.ReadToEnd() | ConvertFrom-Json;
$sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User;
$acl=New-Object System.Security.AccessControl.DirectorySecurity;
$acl.SetSecurityDescriptorSddlForm("D:P(A;OICI;FA;;;$sid)(A;OICI;FA;;;SY)",[System.Security.AccessControl.AccessControlSections]::Access);
[System.IO.Directory]::SetAccessControl($p,$acl)"""
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            input=json.dumps(str(path)), text=True, capture_output=True,
                            env={k: v for k, v in os.environ.items() if k.casefold() != 'psmodulepath'})
    if result.returncode:
        raise driver.DriverError('Could not protect private workspace runtime state')


class WorkspaceRuntime:
    def __init__(self, binary, root, state):
        self.binary, self.root, self.state = binary, root, state
        self.children, self.logs = [], []

    def command(self, *args):
        result = subprocess.run([str(self.binary), *map(str, args)], cwd=self.root,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        if result.returncode:
            # Never include configuration/token-bearing subprocess output in UI/logs.
            raise driver.DriverError('Workspace configuration command failed: ' + ' '.join(map(str, args[:2])))
        return result.stdout

    def start(self):
        validate_state(self.root, self.state)
        private_directory(self.state)
        try:
            env_path = self.state / 'server.env'
            if not env_path.exists():
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1', 0))
                    port = sock.getsockname()[1]
                self.command('server', 'init', '--listen', f'127.0.0.1:{port}',
                             '--data-dir', self.state / 'data', '--env-file', env_path, '--json')
            values = dict(line.split('=', 1) for line in env_path.read_text(encoding='utf-8').splitlines()
                          if '=' in line and not line.startswith('#'))
            token = values['WEBCODEX_TOKEN'].strip().strip('"\'')
            listen = values['WEBCODEX_ADDR'].strip().strip('"\'')
            if not listen.startswith('127.0.0.1:') or not listen[10:].isdigit():
                raise driver.DriverError('Workspace Server must listen on IPv4 loopback')
            url = 'http://' + listen
            token_path, config = self.state / 'runner-token', self.state / 'runner.toml'
            if not config.exists():
                token_path.write_text(token, encoding='utf-8')
                try:
                    self.command('runner', 'init', '--server-url', url, '--token-file', token_path,
                                 '--client-id', 'browser-workspace', '--owner', 'local-owner',
                                 '--allowed-root', self.root, '--project-registry-dir', self.state / 'projects',
                                 '--output', config)
                finally:
                    token_path.unlink(missing_ok=True)
            parsed = tomllib.loads(config.read_text(encoding='utf-8'))
            roots = [pathlib.Path(p).resolve() for p in parsed['policy']['allowed_roots']]
            if roots != [self.root.resolve()] or parsed['policy'].get('allow_cwd_anywhere', False):
                raise driver.DriverError('Workspace Runner authority differs from the selected directory')
            self.command('project', 'register', '--config', config, self.root, '--json')
            # Bind before spawning; do not pair to some other service on a reused port.
            host, port = listen.rsplit(':', 1)
            with socket.socket() as sock:
                sock.bind((host, int(port)))
            env = {k: v for k, v in os.environ.items() if not k.startswith('WEBCODEX_')}
            env['WEBCODEX_ENV_FILE'] = str(env_path)
            env['PATH'] = str(self.binary.parent) + os.pathsep + env.get('PATH', '')
            for name, args in [('webcodex-server.exe', []),
                               ('webcodex-runner.exe', ['--config', str(config)])]:
                log = (self.state / (name + '.log')).open('ab')
                self.logs.append(log)
                self.children.append(subprocess.Popen([str(self.binary.parent / name), *args, '--stop-on-stdin-eof'],
                                     cwd=self.root, env=env, stdin=subprocess.PIPE, stdout=log, stderr=log))
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if any(p.poll() is not None for p in self.children):
                    raise driver.DriverError('Workspace Server/Runner exited; inspect private runtime logs')
                try:
                    project = live.exact_project(url, token)
                    return url, token, project
                except (live.AcceptanceError, OSError, ValueError):
                    time.sleep(.2)
            raise driver.DriverError('Workspace Server/Runner readiness timed out')
        except BaseException:
            self.close()
            raise

    def close(self):
        for child in reversed(self.children):
            if child.stdin:
                child.stdin.close()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.terminate()
                child.wait(timeout=5)
        for log in self.logs:
            log.close()
        self.children, self.logs = [], []
