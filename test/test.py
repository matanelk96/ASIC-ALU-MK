# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles
import random

# ==========================================
# 1. Golden Model: Hardware Emulation in Python
# ==========================================
def expected_alu(op, a, b):
    if op == 0x0: res = a & b
    elif op == 0x1: res = a | b
    elif op == 0x2: res = a + b
    elif op == 0x3: res = a - b
    elif op == 0x4: res = a ^ b
    elif op == 0x5: res = ~(a & b)
    elif op == 0x6: res = ~(a | b)
    elif op == 0x7: res = a << 1
    elif op == 0x8: res = a >> 1
    elif op == 0x9: res = ~a
    elif op == 0xA: res = (~a & 0xFF) + 1  # 2's complement
    else: res = 0
    
    res = res & 0x1FF 
    result_8bit = res & 0xFF
    carry_bit = (res >> 8) & 1
    
    return result_8bit, carry_bit

# ==========================================
# 2. Helper Functions for Pin Management
# ==========================================
def set_control(dut, load_a=0, load_b=0, opcode=0, out_sel=0, reset=0):
    ctrl = (reset << 7) | (out_sel << 6) | (opcode << 2) | (load_b << 1) | load_a
    dut.uio_in.value = ctrl

async def load_registers(dut, a_val, b_val):
    # Load Register A
    dut.ui_in.value = a_val
    set_control(dut, load_a=1)
    await ClockCycles(dut.clk, 2) # Wait 2 cycles to ensure latching
    set_control(dut, load_a=0)
    await ClockCycles(dut.clk, 1) # Buffer cycle

    # Load Register B
    dut.ui_in.value = b_val
    set_control(dut, load_b=1)
    await ClockCycles(dut.clk, 2) # Wait 2 cycles
    set_control(dut, load_b=0)
    await ClockCycles(dut.clk, 1) # Buffer cycle

# ==========================================
# 3. Main Comprehensive Testbench
# ==========================================
@cocotb.test()
async def test_alu_comprehensive(dut):
    dut._log.info("🚀 Starting Comprehensive ALU Testbench...")

    # Start a 10MHz background clock (Fixed warning 'unit' instead of 'units')
    clock = Clock(dut.clk, 100, unit="ns")
    cocotb.start_soon(clock.start())

    # --- Initialization & Reset ---
    dut._log.info("Resetting the chip...")
    dut.ena.value = 1
    dut.ui_in.value = 0
    set_control(dut, reset=0) 
    dut.rst_n.value = 0 
    await ClockCycles(dut.clk, 3) # Generous reset time
    dut.rst_n.value = 1 
    await ClockCycles(dut.clk, 3)

    # --- Generate Test Vectors ---
    edge_cases = [(0,0), (255,255), (0, 255), (255, 0), (1, 255), (128, 128), (170, 85)]
    random_cases = [(random.randint(0, 255), random.randint(0, 255)) for _ in range(20)]
    all_test_cases = edge_cases + random_cases

    opcodes_names = {
        0x0: "AND", 0x1: "OR", 0x2: "ADD", 0x3: "SUB",
        0x4: "XOR", 0x5: "NAND", 0x6: "NOR", 0x7: "SHL",
        0x8: "SHR", 0x9: "NOT A", 0xA: "NEG A"
    }

    # --- Main Testing Loop ---
    for opcode in range(11):
        op_name = opcodes_names[opcode]
        dut._log.info(f"--- Testing Opcode: 0x{opcode:X} ({op_name}) ---")
        
        for a, b in all_test_cases:
            await load_registers(dut, a, b)
            
            exp_result, exp_carry = expected_alu(opcode, a, b)
            
            # Request the result from hardware
            set_control(dut, opcode=opcode, out_sel=0)
            await ClockCycles(dut.clk, 2) # Give combinational logic and registers time to settle
            
            hw_result = int(dut.uo_out.value)
            
            assert hw_result == exp_result, \
                f"❌ ERROR in {op_name}: A={a}, B={b}. Expected Result={exp_result}, Got={hw_result}"

            # Request the Flags
            set_control(dut, opcode=opcode, out_sel=1)
            await ClockCycles(dut.clk, 2)
            
            hw_carry = int(dut.uo_out.value) & 1
            hw_padding = int(dut.uo_out.value) >> 1
            
            assert hw_padding == 0, \
                f"❌ ERROR in {op_name}: Out_Sel=1 Padding is not zero! Got: {int(dut.uo_out.value)}"
            
            assert hw_carry == exp_carry, \
                f"❌ ERROR in {op_name}: A={a}, B={b}. Expected Carry={exp_carry}, Got={hw_carry}"

    dut._log.info("✅ ALL TESTS PASSED SUCCESSFULLY! The ALU is bulletproof.")
