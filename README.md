# AI Photo Curation Agent 📸🤖

Welcome to the AI Photo Curation Agent! This is a local application that automatically reviews a folder of your DNG photographs and evaluates them using Google's Gemini Vision AI. It provides an artistic critique on composition, complexity, and stylistic resemblance to master street photographers, and generates a beautiful HTML report.

## Prerequisites

1. **A Mac Computer**.
2. **Python Installed**: The agent needs Python to run. 
   - Open your Terminal and type `python3 --version`.
   - If it says "command not found", download and install Python from the [official site](https://www.python.org/downloads/macos/).
3. **A Gemini API Key**: The AI brain runs on Google's servers.
   - Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
   - Sign in and click **"Create API Key"**.
   - Copy the generated key. Note: this runs on Gemini's generous free tier for personal use.

## Setup & Running the App

We've provided a simple shortcut to get you started easily!

1. Open the folder containing this tool.
2. Double-click **`run.command`**.
   - *Mac Security Note:* If macOS says it's from an "unidentified developer", right-click `run.command` and select **Open**, then click Open in the prompt.
3. The Terminal will open, create a virtual environment, and install dependencies automatically.
4. On first run, it will ask for your **Gemini API Key**. Paste it and press Enter. (This creates a hidden `.env` file to securely store your key so it isn't uploaded to GitHub).
5. A beautiful **Web App will open in your browser**!

## Using the Agent

1. **Select Photos**: Click "Browse" or paste the path to a folder containing your `.dng` RAW files.
2. **Style Preferences**: Use the sidebar to configure your "Critique Style Preferences". Choose between Color, Black & White, or Any, and select famous photographers for stylistic inspiration.
3. **Start**: Click **Start Analysis**.

## Viewing Your Results

After analysis, results are shown directly in the app. However, a stunning permanent HTML report is also generated for you!

- Open the **`agent_output`** folder.
- Double-click **`index.html`** to view all your previous runs and drill down into the detailed critiques.

## Developer CLI (Optional)

You can also run the agent via the command line instead of the web app:

```bash
# Setup env and activate
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY='your_api_key'

# Run via CLI
python main.py "/path/to/dng/folder" --limit 5
```
