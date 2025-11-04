#!/usr/bin/env python3
"""
UR3 Register Reader - READ-ONLY Diagnostic Tool

Displays the contents of UR3 Modbus holding registers 0-127.
Does NOT write anything - safe for diagnostic use.

Usage:
    export UR3_IP="130.130.130.86"
    python read_ur3_registers.py
"""

import sys
import os

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("ERROR: pymodbus not installed")
    print("Install with: pip install pymodbus --break-system-packages")
    sys.exit(1)


def format_register_value(value):
    """Format register value showing decimal, hex, and binary"""
    return f"{value:5d} (0x{value:04X})"


def read_ur3_registers():
    """Read and display UR3 registers 0-127 (READ-ONLY)"""
    
    # Get UR3 IP from environment or use default
    ur3_ip = os.getenv("UR3_IP", "130.130.130.86")
    ur3_port = int(os.getenv("UR3_MODBUS_PORT", "502"))
    
    print("=" * 80)
    print("UR3 MODBUS REGISTER READER (READ-ONLY)")
    print("=" * 80)
    print(f"Target: {ur3_ip}:{ur3_port}")
    print(f"Reading holding registers 0-127 (UR3 system registers)")
    print("⚠ This script is READ-ONLY - it will NOT write anything to the UR3")
    print("=" * 80)
    print()
    
    # Create client
    print("Creating Modbus TCP client...")
    client = ModbusTcpClient(
        host=ur3_ip,
        port=ur3_port,
        timeout=3
    )
    
    # Test connection
    print(f"Connecting to {ur3_ip}:{ur3_port}...")
    if not client.connect():
        print("✗ FAILED: Cannot connect to UR3")
        print()
        print("Troubleshooting:")
        print("  1. Is the UR3 powered on?")
        print("  2. Is Modbus TCP server enabled on UR3?")
        print("     (Settings → System → Network → Modbus TCP)")
        print("  3. Can you ping the UR3?")
        print(f"     Try: ping {ur3_ip}")
        print("  4. Is the IP address correct?")
        print(f"     Set with: export UR3_IP=\"{ur3_ip}\"")
        return False
    
    print("✓ Connected successfully")
    print()
    
    # Read all registers 0-127 in chunks
    # We'll read in blocks of 32 to avoid timeouts
    chunk_size = 32
    all_registers = []
    
    print("Reading registers in chunks...")
    for start_addr in range(0, 128, chunk_size):
        count = min(chunk_size, 128 - start_addr)
        try:
            result = client.read_holding_registers(address=start_addr, count=count)
            if result.isError():
                print(f"✗ Failed to read registers {start_addr}-{start_addr+count-1}: {result}")
                all_registers.extend([None] * count)
            else:
                all_registers.extend(result.registers)
                print(f"✓ Read registers {start_addr:3d}-{start_addr+count-1:3d}")
        except Exception as e:
            print(f"✗ Exception reading registers {start_addr}-{start_addr+count-1}: {e}")
            all_registers.extend([None] * count)
    
    print()
    print("=" * 80)
    print("REGISTER CONTENTS (0-127)")
    print("=" * 80)
    print()
    
    # Display all registers
    print("Format: Register# | Value (Decimal) | Value (Hex)")
    print("-" * 80)
    
    # Track non-zero registers for summary
    non_zero_registers = []
    
    for i, value in enumerate(all_registers):
        if value is None:
            print(f"Register {i:3d} | ERROR - Could not read")
        else:
            status = ""
            if value != 0:
                non_zero_registers.append((i, value))
                status = " ◀ NON-ZERO"
            
            print(f"Register {i:3d} | {format_register_value(value)}{status}")
        
        # Add spacing every 16 registers for readability
        if (i + 1) % 16 == 0 and i < 127:
            print()
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    if non_zero_registers:
        print(f"Found {len(non_zero_registers)} non-zero registers:")
        print()
        print("Register | Value (Dec) | Value (Hex) | Typical UR3 Usage")
        print("-" * 80)
        
        # Provide context for common UR registers
        ur_register_info = {
            range(0, 6): "Joint positions/velocities",
            range(6, 12): "Tool pose (X, Y, Z, Rx, Ry, Rz)",
            range(18, 24): "Joint currents",
            range(24, 30): "Joint voltages",
            range(30, 42): "TCP force/torque",
            range(42, 48): "Digital inputs/outputs status",
        }
        
        for reg, value in non_zero_registers:
            context = "General purpose / User data"
            for reg_range, description in ur_register_info.items():
                if reg in reg_range:
                    context = description
                    break
            
            print(f"{reg:8d} | {value:11d} | 0x{value:08X} | {context}")
    else:
        print("All registers are zero (or could not be read).")
        print("This may indicate:")
        print("  - Robot is not powered on fully")
        print("  - Registers not initialized yet")
        print("  - All values happen to be zero")
    
    print()
    print("=" * 80)
    print("SAFE REGISTERS FOR YOUR APPLICATION")
    print("=" * 80)
    print()
    print("For your camera inspection system, USE THESE REGISTERS:")
    print()
    print("  Holding Registers (integers): 128-255")
    print("    - These are general purpose registers")
    print("    - Safe to read/write without affecting robot")
    print("    - Example: inspection_id = register 128")
    print()
    print("  Coils (booleans): 128-255")
    print("    - General purpose digital outputs")
    print("    - Safe to read/write")
    print("    - Example: c1_recorrect = coil 128")
    print()
    print("⚠ DO NOT USE REGISTERS 0-127 for your application!")
    print("  These contain robot system data and may change constantly.")
    print()
    
    # Clean up
    print("Closing connection...")
    client.close()
    print("✓ Connection closed")
    print()
    
    return True


def main():
    """Main entry point"""
    try:
        success = read_ur3_registers()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nRead interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
