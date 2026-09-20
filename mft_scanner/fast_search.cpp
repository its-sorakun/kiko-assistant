#include <windows.h>
#include <stdio.h>
#include <string.h>

int wmain(int argc, wchar_t *argv[]) {
    if (argc < 3) {
        wprintf(L"Usage: %s <DriveLetter:> <FileName>\n", argv[0]);
        wprintf(L"Example: %s C: search.py\n", argv[0]);
        return 1;
    }

    wchar_t volume_path[16];
    swprintf(volume_path, 16, L"\\\\.\\%s", argv[1]);
    
    // Requires Administrator privileges to bypass file-level ACLs via the raw DOS device path.
    HANDLE hVol = CreateFileW(volume_path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    if (hVol == INVALID_HANDLE_VALUE) {
        wprintf(L"Failed to open physical volume %s. Error: %lu\n", volume_path, GetLastError());
        return 1;
    }

    USN_JOURNAL_DATA_V0 journalData = {0};
    DWORD bytesReturned = 0;
    
    // Querying the journal populates the valid USN range to determine the stopping point for enumeration.
    if (!DeviceIoControl(hVol, FSCTL_QUERY_USN_JOURNAL, NULL, 0, &journalData, sizeof(journalData), &bytesReturned, NULL)) {
        wprintf(L"Failed to query USN journal. Error: %lu\n", GetLastError());
        CloseHandle(hVol);
        return 1;
    }

    MFT_ENUM_DATA_V0 enumData = {0};
    enumData.StartFileReferenceNumber = 0; // Start at the absolute beginning of the MFT
    enumData.LowUsn = 0;
    enumData.HighUsn = journalData.NextUsn;

    BYTE buffer[8192];
    USN_RECORD_V2 *record = NULL;
    DWORDLONG next_frn = 0;
    
    // Tokenize the search query by spaces for fuzzy multi-keyword matching
    wchar_t query_copy[MAX_PATH];
    wcsncpy_s(query_copy, MAX_PATH, argv[2], MAX_PATH);
    _wcslwr_s(query_copy, MAX_PATH);
    
    wchar_t* context = NULL;
    wchar_t* tokens[32];
    int token_count = 0;
    
    wchar_t* token = wcstok_s(query_copy, L" ", &context);
    while (token != NULL && token_count < 32) {
        tokens[token_count++] = token;
        token = wcstok_s(NULL, L" ", &context);
    }

    wprintf(L"Scanning MFT on %s for '%s'...\n", argv[1], argv[2]);

    // FSCTL_ENUM_USN_DATA reads raw MFT entries directly from disk sectors, ignoring directory structures.
    while (DeviceIoControl(hVol, FSCTL_ENUM_USN_DATA, &enumData, sizeof(enumData), buffer, sizeof(buffer), &bytesReturned, NULL)) {
        
        // Strip the continuation File Reference Number (FRN) from the first 8 bytes to reach the actual records.
        next_frn = *((DWORDLONG*)buffer);
        
        record = (USN_RECORD_V2*)(buffer + sizeof(DWORDLONG));
        
        while ((BYTE*)record < buffer + bytesReturned) {
            // USN records contain the unicode filename without null terminators, requiring manual extraction via offset and length.
            if (record->FileNameLength > 0) {
                wchar_t current_name[MAX_PATH];
                int name_chars = record->FileNameLength / sizeof(wchar_t);
                
                if (name_chars < MAX_PATH) {
                    wcsncpy_s(current_name, MAX_PATH, (wchar_t*)((BYTE*)record + record->FileNameOffset), name_chars);
                    current_name[name_chars] = L'\0';
                    
                    // Convert to lowercase for case-insensitive matching
                    wchar_t lower_name[MAX_PATH];
                    wcsncpy_s(lower_name, MAX_PATH, current_name, MAX_PATH);
                    _wcslwr_s(lower_name, MAX_PATH);
                    
                    bool all_tokens_match = true;
                    for (int i = 0; i < token_count; i++) {
                        if (wcsstr(lower_name, tokens[i]) == NULL) {
                            all_tokens_match = false;
                            break;
                        }
                    }
                    
                    if (all_tokens_match) {
                        FILE_ID_DESCRIPTOR fid = {0};
                        fid.dwSize = sizeof(FILE_ID_DESCRIPTOR);
                        fid.Type = FileIdType;
                        fid.FileId.QuadPart = record->FileReferenceNumber;
                        
                        // Open the file by its internal MFT ID to resolve the full absolute path.
                        HANDLE hFile = OpenFileById(hVol, &fid, 0, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, FILE_FLAG_BACKUP_SEMANTICS);
                        
                        if (hFile != INVALID_HANDLE_VALUE) {
                            wchar_t final_path[MAX_PATH];
                            if (GetFinalPathNameByHandleW(hFile, final_path, MAX_PATH, FILE_NAME_NORMALIZED)) {
                                wchar_t* clean_path = final_path;
                                // Strip the "\\\\?\\" prefix returned by the NT kernel for cleaner output.
                                if (wcsncmp(final_path, L"\\\\?\\", 4) == 0) {
                                    clean_path += 4;
                                }
                                wprintf(L"[MATCH] %s\n", clean_path);
                            } else {
                                wprintf(L"[MATCH] %s (Path resolution failed, File ID: %llu)\n", current_name, record->FileReferenceNumber);
                            }
                            CloseHandle(hFile);
                        } else {
                            wprintf(L"[MATCH] %s (Access denied/locked, File ID: %llu, Error: %lu)\n", current_name, record->FileReferenceNumber, GetLastError());
                        }
                    }
                }
            }
            
            // Pointer math: Leap forward by RecordLength to hit the next variable-length struct header.
            record = (USN_RECORD_V2*)((BYTE*)record + record->RecordLength);
        }
        
        // Seed the next loop iteration with the continuation FRN
        enumData.StartFileReferenceNumber = next_frn;
    }

    CloseHandle(hVol);
    return 0;
}
