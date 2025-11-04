#!/usr/bin/env python3
import sys
import os
from pymodbus.client import ModbusTcpClient

MODBUS_MAP = {
    "inspection_id": 127,
    "photo_step_done": 128,
    "results_version": 129,
    "c1_recorrect": 130,
    "c2_recorrect": 131,
    "c3_recorrect": 132,
    "c4_recorrect": 133,
    "mm_received_instruction": 134,
    "photo_ready_step": 135,
}


def main():
    ur3_ip = os.getenv("UR3_IP", "130.130.130.86")
    ur3_port = int(os.getenv("UR3_MODBUS_PORT", "502"))
    
    print(f"Connecting to UR3 at {ur3_ip}:{ur3_port}...")
    client = ModbusTcpClient(host=ur3_ip, port=ur3_port, timeout=3)
    
    if not client.connect():
        print("ERROR: Failed to connect")
        return
    
    print("Connected!")
    print()
    
    try:
        while (1):
            # Step 1
            print("=" * 60)
            print("STEP 1: Writing photo_step_done = 1")
            print("=" * 60)
            result = client.write_register(MODBUS_MAP["photo_step_done"], 1)
            if result.isError():
                print(f"ERROR: {result}")
            else:
                print("SUCCESS: photo_step_done = 1")
            
            # Read back
            result = client.read_holding_registers(MODBUS_MAP["photo_step_done"], 1)
            if not result.isError():
                print(f"Verified: photo_step_done = {result.registers[0]}")
            
            input("\nPress ENTER to continue...")
            print()
            
            # Step 2
            print("=" * 60)
            print("STEP 2: Writing photo_step_done = 2")
            print("=" * 60)
            result = client.write_register(MODBUS_MAP["photo_step_done"], 2)
            if result.isError():
                print(f"ERROR: {result}")
            else:
                print("SUCCESS: photo_step_done = 2")
            
            # Read back
            result = client.read_holding_registers(MODBUS_MAP["photo_step_done"], 1)
            if not result.isError():
                print(f"Verified: photo_step_done = {result.registers[0]}")
            
            input("\nPress ENTER to continue...")
            print()
            
            # Step 3
            print("=" * 60)
            print("STEP 3: Writing photo_step_done = 0")
            print("=" * 60)
            result = client.write_register(MODBUS_MAP["photo_step_done"], 0)
            if result.isError():
                print(f"ERROR: {result}")
            else:
                print("SUCCESS: photo_step_done = 0")
            
            # Read back
            result = client.read_holding_registers(MODBUS_MAP["photo_step_done"], 1)
            if not result.isError():
                print(f"Verified: photo_step_done = {result.registers[0]}")
            
            input("\nPress ENTER to finish...")
            print()
            
            print("=" * 60)
            print("TEST COMPLETE")
            print("=" * 60)

            input("\nPress ENTER begin again...")
            print()
        
    finally:
        client.close()
        print("Connection closed")


if __name__ == "__main__":
    main()