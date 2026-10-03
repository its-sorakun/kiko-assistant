# tools/terminal_watcher.py
import socket
import threading

def start_udp_listener():
    # Create a non-blocking UDP socket to listen for packets from kiko_shell.exe
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 5555))
    
    print("[Terminal Watcher] Kiko's OS Sensor is listening on UDP 5555...")
    
    while True:
        # recvfrom blocks until a packet arrives, making this thread extremely cheap to run
        data, addr = sock.recvfrom(4096)
        error_msg = data.decode('utf-8', errors='ignore').strip()
        
        if error_msg:
            print("\n" + "="*50)
            print("🚨 KIKO RECEIVED AN ERROR PACKET 🚨")
            print("="*50)
            print(error_msg)
            print("="*50)
            print("-> At this point, Kiko would pass this string to Gemini for a solution.")
            
if __name__ == "__main__":
    start_udp_listener()
