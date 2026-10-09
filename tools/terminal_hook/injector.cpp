#include <windows.h>
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    // IFEO passes the original command line but prefixed with our injector
    // e.g., injector.exe "C:\...\powershell.exe" -NoProfile ...
    
    if (argc < 2) {
        std::cerr << "[-] Needs target executable.\n";
        return 1;
    }

    // Reconstruct command line securely using GetCommandLineW
    LPWSTR rawCmdLine = GetCommandLineW();
    
    // We need to skip the first argument (injector.exe)
    bool inQuotes = false;
    int skipIdx = 0;
    while (rawCmdLine[skipIdx]) {
        if (rawCmdLine[skipIdx] == L'"') inQuotes = !inQuotes;
        if (!inQuotes && rawCmdLine[skipIdx] == L' ') {
            skipIdx++;
            break;
        }
        skipIdx++;
    }
    
    std::wstring cmdLine = &rawCmdLine[skipIdx];

    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi = { 0 };

    std::wcout << L"[*] Kiko IFEO Intercept: Spawning suspended -> " << cmdLine << L"\n";

    if (!CreateProcessW(
        NULL,
        &cmdLine[0],
        NULL,
        NULL,
        FALSE,
        DEBUG_PROCESS | DEBUG_ONLY_THIS_PROCESS, // Bypasses IFEO infinite loop!
        NULL,
        NULL,
        &si,
        &pi
    )) {
        std::cerr << "[-] CreateProcess failed: " << GetLastError() << "\n";
        return 1;
    }

    // Path to our hook DLL (must be absolute)
    wchar_t dllPath[MAX_PATH];
    GetModuleFileNameW(NULL, dllPath, MAX_PATH);
    std::wstring dllStr = dllPath;
    dllStr = dllStr.substr(0, dllStr.find_last_of(L"\\/")) + L"\\hook.dll";

    std::wcout << L"[*] Injecting: " << dllStr << L"\n";

    size_t pathSize = (dllStr.length() + 1) * sizeof(wchar_t);
    LPVOID remoteMem = VirtualAllocEx(pi.hProcess, NULL, pathSize, MEM_COMMIT, PAGE_READWRITE);
    if (!remoteMem) {
        std::cerr << "[-] VirtualAllocEx failed\n";
        TerminateProcess(pi.hProcess, 1);
        return 1;
    }

    if (!WriteProcessMemory(pi.hProcess, remoteMem, dllStr.c_str(), pathSize, NULL)) {
        std::cerr << "[-] WriteProcessMemory failed\n";
        TerminateProcess(pi.hProcess, 1);
        return 1;
    }

    HMODULE hKernel32 = GetModuleHandleW(L"kernel32.dll");
    LPTHREAD_START_ROUTINE pLoadLibraryW = (LPTHREAD_START_ROUTINE)GetProcAddress(hKernel32, "LoadLibraryW");

    HANDLE hThread = CreateRemoteThread(pi.hProcess, NULL, 0, pLoadLibraryW, remoteMem, 0, NULL);
    if (!hThread) {
        std::cerr << "[-] CreateRemoteThread failed\n";
        TerminateProcess(pi.hProcess, 1);
        return 1;
    }

    // We don't wait for the thread here because the process is frozen by the debugger.
    // Instead, we just detach the debugger. This instantly resumes ALL threads in the process,
    // including the main PowerShell thread AND our newly created LoadLibrary thread!
    std::wcout << L"[+] Bypassing IFEO and resuming PowerShell...\n";
    DebugActiveProcessStop(pi.dwProcessId);

    CloseHandle(hThread);
    // Note: We intentionally don't free remoteMem immediately because LoadLibrary needs time to read it.
    // It's a tiny leak in the powershell process, but completely safe.

    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);

    return 0;
}
