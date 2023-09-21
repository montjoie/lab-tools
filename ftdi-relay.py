#!/usr/bin/env python3

import argparse
import serial
import time

# https://sigma-shop.com/product/92/une-canal-usb-relai-pcb-ftdi-chip.html
# KMTronic

parser = argparse.ArgumentParser()
parser.add_argument("--debug", "-d", help="increase debug level", action="store_true")
parser.add_argument("--off", "-0", help="power off", action="store_true")
parser.add_argument("--on", "-1", help="power off", action="store_true")
parser.add_argument("--atx", help="power on then off", action="store_true")
parser.add_argument("--delay", help="delay between 2 actions", type=int, default=2)
parser.add_argument("--serial", help="serialname", type=str, default="/dev/ttyUSB0")
args = parser.parse_args()

ser = serial.Serial(args.serial, 9600)
if args.off:
    if args.debug:
        print("FTDI RELAY: power off")
    ser.write(b'\xFF\x01\x00')
if args.off and args.on:
    time.sleep(args.delay)
if args.on:
    if args.debug:
        print("FTDI RELAY: power on")
    ser.write(b'\xFF\x01\x01')
if args.atx:
    if args.debug:
        print("FTDI RELAY: power on")
    ser.write(b'\xFF\x01\x01')
    time.sleep(args.delay)
    if args.debug:
        print("FTDI RELAY: power off")
    ser.write(b'\xFF\x01\x00')
ser.close()
