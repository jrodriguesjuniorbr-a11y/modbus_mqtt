#!/usr/bin/env python3
"""
raw_modbus_test.py

Send raw Modbus RTU frames (HEX) to a device and print the response.
Uses pyserial only — good to verify wiring / DIP address / baud.

Example:
  python raw_modbus_test.py --port COM16

By default it tries:
 - Channel 1 OPEN : 01 06 00 01 01 00 D9 9A (example from your manual)
 - Read Channel 1 : 01 03 00 01 00 01 D5 CA
Change --baud --slave if needed.
"""
import serial
import argparse
import time
import sys

WRITE_REG = 0X06
READ_REG  = 0X03

def hexstr_to_bytes(s):
    s = s.replace(' ','').replace('\n','')
    return bytes.fromhex(s)

# Common example frames from your manual (slave=1)
EXAMPLES = {
    'chan1_open' : "01 06 00 01 01 00 D9 9A",
    'chan1_close': "01 06 00 01 02 00 D9 6A",
    'read_ch1'   : "01 03 00 01 00 01 D5 CA",
    'remove realationship': "01 06 00 FD 00 00 18 3A",
}
def crc16(data: bytes):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder='little')

# Relay control base (no CRC yet)
def build_relay_command(device, channel, action):
    # channel: 1-8  → convert to register address
    reg_hi = 0x00
    reg_lo = channel  # 1..8

    # action code from manual
    # 01 = open (ON), 02 = close (OFF)
    if action == "on":
        data_hi, data_lo = 0x01, 0x00
    elif action == "off":
        data_hi, data_lo = 0x02, 0x00
    else:
        raise ValueError("action must be 'on' or 'off'")
    
    if channel > 8 or channel < 1:
        raise ValueError("channel must be 1-8")

    frame_wo_crc = bytes([device, WRITE_REG, reg_hi, reg_lo, data_hi, data_lo])

    print("Frame without CRC:", hexdump(frame_wo_crc))
    crc = crc16(frame_wo_crc)
    return frame_wo_crc + crc


def build_read_input(device, input_num):
    # Inputs are 0x0081 - 0x0088
    addr = 0x0080 + input_num
    frame_wo_crc = bytes([
        device,      # slave
        READ_REG,      # read command
        (addr >> 8) & 0xFF,
        addr & 0xFF,
        0x00, 0x01 # read one register
    ])
    crc = crc16(frame_wo_crc)
    return frame_wo_crc + crc

def builst_read_output(device, output_num):
    # Outputs are 0x0001 - 0x0008
    addr = output_num + 1
    frame_wo_crc = bytes([
        device,      # slave
        READ_REG,      # read command
        (addr >> 8) & 0xFF,
        addr & 0xFF,
        0x00, 0x01 # read one register
    ])
    crc = crc16(frame_wo_crc)
    return frame_wo_crc + crc

def hexdump(b):
    return ' '.join(f"{x:02X}" for x in b)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', required=True, help='COM port, e.g. COM16')
    p.add_argument('--device', type=int, default=1, help='slave device id')
    p.add_argument('--baud', type=int, default=9600, help='baud rate')
    p.add_argument('--timeout', type=float, default=0.1, help='serial timeout (s)')
    args = p.parse_args()

    print("Raw Modbus RTU test")
    print("Port:", args.port, "Baud:", args.baud, "Timeout:", args.timeout)
    try:
        ser = serial.Serial(port=args.port, baudrate=args.baud, bytesize=8, parity='N', stopbits=1, timeout=args.timeout)
    except Exception as e:
        print("Failed to open serial port:", e)
        return

    device_selected = args.device

    print("Using slave device ID:", device_selected)

    print("\n--- Interactive Mode ---")
    print("Type: out <number> on/off   (example: out 3 on)")
    print("Type: in <number>           (example: in 2)")
    print("Type: status inp               (reads all inputs)")
    print("Type: status out               (reads all outputs)")
    print("Type: on all                 (turns ON all outputs)")
    print("Type: off all                (turns OFF all outputs)")
    print("Type: exit                   (to quit)\n")

    while True:
        cmd = input("Command> ").strip().lower()
        
        if cmd == "exit":
            break

        print("You typed: ", cmd)

        parts = cmd.split()
        if len(parts) == 3 and parts[0] == "out":
            ch = int(parts[1])
            state = parts[2]
            frame = build_relay_command(device_selected, ch, state)
            ser.reset_input_buffer()
            ser.write(frame)
            time.sleep(0.1)
            resp = ser.read(256)
            print("<- Response:", hexdump(resp))
        elif cmd == "on all":
            for i in range(1, 9):
                frame = build_relay_command(device_selected, i, "on")
                ser.reset_input_buffer()
                ser.write(frame)
                time.sleep(0.01)
                resp = ser.read(256)
                print(f"Channel {i} ON response:", hexdump(resp))
        elif cmd == "off all":
            for i in range(1, 9):
                frame = build_relay_command(device_selected, i, "off")
                ser.reset_input_buffer()
                ser.write(frame)
                time.sleep(0.01)
                resp = ser.read(256)
                print(f"Channel {i} OFF response:", hexdump(resp))        
        elif len(parts) == 2 and parts[0] == "in":
            inp = int(parts[1])
            frame = build_read_input(device_selected, inp)
            ser.reset_input_buffer()
            ser.write(frame)
            time.sleep(0.1)
            resp = ser.read(256)
            size = len(resp)
            if size > 0:
                print("<- Response:", hexdump(resp))
                if resp[4] == 1:
                    print(f"Input {inp} is ON")
                else:
                    print(f"Input {inp} is OFF")
            else:
                print("<- No response (timeout).")

        elif cmd == "status out":
            for i in range(1, 9):
                frame = builst_read_output(device_selected, i)
                ser.reset_input_buffer()
                ser.write(frame)
                time.sleep(0.1)
                resp = ser.read(256)
                size = len(resp)
                if size > 0:
                    if resp[4] == 1:
                        print(f"Output {i} is ON")
                    else:
                        print(f"Output {i} is OFF")
                else:
                    print(f"Output {i}: No response (timeout).")


        elif cmd == "status inp":
            for i in range(1, 9):
                frame = build_read_input(device_selected, i)
                ser.reset_input_buffer()
                ser.write(frame)
                time.sleep(0.1)
                resp = ser.read(256)
                size = len(resp)
                if size > 0:
                    if resp[4] == 1:
                        print(f"Input {i} is ON")
                    else:
                        print(f"Input {i} is OFF")
                else:
                    print(f"Input {i}: No response (timeout).")
        else:
            print("Invalid command format.")


    try:
        for name, hexframe in EXAMPLES.items():
            data = hexstr_to_bytes(hexframe)
            print("\n-> Sending example:", name, hexdump(data))
            ser.reset_input_buffer()
            ser.write(data)
            # short pause — some hardware needs a tiny gap to produce a response
            time.sleep(0.1)
            resp = ser.read(256)  # read up to 256 bytes (timeout-limited)
            if resp:
                print("<- Raw response:", hexdump(resp))
            else:
                print("<- No response (timeout).")
    finally:
        ser.close()


main()