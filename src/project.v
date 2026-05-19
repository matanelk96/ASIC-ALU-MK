/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */
`default_nettype none
`timescale 1ns / 1ps

module tt_um_alu (
    input  wire [7:0] ui_in,    // Dedicated inputs (Data Bus)
    output reg  [7:0] uo_out,   // Dedicated outputs (Result/Flags)
    input  wire [7:0] uio_in,   // Bidirectional IOs: Input path (Control Bus)
    output wire [7:0] uio_out,  // Bidirectional IOs: Output path (Not used)
    output wire [7:0] uio_oe,   // Bidirectional IOs: Enable path (0 = input, 1 = output)
    input  wire       ena,      // Always 1 when the design is powered (Not used)
    input  wire       clk,      // System clock
    input  wire       rst_n     // Tiny Tapeout general active-low hardware reset button
);

    // ==========================================
    // Tiny Tapeout Required Setup
    // ==========================================
    // Set all bidirectional pins to act as inputs (0)
    assign uio_oe  = 8'b00000000;
    
    // Ground the unused outputs to prevent electrical noise
    assign uio_out = 8'b00000000;

    // Prevent Verilator warnings for unused inputs (Only 'ena' is left unused)
    wire _unused = &{ena, 1'b0};

    // ==========================================
    // Control Bus Mapping & Reset Logic
    // ==========================================
    // Extracting control signals from the uio_in bus
    wire load_a       = uio_in[0];
    wire load_b       = uio_in[1];
    wire [3:0] alu_op = uio_in[5:2];
    wire out_sel      = uio_in[6];
    wire rpi_reset    = uio_in[7]; // Reset from Raspberry Pi script (Active-High)

    // GLOBAL RESET: Triggers if RPi sends '1' OR if physical board button is pressed ('rst_n' is '0')
    wire global_reset = rpi_reset | !rst_n;

    // ==========================================
    // Internal Registers
    // ==========================================
    reg [7:0] reg_a;
    reg [7:0] reg_b;

    // Register loading logic with full reset protection
    always @(posedge clk) begin
        if (global_reset) begin
            reg_a <= 8'b0;
            reg_b <= 8'b0;
        end else begin
            if (load_a) reg_a <= ui_in;
            if (load_b) reg_b <= ui_in;
        end
    end

    // ==========================================
    // ALU Core Logic
    // ==========================================
    reg [8:0] alu_result; 

    always @(*) begin
        case (alu_op)
            4'b0000: alu_result = {1'b0, reg_a & reg_b};      // AND
            4'b0001: alu_result = {1'b0, reg_a | reg_b};      // OR
            4'b0010: alu_result = reg_a + reg_b;              // ADD
            4'b0011: alu_result = reg_a - reg_b;              // SUB
            4'b0100: alu_result = {1'b0, reg_a ^ reg_b};      // XOR
            4'b0101: alu_result = {1'b0, ~(reg_a & reg_b)};   // NAND
            4'b0110: alu_result = {1'b0, ~(reg_a | reg_b)};   // NOR
            4'b0111: alu_result = {reg_a, 1'b0};              // SHL (Shift Left)
            4'b1000: alu_result = {1'b0, 1'b0, reg_a[7:1]};   // SHR (Shift Right)
            4'b1001: alu_result = {1'b0, ~reg_a};             // NOT A
            4'b1010: alu_result = {1'b0, ~reg_a} + 1'b1;      // NEG A (2's complement)
            default: alu_result = 9'b0;                       // Default
        endcase
    end

    // ==========================================
    // Output Multiplexer (Result vs. Flags)
    // ==========================================
    always @(posedge clk) begin
        if (global_reset) begin
            uo_out <= 8'b0;
        end else if (out_sel == 1'b0) begin
            uo_out <= alu_result[7:0]; 
        end else begin
            uo_out <= {7'b0, alu_result[8]}; 
        end
    end

endmodule
