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
bool WriteBMP(const char* filename, int width, int height, const std::vector<uint8_t>& data) {
    std::ofstream file(filename, std::ios::binary);
    if (!file) return false;

    BITMAPFILEHEADER fileHeader = {};
    fileHeader.bfType = 0x4D42; // "BM"
    fileHeader.bfSize = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER) + data.size();
    fileHeader.bfOffBits = sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);

    BITMAPINFOHEADER infoHeader = {};
    infoHeader.biSize = sizeof(BITMAPINFOHEADER);
    infoHeader.biWidth = width;
    infoHeader.biHeight = -height; // Top-down DIB
    infoHeader.biPlanes = 1;
    infoHeader.biBitCount = 32;
    infoHeader.biCompression = BI_RGB;

    file.write(reinterpret_cast<const char*>(&fileHeader), sizeof(fileHeader));
    file.write(reinterpret_cast<const char*>(&infoHeader), sizeof(infoHeader));
    file.write(reinterpret_cast<const char*>(data.data()), data.size());
    return true;
}

int main(int argc, char* argv[]) {
    std::string outputPath = "../../scratch/screenshot.bmp";
    if (argc > 1) {
        outputPath = argv[1];
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

        if (WriteBMP(outputPath.c_str(), width, height, imageData)) {
            std::cout << "SUCCESS:" << outputPath << std::endl;
        } else {
            std::cerr << "Failed to write BMP file" << std::endl;
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
