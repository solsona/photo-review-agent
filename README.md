# AI Photo Curation Agent 📸🤖

Welcome to the AI Photo Curation Agent! This is a local application designed to automatically scan a folder of raw DNG photographs, evaluate them, and generate structured artistic critiques and Lightroom star ratings. It now supports both cloud-based analysis via **Google Gemini Vision** and 100% private, local execution using **Gemma 4** vision models via **Ollama**.

---

## Features
* **Dual AI Engines**: Choose between Google Gemini (Cloud) and Ollama (Local) for offline, cost-free processing.
* **Gemma 4 Optimized**: Native support for running the laptop-ready `gemma4:12b` or edge-friendly `gemma4:e4b` local vision models.
* **CPU Parallel Pre-extraction**: Decoupled RAW decoding using a parallel thread pool to pre-cache thumbnails before running GPU-bound LLM queries, preventing CPU bottlenecks.
* **Lightroom Classic Integration**: Generates Adobe-compliant `.xmp` sidecars with star ratings, keywords, and text captions directly importable into Lightroom.
* **Smart Resume Caching**: Skip previously reviewed photos and automatically recover/retry failed runs by parsing existing XMP files.
* **Lightweight UI**: Memory-optimized Streamlit interface using a sliding window to display the last 3 analyzed photos, preventing browser crashes on directories with 800+ photos.

---

## Prerequisites

### 1. General System Requirements
* **macOS** (Apple Silicon M1/M2/M3/M4 or dedicated GPU highly recommended for local execution).
* **Python 3.9+** installed on your system.

### 2. For Google Gemini (Cloud)
* A **Gemini API Key**:
  * Get your key from [Google AI Studio](https://aistudio.google.com/app/apikey) (free tier available).

### 3. For Ollama & Gemma 4 (Local)
* **Ollama App**: Download and run [Ollama for Mac](https://ollama.com).
* **Gemma 4 Model**: Open terminal and download the recommended vision-capable model:
  ```bash
  ollama pull gemma4:12b
  ```

---

## Setup & Running the App

1. Open this project directory.
2. Double-click **`run.command`**.
   * *Mac Security Note:* If macOS displays an "unidentified developer" warning, right-click `run.command` and select **Open**, then click **Open** in the prompt.
3. The Terminal will configure a virtual environment (`venv`), install dependencies, and prompt for your Gemini API key (if running cloud for the first time).
4. A beautiful web application will launch in your browser automatically!

---

## How to Integrate with Adobe Lightroom Classic 🏷️

The curation agent creates Adobe-compliant `.xmp` sidecar files (e.g., `DSC0123.xmp` next to `DSC0123.dng`). These sidecars map:
* **Score (1-10)** ➡️ **Star Rating (1-5)**.
* **Artistic Critique Bullets** ➡️ **Caption** (visible in Lightroom's Metadata panel).
* **AI Evaluation Markers** ➡️ **Keywords** (`AI Reviewed`, `Promising`, `Color` / `Black & White`).

### Importing the Reviews into Lightroom:
There are two ways to sync this metadata into Lightroom Classic depending on your import order:

#### Method A: If you run the AI Agent BEFORE importing into Lightroom
* Simply import the folder of DNGs into Lightroom Classic as usual.
* Lightroom will automatically detect the adjacent `.xmp` files and import the star ratings, captions, and keywords alongside the raw photos!

#### Method B: If you run the AI Agent AFTER the photos are already in Lightroom
1. In Lightroom Classic, select all the DNG photos you just processed.
2. Right-click and choose **Metadata** ➡️ **Read Metadata from Files**.
3. Lightroom will read the `.xmp` files created by the agent, updating the star ratings and captions instantly.

> [!TIP]
> **Lightroom Setup Tip:** To ensure Lightroom Classic writes your manual ratings back to the sidecars, go to **Catalog Settings** ➡️ **Metadata** and check **"Automatically write changes into XMP"**.

---

## Using the Web App

1. **AI Provider**: In the settings sidebar, choose between **Google Gemini (Cloud)** and **Ollama (Local)**.
2. **Ollama configuration**: If you select Ollama, the app dynamically detects your local host and lists your downloaded vision models in a dropdown.
3. **Resuming Work**: Keep **"Skip photos with existing XMP reviews"** checked. If the process is stopped or crashes, restarting it will immediately skip already processed photos and resume where you left off.
4. **Select Folder**: Click **Browse** or paste the absolute path to your photo folder (e.g. `/Volumes/SSD/Photos/2026-06-27`).
5. Click **Start Analysis**.

---

## Developer CLI (Optional)

You can also run the agent via the terminal:

```bash
# Activate environment
source venv/bin/activate

# 1. Run the Single-Photo critique agent
python main.py "/path/to/photos" --provider ollama --model gemma4:12b --skip-existing

# 2. Run the Batch Curator on exported JPEGs for social media grouping
python curator.py "/path/to/exported_jpegs" --provider ollama --model gemma4:12b
```

### CLI Arguments for `main.py`:
* `source_dir`: Path to folder containing DNG files (Required).
* `--provider`: AI backend choice: `gemini` or `ollama` (default: `gemini`).
* `--model`: Model name (default: `gemini-2.5-flash` or `gemma4:12b` based on provider).
* `--ollama-host`: Local Ollama API host (default: `http://localhost:11434`).
* `--skip-existing`: Skip photos that already have an `.xmp` review.
* `--limit`: Limit number of photos to process (for testing).
* `--comment`: Session name or comment to write to index dashboard reports.
