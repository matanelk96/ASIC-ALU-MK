import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles
import random

# ==========================================
# 1. Golden Model: Hardware Emulation in Python
# ==========================================
def expected_alu(op, a, b):
    """
    This function calculates the expected result exactly as our Verilog hardware should.
    It acts as the "source of truth" for the automated tests.
    """
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
    
    # Mask to 9 bits to simulate the internal 9-bit register (alu_result[8:0])
    res = res & 0x1FF 
    
    result_8bit = res & 0xFF     # The lower 8 bits (Calculation Result)
    carry_bit = (res >> 8) & 1   # The 9th bit (Carry/Overflow Flag)
    
    return result_8bit, carry_bit

# ==========================================
# 2. Helper Functions for Pin Management
# ==========================================
def set_control(dut, load_a=0, load_b=0, opcode=0, out_sel=0, reset=0):
    """
    Builds the 8-bit control byte (uio_in) exactly according to our hardware pin mapping.
    """
    ctrl = (reset << 7) | (out_sel << 6) | (opcode << 2) | (load_b << 1) | load_a
    dut.uio_in.value = ctrl

async def load_registers(dut, a_val, b_val):
    """
    Loads data into internal registers A and B by generating clock pulses.
    """
    # Load Register A
    dut.ui_in.value = a_val
    set_control(dut, load_a=1)
    await ClockCycles(dut.clk, 1)
    set_control(dut, load_a=0) # Drop the pulse
    
    # Load Register B
    dut.ui_in.value = b_val
    set_control(dut, load_b=1)
    await ClockCycles(dut.clk, 1)
    set_control(dut, load_b=0)

# ==========================================
# 3. Main Comprehensive Testbench
# ==========================================
@cocotb.test()
async def test_alu_comprehensive(dut):
    dut._log.info("🚀 Starting Comprehensive ALU Testbench...")

    # Start a 10MHz background clock
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # --- Initialization & Reset ---
    dut._log.info("Resetting the chip...")
    dut.ena.value = 1
    dut.ui_in.value = 0
    set_control(dut, reset=0) 
    dut.rst_n.value = 0 # Press physical hardware reset button (Active Low)
    await ClockCycles(dut.clk, 2)
    dut.rst_n.value = 1 # Release reset
    await ClockCycles(dut.clk, 2)

    # --- Generate Test Vectors ---
    # For each opcode, we test: hard edge cases + 20 fully random numbers
    edge_cases = [(0,0), (255,255), (0, 255), (255, 0), (1, 255), (128, 128), (170, 85)]
    random_cases = [(random.randint(0, 255), random.randint(0, 255)) for _ in range(20)]
    all_test_cases = edge_cases + random_cases

    opcodes_names = {
        0x0: "AND", 0x1: "OR", 0x2: "ADD", 0x3: "SUB",
        0x4: "XOR", 0x5: "NAND", 0x6: "NOR", 0x7: "SHL",
        0x8: "SHR", 0x9: "NOT A", 0xA: "NEG A"
    }

    # --- Main Testing Loop ---
    for opcode in range(11): # Iterate through all valid Opcodes (0x0 to 0xA)
        op_name = opcodes_names[opcode]
        dut._log.info(f"--- Testing Opcode: 0x{opcode:X} ({op_name}) ---")
        
        for a, b in all_test_cases:
            # 1. Load values into the DUT (Device Under Test)
            await load_registers(dut, a, b)
            
            # 2. Calculate expected values using the Python Golden Model
            exp_result, exp_carry = expected_alu(opcode, a, b)
            
            # 3. Request the result from hardware (Out_Sel = 0)
            set_control(dut, opcode=opcode, out_sel=0)
            await ClockCycles(dut.clk, 1) # Wait for combinational logic to settle
            
            hw_result = int(dut.uo_out.value)
            
            # Verification - if wrong, the test fails and stops immediately!
            assert hw_result == exp_result, \
                f"❌ ERROR in {op_name}: A={a}, B={b}. Expected Result={exp_result}, Got={hw_result}"

            # 4. Request the Carry/Flags from hardware (Out_Sel = 1)
            set_control(dut, opcode=opcode, out_sel=1)
            await ClockCycles(dut.clk, 1)
            
            # The first bit is the carry, the other 7 bits must be padded with 0
            hw_carry = int(dut.uo_out.value) & 1
            hw_padding = int(dut.uo_out.value) >> 1
            
            assert hw_padding == 0, \
                f"❌ ERROR in {op_name}: Out_Sel=1 Padding is not zero! Got: {int(dut.uo_out.value)}"
            
            assert hw_carry == exp_carry, \
                f"❌ ERROR in {op_name}: A={a}, B={b}. Expected Carry={exp_carry}, Got={hw_carry}"

    dut._log.info("✅ ALL TESTS PASSED SUCCESSFULLY! The ALU is bulletproof.")
