#include <windows.h>
#include <tlhelp32.h>
#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <cwctype>

#pragma comment(lib, "kernel32.lib")

// Helper to check if a string looks like human readable text and NOT code
bool IsHumanReadable(const std::wstring& str) {
    if (str.length() < 15) return false;
    
    int space_count = 0;
    int alpha_count = 0;
    int symbol_count = 0;
    
    for (wchar_t c : str) {
        if (std::iswspace(c)) space_count++;
        else if (std::iswalpha(c)) alpha_count++;
        else if (std::iswpunct(c)) symbol_count++;
    }
    
    // Heuristics for natural chat/UI text
    if (space_count < 2) return false;
    if (alpha_count < (str.length() / 2)) return false;
    
    // Reject strings with too many symbols (likely JSON, JS code, CSS)
    if (symbol_count > (str.length() / 4)) return false;
    
    // Reject common JS/JSON signatures
    if (str.find(L"function(") != std::wstring::npos) return false;
    if (str.find(L"{\\n") != std::wstring::npos) return false;
    if (str.find(L"{\"") != std::wstring::npos) return false;
    
    return true;
}

bool IsHumanReadableASCII(const std::string& str) {
    if (str.length() < 15) return false;
    
    int space_count = 0;
    int alpha_count = 0;
    int symbol_count = 0;
    
    for (char c : str) {
        if (std::isspace(static_cast<unsigned char>(c))) space_count++;
        else if (std::isalpha(static_cast<unsigned char>(c))) alpha_count++;
        else if (std::ispunct(static_cast<unsigned char>(c))) symbol_count++;
    }
    
    if (space_count < 2) return false;
    if (alpha_count < (str.length() / 2)) return false;
    if (symbol_count > (str.length() / 4)) return false;
    
    if (str.find("function(") != std::string::npos) return false;
    if (str.find("{\\n") != std::string::npos) return false;
    if (str.find("{\"") != std::string::npos) return false;
    
    return true;
}

void ScanProcessMemory(DWORD pid) {
    // STRICT SECURITY: Read only, no write permissions
    HANDLE hProcess = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, FALSE, pid);
    if (!hProcess) return;

    SYSTEM_INFO sysInfo;
    GetSystemInfo(&sysInfo);

    LPCVOID minAddress = sysInfo.lpMinimumApplicationAddress;
    LPCVOID maxAddress = sysInfo.lpMaximumApplicationAddress;

    LPCVOID currentAddress = minAddress;
    MEMORY_BASIC_INFORMATION mbi;

    while (currentAddress < maxAddress) {
        if (VirtualQueryEx(hProcess, currentAddress, &mbi, sizeof(mbi)) == sizeof(mbi)) {
            
            // Only scan committed, private memory (skips mapped files, executables, DLLs)
            // Chromium heaps and active JS variables live strictly in MEM_PRIVATE | PAGE_READWRITE.
            if (mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE &&
                (mbi.Protect == PAGE_READWRITE)) {

                std::vector<char> buffer(mbi.RegionSize);
                SIZE_T bytesRead;

                if (ReadProcessMemory(hProcess, mbi.BaseAddress, buffer.data(), mbi.RegionSize, &bytesRead)) {
                    
                    // --- UTF-16 Scan (Common for JS Engines / V8 / Electron) ---
                    std::wstring current_wstr;
                    for (size_t i = 0; i < bytesRead - 1; i += 2) {
                        wchar_t wc = *reinterpret_cast<wchar_t*>(&buffer[i]);
                        if (wc >= 32 && wc <= 126) {
                            current_wstr += wc;
                        } else {
                            if (current_wstr.length() >= 15 && IsHumanReadable(current_wstr)) {
                                std::wcout << current_wstr << L"\n";
                            }
                            current_wstr.clear();
                        }
                    }
                    
                    // --- UTF-8 / ASCII Scan ---
                    std::string current_str;
                    for (size_t i = 0; i < bytesRead; ++i) {
                        char c = buffer[i];
                        if (c >= 32 && c <= 126) {
                            current_str += c;
                        } else {
                            if (current_str.length() >= 15 && IsHumanReadableASCII(current_str)) {
                                std::cout << current_str << "\n";
                            }
                            current_str.clear();
                        }
                    }
                }
            }
            currentAddress = (LPBYTE)mbi.BaseAddress + mbi.RegionSize;
        } else {
            break; // VirtualQueryEx failed, stop scanning
        }
    }
    CloseHandle(hProcess);
}

int wmain(int argc, wchar_t* argv[]) {
    if (argc < 2) {
        std::wcout << L"Usage: memory_scanner.exe <executable_name.exe>\n";
        return 1;
    }

    std::wstring targetExe = argv[1];
    std::transform(targetExe.begin(), targetExe.end(), targetExe.begin(), ::towlower);

    HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (hSnapshot == INVALID_HANDLE_VALUE) {
        return 1;
    }

    PROCESSENTRY32W pe32;
    pe32.dwSize = sizeof(PROCESSENTRY32W);

    if (Process32FirstW(hSnapshot, &pe32)) {
        do {
            std::wstring exeName = pe32.szExeFile;
            std::wstring lowerExeName = exeName;
            std::transform(lowerExeName.begin(), lowerExeName.end(), lowerExeName.begin(), ::towlower);

            if (lowerExeName == targetExe) {
                std::wcout << L"--- START PID " << pe32.th32ProcessID << L" ---\n";
                ScanProcessMemory(pe32.th32ProcessID);
                std::wcout << L"--- END PID " << pe32.th32ProcessID << L" ---\n";
            }
        } while (Process32NextW(hSnapshot, &pe32));
    }

    CloseHandle(hSnapshot);
    return 0;
}
