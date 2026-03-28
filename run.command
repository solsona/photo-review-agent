#!/bin/bash
# Move to the directory where the script is located
cd "$(dirname "$0")"

clear
echo "========================================================"
echo "          AI Photo Curation Agent Setup                 "
echo "========================================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null
then
    echo "❌ Python 3 was not found on your system."
    echo "Please download and install Python from https://www.python.org/downloads/macos/"
    echo "Wait for the installation to finish, and try running this script again."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo "✅ Python is installed."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating a Python virtual environment (this keeps things clean)..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "📥 Checking and installing required packages (this might take a few minutes)..."
pip install -q -r requirements.txt
echo "✅ Packages installed."

# Check for .env file and GEMINI_API_KEY
if [ ! -f ".env" ]; then
    echo ""
    echo "========================================================"
    echo "  🔑 First time setup: We need your Gemini API Key "
    echo "========================================================"
    echo "The agent uses Google's Gemini AI to review your photos."
    echo "You need an API key to use it. Don't worry, it's easy and mostly free!"
    echo ""
    echo "1. Go to: https://aistudio.google.com/app/apikey"
    echo "2. Sign in with your Google account."
    echo "3. Click 'Create API Key' (you may need to accept terms and create a project)."
    echo "   *Note: If prompted for a billing account, you can usually proceed with the free tier limits without setting one up depending on your region.*"
    echo "4. Copy the long string of characters it gives you."
    echo ""
    read -p "Paste your Gemini API Key here and press Enter: " api_key
    
    # Simple validation to ensure it's not empty
    if [ ! -z "$api_key" ]; then
        echo "GEMINI_API_KEY=$api_key" > .env
        echo "✅ API Key successfully saved!"
    else
        echo "⚠️  No API Key provided. You can type it directly inside the app."
    fi
fi

echo ""
echo "========================================================"
echo "  🚀 Starting the Agent Web App! "
echo "========================================================"
echo "This will open a new tab in your browser. Just leave this terminal running in the background."

# Run Streamlit
streamlit run app.py

echo ""
read -p "Press Enter to close this window..."
