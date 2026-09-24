// Copyright (C) 2026 Senpai
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

#include <iostream>
#include <windows.h>
#include "include/IPlatform.h"
#include "include/IDeviceManager.h"
#include "include/ICPUEx.h"
#include "include/IBIOSEx.h"
#include "include/IDevice.h"

// returns IPlatform object
typedef IPlatform& (__stdcall* GetPlatformFunc)();

int main(){
    std::cout << "Starting CPU Monitor" << std::endl;

    // force OS window manager to hide the console window instantly to prevent taskbar clutter
    ShowWindow(GetConsoleWindow(), SW_HIDE);

    // asks windows kernel memory manager for space, INVALID_HANDLE_VALUE to skip using secondary memory and reserve 8 bytes of RAM
    HANDLE hMapFile = CreateFileMapping(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, 8, L"Kiko_CPU_Temp");

    // Error Check the Kernel allocation
    if (hMapFile == NULL) {
        std::cout << "Failed to create Shared Memory! Error: " << GetLastError() << std::endl;
        return 1;
    }

    // Map that Kernel memory into our C++ program as a usable Pointer
    double* pSharedTemp = (double*)MapViewOfFile(hMapFile, FILE_MAP_ALL_ACCESS, 0, 0, 8);

    // Error Check the mapping
    if (pSharedTemp == NULL) {
        std::cout << "Failed to map Shared Memory view!" << std::endl;
        CloseHandle(hMapFile);
        return 1;
    }
    
    // write a default value into the RAM (0.0 means booting up)
    *pSharedTemp = 0.0;


    // load platform.dll into the memory
    HMODULE hPlatform = LoadLibrary(L"Platform.dll"); 
    if(hPlatform == NULL){
        std:: cout << "Failed to load Platform.dll, check if it exits in the correct path";
        return 1;
    }

    // hunt down the memory address of the GetPlatform function after loading it through Platform.dll to prevent DLL hell, both platform.dll and device.dll can be found in cpu_monitor/cpu_monitor/x64/Debug folder
    GetPlatformFunc GetPlatform = (GetPlatformFunc)GetProcAddress(hPlatform, "GetPlatform");

    if (GetPlatform == NULL){
        std::cout << "failed to find the GetPlatform inside the dll" << std::endl;
        return 1;
    }

    // call the function GetPlatform() and retrieve the AMD Platform object
    IPlatform& rPlatform = GetPlatform();

    // tell the AMD driver to initialize it's connection to the kernel
    if(rPlatform.Init() == false){
        std::cout << "failed to initialize the AMD Platform" << std::endl;
        return 1;
    }

    std::cout << "successfully hooked and initialized the AMD Ring-0 driver" << std::endl;

    // get device manager from AMD Platform
    IDeviceManager& rDeviceManager = rPlatform.GetIDeviceManager();

    // ask the device manager for the CPU object (device Type: dtCPU, Index: 0)

    ICPUEx* pCpu = (ICPUEx*)rDeviceManager.GetDevice(dtCPU, 0);

    if(pCpu == NULL){
        std::cout << "Failed to find the CPU device" << std::endl;
        return 1;
    }

    // allocate a blank block of memory on the stack
    CPUParameters stData;

    std::cout << "entering background polling loop..." << std::endl;

    // run infinitely
    while (true) {
        // pass that memory block to the driver to be filled
        int iRet = pCpu->GetCPUParameters(stData);

        // check if it succeeded (0 usually means success in low-level c APIs)
        if (iRet == 0) { 
            // write temperature directly into the shared RAM
            *pSharedTemp = stData.dTemperature;
            std::cout << "writing temperature to shared memory: " << stData.dTemperature << std::endl;
        } else {
            std::cout << "failed to read CPU parameters, error code: " << iRet << std::endl;
        }

        // sleep for 5000 milliseconds to prevent high CPU usage
        Sleep(3000);
    }

    // cleanup shared memory
    UnmapViewOfFile(pSharedTemp);
    CloseHandle(hMapFile);
    
    return 0;


}