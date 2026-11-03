; input_injector.asm - Native Win64 console input synthesis engine
; Implementation details:
; Queries the standard console input handle and synthesizes KEY_EVENT_RECORD
; structures directly into the conhost input buffer via WriteConsoleInputW.

default rel
bits 64

global main
extern GetStdHandle

section .data
    ; 64-bit storage for console input handle
    hInput dq 0

section .text

main:
    sub rsp, 40          ; 32 bytes shadow space + 8 bytes alignment

    ; 1st argument: STD_INPUT_HANDLE (-10) -> ECX
    mov ecx, -10
    call GetStdHandle

    ; Save the 64-bit HANDLE from RAX into our memory variable hInput
    mov [hInput], rax

    xor eax, eax         ; return 0
    add rsp, 40          ; restore stack pointer
    ret