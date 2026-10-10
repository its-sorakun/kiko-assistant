// hook.cpp - Native 64-bit WriteConsoleW interceptor for PowerShell error detection
// Implementation details:
// Intercepts console output within PowerShell by placing a 14-byte absolute jump at the entry
// of kernelbase.dll!WriteConsoleW. Targeting kernelbase.dll directly avoids 6-byte forwarder
// stub corruption present in kernel32.dll on modern 64-bit Windows.
// A CRITICAL_SECTION synchronizes concurrent console writers.
// Instruction caches are flushed via FlushInstructionCache on every hook transition.
// The hook is disabled only momentarily during the underlying WriteConsoleW invocation
// to minimize the window where unmodified code is exposed to other threads.
// Incoming text is accumulated in a rolling buffer to detect error signatures
// ("FullyQualifiedErrorId"). When matched, the error context is dispatched via UDP
// to the local companion daemon, and PowerShell execution pauses synchronously until
// the assistant response is received and rendered to the terminal.

#include <windows.h>
#include <iostream>
#include <string>
#include <fstream>

// Forward declaration
BOOL WINAPI HookedWriteConsoleW(HANDLE, const VOID*, DWORD, LPDWORD, LPVOID);

// Globals to store the original bytes of WriteConsoleW
BYTE originalBytes[14];
void* targetFunc = nullptr;

// Thread synchronization and rolling output buffer
static CRITICAL_SECTION hookLock;
static bool lockInitialized = false;
static std::wstring consoleBuffer;

// Enable/Disable hook functions
void EnableHook() {
    DWORD oldProtect;
    VirtualProtect(targetFunc, 14, PAGE_EXECUTE_READWRITE, &oldProtect);
    
    // 64-bit absolute jump: mov rax, HookedWriteConsoleW; jmp rax; nop; nop
    BYTE jump[14] = {
        0x48, 0xB8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0xFF, 0xE0,
        0x90, 0x90
    };
    
    void* hookFunc = (void*)HookedWriteConsoleW;
    memcpy(&jump[2], &hookFunc, 8);
    memcpy(targetFunc, jump, 14);
    
    VirtualProtect(targetFunc, 14, oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), targetFunc, 14);
}

void DisableHook() {
    DWORD oldProtect;
    VirtualProtect(targetFunc, 14, PAGE_EXECUTE_READWRITE, &oldProtect);
    memcpy(targetFunc, originalBytes, 14);
    VirtualProtect(targetFunc, 14, oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), targetFunc, 14);
}

// Momentarily calls the original API while synchronized
inline BOOL CallRealWriteConsoleW(
    HANDLE  hConsoleOutput,
    const VOID    *lpBuffer,
    DWORD   nNumberOfCharsToWrite,
    LPDWORD lpNumberOfCharsWritten,
    LPVOID  lpReserved
) {
    DisableHook();
    BOOL res = WriteConsoleW(hConsoleOutput, lpBuffer, nNumberOfCharsToWrite, lpNumberOfCharsWritten, lpReserved);
    EnableHook();
    return res;
}

// UDP setup
SOCKET udpSocket;
sockaddr_in serverAddr;

// Read .kiko_port to know where to shoot UDP packets
int GetKikoPort() {
    std::ifstream infile("D:\\codih\\assistant\\.kiko_port");
    int port = 5555;
    if (infile.good()) {
        infile >> port;
    }
    return port;
}

void SetupUDP() {
    WSADATA wsaData;
    WSAStartup(MAKEWORD(2, 2), &wsaData);
    udpSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    
    // Set a 7-second timeout for reading so PowerShell does not freeze indefinitely if Kiko is down
    DWORD timeout = 7000;
    setsockopt(udpSocket, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeout, sizeof(timeout));

    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(GetKikoPort());
    serverAddr.sin_addr.s_addr = inet_addr("127.0.0.1");
}

void BlastUDP(const std::string& msg) {
    serverAddr.sin_port = htons(GetKikoPort());
    sendto(udpSocket, msg.c_str(), msg.length(), 0, (sockaddr*)&serverAddr, sizeof(serverAddr));
}

// Function to synchronously wait for Kiko and print response to terminal
void WaitForKikoAndPrint(HANDLE hConsoleOutput) {
    char buffer[8192];
    sockaddr_in from_addr;
    int from_len = sizeof(from_addr);
    
    int bytes = recvfrom(udpSocket, buffer, sizeof(buffer) - 1, 0, (sockaddr*)&from_addr, &from_len);
    if (bytes > 0) {
        buffer[bytes] = '\0';
        
        // Convert UTF-8 response to UTF-16
        int wLen = MultiByteToWideChar(CP_UTF8, 0, buffer, -1, NULL, 0);
        std::wstring wResponse(wLen, 0);
        MultiByteToWideChar(CP_UTF8, 0, buffer, -1, &wResponse[0], wLen);
        wResponse.resize(wLen - 1);

        // Highlight assistant message using 24-bit ANSI color sequences
        std::wstring finalOutput = L"\n\x1b[38;2;255;105;180m[Kiko]: " + wResponse + L"\x1b[0m\n";

        DWORD written;
        CallRealWriteConsoleW(hConsoleOutput, finalOutput.c_str(), finalOutput.length(), &written, NULL);
    }
}

// Hijacked WriteConsoleW implementation
BOOL WINAPI HookedWriteConsoleW(
    HANDLE  hConsoleOutput,
    const VOID    *lpBuffer,
    DWORD   nNumberOfCharsToWrite,
    LPDWORD lpNumberOfCharsWritten,
    LPVOID  lpReserved
) {
    if (!lockInitialized) return FALSE;

    EnterCriticalSection(&hookLock);
    BOOL result = FALSE;

    try {
        if (lpBuffer != nullptr && nNumberOfCharsToWrite > 0 && nNumberOfCharsToWrite < 1000000) {
            std::wstring chunk((LPCWCH)lpBuffer, nNumberOfCharsToWrite);
            consoleBuffer += chunk;

            // Maintain rolling buffer context
            if (consoleBuffer.length() > 4096) {
                consoleBuffer = consoleBuffer.substr(consoleBuffer.length() - 4096);
            }

            // Inspect chunk for PowerShell error signature
            bool isErrorTriggered = false;
            if (chunk.find(L"FullyQualifiedErrorId") != std::wstring::npos) {
                isErrorTriggered = true;
                
                int utf8Len = WideCharToMultiByte(CP_UTF8, 0, consoleBuffer.c_str(), consoleBuffer.length(), NULL, 0, NULL, NULL);
                if (utf8Len > 0) {
                    std::string utf8Str(utf8Len, 0);
                    WideCharToMultiByte(CP_UTF8, 0, consoleBuffer.c_str(), consoleBuffer.length(), &utf8Str[0], utf8Len, NULL, NULL);
                    BlastUDP(utf8Str);
                }
                consoleBuffer.clear();
            }

            // Call the real function to display error output first
            result = CallRealWriteConsoleW(hConsoleOutput, lpBuffer, nNumberOfCharsToWrite, lpNumberOfCharsWritten, lpReserved);

            // If an error was triggered, pause PowerShell and wait for assistant response
            if (isErrorTriggered) {
                WaitForKikoAndPrint(hConsoleOutput);
            }
        } else {
            result = CallRealWriteConsoleW(hConsoleOutput, lpBuffer, nNumberOfCharsToWrite, lpNumberOfCharsWritten, lpReserved);
        }
    } catch (...) {
        // Failsafe in case of invalid memory pointers
        result = CallRealWriteConsoleW(hConsoleOutput, lpBuffer, nNumberOfCharsToWrite, lpNumberOfCharsWritten, lpReserved);
    }

    LeaveCriticalSection(&hookLock);
    return result;
}

// DLL Entry Point
BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved) {
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        
        InitializeCriticalSection(&hookLock);
        lockInitialized = true;
        
        SetupUDP();
        
        // Target kernelbase.dll directly to avoid 6-byte thunk corruption in kernel32.dll
        HMODULE hKernelBase = GetModuleHandleW(L"kernelbase.dll");
        targetFunc = (void*)GetProcAddress(hKernelBase, "WriteConsoleW");
        
        if (targetFunc != nullptr) {
            memcpy(originalBytes, targetFunc, 14);
            EnableHook();
        }
    }
    return TRUE;
}
