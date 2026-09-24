# Copyright (C) 2026 Senpai
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

import ctypes

def copy_to_clipboard(text: str) -> str:
    """
    Copies the provided text directly to the native Windows clipboard using kernel32/user32 APIs.
    Use this to auto-copy drafted emails, code snippets, or any text the user requests to be copied.
    """
    try:
        # Constants for Windows API
        GMEM_DDESHARE = 0x2000
        CF_UNICODETEXT = 13
        
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        # Ensure 64-bit pointer compatibility
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_int
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        
        # 1. Open the clipboard
        if not user32.OpenClipboard(0):
            return "Failed to open Windows clipboard."
            
        # 2. Empty the clipboard
        user32.EmptyClipboard()
        
        # 3. Allocate global memory for the text
        # UTF-16-LE is the native Unicode format for Windows. 
        # We add b'\0\0' for the null terminator.
        text_bytes = text.encode('utf-16-le') + b'\0\0'
        
        # GlobalAlloc
        hCd = kernel32.GlobalAlloc(GMEM_DDESHARE, len(text_bytes))
        if not hCd:
            user32.CloseClipboard()
            return "Failed to allocate global memory for clipboard."
            
        # 4. Lock the memory and copy data
        pchData = kernel32.GlobalLock(hCd)
        ctypes.memmove(pchData, text_bytes, len(text_bytes))
        kernel32.GlobalUnlock(hCd)
        
        # 5. Set the clipboard data
        user32.SetClipboardData(CF_UNICODETEXT, hCd)
        
        # 6. Close the clipboard
        user32.CloseClipboard()
        
        return "Successfully copied the text to the Windows clipboard."
        
    except Exception as e:
        return f"Failed to copy to clipboard: {e}"
