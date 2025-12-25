#!/usr/bin/env python3
"""
raw_modbus_mqtt_json.py

MQTT <-> Modbus RTU bridge using JSON commands.

MQTT CMD topic:
  george/test/board/cmd

MQTT RESPONSE topic:
  george/test/board/response
"""

import serial
import argparse
import time
import sys
import json
import paho.mqtt.client as mqtt

# -------------------
# MODBUS CONSTANTS
# -------------------
WRITE_REG = 0x06
READ_REG  = 0x03

# -------------------
# CRC16
# -------------------
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

def hexdump(b):
    return ' '.join(f"{x:02X}" for x in b)

# -------------------
# FRAME BUILDERS
# -------------------
def build_relay_command(device, channel, action):
    if channel < 1 or channel > 8:
        raise ValueError("channel must be 1-8")

    if action == "on":
        data_hi, data_lo = 0x01, 0x00
    elif action == "off":
        data_hi, data_lo = 0x02, 0x00
    else:
        raise ValueError("action must be 'on' or 'off'")

    frame = bytes([
        device,
        WRITE_REG,
        0x00,
        channel,
        data_hi,
        data_lo
    ])
    return frame + crc16(frame)

def build_read_input(device, input_num):
    addr = 0x0080 + input_num
    frame = bytes([
        device,
        READ_REG,
        (addr >> 8) & 0xFF,
        addr & 0xFF,
        0x00,
        0x01
    ])
    return frame + crc16(frame)

def build_read_output(device, output_num):
    frame = bytes([
        device,
        READ_REG,
        0x00,
        output_num,
        0x00,
        0x01
    ])
    return frame + crc16(frame)

# -------------------
# MQTT HELPERS
# -------------------
def publish_json(obj):
    client.publish(
        "george/test/board/response",
        json.dumps(obj, indent=2),
        qos=1
    )

# -------------------
# COMMAND PROCESSOR
# -------------------
def process_command(data):
    cmd = data.get("cmd")

    try:
        # ---------------- output single ----------------
        if cmd == "output":
            ch = data["channel"]
            state = data["state"]

            frame = build_relay_command(device_selected, ch, state)
            ser.reset_input_buffer()
            ser.write(frame)
            time.sleep(0.1)
            resp = ser.read(256)

            publish_json({
                "result": "ok",
                "cmd": cmd,
                "channel": ch,
                "state": state,
                "response": hexdump(resp)
            })

        # ---------------- output all ----------------
        elif cmd == "output_all":
            state = data["state"]
            results = []

            for i in range(1, 9):
                frame = build_relay_command(device_selected, i, state)
                ser.reset_input_buffer()
                ser.write(frame)
                time.sleep(0.05)
                resp = ser.read(256)

                results.append({
                    "channel": i,
                    "response": hexdump(resp) if resp else None
                })

            publish_json({
                "result": "ok",
                "cmd": cmd,
                "state": state,
                "outputs": results
            })

        # ---------------- read input ----------------
        elif cmd == "input":
            ch = data["channel"]
            frame = build_read_input(device_selected, ch)

            ser.reset_input_buffer()
            ser.write(frame)
            time.sleep(0.1)
            resp = ser.read(256)

            publish_json({
                "cmd": cmd,
                "input": ch,
                "state": "on" if resp and resp[4] == 1 else "off",
                "raw": hexdump(resp)
            })

        # ---------------- status ----------------
        elif cmd == "status":
            target = data["target"]
            states = []

            for i in range(1, 9):
                frame = (
                    build_read_input(device_selected, i)
                    if target == "inputs"
                    else build_read_output(device_selected, i)
                )

                ser.reset_input_buffer()
                ser.write(frame)
                time.sleep(0.1)
                resp = ser.read(256)

                states.append({
                    "channel": i,
                    "state": "on" if resp and resp[4] == 1 else "off"
                })

            publish_json({
                "cmd": cmd,
                "target": target,
                "states": states
            })

        else:
            publish_json({
                "result": "error",
                "message": "Unknown command"
            })

    except Exception as e:
        publish_json({
            "result": "error",
            "message": str(e)
        })

# -------------------
# MQTT CALLBACKS
# -------------------
def on_connect(client, userdata, flags, reason_code, properties):
    print("MQTT connected:", reason_code)
    client.subscribe("george/test/board/cmd")
    publish_json({"status": "online"})

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
    except json.JSONDecodeError:
        publish_json({"error": "Invalid JSON"})
        return

    process_command(data)

# -------------------
# MAIN
# -------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--device", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=0.1)
    args = parser.parse_args()

    global ser
    global device_selected
    global client

    device_selected = args.device

    try:
        ser = serial.Serial(
            port=args.port,
            baudrate=args.baud,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=args.timeout
        )
    except Exception as e:
        print("Serial error:", e)
        sys.exit(1)

    client = mqtt.Client(
        client_id="modbus-json-bridge",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect("yurir.org", 1883, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()
