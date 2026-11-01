#!/usr/bin/python3
"""Repair the exact known WaveShare EDID on all four mapped NVIDIA DisplayPort connectors."""
from pathlib import Path
import ctypes,fcntl,hashlib,os,subprocess,time,tempfile
from itertools import combinations
DATA=Path('/usr/local/share/waveshare-display')
RAW_HASH='32e8ad5ca55f0133ec2d758a9937ab417d98c179681399ec45860d9633c3f70e'
FIXED_HASH='3a5552c40b66dad2b09603a4178fe89da92bb0f70b3051ed3921b0f5e3931e5f'
GPU='0000:02:00.0'
XORG_CONFIG=Path('/etc/X11/xorg.conf.d/99-waveshare-edid.conf')
PROFILES=(('DP-1','NVIDIA i2c adapter 3 at 2:00.0','DFP-0'),
          ('DP-2','NVIDIA i2c adapter 4 at 2:00.0','DFP-2'),
          ('DP-3','NVIDIA i2c adapter 5 at 2:00.0','DFP-4'),
          ('DP-4','NVIDIA i2c adapter 6 at 2:00.0','DFP-6'))
XORG_CONTENT='# Generated for the verified malformed WaveShare EDID.\nSection "OutputClass"\n    Identifier "waveshare-known-edid"\n    MatchDriver "nvidia-drm"\n    Option "CustomEDID" "DFP-2:/usr/local/share/waveshare-display/edid-fixed.bin"\nEndSection\n'
def prepare_xorg(targets):
    content=XORG_CONTENT.replace("DFP-2:/usr/local/share/waveshare-display/edid-fixed.bin",
        ";".join(target+":/usr/local/share/waveshare-display/edid-fixed.bin" for target in targets))
    owned={XORG_CONTENT}
    names=[profile[2] for profile in PROFILES]
    for count in range(1,len(names)+1):
        for targets_owned in combinations(names,count):
            owned.add(XORG_CONTENT.replace("DFP-2:/usr/local/share/waveshare-display/edid-fixed.bin",
                ";".join(target+":/usr/local/share/waveshare-display/edid-fixed.bin" for target in targets_owned)))
    existing=XORG_CONFIG.read_text() if XORG_CONFIG.exists() else None
    if targets:
        if existing==content: return False
        if existing is not None and existing not in owned: raise RuntimeError('Refusing to replace an unrelated Xorg config')
        fd,name=tempfile.mkstemp(prefix='.waveshare-edid-',dir=XORG_CONFIG.parent)
        try:
            with os.fdopen(fd,'w') as f: f.write(content)
            os.chmod(name,0o644);os.replace(name,XORG_CONFIG)
        finally:
            if os.path.exists(name): os.unlink(name)
        return True
    if existing in owned:
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
def find_connector(port):
    for p in Path('/sys/class/drm').glob('card*-'+port):
        if (p.resolve().parent/'device').resolve().name==GPU: return p
    return None
def main():
    lock=open('/run/lock/waveshare-edid.lock','a')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: return
    fixed=(DATA/'edid-fixed.bin').read_bytes()
    if hashlib.sha256(fixed).hexdigest()!=FIXED_HASH: raise RuntimeError('Corrected EDID file changed')
    subprocess.run(['modprobe','-q','i2c-dev'],check=True)
    connectors=[]
    for attempt in range(20):
        connectors=[(find_connector(port),port,ddc,target) for port,ddc,target in PROFILES]
        if all(conn is not None for conn,_,_,_ in connectors): break
        time.sleep(.1)
    states=[]
    for conn,port,ddc,target in connectors:
        if conn is None: continue
        override=Path('/sys/kernel/debug/dri')/GPU/port/'edid_override'
        previous=override.read_bytes() if override.exists() else b''
        match=False
        if (conn/'status').read_text().strip()=='connected':
            bus=next((bus for bus in Path('/sys/bus/i2c/devices').glob('i2c-*')
                      if bus.resolve().parent.name==GPU and (bus/'name').read_text().strip()==ddc),None)
            if bus is None: raise RuntimeError('Expected DDC adapter absent: '+ddc)
            for retry in range(3):
                try:
                    match=hashlib.sha256(read_edid(bus)).hexdigest()==RAW_HASH
                    break
                except OSError:
                    if retry==2: raise
                    time.sleep(.2)
        if match and not override.exists(): raise RuntimeError('DRM EDID override interface unavailable: '+port)
        states.append((conn,port,target,override,previous,match))
    config_changed=prepare_xorg([target for _,_,target,_,_,match in states if match])
    for conn,port,target,override,previous,match in states:
        changed=False
        if match:
            if previous!=fixed or (conn/'edid').read_bytes()!=fixed:
                override.write_bytes(fixed);changed=True
            print(port+': WaveShare matched: corrected EDID '+('applied' if changed else 'already active'))
        elif previous==fixed:
            override.write_bytes(b'reset');changed=True
            print(port+': Different/absent monitor: WaveShare override removed')
        else: print(port+': Different/absent monitor: normal EDID settings retained')
        if changed:
            (conn/'status').write_text('detect\n')
            subprocess.run(['udevadm','trigger','--action=change',str(conn.resolve().parent)],check=True)
    refresh_greeter(config_changed)
if __name__=='__main__': main()
