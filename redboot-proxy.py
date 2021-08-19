#!/usr/bin/env python3

import serial
import argparse
import time
import os
import socket
import subprocess
import re
import sys

# substract uboot header len
def uboot_header(s):
    addr = int(s, base=16) - 64
    return "0x%x" % addr

parser = argparse.ArgumentParser()
parser.add_argument("--proxy", action="store_true", help="enable TFTP proxy")
parser.add_argument("--debug", "-d", action="store_true", help="enable debug")
parser.add_argument("--name", "-n", type=str, help="tty name")
parser.add_argument("--port", "-p", type=int, help="Cambrionix port to control")
parser.add_argument("--netport", type=int, help="Nerwork port", default=12346)
parser.add_argument("--baud", type=int, help="baud rate", default=115200)

args = parser.parse_args()

s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
host = socket.gethostname()
print("DEBUG: listen on %d" % args.netport)
s.bind(("0.0.0.0", args.netport))
s.setblocking(0)
s.listen(5)
clients = []
opened = False
loopn = 0
discard = 0
serial_timeout = 0

# phase:
# 0 need to send uboot 
# 1 waiting for uboot commands
# 2 need to boot, send command to console
# 3 pass though
phase = 0
redboot = 0
console_out = b""
tftp = {}
console_ok = False
console_timeout = 0
in_tftp = False

rtype = 0
csleep = 1

def full_reset():
    global phase
    global redboot
    global clients
    global console_out

    print("DOING FULL RESET")
    if args.proxy:
        os.remove("/var/lib/lava/dispatcher/tmp/ssi1328.image")
        os.remove("/var/lib/lava/dispatcher/tmp/ssi1328.ramdisk")
    phase = 0
    redboot = 0
    for client in clients:
        client.send(console_out)
        client.close()
        clients.remove(client)
    console_out = b""

def handle_intial_console():
    global console_out
    global phase
    global redboot
    global in_tftp
    global tftp
    global console_ok
    global console_timeout
    global rtype
    global csleep
    global ser

    # writes
    if not console_ok:
        if csleep > 0:
            console_timeout += 1
        if console_timeout == 60:
            console_timeout = 0
            print("TRY TO GRAB CONSOLE")
            ser.write("\r\n".encode("UTF8"))
    if phase == 2 and console_ok:
        print("init_console phase=%d redboot=%d" % (phase, redboot))
        if redboot == 2:
            cmd = "go %s\r\n" % tftp["aimage"]
            bcmd = cmd.encode("ascii")
            console_out += bcmd
            for client in clients:
                client.send(console_out)
                client.send(b'Starting kernel')
            ser.write(bcmd)
            redboot = 3
            phase = 3
            console_ok = False
        if redboot == 1:
            cmd = "load -r -h %s -b %s %s\r\n" % (tftp["server"], tftp["aimage"], tftp["image"])
            if rtype == 1:
                cmd = "load -m tftp -b %s\n" % tftp["aimage"]
            print("SEND %s" % cmd)
            bcmd = cmd.encode("ascii")
            print(bcmd)
            ser.write(bcmd)
            redboot = 2
            console_ok = False
        if redboot == 0:
            cmd = "load -r -h %s -b %s %s\r\n" % (tftp["server"], tftp["aramdisk"], tftp["ramdisk"])
            if rtype == 1:
                cmd = "\rload -m tftp -b %s\n" % tftp["aramdisk"]
            print("SEND %s" % cmd)
            bcmd = cmd.encode("ascii")
            print(bcmd)
            ser.write(bcmd)
            redboot = 1
            console_ok = False
    # reads
    try:
        #RedBoot
        b = ser.readline()
        if len(b) == 0:
            csleep = 1
            return
        csleep = 0
        console_timeout = 0
        if in_tftp:
            print("TFTP FILTER %d" % len(b))
            # filters chars
            bb = bytearray(b'')
            for c in b:
                if c == 0 or c == 8 or c == 47 or c == 45 or c == 124 or c == 92:
                    continue
                in_tftp = False
                bb.append(c)
            b = bytes(bb)
            print("TFTP FILTERED to %d" % len(b))
        if len(b) == 0:
            return
        if args.debug:
            print("SERIAL %d" % len(b))
            print(b)
        buf = b.decode("UTF8", errors='ignore')
        console_out += b
        if re.search("TFTP Server IP Address:", buf):
            cmd = '%s\n' % tftp["server"]
            print("SEND %s" % cmd)
            bcmd = cmd.encode("ascii")
            print(bcmd)
            ret = ser.write(bcmd)
            print(ret)
        if re.search("Image Path and name", buf):
            time.sleep(1)
            if redboot == 1:
                cmd = '%s\n' % tftp["ramdisk"]
            else:
                cmd = '%s\n' % tftp["image"]
            print("SEND %s" % cmd)
            bcmd = cmd.encode("ascii")
            print(bcmd)
            ret = ser.write(bcmd)
            print(ret)
        if re.search("=> Select:", buf):
            print("SEND 5")
            ser.write(b'5')
        if re.search("to abort booting within", buf):
            print("SENDBREAK")
            # send ctrl-c
            ser.write(b'\x03')
        if re.search("file not found", buf):
            print("TFTP ERROR")
            full_reset()
            return
        if re.search("Failed for TFTP", buf):
            print("TFTP ERROR")
            full_reset()
            return
        if re.search("operation timed out", buf):
            print("TFTP ERROR")
            full_reset()
            return
        if re.search("Illegal IP address", buf):
            print("TFTP ERROR")
            full_reset()
            return
        if len(b) == 8 and buf == 'sl-boot>':
            print("CONSOLE OK")
            console_ok = True
            rtype = 1
        if len(b) == 9 and buf == 'RedBoot> ':
            print("CONSOLE OK")
            console_ok = True
        #if len(b) == 31 and re.search("Using default protocol", buf):
            #in_tftp = True
    except serial.serialutil.SerialException:
        ser.close()
        if args.debug:
            print("DISCO")
        opened = False

def handle_initial_net():
    global clients
    global tftp
    global phase

    nn = 0
    for client in clients:
        try:
            buf = client.recv(1024)
            nn = nn + 1
            if len(buf) == 0:
                if args.debug:
                    print("CLIENT DISCO")
                clients.remove(client)
            if len(buf) == 2 and buf.decode("UTF-8") == '\r\n':
                client.send("=>\r\n".encode("UTF8"))
                continue
            if len(buf) > 0:
                if args.debug:
                    print("DEBUG: client %d send %s data" % (nn, len(buf)))
                    print("ENDBUF")
                bubu = buf.decode("UTF-8").rstrip("\n")
                if bubu[0:6] == 'setenv':
                    setenv_args = bubu.split()
                    if setenv_args[1] == 'serverip':
                        print("SERVERIP %s" % setenv_args[2])
                        tftp["server"] = setenv_args[2]
                    client.send("=>\r\n".encode("UTF8"))
                    continue
                if bubu[0:4] == 'dhcp':
                    client.send("=>\r\n".encode("UTF8"))
                    continue
                if bubu[0:4] == 'tftp':
                    tftp_args = bubu.split()
                    print("TFTP PATH %s" % tftp_args[2])
                    client.send("=>\r\n".encode("UTF8"))
                    if re.search("zImage", bubu) or re.search("kernel-dtb", bubu) or re.search("uImage", bubu):
                        tftp["aimage"] = tftp_args[1]
                        tftp["image"] = tftp_args[2]
                        print("TFTP is for image %s at %s" % (tftp["image"], tftp["aimage"]))
                    if re.search("ramdisk", bubu) or re.search("rootfs", bubu):
                        tftp["aramdisk"] = uboot_header(tftp_args[1])
                        tftp["ramdisk"] = tftp_args[2]
                        print("TFTP is for ramdisk")
                    continue
                if bubu[0:5] == 'booti' or bubu[0:5] == 'bootz' or bubu[0:5] == 'bootm':
                    f = open("/tmp/doserial.sh", 'w')
                    phase = 2
                    if not args.proxy:
                        continue
                    f.write('#!/bin/sh\n')
                    f.write("curl --no-progress-meter tftp://%s/%s --output - > /var/lib/lava/dispatcher/tmp/ssi1328.ramdisk\n" % (tftp["server"], tftp["ramdisk"]))
                    f.write("curl --no-progress-meter tftp://%s/%s --output - > /var/lib/lava/dispatcher/tmp/ssi1328.image\n" % (tftp["server"], tftp["image"]))
                    f.close()

                    # TODO handle errors
                    os.chmod("/tmp/doserial.sh", 755)
                    subprocess.run("/tmp/doserial.sh")
                    os.chmod("/var/lib/lava/dispatcher/tmp/ssi1328.image", 644)
                    os.chmod("/var/lib/lava/dispatcher/tmp/ssi1328.ramdisk", 644)
                    print("PHASE 2 ============================================================")
                    tftp["image"] = "ssi1328.image"
                    tftp["ramdisk"] = "ssi1328.ramdisk"
                    # TODO hardcoded
                    tftp["server"] = "192.168.1.40"
                    # TODO remove them in full reset

                    continue
                print("UNHANDLED")

        except OSError as e:
            #if args.debug:
            #    print("DEBUG: nothing for %s %d" % (client, e.errno))
            nothing = 0

while True:
    loopn = loopn + 1
    try:
        c, addr = s.accept()
        c.setblocking(0)
        if args.debug:
            print("DEBUG: connected from ")
        clients.append(c)
    except socket.error:
        nothing = 0
        #if args.debug:
        #    print("DEBUG: no new client")
    if len(clients) == 0:
        time.sleep(csleep)
    if not opened:
        try:
            ser = serial.Serial(args.name, args.baud, timeout=1)
            opened = True
            serial_timeout = 10
        except FileNotFoundError:
            if args.debug:
                print("RETRY %d" % loopn)
            time.sleep(1)
            continue
        except serial.serialutil.SerialException:
            if args.debug:
                print("RETRY %d" % loopn)
            time.sleep(1)
            continue
    nn = 0
    if phase > 0 and len(clients) == 0:
        print("NEED FULL RESET")
        full_reset()
    if phase == 0 and len(clients) > 0:
        for client in clients:
            client.send("Fake U-Boot, redboot proxy\n".encode("UTF8"))
            client.send("Hit any key to stop autoboot\n".encode("UTF8"))
        phase = 1
    if phase < 3:
        handle_initial_net()
        handle_intial_console()
        continue
    for client in clients:
        try:
            buf = client.recv(1024)
            nn = nn + 1
            if len(buf) == 0:
                if args.debug:
                    print("CLIENT DISCO")
                clients.remove(client)
            if len(buf) > 0:
                if args.debug:
                    print("DEBUG: client %d send %s data" % (nn, len(buf)))
                    print("ENDBUF")
                bubu = buf.decode("UTF-8").rstrip("\n")
                ser.write(bubu.encode("UTF-8"))
                discard = len(buf)
        except OSError as e:
            nothing = 0
            #if args.debug:
            #    print("DEBUG: nothing for %s %d" % (client, e.errno))
    try:
        #if args.debug:
        #    print("DEBUG: serial recv")
        b = ser.readline()
        if (len(b) > 0):
            if discard == len(b):
                discard = 0
                continue
            if args.debug:
                print("SERIAL %d" % len(b))
                print(b)
            nn = 0
            for client in clients:
                if args.debug:
                    print("Send to %d" % nn)
                nn = nn +1
                client.send(b)
    except serial.serialutil.SerialException:
        ser.close()
        if args.debug:
            print("DISCO")
        opened = False


sys.exit(0)

