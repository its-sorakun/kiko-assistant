# Kiko: Native OS-Aware Assistant

Kiko is an experimental, event-driven virtual assistant designed to explore the intersection between modern Large Language Model (LLM) function calling and low-level Windows OS mechanics. 

Instead of treating the operating system as a black box and interacting via high-level graphical UI automation (like simulated mouse clicks or fragile OCR scraping), the project is engineered to drop down to the underlying mechanisms. Kiko interfaces directly with the native Win32 API, Windows Management Instrumentation (WMI), and the asynchronous Windows Runtime (WinRT).

> For a highly verbose breakdown of the specific kernel and user-space hooks employed, refer to [INTERNALS.md](INTERNALS.md).

## What Kiko Can Do

Because Kiko is hooked directly into the OS rather than relying on clunky GUI automation, she wields god-tier control over your Windows environment. She can do things most assistants simply cannot:

- **Ultra-Fast Global File Search**: Finds *any* file across all your hard drives in milliseconds using a raw NTFS Master File Table scanner. It completely bypasses the agonizingly slow Windows Indexing Service. *(Example: "Kiko, where is my monthly transaction report xlsx file kept? Open the parent folder if you find it.")*
- **Instant Background Media Control**: Hooks into the WinRT System Media Transport Controls to perfectly manage your music in the background, even if a browser tab stole your global media keys. *(Example: "Kiko, pause the music." or "Kiko, skip this music." or "Kiko, isn't the currently playing music good? What song is this?")*
- **Real CPU Thermals**: Reads your actual CPU die temperatures directly through a custom C++ daemon interfacing with AMD's Ring-0 monitoring driver, entirely bypassing Windows' useless WMI placeholders. *(Example: "Kiko, why are my fans spinning so loud? Are my CPU thermals spiking?")*
- **Launch & Kill Anything**: Crawls your Windows Registry to natively spawn applications, or drops a kernel-level `taskkill /F` to violently rip hung programs out of memory. *(Example: "Kiko, Discord is frozen again, kill it and restart it.")*
- **Reads Your Active Editor**: Silently inspects the DWM window stack to figure out exactly what file you are currently coding in, then reads the raw bytes straight from your disk — no messy clipboard pasting required! *(Example: "Kiko, look at the python script I have open right now, why is this function crashing?")*
- **Direct Memory Scraping**: For heavily sandboxed apps that block normal text extraction, Kiko unleashes a custom C++ scanner to rip text strings directly out of the target application's live heap memory. *(Example: "Kiko, read my active Discord chat and summarize what my friends are arguing about.")*
- **GPU-Powered Screen Vision**: Hooks into the DXGI Desktop Duplication API to capture your raw screen directly from GPU VRAM in ~1ms. If an anti-cheat blocks it, she violently forces composition via GDI fallback to pipe the frame straight into her vision model. *(Example: "Kiko, look at my screen, is this weapon good enough for my character?")*
- **Agentic Directory & Codebase Ingestion**: Point her at any massive folder and she'll recursively ingest the entire directory tree, selectively ripping file contents straight into her memory to understand your entire project architecture. *(Example: "Kiko, scan my `~/Documents/Projects/Kiko-Assistant` codebase and explain how the code is structured.")*
- **Chat With PDFs**: Unleashes a dedicated LangGraph RAG sub-agent to embed massive documents into a local FAISS vector index so you can interrogate your files naturally — zero cloud uploads required. *(Example: "Kiko, find the 'Transaction_History.pdf', read it, and tell me how can I manage my expenses for the next month.")*
- **Live Web Browsing**: Bypasses AI hallucinations entirely by autonomously browsing the live internet, deep-diving into target URLs, and stripping the raw HTML down to pure text to feed her context. *(Example: "Kiko, tell me the latest India VS Sri Lanka cricket scores, and future schedules.")*
- **Intelligent Weather & Telemetry**: Pulls real-time conditions, 7-day forecasts or 5 hour forcasts, based on your coordinates. If your Windows Location is disabled, she doesn't just fail — she asks if she should temporarily bypass the OS lock. Give her the go-ahead, and she autonomously enables Windows Location, fetches the weather, and immediately locks the permission back down. *(Example: "Kiko, how's the weather looking outside right now?" or "Kiko, do I need an umbrella?")*
- **Job Application Orchestrator**: Fully automates your job email draft. Give her a target email or JD, and she will extract the company name, scrape their live website for details, evaluate your locally stored resumes via MFT file search, and write a hyper-tailored cold email. *(Example: "Kiko, I want to apply to hr@companyname.com, write an email using the resume that best fits an AI engineering role.")*
- **Native Clipboard Access**: Silently injects formatted text directly into your Windows clipboard via raw Win32 calls. *(Example: "Kiko, draft a romantic message for my crush and put it on my clipboard.")*
- **Kernel-Level Bluetooth Control**: Forcefully toggles your Bluetooth radio on/off, queries battery levels, and connects/disconnects paired devices using a custom C++ binary that injects flags straight into the Bluetooth stack — completely bypassing the flaky Windows UI! *(Example: "Kiko, turn on bluetooth" or "Kiko, my headphones disconnected, force connect to 'WH-1000XM4'.")*
- **Dynamic Permission Bypassing & Privacy Control**: Autonomously rips open locked OS capabilities in the Registry (like Location or Radios) to execute restricted commands, then instantly locks them back down(if required). Alternatively, you can use her as a master privacy switch. *(Example: "Kiko, turn off my microphone and lock my camera access right now.")*
- **Full Spotify Integration**: Searches the global catalog, generates custom playlists, queries your listening stats, and transfers playback between your hardware devices using the Spotify Web API. *(Example: "Kiko, transfer my music to my Phone and queue up some Genshin Impact music.")*
- **Persistent Neural Memory**: Silently logs your preferences, system quirks, and past conversations into a local SQLite database. She builds a permanent profile of how you work and uses it to hyper-personalize her behavior without needing to be told twice. *(Example: "Kiko, always remember that I prefer vedic tea over chai.")*

*(Note: If I forgot to add something, check out INTERNALS.md — or just consider it a hidden easter egg xD)*

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
- **Native OS-Level Location & Weather Polling**: Instead of relying on hardcoded location fallbacks, Kiko integrates directly into the Windows OS Capability Access Manager (`camsvc`) via raw Registry hooking. She autonomously evaluates the global device-level location `ConsentStore` state. If disabled, she prompts the user for consent, physically toggles the OS master switch in `HKEY_LOCAL_MACHINE` to perform IP-based geolocation via the OpenWeatherMap API, and immediately locks the permission back down to strictly enforce user privacy.
- **Kernel-Level Termination**: Applications are closed by dropping kernel-level termination signals (`taskkill /F`), forcefully removing hung or unresponsive processes from memory rather than issuing polite GUI close requests.
- **Autonomous Web Scraping & Bot Evasion**: Bypasses the need for expensive third-party search APIs. Kiko utilizes the Python standard library to construct a two-stage raw HTTP state-machine parser. By targeting the lightweight `lite.duckduckgo.com` POST endpoint and rotating randomly generated `User-Agent` headers, the scraper evades CAPTCHA blocks. A secondary crawler deep-dives into the top target URL, actively stripping backend DOM code on the fly to feed pure context directly into the LLM.
- **GPU-Accelerated RAG Vector Engine**: Long-term conversational memory and screen scraping context are managed using a high-performance vector pipeline. Embeddings are generated natively and piped directly into a local PyTorch FAISS index. By utilizing CUDA 12.4 hardware acceleration, Kiko bypasses slow CPU-bound cosine similarity math, executing semantic similarity searches instantaneously across massive text blobs on the dedicated GPU.
- **Global Master File Table (MFT) Scanner**: Drops down to raw NTFS kernel structures via `FSCTL_ENUM_USN_DATA` using a custom C++ executable (`mft_scanner`). It bypasses the agonizingly slow Windows Indexing Service to recursively scan the entire physical disk in milliseconds, utilizing a highly optimized tokenized fuzzy substring matching algorithm. The wrapper explicitly utilizes `psutil` to dynamically discover all mounted NTFS volumes natively, sequentially blasting through `C:`, `D:`, and all other physical drives seamlessly without hardcoding target partitions.
- **Agentic PDF Analysis (LangGraph + FAISS)**: Instead of passing raw PDF byte strings into the LLM context, Kiko delegates PDF analysis to a dedicated LangGraph sub-agent workflow. The document is ingested via `PyPDFLoader`, semantically mapped using high-speed CPU-optimized HuggingFace embeddings (`all-MiniLM-L6-v2`), and cached in a purely ephemeral in-memory FAISS vector database. Kiko retrieves exactly the chunks she needs natively without external AI framework bloat dragging down generation speed.
- **Direct Memory Hooking & Context Scraping**: Instead of relying on fragile UIAutomation trees or OCR, Kiko defaults to a custom C++ Direct Memory Scanner (`memory_scanner.exe`) for heavily sandboxed apps (like Discord and Electron wrappers). This drops down to `ReadProcessMemory` to rip strings directly from the target application's active `PAGE_READWRITE` heap chunks, cross-sectioning the memory and stripping V8 Javascript noise to extract pure chat context. Standard Microsoft UI Automation (UIA) remains available as a secondary option for legacy GUI frameworks.
- **Native Multimodal Frame Buffer Vision**: When text extraction isn't enough (like analyzing a video game state or reading an image), Kiko invokes a custom C++ tool (`dxgi_capture.exe`) that hooks the OS Desktop Window Manager (DWM) via the DXGI Desktop Duplication API. This rips the raw frame buffer directly from the GPU VRAM in roughly 1ms. To completely eliminate SSD I/O bottlenecks, the C++ executable blasts the raw 33MB+ pixel grid directly into Python via a Win32 Inter-Process Communication (IPC) Shared Memory Mapped block. Python rebuilds the grid in RAM instantaneously. If the game utilizes Multi-Plane Overlays (MPO) or Kernel Anti-Cheat that causes DXGI to capture a black screen, the vision tool autonomously detects the zero-variance frame and drops down to a legacy Win32 GDI `BitBlt` capture to violently force DWM composition, piping the final bytes directly into Gemini's multimodal vision encoder.
- **Context Token Management**: To prevent raw heap dumps or intensive recursive web searches from exploding the LLM context window and triggering API rate limits, Kiko is armed with a short-term memory wipe tool. She can autonomously evaluate her own context bloat and wipe her session history on the fly before initiating heavy queries.
- **Native Win32 Clipboard**: Enables Kiko to seamlessly push text payloads directly into the host OS clipboard utilizing `kernel32` and `user32` ctypes bindings, bypassing the need for external CLI binaries.
- **Agentic Job Application Helper**: A dedicated orchestration workflow that fully automates job applications. When given a target HR email (either provided directly in chat or autonomously extracted from a target document), Kiko deduces the company name, performs a live web search for company details, and evaluates available resumes to select the best fit(If multiple resumes exists, it will select the best fit based on the job description and your field). She then passes the data to an isolated helper tool that drafts a strictly professional email (bypassing her persona) and natively injects the final draft directly into the clipboard.
- **Dynamic Hot-Swapping**: Kiko's tools architecture dynamically resolves function pointers straight from module exports at runtime. Kiko is equipped with a `reload_core_systems` tool, allowing her to natively trigger Python's `importlib.reload()` on all her internal subsystems and rebuild her Gemini API schema dynamically without dropping the chat session loop, enabling live code editing.

## Configuration & Usage

### Prerequisites
- Python 3.10 to 3.13 (Note: If using Python 3.14+, you must manually update `requirements.txt` to point to a newer PyTorch CUDA index like `cu126`, as `cu124` wheels are no longer compiled for newer Python releases).
- Windows 10 or Windows 11 (required for WinRT SMTC hooks)
- An Nvidia GPU supporting CUDA 12.4+ (highly recommended to prevent the FAISS/PyTorch RAG engines from falling back to agonizingly slow CPU computation).
- A Gemini API Key from Google AI Studio
- For temperature polling: AMD Ryzen CPU and AMD Ryzen Master Monitoring SDK installed on the host system (currently supports only AMD Ryzen CPUs)

### Installation

1. Clone the repository to your local machine.
2. Install the required native bindings and dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: The `winsdk` package may trigger local C++ compilation if pre-compiled wheels are unavailable for your specific Python architecture. This will spike CPU usage temporarily).*

### Configuration

**1. Create the Environment File:**
Create a `.env` file in the root directory of the project and insert your API credentials:

```env
# Google Gemini API
GEMINI_API_KEY=your_actual_api_key_here

# Spotify Developer API
SPOTIPY_CLIENT_ID=your_spotify_client_id_here
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret_here
SPOTIPY_REDIRECT_URI=http://127.0.0.1:8080(or any port which is not used by any other application)
```

**2. Spotify OAuth Setup:**
To get Kiko working with your personal Spotify account:
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create app**. Give it a name like "Kiko Assistant".
3. In the App settings, find the **Redirect URIs** section.
4. Add EXACTLY `http://127.0.0.1:8080` (Do *not* use `localhost`, it will fail).
5. Copy your **Client ID** and **Client Secret** from the dashboard and paste them into your `.env` file.

*(Note: The Spotify Redirect URI must strictly use the loopback IP `127.0.0.1` and exactly match the URI registered in your Spotify Developer Dashboard. Using the string `localhost` will be rejected by Spotify's OAuth flow).*

### Execution

Execute the main script from your terminal:
```bash
python main.py
```
Kiko will initialize the chat session. You can immediately begin interacting via natural language commands to inspect your system, launch applications, or manipulate background media.

## License

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**. 
See the [LICENSE](LICENSE) file for more details.
