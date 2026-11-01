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
    current = json.loads((POST / 'evidence/2026-10-31-followup.json').read_text())
    for target, digest in current['installed_sha256'].items():
        source = FILES / 'v3/root' / target.lstrip('/')
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, target
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

    source = FILES / 'v3/root/usr/local/libexec/waveshare-edid-prepare.py'
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
        xorg_before=xorg_before.replace('DFP-2:', target+':') if xorg_before else None
        xorg_after=xorg_after.replace('DFP-2:', target+':') if xorg_after else None
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
    # Exercise a real port move with all four connector fixtures present.
    spec = importlib.util.spec_from_file_location('multiport_guard', source)
    multi = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(multi)
    with tempfile.TemporaryDirectory(prefix='display-multiport-check-') as directory:
        root = Path(directory)
        data = root / 'data'
        data.mkdir()
        (data / 'edid-fixed.bin').write_bytes(fixed)
        buses = root / multi.GPU
        debug_root = root / 'debug'
        conns = {}
        overrides = {}
        for index, (port, ddc, _) in enumerate(multi.PROFILES):
            bus = buses / ('i2c-' + str(index))
            bus.mkdir(parents=True)
            (bus / 'name').write_text(ddc)
            conn = root / 'card1' / ('card1-' + port)
            conn.mkdir(parents=True)
            (conn / 'status').write_text('connected')
            (conn / 'edid').write_bytes(b'')
            conns[port] = conn
            override = debug_root / multi.GPU / port / 'edid_override'
            override.parent.mkdir(parents=True)
            override.write_bytes(b'unrelated' if port == 'DP-4' else b'')
            overrides[port] = override
        multi.DATA = data
        multi.XORG_CONFIG = root / 'xorg.conf'
        multi.Path = lambda value: {
            '/sys/kernel/debug/dri': debug_root,
            '/sys/bus/i2c/devices': buses,
        }.get(str(value), Path(value))
        multi.find_connector = conns.get
        multi.open = lambda name, *a, **kw: builtins.open(
            root / 'lock' if name == '/run/lock/waveshare-edid.lock' else name, *a, **kw)
        calls = []
        multi.subprocess = types.SimpleNamespace(run=lambda args, **kw: (
            calls.append(args) or types.SimpleNamespace(returncode=0, stdout='inactive\n')))
        for selected, target in [('i2c-0', 'DFP-0'), ('i2c-2', 'DFP-4')]:
            for conn in conns.values():
                (conn / 'status').write_text('connected')
            multi.read_edid = lambda bus: raw if bus.name == selected else bytes(256)
            with contextlib.redirect_stdout(io.StringIO()):
                multi.main()
            port = 'DP-1' if selected == 'i2c-0' else 'DP-3'
            assert overrides[port].read_bytes() == fixed
            assert target + ':' in multi.XORG_CONFIG.read_text()
            assert overrides['DP-2'].read_bytes() == b''
            assert overrides['DP-4'].read_bytes() == b'unrelated'
        assert overrides['DP-1'].read_bytes() == b'reset'
        results.append({'case': 'move-DP-1-to-DP-3-with-other-monitors', 'passed': True})

        # A failed DDC read must not clear overrides or change Xorg settings.
        before = multi.XORG_CONFIG.read_bytes()
        before_overrides = {port: path.read_bytes() for port, path in overrides.items()}
        for conn in conns.values():
            (conn / 'status').write_text('connected')
        def fail_ddc(bus):
            raise OSError('fixture DDC unavailable')
        multi.read_edid = fail_ddc
        multi.time = types.SimpleNamespace(sleep=lambda _: None)
        try:
            multi.main()
        except OSError:
            pass
        else:
            raise AssertionError('DDC failure should fail closed')
        assert multi.XORG_CONFIG.read_bytes() == before
        assert {port: path.read_bytes() for port, path in overrides.items()} == before_overrides
        results.append({'case': 'ddc-failure-preserves-current-configuration', 'passed': True})

    print(json.dumps({'historical_bundle_files_verified': len(record['installed']),
                      'current_overlay_files_verified': len(current['installed_sha256']),
                      'edid_repair_verified': True, 'guard_checks': results}, indent=2))


if __name__ == '__main__':
    main()
