// Why C++ instead of Python ctypes?
// The Windows Bluetooth APIs (bluetoothapis.h) require complex memory structs 
// like BLUETOOTH_DEVICE_SEARCH_PARAMS and BLUETOOTH_DEVICE_INFO. 
// Recreating these packed structs manually in Python via ctypes is error-prone and obscures the actual kernel interaction.
// Dropping down to C++ allows the compiler to natively handle struct alignment, 
// exposing the direct mechanism of how Windows enumerates radios and paired devices without fragile abstraction layers.

#include <windows.h>
#include <bluetoothapis.h>
#include <iostream>
#include <string>

#pragma comment(lib, "Bthprops.lib")

// The Audio Sink Service Class GUID (common for headphones/speakers)
// {0000110B-0000-1000-8000-00805F9B34FB}
const GUID GUID_AUDIO_SINK = { 0x0000110b, 0x0000, 0x1000, { 0x80, 0x00, 0x00, 0x80, 0x5f, 0x9b, 0x34, 0xfb } };

void list_devices() {
    BLUETOOTH_DEVICE_SEARCH_PARAMS search_params = { sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS) };
    search_params.fReturnAuthenticated = TRUE;
    search_params.fReturnRemembered = TRUE;
    search_params.fReturnConnected = TRUE;
    search_params.fReturnUnknown = FALSE;
    search_params.fIssueInquiry = FALSE; // Fast check of already paired devices
    search_params.cTimeoutMultiplier = 0;

    BLUETOOTH_DEVICE_INFO device_info = { sizeof(BLUETOOTH_DEVICE_INFO) };

    HBLUETOOTH_DEVICE_FIND hFind = BluetoothFindFirstDevice(&search_params, &device_info);
    if (hFind == NULL) {
        std::cout << "[]" << std::endl;
        return;
    }

    std::cout << "[" << std::endl;
    bool first = true;
    do {
        if (!first) {
            std::cout << "," << std::endl;
        }
        first = false;
        
        // Convert wide string to narrow UTF-8 string properly via Win32 API to avoid C4244 data loss warnings
        std::string name;
        int size_needed = WideCharToMultiByte(CP_UTF8, 0, device_info.szName, -1, NULL, 0, NULL, NULL);
        if (size_needed > 0) {
            name.resize(size_needed - 1); // Size includes null terminator, we don't want it in std::string
            WideCharToMultiByte(CP_UTF8, 0, device_info.szName, -1, &name[0], size_needed - 1, NULL, NULL);
        }
        
        // Format MAC address
        char mac[18];
        snprintf(mac, sizeof(mac), "%02X:%02X:%02X:%02X:%02X:%02X",
            device_info.Address.rgBytes[5], device_info.Address.rgBytes[4],
            device_info.Address.rgBytes[3], device_info.Address.rgBytes[2],
            device_info.Address.rgBytes[1], device_info.Address.rgBytes[0]);

        std::cout << "  {" << std::endl;
        std::cout << "    \"name\": \"" << name << "\"," << std::endl;
        std::cout << "    \"mac\": \"" << mac << "\"," << std::endl;
        std::cout << "    \"connected\": " << (device_info.fConnected ? "true" : "false") << std::endl;
        std::cout << "  }";
    } while (BluetoothFindNextDevice(hFind, &device_info));
    std::cout << "\n]" << std::endl;

    BluetoothFindDeviceClose(hFind);
}

void toggle_service(const std::string& target_mac, bool connect) {
    BLUETOOTH_DEVICE_SEARCH_PARAMS search_params = { sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS) };
    search_params.fReturnAuthenticated = TRUE;
    search_params.fReturnRemembered = TRUE;
    search_params.fReturnConnected = TRUE;
    search_params.fReturnUnknown = FALSE;
    search_params.fIssueInquiry = FALSE;
    search_params.cTimeoutMultiplier = 0;

    BLUETOOTH_DEVICE_INFO device_info = { sizeof(BLUETOOTH_DEVICE_INFO) };

    HBLUETOOTH_DEVICE_FIND hFind = BluetoothFindFirstDevice(&search_params, &device_info);
    if (hFind == NULL) {
        std::cerr << "No paired devices found." << std::endl;
        return;
    }

    bool found = false;
    do {
        char mac[18];
        snprintf(mac, sizeof(mac), "%02X:%02X:%02X:%02X:%02X:%02X",
            device_info.Address.rgBytes[5], device_info.Address.rgBytes[4],
            device_info.Address.rgBytes[3], device_info.Address.rgBytes[2],
            device_info.Address.rgBytes[1], device_info.Address.rgBytes[0]);

        if (target_mac == mac) {
            found = true;
            // Forcefully enable or disable the Audio Sink service to trigger connection state
            // This is a powerful hack: Windows automatically establishes the base connection 
            // when a specific service flag is forced to ON.
            DWORD flags = connect ? BLUETOOTH_SERVICE_ENABLE : BLUETOOTH_SERVICE_DISABLE;
            DWORD result = BluetoothSetServiceState(NULL, &device_info, &GUID_AUDIO_SINK, flags);
            if (result == ERROR_SUCCESS) {
                std::cout << (connect ? "Connection signal sent." : "Disconnection signal sent.") << std::endl;
            } else {
                std::cout << "Failed to toggle service state. Error: " << result << std::endl;
            }
            break;
        }
    } while (BluetoothFindNextDevice(hFind, &device_info));

    BluetoothFindDeviceClose(hFind);
    
    if (!found) {
        std::cout << "Device with MAC " << target_mac << " not found among paired devices." << std::endl;
    }
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: bt_manager.exe <list|connect|disconnect> [MAC_ADDRESS]" << std::endl;
        return 1;
    }

    std::string command = argv[1];

    if (command == "list") {
        list_devices();
    } else if (command == "connect" && argc >= 3) {
        toggle_service(argv[2], true);
    } else if (command == "disconnect" && argc >= 3) {
        toggle_service(argv[2], false);
    } else {
        std::cerr << "Invalid command." << std::endl;
        return 1;
    }

    return 0;
}
