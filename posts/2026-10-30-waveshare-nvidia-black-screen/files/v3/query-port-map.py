#!/usr/bin/python3
"""Read NVIDIA RM connector/DDC metadata; no display settings are changed.

Struct layouts and GET command identifiers follow installed NVIDIA 580.178.04
SDK headers nvos.h, cl0080.h, ctrl0073system.h and ctrl0073specific.h.
Run on the incident host as root. This diagnostic is not a startup dependency.
"""
import ctypes as c
import fcntl
import os

U = c.c_uint32
P = c.c_uint64
class Alloc(c.Structure):
    _fields_ = [('root', U), ('parent', U), ('new', U), ('cls', U),
                ('params', P), ('size', U), ('status', U)]
class Ctrl(c.Structure):
    _fields_ = [('client', U), ('obj', U), ('cmd', U), ('flags', U),
                ('params', P), ('size', U), ('status', U)]
class Device(c.Structure):
    _fields_ = [('device', U), ('share', U), ('targetClient', U),
                ('targetDevice', U), ('flags', U), ('vasize', P),
                ('vastart', P), ('valimit', P), ('vamode', U)]

def main():
    fd = os.open('/dev/nvidiactl', os.O_RDWR)
    gpu_fd = os.open('/dev/nvidia0', os.O_RDWR)
    fcntl.ioctl(gpu_fd, 0xc00446c9, c.c_int(fd))
    try:
        def ioctl(num, p):
            fcntl.ioctl(fd, 0xc0000000 | (c.sizeof(p) << 16) | (ord('F') << 8) | num, p)
            if p.status:
                raise RuntimeError('NVIDIA RM status ' + hex(p.status))
        root = Alloc(0, 0, 0, 0, 0, 0, 0)
        ioctl(0x2b, root)
        client = root.new
        def control(obj, cmd, p):
            x = Ctrl(client, obj, cmd, 0, c.addressof(p), c.sizeof(p), 0)
            ioctl(0x2a, x)
        ids = (U * 32)()
        control(client, 0x201, ids)
        gpu_ids = [gid for gid in ids if gid != 0xffffffff]
        if len(gpu_ids) != 1:
            raise RuntimeError('Diagnostic expects exactly one NVIDIA GPU')
        info = (U * 8)(gpu_ids[0])
        control(client, 0x205, info)
        dev = Device(device=info[2])
        a = Alloc(client, client, 0x100, 0x80, c.addressof(dev), c.sizeof(dev), 0)
        ioctl(0x2b, a)
        a = Alloc(client, 0x100, 0x101, 0x73, 0, 0, 0)
        ioctl(0x2b, a)
        supported = (U * 3)()
        control(0x101, 0x730107, supported)
        print('Supported display mask:', hex(supported[1]))
        for i in range(32):
            if not supported[1] & (1 << i):
                continue
            ports = (U * 4)(0, 1 << i, 0, 0)
            control(0x101, 0x730211, ports)
            data = (U * 18)(0, 1 << i)
            control(0x101, 0x730250, data)
            print('display_mask=' + hex(1 << i), 'ddc_port=' + str(ports[3]),
                  'connector_count=' + str(data[4]),
                  'connectors=' + str([list(data[5 + j*3:8 + j*3])
                                       for j in range(min(data[4], 4))]))
    finally:
        # Closing the RM client descriptor releases its allocated query handles.
        os.close(gpu_fd)
        os.close(fd)

if __name__ == '__main__':
    main()
