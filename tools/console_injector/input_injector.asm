; input_injector.asm - Native Win64 console input synthesis engine

extern printf
extern GetStdHandle
default rel
bits 64

global main

section .data
    hInput dq 0
    fmt    db "Console Input Handle: %p", 10, 0

section .text

main:
    sub rsp, 40          ; 32 bytes shadow space + 8 bytes alignment

    ; 1. Ask Windows for the console input handle
    mov ecx, -10
    call GetStdHandle

    ; 2. Save the handle into memory
    mov [hInput], rax

    ; 3. Print the handle!
    lea rcx, [fmt]       ; 1st arg: format string -> RCX
    mov rdx, rax         ; 2nd arg: handle value from RAX -> RDX
    call printf          ; call C runtime printf(rcx, rdx)

    ; 4. Exit cleanly
    xor eax, eax         ; return 0
    add rsp, 40          ; restore stack pointer
    ret