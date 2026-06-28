import streamlit as st
import os
import tempfile
from curator import analyze_portfolio_batch

st.set_page_config(
    page_title="Portfolio Curator",
    page_icon="✨",
    layout="wide",
)

st.title("✨ Portfolio & Social Curator")
st.markdown("""
Welcome to the final step of your workflow! 
Upload your **final, edited JPEGs** here. The AI will view the entire batch and:
1. Group them into thematic social media posts with captions.
2. Pick the absolute best images for your permanent portfolio.

**iPad Users:** Tap "Browse files" below to select photos directly from your Photo Library!
""")

uploaded_files = st.file_uploader("Select Exported JPEGs", type=['jpg', 'jpeg', 'png'], accept_multiple_files=True)

if uploaded_files:
    st.info(f"{len(uploaded_files)} images ready for curation.")
    
    if st.button("✨ Analyze Batch", type="primary"):
        # Retrieve settings from session state
        provider = st.session_state.get("ai_provider", "Google Gemini (Cloud)")
        provider_val = "gemini" if provider == "Google Gemini (Cloud)" else "ollama"
        
        is_valid = True
        if provider_val == "gemini":
            if not os.environ.get("GEMINI_API_KEY") and 'api_key' in st.session_state and st.session_state.api_key:
                os.environ["GEMINI_API_KEY"] = st.session_state.api_key
                
            if not os.environ.get("GEMINI_API_KEY"):
                st.error("Please set your Gemini API Key in the main app page sidebar first.")
                is_valid = False
                
        if is_valid:
            with st.spinner("Analyzing batch... This might take a minute."):
                # Save uploaded files to a temporary directory
                with tempfile.TemporaryDirectory() as temp_dir:
                    file_paths = []
                    for uploaded_file in uploaded_files:
                        temp_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        file_paths.append(temp_path)
                        
                    # Retrieve host and model
                    if provider_val == "gemini":
                        model_name = st.session_state.get("gemini_model", "gemini-2.5-pro")
                        # Curation is better suited for a larger model like gemini-2.5-pro
                        if model_name == "gemini-2.5-flash":
                            model_name = "gemini-2.5-pro"
                        host = ""
                    else:
                        model_name = st.session_state.get("ollama_model", "gemma4:12b")
                        host = st.session_state.get("ollama_host", "http://localhost:11434")
                        
                    # Call the curator logic
                    results = analyze_portfolio_batch(
                        file_paths,
                        model_name=model_name,
                        provider=provider_val,
                        host=host
                    )
                    
            if results:
                st.success("Curation Complete!")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.header("📱 Social Media Themes")
                    for theme in results.get("themes", []):
                        with st.expander(f"Theme: {theme['theme_name']}", expanded=True):
                            st.markdown(f"**Caption:**\n\n{theme['social_media_caption']}")
                            st.markdown(f"**Photos to Include:**\n" + "\n".join([f"- {f}" for f in theme['included_filenames']]))
                            
                with col2:
                    st.header("🏆 Portfolio Recommendations")
                    for rec in results.get("portfolio_recommendations", []):
                        with st.container():
                            st.subheader(rec['filename'])
                            st.markdown(f"**Title:** {rec['title']}")
                            st.markdown(f"**Why it stands out:** {rec['description']}")
                            st.markdown(f"**Tags:** {', '.join(rec['tags'])}")
                            st.markdown("---")
                            
                st.header("💻 Developer Output (JSON)")
                st.json(results)
            else:
                st.error("An error occurred during analysis. Check the terminal logs.")
