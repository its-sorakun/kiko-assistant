# tools/clipboard.py - Native Win32 clipboard text injection and retrieval
# Implementation details:
# Interacts directly with kernel32 and user32 memory buffers to read and write clipboard data without external binaries.

import ctypes

def copy_to_clipboard(text: str) -> str:
    """
    Copies the provided text directly to the native Windows clipboard using kernel32/user32 APIs.
    Use this to auto-copy drafted emails, code snippets, or any text requested to be copied.
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

def read_clipboard() -> str:
    """
    Reads the current plain text stored in the native Windows clipboard.
    Use this when requested to inspect, read, check, or retrieve the text currently stored on the clipboard.
    """
    try:
        CF_UNICODETEXT = 13
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = ctypes.c_bool
        user32.GetClipboardData.argtypes = [ctypes.c_uint]
        user32.GetClipboardData.restype = ctypes.c_void_p
        user32.IsClipboardFormatAvailable.argtypes = [ctypes.c_uint]
        user32.IsClipboardFormatAvailable.restype = ctypes.c_bool
        
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_int
        
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return "Notice: No text content found in Windows clipboard (it may contain binary data, an image, or be empty)."
            
        if not user32.OpenClipboard(0):
            return "Error: Unable to open Windows clipboard (it may be locked by another process)."
            
        try:
            h_data = user32.GetClipboardData(CF_UNICODETEXT)
            if not h_data:
                return "Notice: Clipboard contains no text data."
                
            p_data = kernel32.GlobalLock(h_data)
            if not p_data:
                return "Error: Unable to lock clipboard memory handle."
                
            try:
                # Read null-terminated UTF-16 text
                text = ctypes.wstring_at(p_data)
                return text
            finally:
                kernel32.GlobalUnlock(h_data)
        finally:
            user32.CloseClipboard()
            
    except Exception as e:
        return f"Error reading clipboard: {e}"
