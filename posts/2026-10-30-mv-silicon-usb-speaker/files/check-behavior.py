#!/usr/bin/env python3
"""Exercise copied speaker scripts with fake mixers, sessions and state.

No sudo, real mixer, real sound server, /etc writes or actual boot IDs are used.
Only fixture copies have their absolute input paths redirected.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile

POST = Path(__file__).resolve().parents[1]
SOURCE = POST / 'files/usb-speaker-fix'
SINK = 'alsa_output.usb-MV-SILICON_USB_Speaker-00.iec958-stereo'

PACTL = r'''
from pathlib import Path
import json,os,sys
state_path=Path(os.environ['FAKE_AUDIO_STATE'])
state=json.loads(state_path.read_text())
args=sys.argv[1:]
if args==['list','short','sinks']:
    if state['present']: print('17\talsa_output.usb-MV-SILICON_USB_Speaker-00.iec958-stereo\tPipeWire\ts16le\tRUNNING')
elif args and args[0]=='get-sink-mute': print('Mute: '+('yes' if state['muted'] else 'no'))
elif args and args[0]=='get-sink-volume': print('Volume: mono: 65536 / '+str(state['volume'])+'% / 0.00 dB')
elif args and args[0] in ('set-sink-mute','set-sink-volume'):
    with open(os.environ['FAKE_AUDIO_LOG'],'a') as f: f.write(json.dumps({'program':'pactl','args':args})+'\n')
    if args[0]=='set-sink-mute': state['muted']=args[2]!='0'
    else: state['volume']=int(args[2].rstrip('%'))
    state_path.write_text(json.dumps(state))
else: raise SystemExit(2)
'''
AMIXER = r'''
import json,os,sys
with open(os.environ['FAKE_AUDIO_LOG'],'a') as f:
    f.write(json.dumps({'program':'amixer','args':sys.argv[1:]})+'\n')
'''


def executable(path, content):
    path.write_text(content)
    path.chmod(0o755)


def fixture(root, *, present=True, muted=False, volume=42, seen=None, config='', cards=True):
    fake_bin = root / 'bin'
    fake_bin.mkdir()
    for name, body in [('pactl', PACTL), ('amixer', AMIXER)]:
        executable(fake_bin / name, '#!' + sys.executable + '\n' + body)
    executable(fake_bin / 'id', '#!/bin/sh\nprintf "user\\n"\n')
    executable(fake_bin / 'runuser', '#!/bin/sh\nwhile [ "$1" != "--" ]; do shift; done\nshift\nexec "$@"\n')
    executable(fake_bin / 'sleep', '#!/bin/sh\nexit 0\n')
    audio_state = root / 'audio.json'
    audio_state.write_text(json.dumps({'present': present, 'muted': muted, 'volume': volume}))
    log = root / 'calls.jsonl'
    log.write_text('')
    config_file = root / 'speaker-config'
    config_file.write_text(config)
    boot = root / 'boot-id'
    boot.write_text('fixture-boot-A\n')
    asound = root / 'asound'
    for card, identity in [('0', '1111:2222'), ('7', '8888:1719' if cards else '9999:9999'), ('8', '8888:1719' if cards else '9999:9999')]:
        p = asound / ('card' + card)
        p.mkdir(parents=True)
        (p / 'usbid').write_text(identity + '\n')
    runtime = root / 'runtime/1000'
    runtime.mkdir(parents=True)
    state = root / 'state'
    marker = state / 'reset-usb-speaker/last-boot-id'
    if seen is not None:
        marker.parent.mkdir(parents=True)
        marker.write_text(seen + '\n')
    env = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ.get('PATH', ''),
               XDG_STATE_HOME=str(state), FAKE_AUDIO_STATE=str(audio_state), FAKE_AUDIO_LOG=str(log))
    scripts = {}
    for name in ['reset-usb-speaker-audio.sh', 'reset-usb-speaker-pipewire-session.sh']:
        text = (SOURCE / 'bin' / name).read_text()
        text = text.replace('/etc/default/usb-speaker', str(config_file))
        text = text.replace('/proc/asound/card*/usbid', str(asound / 'card*/usbid'))
        text = text.replace('/run/user/*', str(root / 'runtime/*'))
        text = text.replace('/proc/sys/kernel/random/boot_id', str(boot))
        scripts[name] = root / name
        scripts[name].write_text(text)
    return env, scripts, log, marker, fake_bin


def calls(log):
    return [json.loads(line) for line in log.read_text().splitlines()]


def run(script, env):
    result = subprocess.run(['/bin/sh', str(script)], env=env, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


def main():
    manifest = json.loads((POST / 'evidence/provenance.json').read_text())['files']
    for item in manifest:
        path = SOURCE / item['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], item['path']
        if path.suffix == '.sh':
            subprocess.run(['/bin/sh', '-n', str(path)], check=True)
    results = []
    for name, present, cards, config, card, pcm, software in [
        ('plug-target-card-and-sink', True, True, '', '7', '100%', '40%'),
        ('boot-without-user-sink-still-repairs-alsa', False, True, '', '7', '100%', None),
        ('unrelated-device-and-sink-untouched', False, False, '', None, None, None),
        ('shared-config-overrides-defaults', True, True, 'USB_ID="1111:2222"\nPCM_VOLUME=75%\nPW_VOLUME=17%\n', '0', '75%', '17%'),
    ]:
        with tempfile.TemporaryDirectory(prefix='speaker-fixture-') as directory:
            env, scripts, log, marker, fake_bin = fixture(Path(directory), present=present, cards=cards, config=config)
            run(scripts['reset-usb-speaker-audio.sh'], env)
            events = calls(log)
            hardware = [e['args'] for e in events if e['program'] == 'amixer']
            expected = [] if card is None else [['-c', card, 'sset', 'PCM', pcm, 'unmute']]
            assert hardware == expected, (name, hardware)
            setters = [e['args'] for e in events if e['program'] == 'pactl']
            expected = [] if software is None else [['set-sink-mute', SINK, '0'], ['set-sink-volume', SINK, software]]
            assert setters == expected, (name, setters)
            results.append({'case': name, 'passed': True})

    for name, present, muted, volume, seen, config, expected in [
        ('login-muted-is-repaired-even-same-boot', True, True, 52, 'fixture-boot-A', '', '40%'),
        ('login-zero-volume-is-repaired', True, False, 0, 'fixture-boot-A', '', '40%'),
        ('login-threshold-is-inclusive', True, False, 5, 'fixture-boot-A', '', '40%'),
        ('healthy-first-login-new-boot-gets-default', True, False, 52, 'fixture-boot-B', '', '40%'),
        ('healthy-same-boot-keeps-user-level', True, False, 29, 'fixture-boot-A', '', None),
        ('missing-sink-does-not-mark-boot', False, False, 52, None, '', None),
        ('configured-threshold-preserves-higher-level', True, False, 3, 'fixture-boot-A', 'LOW_VOLUME=2\nPW_VOLUME=17%\n', None),
        ('configured-default-used-for-repair', True, True, 52, 'fixture-boot-A', 'PW_VOLUME=17%\n', '17%'),
    ]:
        with tempfile.TemporaryDirectory(prefix='speaker-fixture-') as directory:
            env, scripts, log, marker, fake_bin = fixture(Path(directory), present=present, muted=muted, volume=volume, seen=seen, config=config)
            run(scripts['reset-usb-speaker-pipewire-session.sh'], env)
            setters = [e['args'] for e in calls(log)]
            desired = [] if expected is None else [['set-sink-mute', SINK, '0'], ['set-sink-volume', SINK, expected]]
            assert setters == desired, (name, setters)
            if expected is not None:
                assert marker.read_text().strip() == 'fixture-boot-A', name
            elif not present:
                assert not marker.exists(), name
            results.append({'case': name, 'passed': True})
    with tempfile.TemporaryDirectory(prefix='speaker-fixture-') as directory:
        env, scripts, log, marker, fake_bin = fixture(Path(directory))
        (fake_bin / 'pactl').unlink()
        # The early missing-tool branch needs only shell builtins: do not search host PATH.
        env['PATH'] = str(fake_bin)
        run(scripts['reset-usb-speaker-pipewire-session.sh'], env)
        assert calls(log) == [] and not marker.exists()
        results.append({'case': 'missing-pactl-exits-without-changes', 'passed': True})
    print(json.dumps({'source_files_verified': len(manifest),
                      'hardware_access': False, 'behavior_checks': results}, indent=2))


if __name__ == '__main__':
    main()
