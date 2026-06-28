import streamlit as st
import os
import json
import datetime
import subprocess
from dotenv import load_dotenv
load_dotenv()

from dng_utils import extract_thumbnail
from agent import analyze_photo, get_ollama_models
from main import generate_html_report, generate_master_index
from xmp_utils import generate_xmp_sidecar

st.set_page_config(
    page_title="AI Photo Curation Agent",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if 'api_key' not in st.session_state:
    st.session_state.api_key = os.environ.get("GEMINI_API_KEY", "")
if 'ai_provider' not in st.session_state:
    st.session_state.ai_provider = "Google Gemini (Cloud)"
if 'ollama_host' not in st.session_state:
    st.session_state.ollama_host = "http://localhost:11434"
if 'ollama_model' not in st.session_state:
    st.session_state.ollama_model = "gemma4:12b"
if 'gemini_model' not in st.session_state:
    st.session_state.gemini_model = "gemini-2.5-flash"
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'results' not in st.session_state:
    st.session_state.results = []

st.title("📸 AI Photo Curation Agent")
st.markdown("""
Welcome to your AI photographer assistant! This tool uses Google's Gemini Vision or local Gemma 4 models to automatically review, score, and critique your raw DNG photos based on composition, complexity, and stylistic resemblance to the masters of street photography.
""")

# Sidebar settings
with st.sidebar:
    st.header("⚙️ Settings")
    
    ai_provider = st.selectbox(
        "AI Provider",
        ["Google Gemini (Cloud)", "Ollama (Local)"],
        index=0 if st.session_state.ai_provider == "Google Gemini (Cloud)" else 1,
        key="ai_provider_select"
    )
    st.session_state.ai_provider = ai_provider
    
    if ai_provider == "Google Gemini (Cloud)":
        api_key_input = st.text_input("Gemini API Key", value=st.session_state.api_key, type="password", help="Get this from https://aistudio.google.com/app/apikey")
        if api_key_input:
            st.session_state.api_key = api_key_input
            os.environ["GEMINI_API_KEY"] = api_key_input
            
        gemini_model = st.selectbox(
            "Gemini Model",
            ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-exp"],
            index=0 if st.session_state.gemini_model == "gemini-2.5-flash" else (1 if st.session_state.gemini_model == "gemini-2.5-pro" else 2)
        )
        st.session_state.gemini_model = gemini_model
        selected_model = gemini_model
    else:
        ollama_host = st.text_input("Ollama Host", value=st.session_state.ollama_host)
        st.session_state.ollama_host = ollama_host
        
        # Load models dynamically
        local_models = get_ollama_models(ollama_host)
        
        if local_models:
            default_idx = 0
            if "gemma4:12b" in local_models:
                default_idx = local_models.index("gemma4:12b")
            elif st.session_state.ollama_model in local_models:
                default_idx = local_models.index(st.session_state.ollama_model)
                
            selected_local_model = st.selectbox(
                "Ollama Model",
                local_models,
                index=default_idx,
                help="Select one of the installed local vision models. Gemma 4 models (e.g. gemma4:12b) are recommended."
            )
            st.session_state.ollama_model = selected_local_model
            selected_model = selected_local_model
            st.success(f"Connected! Found {len(local_models)} local models.")
        else:
            st.warning("⚠️ Could not connect to Ollama or no models installed. Make sure Ollama is running (`ollama serve`) and has a vision model installed (e.g. `gemma4:12b`).")
            selected_local_model = st.text_input(
                "Specify Model Name",
                value=st.session_state.ollama_model,
                help="Type the exact name of the Ollama model (e.g., gemma4:12b)"
            )
            st.session_state.ollama_model = selected_local_model
            selected_model = selected_local_model
        
    st.markdown("---")
    st.subheader("Analysis Configuration")
    output_dir = st.text_input("Output Folder Name", value="agent_output")
    session_date = st.date_input("Session Date", value=datetime.date.today())
    comment = st.text_input("Session Name / Comment (Optional)", placeholder="e.g., Street Walk with Leica Q3")
    limit_photos = st.number_input("Limit Photos (0 = No limit)", min_value=0, value=0, help="Useful for quickly testing on a few photos first.")
    skip_existing = st.checkbox("Skip photos with existing XMP reviews", value=True, help="If a .xmp sidecar file already exists for a photo and contains a review, load the cached review instead of calling the AI.")
    
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
    source_dir = st.text_input("Path to DNG folder:", value=st.session_state.folder_path, placeholder="/Volumes/T9/Pictures CC/2026/03-01", help="Select or paste the absolute path to your folder containing DNG files.")
with col2:
    st.button("📁 Browse...", on_click=pick_folder, width="stretch")

if st.button("🚀 Start Analysis", type="primary", width="stretch"):
    is_valid = True
    if st.session_state.ai_provider == "Google Gemini (Cloud)":
        if not st.session_state.api_key:
            st.error("Please provide a Gemini API Key in the sidebar.")
            is_valid = False
            
    if is_valid:
        if not source_dir or not os.path.exists(source_dir):
            st.error(f"The directory '{source_dir}' does not exist. Please check the path and try again.")
            is_valid = False
            
    if is_valid:
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
            st.session_state.processing = False
        else:
            st.info(f"Found {len(dng_files)} DNG files to process. Starting analysis...")
            
            # Pre-extract thumbnails in parallel to optimize CPU utilization
            st.write("### ⚙️ Optimizing CPU: Pre-extracting photo thumbnails in parallel...")
            pre_progress = st.progress(0)
            pre_status = st.empty()
            
            from concurrent.futures import ThreadPoolExecutor
            max_workers = min(8, os.cpu_count() or 4)
            
            def pre_extract(fname):
                try:
                    dng_p = os.path.join(source_dir, fname)
                    extract_thumbnail(dng_p, cache_dir)
                except Exception as e:
                    print(f"Error pre-extracting {fname}: {e}")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                total_files = len(dng_files)
                for idx, _ in enumerate(executor.map(pre_extract, dng_files)):
                    pre_progress.progress((idx + 1) / total_files)
                    pre_status.text(f"Cached {idx+1}/{total_files} thumbnails...")
            
            pre_progress.empty()
            pre_status.empty()
            
            st.write("### ⏱️ Processing Progress")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            st.write("### 📸 Recently Analyzed (Showing last 3)")
            recent_container = st.empty()
            
            for i, filename in enumerate(dng_files):
                dng_path = os.path.join(source_dir, filename)
                
                # Check for existing XMP review
                analysis = None
                xmp_path = os.path.splitext(dng_path)[0] + ".xmp"
                
                if skip_existing and os.path.exists(xmp_path):
                    status_text.text(f"Loading existing XMP review ({i+1}/{len(dng_files)}): {filename} ...")
                    from xmp_utils import read_xmp_sidecar
                    analysis = read_xmp_sidecar(xmp_path)
                    if analysis:
                        # Extract Thumbnail for display grid/reports (fast)
                        thumb_path = extract_thumbnail(dng_path, cache_dir)
                
                if not analysis:
                    status_text.text(f"Processing ({i+1}/{len(dng_files)}): {filename} ...")
                    # Extract Thumbnail
                    thumb_path = extract_thumbnail(dng_path, cache_dir)
                    
                    if thumb_path:
                        final_photographers = list(photographers_choice)

                        # Analyze via selected provider
                        provider_val = "gemini" if st.session_state.ai_provider == "Google Gemini (Cloud)" else "ollama"
                        analysis = analyze_photo(
                            thumb_path, 
                            model_name=selected_model, 
                            style=style_choice, 
                            photographers=final_photographers,
                            provider=provider_val,
                            ollama_host=st.session_state.ollama_host
                        )
                
                # If we have a successful analysis (either from AI or loaded from XMP)
                if analysis and thumb_path:
                    final_photographers = list(photographers_choice)
                    result = {
                        "filename": filename,
                        "dng_path": dng_path,
                        "thumb_path": thumb_path,
                        "score": analysis.get("score", 0),
                        "is_promising": analysis.get("is_promising", False),
                        "critique_bullets": analysis.get("critique_bullets", [])
                    }
                    st.session_state.results.append(result)
                    
                    # Generate/Update XMP Sidecar for Lightroom
                    generate_xmp_sidecar(
                        dng_path=dng_path,
                        score=analysis.get("score", 0),
                        is_promising=analysis.get("is_promising", False),
                        critique_bullets=analysis.get("critique_bullets", []),
                        style=style_choice,
                        photographers=final_photographers
                    )
                    
                    # Display real-time sliding window (last 3 photos) to prevent memory bloating
                    with recent_container.container():
                        recent_photos = st.session_state.results[-3:]
                        r_cols = st.columns(len(recent_photos) if len(recent_photos) > 0 else 1)
                        for r_idx, res in enumerate(recent_photos):
                            with r_cols[r_idx]:
                                st.image(res['thumb_path'], caption=f"{res['filename']} (Score: {res['score']}/10)", width="stretch")
                                if res['is_promising']:
                                    st.success("Promising Candidate!")
                                else:
                                    st.info("Review Standard")
                                with st.expander("Show AI Critique"):
                                    for bullet in res['critique_bullets']:
                                        st.write(f"- {bullet}")
                
                # Periodically collect garbage to free up RAM
                if (i + 1) % 20 == 0:
                    import gc
                    gc.collect()
                
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
