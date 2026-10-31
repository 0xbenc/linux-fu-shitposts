#!/usr/bin/python3
"""Repair only the observed malformed WaveShare EDID on this GPU's DP-2."""
from pathlib import Path
import ctypes,fcntl,hashlib,os,subprocess,time,tempfile
DATA=Path('/usr/local/share/waveshare-display')
RAW_HASH='32e8ad5ca55f0133ec2d758a9937ab417d98c179681399ec45860d9633c3f70e'
FIXED_HASH='3a5552c40b66dad2b09603a4178fe89da92bb0f70b3051ed3921b0f5e3931e5f'
GPU='0000:02:00.0'
XORG_CONFIG=Path('/etc/X11/xorg.conf.d/99-waveshare-edid.conf')
XORG_CONTENT='# Generated for the verified malformed WaveShare EDID.\nSection "OutputClass"\n    Identifier "waveshare-known-edid"\n    MatchDriver "nvidia-drm"\n    Option "CustomEDID" "DFP-2:/usr/local/share/waveshare-display/edid-fixed.bin"\nEndSection\n'
def prepare_xorg(match):
    existing=XORG_CONFIG.read_text() if XORG_CONFIG.exists() else None
    if match:
        if existing==XORG_CONTENT: return False
        if existing is not None: raise RuntimeError('Refusing to replace an unrelated Xorg config')
        fd,name=tempfile.mkstemp(prefix='.waveshare-edid-',dir=XORG_CONFIG.parent)
        try:
            with os.fdopen(fd,'w') as f: f.write(XORG_CONTENT)
            os.chmod(name,0o644);os.replace(name,XORG_CONFIG)
        finally:
            if os.path.exists(name): os.unlink(name)
        return True
    if existing==XORG_CONTENT:
        XORG_CONFIG.unlink();return True
    return False
def refresh_greeter(config_changed):
    if not config_changed: return
    state=subprocess.run(['systemctl','is-active','sddm'],capture_output=True,text=True)
    if state.stdout.strip()!='active': return
    sessions=subprocess.run(['loginctl','list-sessions','--no-legend'],capture_output=True,text=True,check=True).stdout
    desktop=any(len(cols:=line.split())>3 and cols[3]=='seat0' and cols[2]!='sddm' for line in sessions.splitlines())
    if not desktop:
        subprocess.run(['systemctl','--no-block','try-restart','sddm'],check=True)

class Msg(ctypes.Structure):
    _fields_=[('addr',ctypes.c_ushort),('flags',ctypes.c_ushort),('length',ctypes.c_ushort),('buf',ctypes.c_void_p)]
class Rdwr(ctypes.Structure):
    _fields_=[('msgs',ctypes.POINTER(Msg)),('nmsgs',ctypes.c_uint)]
def read_edid(bus):
    fd=os.open('/dev/'+bus.name,os.O_RDWR)
    try:
        blocks=[]
        for off in (0,128):
            offset=(ctypes.c_ubyte*1)(off);buf=(ctypes.c_ubyte*128)()
            msgs=(Msg*2)(Msg(0x50,0,1,ctypes.addressof(offset)),Msg(0x50,1,128,ctypes.addressof(buf)))
            fcntl.ioctl(fd,0x0707,Rdwr(msgs,2));blocks.append(bytes(buf))
        return b''.join(blocks)
    finally: os.close(fd)
def find_connector():
    for p in Path('/sys/class/drm').glob('card*-DP-2'):
        if (p.resolve().parent/'device').resolve().name==GPU: return p
    return None
def main():
    lock=open('/run/lock/waveshare-edid.lock','a')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: return
    fixed=(DATA/'edid-fixed.bin').read_bytes()
    if hashlib.sha256(fixed).hexdigest()!=FIXED_HASH: raise RuntimeError('Corrected EDID file changed')
    subprocess.run(['modprobe','-q','i2c-dev'],check=True)
    conn=None
    for attempt in range(20):
        conn=find_connector()
        if conn is not None: break
        time.sleep(.1)
    if conn is None:
        print('WaveShare: expected GPU connector absent; no changes');return
    override=Path('/sys/kernel/debug/dri')/GPU/'DP-2'/'edid_override'
    previous=override.read_bytes() if override.exists() else b''
    match=False
    if (conn/'status').read_text().strip()=='connected':
        for bus in Path('/sys/bus/i2c/devices').glob('i2c-*'):
            if bus.resolve().parent.name!=GPU: continue
            if (bus/'name').read_text().strip()!='NVIDIA i2c adapter 4 at 2:00.0': continue
            try: match=hashlib.sha256(read_edid(bus)).hexdigest()==RAW_HASH
            except OSError as exc: print('WaveShare DDC read:',exc)
            break
    config_changed=prepare_xorg(match)
    changed=False
    if match:
        if not override.exists(): raise RuntimeError('DRM EDID override interface unavailable')
        if previous!=fixed or (conn/'edid').read_bytes()!=fixed:
            override.write_bytes(fixed);changed=True
        print('WaveShare matched: corrected EDID '+('applied' if changed else 'already active'))
    elif previous==fixed:
        override.write_bytes(b'reset');changed=True
        print('Different/absent monitor: WaveShare override removed')
    else: print('Different/absent monitor: normal EDID settings retained')
    if changed:
        (conn/'status').write_text('detect\n')
        card=conn.resolve().parent
        subprocess.run(['udevadm','trigger','--action=change',str(card)],check=True)
    refresh_greeter(config_changed)
if __name__=='__main__': main()
