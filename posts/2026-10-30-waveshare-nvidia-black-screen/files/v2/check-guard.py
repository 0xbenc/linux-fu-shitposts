#!/usr/bin/env python3
"""Check the saved bundle and guard without root or hardware access."""
from pathlib import Path
import builtins
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import types

sys.dont_write_bytecode = True
POST = Path(__file__).resolve().parents[2]
FILES = POST / 'files'


def main():
    record = json.loads((POST / 'evidence/session.json').read_text())
    for target, item in record['installed'].items():
        source = (FILES / 'generated-xorg.conf' if target.startswith('/etc/X11/')
                  else FILES / 'root' / target.lstrip('/'))
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item['sha256'], target
    data = FILES / 'root/usr/local/share/waveshare-display'
    raw = (data / 'edid-raw.bin').read_bytes()
    fixed = (data / 'edid-fixed.bin').read_bytes()
    assert len(raw) == len(fixed) == 256
    assert all(sum(blob[n:n + 128]) % 256 == 0
               for blob in (raw, fixed) for n in (0, 128))
    assert raw[54:72] == fixed[54:72] and raw[128:] == fixed[128:]
    expected = bytearray(raw)
    expected[90:108] = expected[108:126] = bytes.fromhex('000000100000000000000000000000000000')
    expected[127] = (-sum(expected[:127])) % 256
    assert bytes(expected) == fixed

    source = FILES / 'v2/root/usr/local/libexec/waveshare-edid-prepare.py'
    spec = importlib.util.spec_from_file_location('guard', source)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    results = []
    cases = [
        ('known-screen-apply', True, True, b'', b'', fixed, True, None, guard.XORG_CONTENT),
        ('known-screen-idempotent', True, True, fixed, fixed, fixed, False, guard.XORG_CONTENT, guard.XORG_CONTENT),
        ('different-screen-clear-own-overrides', True, False, fixed, fixed, b'reset', True, guard.XORG_CONTENT, None),
        ('different-screen-preserve-unrelated-overrides', True, False, b'unrelated', b'', b'unrelated', False, 'unrelated', 'unrelated'),
        ('unplugged-screen-clear-own-overrides', False, False, fixed, fixed, b'reset', True, guard.XORG_CONTENT, None),
    ]
    for port, ddc, target in guard.PROFILES:
      for name, connected, matches, previous, kernel, expected, changed, xorg_before, xorg_after in cases:
        name=port+'-'+name
        if port=='DP-1':
            xorg_before=xorg_before.replace('DFP-2:', 'DFP-0:') if xorg_before else None
            xorg_after=xorg_after.replace('DFP-2:', 'DFP-0:') if xorg_after else None
        with tempfile.TemporaryDirectory(prefix='display-guard-check-') as directory:
            root = Path(directory)
            fake_data = root / 'data'
            fake_data.mkdir()
            (fake_data / 'edid-fixed.bin').write_bytes(fixed)
            bus_root = root / guard.GPU
            bus = bus_root / 'i2c-2'
            bus.mkdir(parents=True)
            (bus / 'name').write_text(ddc+'\n')
            debug_root = root / 'debug'
            debug = debug_root / guard.GPU / port
            debug.mkdir(parents=True)
            (debug / 'edid_override').write_bytes(previous)
            conn = root / ('card1/card1-'+port)
            conn.mkdir(parents=True)
            (conn / 'status').write_text('connected' if connected else 'disconnected')
            (conn / 'edid').write_bytes(kernel)
            xorg = root / 'xorg.conf'
            if xorg_before is not None:
                xorg.write_text(xorg_before)
            calls = []

            def run(args, **kwargs):
                calls.append(args)
                return types.SimpleNamespace(returncode=0, stdout='inactive\n')

            guard.DATA = fake_data
            guard.XORG_CONFIG = xorg
            guard.Path = lambda value: {
                '/sys/kernel/debug/dri': debug_root,
                '/sys/bus/i2c/devices': bus_root,
            }.get(str(value), Path(value))
            guard.find_connector = lambda selected: conn if selected==port else None
            guard.read_edid = lambda bus: raw if matches else bytes(256)
            guard.open = lambda name, *a, **kw: builtins.open(
                root / 'lock' if name == '/run/lock/waveshare-edid.lock' else name, *a, **kw)
            guard.subprocess = types.SimpleNamespace(run=run)
            guard.time = types.SimpleNamespace(sleep=lambda _: None)
            with contextlib.redirect_stdout(io.StringIO()):
                guard.main()
            assert (debug / 'edid_override').read_bytes() == expected, name
            assert (xorg.read_text() if xorg.exists() else None) == xorg_after, name
            assert sum(call[0] == 'udevadm' for call in calls) == int(changed), name
            results.append({'case': name, 'passed': True})

    for name, state, sessions, restart in [
        ('greeter-refresh-when-no-desktop', 'active', 'c1 960 sddm seat0 100 greeter tty2 no -\n', True),
        ('preserve-active-user-desktop', 'active', '5 1000 user seat0 200 user tty1 no -\n', False),
        ('no-restart-during-startup', 'activating', '', False),
    ]:
        calls = []

        def run(args, **kwargs):
            calls.append(args)
            return types.SimpleNamespace(returncode=0, stdout=state + '\n' if args[0] == 'systemctl' else sessions)

        guard.subprocess = types.SimpleNamespace(run=run)
        guard.refresh_greeter(True)
        assert any('--no-block' in call for call in calls) == restart, name
        results.append({'case': name, 'passed': True})
    print(json.dumps({'bundle_files_verified': len(record['installed']),
                      'edid_repair_verified': True, 'guard_checks': results}, indent=2))


if __name__ == '__main__':
    main()
