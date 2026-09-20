# Kiko: Native OS-Aware Assistant

Kiko is an experimental, event-driven virtual assistant designed to explore the intersection between modern Large Language Model (LLM) function calling and low-level Windows OS mechanics. 

Instead of treating the operating system as a black box and interacting via high-level graphical UI automation (like simulated mouse clicks or fragile OCR scraping), the project is engineered to drop down to the underlying mechanisms. Kiko interfaces directly with the native Win32 API, Windows Management Instrumentation (WMI), and the asynchronous Windows Runtime (WinRT).

> For a highly verbose breakdown of the specific kernel and user-space hooks employed, refer to [INTERNALS.md](INTERNALS.md).

## What Kiko Can Do

Because the assistant is hooked directly into the OS, it exposes several core features:
- **System Media Inspection**: Extracts currently playing audio metadata directly from the WinRT DWM media session.
- **Background Media Control**: Sends transport controls (play/pause/skip) directly to specific background processes, bypassing the dominant global media session.
- **Hardware Telemetry**: Evaluates memory/CPU utilization. Bypasses restrictive user-space WMI thermal zones by invoking a custom native C++ daemon (`cpu_monitor`). The daemon interfaces with the AMD Ryzen Master SDK Ring-0 driver to map physical CPU MSR sensors directly into shared memory, eliminating initialization latency during telemetry polling. *(Note: Core thermal polling currently requires an AMD processor and the official AMD Ryzen Master Monitoring SDK to be installed on the host system).*
- **Native Application Launching**: Resolves physical executables via Registry Uninstall hives and spawns them as detached processes.
- **Kernel-Level Process Termination**: Drops `taskkill /F` signals to forcefully clear hung or unresponsive processes from memory.
- **Context-Aware File Reading**: Crawls the Z-order stack to identify the active code editor, parses the window title, and reads the raw file from disk.
- **Silent Filesystem Inspection**: Enables the assistant to query directory structures natively and ingest folder contents directly into its LLM context without relying on visual Windows Explorer windows.
- **Autonomous Web Scraping & Deep-Dive Crawling**: Bypasses AI hallucinations by autonomously browsing the live internet. Fetches real-time search snippets via `lite.duckduckgo.com` and automatically deep-dives into target URLs to extract in-depth text content using event-driven HTML state machines.

## How It Works (The Reasoning Engine)

At the core of Kiko is the `google.genai` SDK, leveraging the Gemini 3.1 Flash Lite model.

Unlike legacy assistant scripts that rely on hardcoded `if/else` intent routing or regex string matching, Kiko delegates all reasoning to the generative model. 

1. **Tool Schema Injection**: The local Python runtime defines a schema of available OS hooks (e.g., `control_system_media`, `get_active_window`, `force_kill_process`) and passes this to Gemini.
2. **Dynamic Decision Making**: When a natural language command is provided (e.g., "Skip this song" or "Why is my PC running hot?"), Gemini determines exactly which native hook to invoke and extracts the necessary arguments.
3. **Local Execution**: Gemini returns a hidden JSON payload to the local script. The Python runtime executes the Win32/WinRT bindings locally—Gemini never has direct access to the host machine.
4. **Contextual Feedback**: The raw execution results are passed back to Gemini to format a natural, contextual response.

## Core Capabilities & Implementation Details

- **DWM Z-Order Interception**: When queried about the user's active context, Kiko bypasses the invoking terminal. By traversing the Desktop Window Manager (DWM) Z-order stack downwards, she can ignore terminal wrappers and identify the true underlying foreground application, even intercepting bare desktop shells (`WorkerW`, `Progman`).
- **WinRT Media Hooking (SMTC)**: Media control completely bypasses simulated keyboard media keys. Kiko hooks into the asynchronous WinRT System Media Transport Controls (SMTC) via the `winsdk` projection. This allows her to iterate through background audio sessions and pipe transport signals specifically to hidden background processes (like Spotify), bypassing dominant global media sessions.
- **Native Registry Resolution**: Applications are launched natively by crawling Windows Registry hives (`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` and `WOW6432Node`) to discover physical executable paths, rather than relying on environment variables or the `start` shell command.
- **Direct Memory & Thermal Probing**: Hardware vitals are read via `psutil`. Thermal data extraction is attempted through Windows Management Instrumentation (WMI) ACPI hooks, exposing the limitations of user-space thermal diode access without Ring-0 drivers.
- **Native Windows Toast Alerts**: Uses the `winsdk` to push native Windows Action Center notifications. A dedicated background thread continuously monitors the shared memory block, evaluating real-time thermal data against hysteresis logic (preventing notification spam) and issuing alerts immediately when safe thresholds are exceeded.
- **Kernel-Level Termination**: Applications are closed by dropping kernel-level termination signals (`taskkill /F`), forcefully removing hung or unresponsive processes from memory rather than issuing polite GUI close requests.
- **Autonomous Web Scraping & Bot Evasion**: Bypasses the need for expensive third-party search APIs. Kiko utilizes the Python standard library to construct a two-stage raw HTTP state-machine parser. By targeting the lightweight `lite.duckduckgo.com` POST endpoint and rotating randomly generated `User-Agent` headers, the scraper evades CAPTCHA blocks. A secondary crawler deep-dives into the top target URL, actively stripping backend DOM code on the fly to feed pure context directly into the LLM.
- **Native RAG Vector Engine**: Long-term conversational memory is implemented completely from scratch without external frameworks like Langchain or ChromaDB. 3072-dimensional embeddings are packed into raw C-level binary blobs via the `struct` module and stored in a native SQLite database. Contextual retrieval is executed via a pure-Python Cosine Similarity scan across the vector table.
- **Global Master File Table (MFT) Scanner**: Drops down to raw NTFS kernel structures via `FSCTL_ENUM_USN_DATA` using a custom C++ executable (`mft_scanner`). It bypasses the agonizingly slow Windows Indexing Service to recursively scan the entire physical disk in milliseconds, utilizing a highly optimized tokenized fuzzy substring matching algorithm to find files based on multi-keyword natural language cues.

## Configuration & Usage

### Prerequisites
- Python 3.10+
- Windows 10 or Windows 11 (required for WinRT SMTC hooks)
- A Gemini API Key from Google AI Studio
- For temperature polling: AMD Ryzen CPU and AMD Ryzen Master Monitoring SDK installed on the host system

### Installation

1. Clone the repository to your local machine.
2. Install the required native bindings and dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: The `winsdk` package may trigger local C++ compilation if pre-compiled wheels are unavailable for your specific Python architecture. This will spike CPU usage temporarily).*

### Configuration

Create a `.env` file in the root directory of the project and insert your API key:
```env
GEMINI_API_KEY=your_actual_api_key_here
```

### Execution

Execute the main script from your terminal:
```bash
python main.py
```
Kiko will initialize the chat session. You can immediately begin interacting via natural language commands to inspect your system, launch applications, or manipulate background media.
