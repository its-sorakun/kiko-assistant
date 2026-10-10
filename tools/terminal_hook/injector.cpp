// injector.cpp - IFEO interceptor and DLL injection harness
// Implementation details:
// Windows Image File Execution Options (IFEO) redirects process creation of powershell.exe
// to this binary. To prevent infinite recursion, the target process is spawned with DEBUG_PROCESS,
// which causes the kernel to bypass IFEO for child processes.
// Once created, the full startup context (STARTUPINFO, standard handles, and ConPTY pipes)
// is inherited so integrated terminal managers like Antigravity maintain full connectivity.
// The hook DLL is injected into the remote process via CreateRemoteThread and LoadLibraryW.
// The debugger is detached, and the injector process waits for the child process to terminate,
// forwarding the exit code and ignoring Ctrl+C events so terminal sessions remain alive.

#include <windows.h>
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "[-] Needs target executable.\n";
        return 1;
    }

    // Reconstruct command line securely using GetCommandLineW
    LPWSTR rawCmdLine = GetCommandLineW();
    
    // Skip the first argument (injector.exe)
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

    while (rawCmdLine[skipIdx] == L' ') {
        skipIdx++;
    }
    
    std::wstring cmdLine = &rawCmdLine[skipIdx];
    if (cmdLine.empty()) {
        cmdLine = L"powershell.exe";
    }

    // Forward the parent process startup info to preserve standard streams and ConPTY handles
    STARTUPINFOW si = { sizeof(si) };
    GetStartupInfoW(&si);
    PROCESS_INFORMATION pi = { 0 };

    if (!CreateProcessW(
        NULL,
        &cmdLine[0],
        NULL,
        NULL,
        TRUE, // Inherit standard handles and terminal pipes
        DEBUG_PROCESS | DEBUG_ONLY_THIS_PROCESS, // Bypasses IFEO infinite loop
        NULL,
        NULL,
        &si,
        &pi
    )) {
        std::cerr << "[-] CreateProcess failed: " << GetLastError() << "\n";
        return 1;
    }

    // Path to hook DLL (located in the same directory as injector)
    wchar_t dllPath[MAX_PATH];
    GetModuleFileNameW(NULL, dllPath, MAX_PATH);
    std::wstring dllStr = dllPath;
    dllStr = dllStr.substr(0, dllStr.find_last_of(L"\\/")) + L"\\hook.dll";

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

    // Detach debugger to resume all threads in PowerShell
    DebugActiveProcessStop(pi.dwProcessId);
    CloseHandle(hThread);

    // Ignore Ctrl+C in injector so PowerShell handles keyboard interrupts directly
    SetConsoleCtrlHandler(NULL, TRUE);

    // Keep injector process alive as long as PowerShell is running
    WaitForSingleObject(pi.hProcess, INFINITE);

    DWORD exitCode = 0;
    GetExitCodeProcess(pi.hProcess, &exitCode);

    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);

    return (int)exitCode;
}
