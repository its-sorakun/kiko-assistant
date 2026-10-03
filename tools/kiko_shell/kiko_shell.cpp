// kiko_shell.cpp
// A C++ wrapper that spawns powershell.exe and hijacks its StandardError pipe
// to detect failures mechanically.

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <iostream>
#include <string>
#include <thread>

#pragma comment(lib, "ws2_32.lib")

SOCKET udp_socket;
sockaddr_in kiko_addr;

void init_udp_sender() {
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        std::cerr << "WSAStartup failed. UDP bridge is down.\n";
        exit(1);
    }
    
    udp_socket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (udp_socket == INVALID_SOCKET) {
        std::cerr << "Socket creation failed. UDP bridge is down.\n";
        WSACleanup();
        exit(1);
    }
    
    kiko_addr.sin_family = AF_INET;
    kiko_addr.sin_port = htons(5555);
    inet_pton(AF_INET, "127.0.0.1", &kiko_addr.sin_addr);
}

// Thread to constantly read from the child's STDOUT and print it to our screen
void read_stdout(HANDLE hPipeRead) {
    char buffer[4096];
    DWORD bytesRead;
    while (ReadFile(hPipeRead, buffer, sizeof(buffer) - 1, &bytesRead, NULL) && bytesRead > 0) {
        buffer[bytesRead] = '\0';
        std::cout << buffer;
    }
}

// Thread to listen for Kiko's replies and print them directly in our shell
void read_udp_responses() {
    char buffer[8192];
    sockaddr_in from_addr;
    int from_len = sizeof(from_addr);
    while (true) {
        int bytes = recvfrom(udp_socket, buffer, sizeof(buffer) - 1, 0, (sockaddr*)&from_addr, &from_len);
        if (bytes > 0) {
            buffer[bytes] = '\0';
            // Print Kiko's response in bright pink
            std::cout << "\n\033[95m[Kiko]: " << buffer << "\033[0m\n> ";
            std::cout.flush();
        }
    }
}

// Thread to constantly read from the child's STDERR and intercept errors
void read_stderr(HANDLE hPipeRead) {
    char buffer[4096];
    DWORD bytesRead;
    while (ReadFile(hPipeRead, buffer, sizeof(buffer) - 1, &bytesRead, NULL) && bytesRead > 0) {
        buffer[bytesRead] = '\0';
        
        std::cerr << "\n[KIKO INTERCEPTED ERROR]:\n" << buffer << "\n";
        
        int kiko_port = 5555;
        // Dynamically resolve Kiko's active UDP port in case she had to failover to a new one
        // We check two directories up since this binary runs from tools/kiko_shell/
        FILE* fp = fopen("../../.kiko_port", "r");
        if (!fp) fp = fopen(".kiko_port", "r"); // Fallback if run from the project root
        
        if (fp) {
            fscanf(fp, "%d", &kiko_port);
            fclose(fp);
        }
        kiko_addr.sin_port = htons(kiko_port);
        
        std::cerr << "[DEBUG] Sending UDP packet to port " << kiko_port << "\n";
        
        // UDP is connectionless. If Kiko's Python script isn't running, the OS just drops the packet.
        // This ensures the C++ terminal never hangs waiting for a TCP handshake.
        sendto(udp_socket, buffer, bytesRead, 0, (sockaddr*)&kiko_addr, sizeof(kiko_addr));
    }
}

int main() {
    init_udp_sender();
    
    HANDLE hChildStdOutRead, hChildStdOutWrite;
    HANDLE hChildStdErrRead, hChildStdErrWrite;
    HANDLE hChildStdInRead, hChildStdInWrite;
    
    SECURITY_ATTRIBUTES saAttr;
    saAttr.nLength = sizeof(SECURITY_ATTRIBUTES);
    saAttr.bInheritHandle = TRUE;
    saAttr.lpSecurityDescriptor = NULL;
    
    // Create the pipes. The child writes to 'Write', we read from 'Read'.
    if (!CreatePipe(&hChildStdOutRead, &hChildStdOutWrite, &saAttr, 0)) {
        std::cerr << "Stdout pipe creation failed\n";
        return 1;
    }
    // Ensure the read handle to the pipe for STDOUT is not inherited.
    SetHandleInformation(hChildStdOutRead, HANDLE_FLAG_INHERIT, 0);

    if (!CreatePipe(&hChildStdErrRead, &hChildStdErrWrite, &saAttr, 0)) {
        std::cerr << "Stderr pipe creation failed\n";
        return 1;
    }
    SetHandleInformation(hChildStdErrRead, HANDLE_FLAG_INHERIT, 0);

    if (!CreatePipe(&hChildStdInRead, &hChildStdInWrite, &saAttr, 0)) {
        std::cerr << "Stdin pipe creation failed\n";
        return 1;
    }
    SetHandleInformation(hChildStdInWrite, HANDLE_FLAG_INHERIT, 0);

    // Prepare the STARTUPINFO to map the pipes to the child process
    STARTUPINFO si;
    ZeroMemory(&si, sizeof(STARTUPINFO));
    si.cb = sizeof(STARTUPINFO);
    si.hStdError = hChildStdErrWrite;
    si.hStdOutput = hChildStdOutWrite;
    si.hStdInput = hChildStdInRead;
    si.dwFlags |= STARTF_USESTDHANDLES; // Tell Windows to actually use our handles

    PROCESS_INFORMATION pi;
    ZeroMemory(&pi, sizeof(PROCESS_INFORMATION));
    
    // Command line to launch powershell
    std::string cmd = "powershell.exe";
    
    if (!CreateProcess(
        NULL,
        &cmd[0],       // command line (must be modifiable buffer)
        NULL,          // process security attributes
        NULL,          // primary thread security attributes
        TRUE,          // handles are inherited
        0,             // creation flags
        NULL,          // use parent's environment
        NULL,          // use parent's current directory
        &si,           // STARTUPINFO pointer
        &pi))          // receives PROCESS_INFORMATION
    {
        std::cerr << "CreateProcess failed (" << GetLastError() << ").\n";
        return 1;
    }
    
    // We must close our copies of the child's write handles so the pipes will actually close
    // when the child terminates. Otherwise ReadFile will hang forever waiting for more data.
    CloseHandle(hChildStdOutWrite);
    CloseHandle(hChildStdErrWrite);
    CloseHandle(hChildStdInRead);

    // Launch threads to read STDOUT and STDERR asynchronously
    std::thread stdout_thread(read_stdout, hChildStdOutRead);
    std::thread stderr_thread(read_stderr, hChildStdErrRead);
    std::thread udp_thread(read_udp_responses);
    
    // Main loop: read from our real keyboard and write to the child's STDIN pipe
    char buffer[4096];
    DWORD bytesWritten;
    HANDLE hStdin = GetStdHandle(STD_INPUT_HANDLE);
    DWORD bytesRead;
    
    while (ReadFile(hStdin, buffer, sizeof(buffer), &bytesRead, NULL) && bytesRead > 0) {
        if (!WriteFile(hChildStdInWrite, buffer, bytesRead, &bytesWritten, NULL)) {
            break; // Child probably died
        }
    }
    
    // Clean up and wait for the child
    WaitForSingleObject(pi.hProcess, INFINITE);
    
    // We don't strictly need to wait for threads here since the process is exiting,
    // but it's good practice. (They might block on ReadFile if the child didn't close its handles).
    // stdout_thread.join();
    // stderr_thread.join();
    
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    CloseHandle(hChildStdOutRead);
    CloseHandle(hChildStdErrRead);
    CloseHandle(hChildStdInWrite);
    
    return 0;
}
