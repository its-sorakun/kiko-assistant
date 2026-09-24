// Copyright (C) 2026 its-sorakun
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

#include <windows.h>
#include <d3d11.h>
#include <dxgi1_2.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <cstdint>

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")

// Helper to write a simple 32-bit BGRA BMP
bool WriteToSharedMemory(const char* mapName, int width, int height, const std::vector<uint8_t>& data) {
    
    //need to know exactly how big the memory block is. It will be the size of the raw pixels + 8 bytes (two integers to store width and height)
    size_t totalSize = sizeof(int) * 2 + data.size();

    // Ask the OS to find the memory block Python created
    HANDLE hMapFile = OpenFileMappingA(
        FILE_MAP_ALL_ACCESS,                 //permission to read and write
        FALSE,                               //Do not inherit the name
        mapName                              // The global string name Python used
    );

    if (hMapFile == NULL) {
        std::cerr << "Could not open file mapping object (" << GetLastError() << ").\n";
        return false;
    }
    
    // Map the memory into our C++ process address space to write to it
    LPVOID pBuf = MapViewOfFile(
        hMapFile, 
        FILE_MAP_ALL_ACCESS, 
        0, 0, 
        totalSize
    );

    if (pBuf == NULL) {
        std::cerr << "Could not map view of file (" << GetLastError() << ").\n";
        CloseHandle(hMapFile);
        return false;
    }

    // Write the Width and Height at the very beginning of the memory block (An int is 4 bytes, so this takes up the first 8 bytes of the block)
    int* pHeader = static_cast<int*>(pBuf);
    pHeader[0] = width;
    pHeader[1] = height;

    //Shift our pointer forward by 2 integers (8 bytes). This points exactly to where the pixel data should begin
    uint8_t* pPixels = reinterpret_cast<uint8_t*>(pHeader + 2);
    
    //Blast the raw pixels straight from the GPU into the Shared Memory!
    memcpy(pPixels, data.data(), data.size());

    // Clean up our local C++ pointers (The memory isn't destroyed because Python still holds the master handle)
    UnmapViewOfFile(pBuf);
    CloseHandle(hMapFile);

    

    return true;
}


int main(int argc, char* argv[]) {
    std::string mapName = "Local\\KikoDXGIFrame";
    if (argc > 1) {
        mapName = argv[1];
    }


    ID3D11Device* d3dDevice = nullptr;
    ID3D11DeviceContext* d3dContext = nullptr;
    D3D_FEATURE_LEVEL featureLevel;
    
    HRESULT hr = D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0, nullptr, 0, D3D11_SDK_VERSION, &d3dDevice, &featureLevel, &d3dContext);
    if (FAILED(hr)) {
        std::cerr << "D3D11CreateDevice failed" << std::endl;
        return 1;
    }

    IDXGIDevice* dxgiDevice = nullptr;
    hr = d3dDevice->QueryInterface(__uuidof(IDXGIDevice), (void**)&dxgiDevice);
    
    IDXGIAdapter* dxgiAdapter = nullptr;
    hr = dxgiDevice->GetParent(__uuidof(IDXGIAdapter), (void**)&dxgiAdapter);

    IDXGIOutput* dxgiOutput = nullptr;
    hr = dxgiAdapter->EnumOutputs(0, &dxgiOutput);

    IDXGIOutput1* dxgiOutput1 = nullptr;
    hr = dxgiOutput->QueryInterface(__uuidof(IDXGIOutput1), (void**)&dxgiOutput1);

    IDXGIOutputDuplication* deskDupl = nullptr;
    hr = dxgiOutput1->DuplicateOutput(d3dDevice, &deskDupl);
    if (FAILED(hr)) {
        std::cerr << "Failed to initialize Desktop Duplication (Check if running in exclusive fullscreen or over RDP)" << std::endl;
        return 1;
    }

    DXGI_OUTDUPL_FRAME_INFO frameInfo;
    IDXGIResource* desktopResource = nullptr;
    
    // Retry acquiring the next frame
    for (int i = 0; i < 50; ++i) {
        hr = deskDupl->AcquireNextFrame(500, &frameInfo, &desktopResource);
        if (SUCCEEDED(hr)) break;
    }

    if (FAILED(hr)) {
        std::cerr << "Failed to acquire next frame" << std::endl;
        return 1;
    }

    ID3D11Texture2D* acquiredDesktopImage = nullptr;
    hr = desktopResource->QueryInterface(__uuidof(ID3D11Texture2D), (void**)&acquiredDesktopImage);

    D3D11_TEXTURE2D_DESC desc;
    acquiredDesktopImage->GetDesc(&desc);

    // Create a staging texture to read the GPU memory from the CPU
    D3D11_TEXTURE2D_DESC stagingDesc = desc;
    stagingDesc.Usage = D3D11_USAGE_STAGING;
    stagingDesc.CPUAccessFlags = D3D11_CPU_ACCESS_READ;
    stagingDesc.BindFlags = 0;
    stagingDesc.MiscFlags = 0;
    stagingDesc.MipLevels = 1;
    stagingDesc.ArraySize = 1;

    ID3D11Texture2D* stagingTexture = nullptr;
    hr = d3dDevice->CreateTexture2D(&stagingDesc, nullptr, &stagingTexture);

    // Copy from the GPU resource to our CPU staging texture
    d3dContext->CopyResource(stagingTexture, acquiredDesktopImage);

    D3D11_MAPPED_SUBRESOURCE mapped;
    hr = d3dContext->Map(stagingTexture, 0, D3D11_MAP_READ, 0, &mapped);
    if (SUCCEEDED(hr)) {
        int width = desc.Width;
        int height = desc.Height;
        
        // Extract raw bytes. DXGI formats are usually BGRA.
        std::vector<uint8_t> imageData(width * height * 4);
        uint8_t* pSrc = static_cast<uint8_t*>(mapped.pData);
        uint8_t* pDest = imageData.data();
        
        for (int y = 0; y < height; ++y) {
            memcpy(pDest, pSrc, width * 4);
            pSrc += mapped.RowPitch;
            pDest += width * 4;
        }

        d3dContext->Unmap(stagingTexture, 0);

        if (!WriteToSharedMemory(mapName.c_str(), width, height, imageData)) {
            std::cerr << "Failed to write to shared memory!" << std::endl;
            return 1;
        } else {
            std::cout << "SUCCESS:" << mapName << std::endl;
        }
    } else {
        std::cerr << "Failed to map staging texture" << std::endl;
    }

    // Cleanup
    deskDupl->ReleaseFrame();
    if (stagingTexture) stagingTexture->Release();
    if (acquiredDesktopImage) acquiredDesktopImage->Release();
    if (desktopResource) desktopResource->Release();
    if (deskDupl) deskDupl->Release();
    if (dxgiOutput1) dxgiOutput1->Release();
    if (dxgiOutput) dxgiOutput->Release();
    if (dxgiAdapter) dxgiAdapter->Release();
    if (dxgiDevice) dxgiDevice->Release();
    if (d3dContext) d3dContext->Release();
    if (d3dDevice) d3dDevice->Release();

    return 0;
}
