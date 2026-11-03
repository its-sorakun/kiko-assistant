@echo off
nasm -f win64 input_injector.asm -o input_injector.obj
gcc input_injector.obj -o input_injector.exe
echo Build complete: input_injector.exe