# Copyright (C) 2026 its-sorakun
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import sys
import ctypes
from ctypes import wintypes

# Raw Win32 Constants
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_POPUP = 0x80000000

LWA_COLORKEY = 1
WM_PAINT = 0x000F
WM_DESTROY = 0x0002

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Explicitly define argument types for 64-bit compatibility
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = wintypes.LPARAM

# Define C structures for Win32 API calls
class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ('hdc', wintypes.HDC),
        ('fErase', wintypes.BOOL),
        ('rcPaint', wintypes.RECT),
        ('fRestore', wintypes.BOOL),
        ('fIncUpdate', wintypes.BOOL),
        ('rgbReserved', ctypes.c_byte * 32)
    ]

class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ('style', wintypes.UINT),
        ('lpfnWndProc', ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HANDLE),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR)
    ]

def main():
    if len(sys.argv) < 2:
        temp = "XX.X"
    else:
        temp = sys.argv[1]

    text = f"[ KIKO'S WARNING ] CPU THERMAL THRESHOLD EXCEEDED ({temp}°C)"
    
    # The Window Procedure to intercept hardware paint signals
    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_PAINT:
            ps = PAINTSTRUCT()
            hdc = user32.BeginPaint(hwnd, ctypes.byref(ps))
            
            # create logical font (36px Consolas, regular weight, Cleartype)
            hfont = gdi32.CreateFontW(
                36, 0, 0, 0, 400, 0, 0, 0, 0, 0, 0, 5, 0, "Consolas"
            )
            old_font = gdi32.SelectObject(hdc, hfont)
            
            # Draw Cyan text. 0x00BBGGRR format (so pure cyan is 0x00FFFF00)
            gdi32.SetTextColor(hdc, 0x00FFFF00)
            gdi32.SetBkMode(hdc, 1) # TRANSPARENT background behind the text
            
            rect = wintypes.RECT(0, 0, 1000, 100)
            user32.DrawTextW(hdc, text, -1, ctypes.byref(rect), 0x0020 | 0x0001) # DT_SINGLELINE | DT_CENTER
            
            gdi32.SelectObject(hdc, old_font)
            gdi32.DeleteObject(hfont)
            
            user32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        
    # Marshal the python function into a C function pointer
    WndProcType = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    wndproc_c = WndProcType(wndproc)
    
    hInst = kernel32.GetModuleHandleW(None)
    class_name = "KikoOverlayClass"
    
    wndclass = WNDCLASS()
    wndclass.hInstance = hInst
    wndclass.lpszClassName = class_name
    wndclass.lpfnWndProc = wndproc_c
    
    # Create black brush for the window background. We will use ColorKeying to make pure black 100% transparent.
    wndclass.hbrBackground = gdi32.CreateSolidBrush(0x000000) 
    
    user32.RegisterClassW(ctypes.byref(wndclass))
    
    screen_width = user32.GetSystemMetrics(0)
    
    # Create a borderless, transparent, topmost window that ignores all mouse clicks
    hwnd = user32.CreateWindowExW(
        WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
        class_name,
        "Kiko Overlay",
        WS_POPUP,
        int((screen_width - 1000) / 2), # center X
        100, # Near top of screen
        1000,
        100,
        None, None, hInst, None
    )
    
    # Tell the DWM to key out pure black (0x000000) to complete transparency
    user32.SetLayeredWindowAttributes(hwnd, 0, 0, LWA_COLORKEY)
    
    user32.ShowWindow(hwnd, 5) # SW_SHOW
    user32.UpdateWindow(hwnd)
    
    # Execute the Win32 message pump to keep the window alive
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

if __name__ == "__main__":
    main()
