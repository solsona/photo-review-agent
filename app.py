import streamlit as st
import os
import json
import datetime
import subprocess
from dng_utils import extract_thumbnail
from agent import analyze_photo
from main import generate_html_report, generate_master_index

st.set_page_config(
    page_title="AI Photo Curation Agent",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if 'api_key' not in st.session_state:
    st.session_state.api_key = os.environ.get("GEMINI_API_KEY", "")
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'results' not in st.session_state:
    st.session_state.results = []

st.title("📸 AI Photo Curation Agent")
st.markdown("""
Welcome to your AI photographer assistant! This tool uses Google's Gemini Vision to automatically review, score, and critique your raw DNG photos based on composition, complexity, and stylistic resemblance to the masters of street photography.
""")

# Sidebar settings
with st.sidebar:
    st.header("⚙️ Settings")
    api_key_input = st.text_input("Gemini API Key", value=st.session_state.api_key, type="password", help="Get this from https://aistudio.google.com/app/apikey")
    if api_key_input:
        st.session_state.api_key = api_key_input
        os.environ["GEMINI_API_KEY"] = api_key_input
        
    st.markdown("---")
    st.subheader("Analysis Configuration")
    output_dir = st.text_input("Output Folder Name", value="agent_output")
    session_date = st.date_input("Session Date", value=datetime.date.today())
    comment = st.text_input("Session Name / Comment (Optional)", placeholder="e.g., Street Walk with Leica Q3")
    limit_photos = st.number_input("Limit Photos (0 = No limit)", min_value=0, value=0, help="Useful for quickly testing on a few photos first.")
    
    st.markdown("---")
    st.subheader("Critique Style Preferences")
    
    # Initialize session states for custom photographers
    if 'selected_photogs' not in st.session_state:
        st.session_state.selected_photogs = ["Vivian Maier", "Alex Webb", "Alan Schaller"]
    if 'custom_photogs' not in st.session_state:
        st.session_state.custom_photogs = []
    if 'prev_style' not in st.session_state:
        st.session_state.prev_style = "Any"

    style_choice = st.selectbox("Photography Style", ["Any", "Color", "Black & White (Monochrome)"])
    
    if style_choice != st.session_state.prev_style:
        if style_choice == "Color":
            st.session_state.selected_photogs = ["Alex Webb", "Saul Leiter", "Joel Meyerowitz"]
        elif style_choice == "Black & White (Monochrome)":
            st.session_state.selected_photogs = ["Fan Ho", "Henri Cartier-Bresson", "Alan Schaller"]
        else:
            st.session_state.selected_photogs = ["Vivian Maier", "Alex Webb", "Alan Schaller"]
        st.session_state.prev_style = style_choice

    if style_choice == "Color":
        suggested_photographers = ["Alex Webb", "Saul Leiter", "Joel Meyerowitz", "William Eggleston", "Fred Herzog", "Harry Gruyaert"]
    elif style_choice == "Black & White (Monochrome)":
        suggested_photographers = ["Fan Ho", "Henri Cartier-Bresson", "Alan Schaller", "Daido Moriyama", "Vivian Maier", "Sebastião Salgado"]
    else:
        suggested_photographers = ["Vivian Maier", "Alex Webb", "Alan Schaller", "Fan Ho", "Henri Cartier-Bresson", "Saul Leiter"]
        
    def add_custom_photog():
        val = st.session_state.custom_photog_in
        if val:
            for p in val.split(","):
                p = p.strip()
                if p:
                    if p not in st.session_state.custom_photogs:
                        st.session_state.custom_photogs.append(p)
                    if p not in st.session_state.selected_photogs:
                        st.session_state.selected_photogs.append(p)
        st.session_state.custom_photog_in = ""

    all_options = []
    for p in suggested_photographers + st.session_state.custom_photogs:
        if p not in all_options:
            all_options.append(p)

    st.session_state.selected_photogs = [p for p in st.session_state.selected_photogs if p in all_options]

    photographers_choice = st.multiselect(
        "Photographer Inspiration",
        options=all_options,
        key="selected_photogs",
        help="Select the master photographers you'd like the AI to compare your photos against."
    )
    st.text_input("Other Photographers", key="custom_photog_in", on_change=add_custom_photog, placeholder="e.g., Tatsuo Suzuki, Robert Frank", help="Type a name and press Enter to add to the list above.")
    
st.header("📂 Select Photos")

# Initialize folder_path in session state
if "folder_path" not in st.session_state:
    st.session_state.folder_path = ""

def pick_folder():
    script = 'return POSIX path of (choose folder with prompt "Select the folder containing your DNG photos:")'
    try:
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            st.session_state.folder_path = result.stdout.strip()
    except Exception as e:
        st.error(f"Error selecting folder: {e}")

col1, col2 = st.columns([5, 1], vertical_alignment="bottom")
with col1:
    # Use the session stat directly as the value so it maps immediately
    source_dir = st.text_input("Path to DNG folder:", value=st.session_state.folder_path, placeholder="/Volumes/T9/Pictures CC/2026/03-01", help="Select or paste the absolute path to your folder containing DNG files.")
with col2:
    # The 'on_click' triggers the picker BEFORE rerending the UI
    st.button("📁 Browse...", on_click=pick_folder, width="stretch")

if st.button("🚀 Start Analysis", type="primary", width="stretch"):
    if not st.session_state.api_key:
        st.error("Please provide a Gemini API Key in the sidebar.")
    elif not source_dir or not os.path.exists(source_dir):
        st.error(f"The directory '{source_dir}' does not exist. Please check the path and try again.")
    else:
        st.session_state.processing = True
        st.session_state.results = []
        
        # Setup directories
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path_slug = os.path.basename(os.path.normpath(source_dir))
        run_name = f"{timestamp}_{path_slug}"
        
        runs_dir = os.path.join(output_dir, "runs")
        os.makedirs(runs_dir, exist_ok=True)
        
        run_dir = os.path.join(runs_dir, run_name)
        os.makedirs(run_dir, exist_ok=True)
        
        cache_dir = os.path.join(run_dir, "thumbnails")
        os.makedirs(cache_dir, exist_ok=True)
        
        dng_files = [f for f in os.listdir(source_dir) if f.lower().endswith('.dng')]
        if limit_photos > 0:
            dng_files = dng_files[:limit_photos]
            
        if not dng_files:
            st.warning("No DNG files found in the specified directory.")
        else:
            st.info(f"Found {len(dng_files)} DNG files to process. Starting analysis...")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Placeholders for grid display
            results_container = st.container()
            
            cols = results_container.columns(3)
            
            for i, filename in enumerate(dng_files):
                dng_path = os.path.join(source_dir, filename)
                status_text.text(f"Processing ({i+1}/{len(dng_files)}): {filename} ...")
                
                # Extract Thumbnail
                thumb_path = extract_thumbnail(dng_path, cache_dir)
                
                if thumb_path:
                    final_photographers = list(photographers_choice)

                    # Analyze via Gemini
                    analysis = analyze_photo(thumb_path, style=style_choice, photographers=final_photographers)
                    
                    result = {
                        "filename": filename,
                        "dng_path": dng_path,
                        "thumb_path": thumb_path,
                        "score": analysis.get("score", 0),
                        "is_promising": analysis.get("is_promising", False),
                        "critique_bullets": analysis.get("critique_bullets", [])
                    }
                    st.session_state.results.append(result)
                    
                    # Display real-time in the grid
                    col = cols[i % 3]
                    with col:
                        # Using relative paths for streamlit local image display works best if we use the absolute path 
                        # or read the file. Streamlit's st.image uses the absolute path directly.
                        st.image(thumb_path, caption=f"Score: {result['score']}/10", width="stretch")
                        if result['is_promising']:
                            st.success(f"{filename} - Promising!")
                        else:
                            st.info(f"{filename}")
                        with st.expander("Show AI Critique"):
                            for bullet in result['critique_bullets']:
                                st.write(f"- {bullet}")
                
                # Update progress
                progress_bar.progress((i + 1) / len(dng_files))
                
            status_text.text("Saving reports...")
            
            # Save metadata and reports
            run_metadata = {
                "session_date": session_date.strftime("%Y-%m-%d"),
                "comment": comment,
                "photos": st.session_state.results
            }
            with open(os.path.join(run_dir, "metadata.json"), "w") as f:
                json.dump(run_metadata, f, indent=2)
                
            report_path = os.path.join(run_dir, "review_results.html")
            master_index_path = os.path.join(output_dir, "index.html")
            generate_html_report(source_dir, st.session_state.results, output_file=report_path)
            generate_master_index(output_dir)
            
            # Save paths in session state so buttons can be rendered outside
            st.session_state.last_report = os.path.abspath(report_path)
            st.session_state.last_index = os.path.abspath(master_index_path)
            
            st.success(f"🎉 Analysis Complete! Processed {len(dng_files)} photos.")
            
            st.session_state.processing = False

if len(st.session_state.results) > 0 and not st.session_state.processing:
    if "last_report" in st.session_state and "last_index" in st.session_state:
        st.markdown("### 📊 Reports")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📄 Open HTML Report", use_container_width=True, type="primary"):
                subprocess.run(["open", st.session_state.last_report])
        with col2:
            if st.button("📁 Open Master Index", use_container_width=True):
                subprocess.run(["open", st.session_state.last_index])
                
    st.markdown("---")
    st.subheader("🏆 Top Rated Photos from Last Run")
    sorted_results = sorted(st.session_state.results, key=lambda x: x.get("score", 0), reverse=True)
    
    # Display the top 6 photos
    top_photos = sorted_results[:6]
    top_cols = st.columns(min(3, len(top_photos)) if len(top_photos) > 0 else 1)
    
    for i, res in enumerate(top_photos):
        col = top_cols[i % 3]
        with col:
            st.image(res['thumb_path'], width="stretch")
            st.metric(label=res['filename'], value=f"{res['score']}/10")
            if res['is_promising']:
                st.markdown("🌟 **Promising Candidate**")
