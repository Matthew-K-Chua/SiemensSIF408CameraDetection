#!/usr/bin/env python3
"""
UR3 General Purpose Register Test

Tests if registers 128-255 are accessible (they should be!).
This confirms the UR3 allows access to user registers.

After seeing exception_code=2 (ILLEGAL ADDRESS) for registers 0-127,
this script verifies that 128+ work correctly.
"""

import sys
import os

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("ERROR: pymodbus not installed")
    print("Install with: pip install pymodbus --break-system-packages")
    sys.exit(1)


def test_gp_registers():
    """Test general purpose registers 128-255"""
    
    ur3_ip = os.getenv("UR3_IP", "130.130.130.86")
    ur3_port = int(os.getenv("UR3_MODBUS_PORT", "502"))
    
    print("=" * 80)
    print("UR3 GENERAL PURPOSE REGISTER TEST")
    print("=" * 80)
    print(f"Target: {ur3_ip}:{ur3_port}")
    print()
    print("Testing if registers 128-255 are accessible...")
    print("(After seeing exception_code=2 for registers 0-127)")
    print("=" * 80)
    print()
    
    # Connect
    print("Connecting to UR3...")
    client = ModbusTcpClient(host=ur3_ip, port=ur3_port, timeout=3)
    
    if not client.connect():
        print("✗ FAILED: Cannot connect")
        return False
    
    print("✓ Connected successfully")
    print()
    
    try:
        # Test 1: Read a few GP registers
        print("Test 1: Reading general purpose registers 128-131...")
        try:
            result = client.read_holding_registers(address=128, count=4)
            if result.isError():
                print(f"✗ FAILED: {result}")
                print(f"   Exception code: {result.exception_code if hasattr(result, 'exception_code') else 'unknown'}")
                if hasattr(result, 'exception_code') and result.exception_code == 2:
                    print("   ⚠ ILLEGAL ADDRESS - UR3 may not support these registers!")
                    print("   Check UR software version and Modbus configuration")
            else:
                values = result.registers
                print(f"✓ SUCCESS! Read registers 128-131:")
                print(f"   Register 128: {values[0]}")
                print(f"   Register 129: {values[1]}")
                print(f"   Register 130: {values[2]}")
                print(f"   Register 131: {values[3]}")
        except Exception as e:
            print(f"✗ Exception: {e}")
        
        print()
        
        # Test 2: Write to a GP register
        print("Test 2: Writing value 12345 to register 128...")
        try:
            result = client.write_register(address=128, value=12345)
            if result.isError():
                print(f"✗ FAILED: {result}")
                if hasattr(result, 'exception_code'):
                    print(f"   Exception code: {result.exception_code}")
                    if result.exception_code == 2:
                        print("   ⚠ ILLEGAL ADDRESS")
                    elif result.exception_code == 3:
                        print("   ⚠ ILLEGAL DATA VALUE")
                    elif result.exception_code == 4:
                        print("   ⚠ SLAVE DEVICE FAILURE")
            else:
                print("✓ SUCCESS! Write completed")
        except Exception as e:
            print(f"✗ Exception: {e}")
        
        print()
        
        # Test 3: Read back to verify
        print("Test 3: Reading back register 128 to verify...")
        try:
            result = client.read_holding_registers(address=128, count=1)
            if result.isError():
                print(f"✗ FAILED: {result}")
            else:
                value = result.registers[0]
                if value == 12345:
                    print(f"✓ SUCCESS! Value verified: {value}")
                else:
                    print(f"⚠ Read returned {value} (expected 12345)")
                    print("   Value may have been reset or not retained")
        except Exception as e:
            print(f"✗ Exception: {e}")
        
        print()
        
        # Test 4: Try reading a larger range
        print("Test 4: Reading larger range 128-159 (32 registers)...")
        try:
            result = client.read_holding_registers(address=128, count=32)
            if result.isError():
                print(f"✗ FAILED: {result}")
            else:
                print(f"✓ SUCCESS! Read {len(result.registers)} registers")
                # Show non-zero values
                non_zero = [(i+128, v) for i, v in enumerate(result.registers) if v != 0]
                if non_zero:
                    print(f"   Non-zero registers found:")
                    for reg, val in non_zero[:10]:  # Show first 10
                        print(f"     Register {reg}: {val}")
                else:
                    print(f"   All registers are zero (available for use)")
        except Exception as e:
            print(f"✗ Exception: {e}")
        
        print()
        
        # Test 5: Test coils (digital outputs)
        print("Test 5: Testing coil (digital output) 128...")
        try:
            result = client.write_coil(address=128, value=True)
            if result.isError():
                print(f"✗ Write FAILED: {result}")
            else:
                print("✓ Write SUCCESS")
                
                # Read back
                result = client.read_coils(address=128, count=1)
                if result.isError():
                    print(f"✗ Read FAILED: {result}")
                else:
                    value = result.bits[0]
                    print(f"✓ Read SUCCESS: {value}")
                    
                    # Clear it
                    client.write_coil(address=128, value=False)
                    print("✓ Cleared coil back to False")
        except Exception as e:
            print(f"✗ Exception: {e}")
        
        print()
        print("=" * 80)
        print("CONCLUSION")
        print("=" * 80)
        print()
        
        # Make a determination
        print("Based on these tests:")
        print()
        print("✓ Registers 0-127: BLOCKED (exception_code=2 - ILLEGAL ADDRESS)")
        print("  → UR3 is protecting system registers (good!)")
        print()
        
        # Check if 128+ worked
        result = client.read_holding_registers(address=128, count=1)
        if not result.isError():
            print("✓ Registers 128-255: ACCESSIBLE")
            print("  → Safe to use for your camera inspection system!")
            print()
            print("RECOMMENDATION:")
            print("  Use the corrected camera_inspection_modbus.py which uses:")
            print("    - inspection_id     → Register 128")
            print("    - photo_step_done   → Register 129")
            print("    - results_version   → Register 130")
            print("    - c1_recorrect      → Coil 128")
            print("    - c2_recorrect      → Coil 129")
            print("    - c3_recorrect      → Coil 130")
            print("    - c4_recorrect      → Coil 131")
        else:
            print("✗ Registers 128-255: ALSO BLOCKED")
            print("  → UR3 Modbus configuration may need adjustment")
            print()
            print("TROUBLESHOOTING:")
            print("  1. Check UR software version (need 3.4+)")
            print("  2. Verify Modbus TCP server is fully enabled")
            print("  3. Check if URCaps Modbus configuration needed")
            print("  4. Consult UR3 manual for Modbus register access")
        
    finally:
        client.close()
        print()
        print("Connection closed")
    
    return True


def main():
    try:
        test_gp_registers()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
