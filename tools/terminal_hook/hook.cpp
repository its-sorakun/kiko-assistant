// hook.cpp - Native 64-bit absolute jump hook for WriteConsoleW
#include <windows.h>
#include <iostream>
#include <string>
#include <fstream>
#include <thread>

// Forward declaration
BOOL WINAPI HookedWriteConsoleW(HANDLE, const VOID*, DWORD, LPDWORD, LPVOID);

// Globals to store the original bytes of WriteConsoleW
BYTE originalBytes[14];
void* targetFunc = nullptr;

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
    
    // Set a 7-second timeout for reading so PowerShell doesn't freeze forever if Kiko is down
    DWORD timeout = 7000;
    setsockopt(udpSocket, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeout, sizeof(timeout));

    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(GetKikoPort());
    serverAddr.sin_addr.s_addr = inet_addr("127.0.0.1");
}

void BlastUDP(const std::string& msg) {
    sendto(udpSocket, msg.c_str(), msg.length(), 0, (sockaddr*)&serverAddr, sizeof(serverAddr));
}

// Function to synchronously wait for Kiko and print it perfectly
void WaitForKikoAndPrint(HANDLE hConsoleOutput) {
    char buffer[8192];
    sockaddr_in from_addr;
    int from_len = sizeof(from_addr);
    
    int bytes = recvfrom(udpSocket, buffer, sizeof(buffer) - 1, 0, (sockaddr*)&from_addr, &from_len);
    if (bytes > 0) {
        buffer[bytes] = '\0';
        
        // Convert Kiko's UTF-8 response to WideString (UTF-16) so emojis and kanji work flawlessly!
        int wLen = MultiByteToWideChar(CP_UTF8, 0, buffer, -1, NULL, 0);
        std::wstring wResponse(wLen, 0);
        MultiByteToWideChar(CP_UTF8, 0, buffer, -1, &wResponse[0], wLen);
        wResponse.resize(wLen - 1);

        // Make it pink using VT sequences
        std::wstring finalOutput = L"\n\x1b[38;2;255;105;180m[Kiko]: " + wResponse + L"\x1b[0m\n";

        DWORD written;
        WriteConsoleW(hConsoleOutput, finalOutput.c_str(), finalOutput.length(), &written, NULL);
    }
}

// Enable/Disable hook functions
void EnableHook() {
    DWORD oldProtect;
    VirtualProtect(targetFunc, 14, PAGE_EXECUTE_READWRITE, &oldProtect);
    
    // 64-bit absolute jump
    // mov rax, HookedWriteConsoleW
    // jmp rax
    BYTE jump[14] = {
        0x48, 0xB8, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0xFF, 0xE0,
        0x00, 0x00
    };
    
    void* hookFunc = (void*)HookedWriteConsoleW;
    memcpy(&jump[2], &hookFunc, 8);
    memcpy(targetFunc, jump, 14);
    
    VirtualProtect(targetFunc, 14, oldProtect, &oldProtect);
}

void DisableHook() {
    DWORD oldProtect;
    VirtualProtect(targetFunc, 14, PAGE_EXECUTE_READWRITE, &oldProtect);
    memcpy(targetFunc, originalBytes, 14);
    VirtualProtect(targetFunc, 14, oldProtect, &oldProtect);
}

// Rolling buffer to keep track of the last few kilobytes of terminal output
static std::wstring consoleBuffer;

// Our hijacked function
BOOL WINAPI HookedWriteConsoleW(
    HANDLE  hConsoleOutput,
    const VOID    *lpBuffer,
    DWORD   nNumberOfCharsToWrite,
    LPDWORD lpNumberOfCharsWritten,
    LPVOID  lpReserved
) {
    // 1. Temporarily unhook so we can call the real API without infinite recursion
    DisableHook();

    // 2. Accumulate everything written to the console into our rolling buffer
    std::wstring chunk((LPCWCH)lpBuffer, nNumberOfCharsToWrite);
    
    // Quick debug: log what we actually see to figure out why the hook is blind
    std::wofstream debugLog(L"D:\\codih\\assistant\\scratch\\hook_log.txt", std::ios::app);
    if (debugLog.is_open()) {
        debugLog << L"[CHUNK START]" << chunk << L"[CHUNK END]\n";
    }

    consoleBuffer += chunk;

    // Keep the buffer size manageable (last 4096 characters is plenty of context)
    if (consoleBuffer.length() > 4096) {
        consoleBuffer = consoleBuffer.substr(consoleBuffer.length() - 4096);
    }

    // 3. Look for PowerShell error signatures in the incoming chunk
    bool isErrorTriggered = false;
    if (chunk.find(L"CategoryInfo") != std::wstring::npos || 
        chunk.find(L"FullyQualifiedErrorId") != std::wstring::npos) {
        
        isErrorTriggered = true;
        
        int utf8Len = WideCharToMultiByte(CP_UTF8, 0, consoleBuffer.c_str(), consoleBuffer.length(), NULL, 0, NULL, NULL);
        std::string utf8Str(utf8Len, 0);
        WideCharToMultiByte(CP_UTF8, 0, consoleBuffer.c_str(), consoleBuffer.length(), &utf8Str[0], utf8Len, NULL, NULL);
        
        BlastUDP(utf8Str);
        consoleBuffer.clear();
    }

    // 4. Call the original function so the error text paints to the terminal FIRST
    BOOL result = WriteConsoleW(hConsoleOutput, lpBuffer, nNumberOfCharsToWrite, lpNumberOfCharsWritten, lpReserved);

    // 5. If we just sent an error to Kiko, we FREEZE PowerShell right here!
    // We wait up to 7 seconds for Kiko to reply. PowerShell cannot print the next prompt until we return!
    if (isErrorTriggered) {
        WaitForKikoAndPrint(hConsoleOutput);
    }

    // 6. Re-hook for the next call
    EnableHook();

    return result;
}

// DLL Entry Point
BOOL APIENTRY DllMain(HMODULE hModule, DWORD  ul_reason_for_call, LPVOID lpReserved) {
    if (ul_reason_for_call == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(hModule);
        
        SetupUDP();
        
        // Get the memory address of the real WriteConsoleW
        HMODULE hKernel32 = GetModuleHandleW(L"kernel32.dll");
        targetFunc = (void*)GetProcAddress(hKernel32, "WriteConsoleW");
        
        // Save the first 14 bytes so we can unhook later
        memcpy(originalBytes, targetFunc, 14);
        
        // Patch the API!
        EnableHook();
    }
    return TRUE;
}
