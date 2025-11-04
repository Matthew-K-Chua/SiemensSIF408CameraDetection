#!/usr/bin/env python3
"""
Modbus TCP Server for UR3
Exposes holding register 129 as 'mm_pht_stp_done' (Register Input on UR).
Tested with pymodbus 3.6.9.
"""

from pymodbus.server import StartTcpServer
from pymodbus.datastore import (
    ModbusSlaveContext,
    ModbusServerContext,
    ModbusSequentialDataBlock,
)
import threading

# ----------------------------------------------------------------------
# Addresses from your UR pendant
MM_PHT_STP_DONE_ADDR = 129  # mm_pht_stp_done
# ----------------------------------------------------------------------

# Create data store (200 registers to cover 0..199)
store = ModbusSlaveContext(
    hr=ModbusSequentialDataBlock(0, [0] * 200),
    di=ModbusSequentialDataBlock(0, [0] * 200),
    co=ModbusSequentialDataBlock(0, [0] * 200),
    ir=ModbusSequentialDataBlock(0, [0] * 200),
)
context = ModbusServerContext(slaves=store, single=True)

# --- Helper functions -------------------------------------------------
def set_mm_pht_stp_done(value: int):
    """Write to holding register 129 so UR3 can read it."""
    slave_id = 0x00
    context[slave_id].setValues(4, MM_PHT_STP_DONE_ADDR, [value])

def get_mm_pht_stp_done() -> int:
    """Read current value of holding register 129."""
    slave_id = 0x00
    return context[slave_id].getValues(4, MM_PHT_STP_DONE_ADDR, count=1)[0]

# ----------------------------------------------------------------------

def console_loop():
    """Simple console for manual testing."""
    while True:
        current = get_mm_pht_stp_done()
        print(f"[SERVER] mm_pht_stp_done (addr 129) currently = {current}")
        try:
            new_val = input("Enter new value (blank to skip): ").strip()
        except EOFError:
            break
        if new_val:
            try:
                val = int(new_val)
                set_mm_pht_stp_done(val)
                print(f"[SERVER] wrote {val} to register 129\n")
            except ValueError:
                print("Please enter an integer.\n")
        else:
            print()

# ----------------------------------------------------------------------

if __name__ == "__main__":
    # Run interactive console in background
    threading.Thread(target=console_loop, daemon=True).start()

    # Start Modbus TCP server
    # Note: Port 502 requires sudo on macOS/Linux; use 1502 if you prefer not to.
    StartTcpServer(context=context, address=("0.0.0.0", 502))

