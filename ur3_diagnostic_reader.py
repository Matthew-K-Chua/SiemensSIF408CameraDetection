#!/usr/bin/env python3
"""
UR3 Complete Diagnostic Reader - READ-ONLY

Displays contents of:
- Holding registers 0-127 (system) and 128-255 (general purpose)
- Coils 0-127 (standard outputs) and 128-255 (general purpose)

Does NOT write anything - completely safe for diagnostic use.

Usage:
    export UR3_IP="130.130.130.86"
    
    # Read everything
    python ur3_diagnostic_reader.py --all
    
    # Read only system registers (0-127)
    python ur3_diagnostic_reader.py --system
    
    # Read only general purpose registers (128-255)
    python ur3_diagnostic_reader.py --gp
    
    # Read coils too
    python ur3_diagnostic_reader.py --all --coils
"""

import sys
import os
import argparse

try:
    from pymodbus.client import ModbusTcpClient
except ImportError:
    print("ERROR: pymodbus not installed")
    print("Install with: pip install pymodbus --break-system-packages")
    sys.exit(1)


def format_value(value):
    """Format value showing decimal and hex"""
    if value is None:
        return "ERROR".ljust(20)
    return f"{value:5d} (0x{value:04X})".ljust(20)


def read_registers(client, start_addr, count, chunk_size=32):
    """
    Read holding registers in chunks.
    Returns list of values (or None for failed reads).
    """
    all_values = []
    
    for chunk_start in range(start_addr, start_addr + count, chunk_size):
        chunk_count = min(chunk_size, start_addr + count - chunk_start)
        try:
            result = client.read_holding_registers(address=chunk_start, count=chunk_count)
            if result.isError():
                print(f"  ⚠ Failed to read registers {chunk_start}-{chunk_start+chunk_count-1}")
                all_values.extend([None] * chunk_count)
            else:
                all_values.extend(result.registers)
        except Exception as e:
            print(f"  ⚠ Exception reading registers {chunk_start}-{chunk_start+chunk_count-1}: {e}")
            all_values.extend([None] * chunk_count)
    
    return all_values


def read_coils(client, start_addr, count, chunk_size=32):
    """
    Read coils in chunks.
    Returns list of boolean values (or None for failed reads).
    """
    all_values = []
    
    for chunk_start in range(start_addr, start_addr + count, chunk_size):
        chunk_count = min(chunk_size, start_addr + count - chunk_start)
        try:
            result = client.read_coils(address=chunk_start, count=chunk_count)
            if result.isError():
                print(f"  ⚠ Failed to read coils {chunk_start}-{chunk_start+chunk_count-1}")
                all_values.extend([None] * chunk_count)
            else:
                all_values.extend(result.bits[:chunk_count])
        except Exception as e:
            print(f"  ⚠ Exception reading coils {chunk_start}-{chunk_start+chunk_count-1}: {e}")
            all_values.extend([None] * chunk_count)
    
    return all_values


def display_registers(values, start_addr, title):
    """Display register values in a formatted table"""
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)
    print()
    print(f"Register Range: {start_addr} - {start_addr + len(values) - 1}")
    print()
    print("Register | Value               | Status")
    print("-" * 80)
    
    non_zero = []
    
    for i, value in enumerate(values):
        reg_num = start_addr + i
        status = ""
        
        if value is None:
            status = "READ ERROR"
        elif value != 0:
            non_zero.append((reg_num, value))
            status = "◀ NON-ZERO"
        else:
            status = "Zero"
        
        print(f"{reg_num:8d} | {format_value(value)} | {status}")
        
        # Spacing every 16 registers
        if (i + 1) % 16 == 0 and i < len(values) - 1:
            print()
    
    print()
    print(f"Summary: {len(non_zero)} non-zero values out of {len(values)} registers")
    
    if non_zero:
        print()
        print("Non-zero registers:")
        for reg, val in non_zero:
            print(f"  Register {reg}: {val} (0x{val:04X})")
    
    return non_zero


def display_coils(values, start_addr, title):
    """Display coil values in a formatted table"""
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)
    print()
    print(f"Coil Range: {start_addr} - {start_addr + len(values) - 1}")
    print()
    print("Coil     | Value | Status")
    print("-" * 80)
    
    true_coils = []
    
    for i, value in enumerate(values):
        coil_num = start_addr + i
        
        if value is None:
            status = "READ ERROR"
            display_val = "ERROR"
        elif value:
            true_coils.append(coil_num)
            status = "◀ TRUE"
            display_val = "TRUE "
        else:
            status = "False"
            display_val = "FALSE"
        
        print(f"{coil_num:8d} | {display_val} | {status}")
        
        # Spacing every 16 coils
        if (i + 1) % 16 == 0 and i < len(values) - 1:
            print()
    
    print()
    print(f"Summary: {len(true_coils)} TRUE coils out of {len(values)}")
    
    if true_coils:
        print()
        print("TRUE coils:")
        for coil in true_coils:
            print(f"  Coil {coil}")
    
    return true_coils


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="UR3 Modbus Diagnostic Reader (READ-ONLY)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--system", action="store_true",
                      help="Read system registers (0-127)")
    parser.add_argument("--gp", action="store_true",
                      help="Read general purpose registers (128-255)")
    parser.add_argument("--all", action="store_true",
                      help="Read all registers (0-255)")
    parser.add_argument("--coils", action="store_true",
                      help="Also read coils (digital outputs)")
    
    args = parser.parse_args()
    
    # Default to system only if nothing specified
    if not (args.system or args.gp or args.all):
        args.system = True
    
    # Get UR3 IP from environment
    ur3_ip = os.getenv("UR3_IP", "130.130.130.86")
    ur3_port = int(os.getenv("UR3_MODBUS_PORT", "502"))
    
    print()
    print("=" * 80)
    print("UR3 MODBUS DIAGNOSTIC READER (READ-ONLY)")
    print("=" * 80)
    print(f"Target: {ur3_ip}:{ur3_port}")
    print("⚠ This script is READ-ONLY - it will NOT write anything to the UR3")
    print("=" * 80)
    print()
    
    # Create and connect client
    print("Connecting to UR3...")
    client = ModbusTcpClient(host=ur3_ip, port=ur3_port, timeout=5)
    
    if not client.connect():
        print("✗ FAILED: Cannot connect to UR3")
        print()
        print("Troubleshooting:")
        print("  1. Is the UR3 powered on?")
        print("  2. Is Modbus TCP server enabled?")
        print(f"  3. Can you ping {ur3_ip}?")
        print(f"  4. Try: export UR3_IP=\"{ur3_ip}\"")
        return False
    
    print("✓ Connected successfully")
    
    try:
        # Read system registers (0-127)
        if args.system or args.all:
            print("\nReading system registers 0-127...")
            system_regs = read_registers(client, 0, 128)
            display_registers(system_regs, 0, "SYSTEM REGISTERS (0-127) - UR3 Internal Use")
        
        # Read general purpose registers (128-255)
        if args.gp or args.all:
            print("\nReading general purpose registers 128-255...")
            gp_regs = read_registers(client, 128, 128)
            display_registers(gp_regs, 128, "GENERAL PURPOSE REGISTERS (128-255) - Safe for User")
        
        # Read coils if requested
        if args.coils:
            if args.system or args.all:
                print("\nReading system coils 0-127...")
                system_coils = read_coils(client, 0, 128)
                display_coils(system_coils, 0, "SYSTEM COILS (0-127) - Standard Digital Outputs")
            
            if args.gp or args.all:
                print("\nReading general purpose coils 128-255...")
                gp_coils = read_coils(client, 128, 128)
                display_coils(gp_coils, 128, "GENERAL PURPOSE COILS (128-255) - Safe for User")
        
        # Final recommendations
        print()
        print("=" * 80)
        print("RECOMMENDATIONS FOR YOUR CAMERA INSPECTION SYSTEM")
        print("=" * 80)
        print()
        print("✓ SAFE TO USE (General Purpose - Won't affect robot):")
        print("  • Holding Registers: 128-255")
        print("  • Coils: 128-255")
        print()
        print("✗ DO NOT USE (System - Contains robot data):")
        print("  • Holding Registers: 0-127")
        print("  • Coils: 0-7 (these are physical robot outputs)")
        print()
        print("For your application, use this mapping:")
        print("  inspection_id     → Register 128")
        print("  photo_step_done   → Register 129")
        print("  results_version   → Register 130")
        print("  c1_recorrect      → Coil 128")
        print("  c2_recorrect      → Coil 129")
        print("  c3_recorrect      → Coil 130")
        print("  c4_recorrect      → Coil 131")
        print()
        
    finally:
        client.close()
        print("Connection closed")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
