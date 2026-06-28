import os
import json
import argparse
import base64
import urllib.request
import urllib.error
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tqdm import tqdm

def analyze_portfolio_batch(image_paths, model_name="gemini-2.5-pro", provider="gemini", host="http://localhost:11434"):
    """
    Sends a batch of exported JPEGs to the specified provider (Gemini or Ollama) for final curation.
    """
    if provider.lower() == "ollama":
        # Load and base64-encode all images
        print(f"Encoding {len(image_paths)} images for local curation...")
        images_base64 = []
        for path in tqdm(image_paths, desc="Encoding"):
            try:
                with open(path, "rb") as image_file:
                    images_base64.append(base64.b64encode(image_file.read()).decode("utf-8"))
            except Exception as e:
                print(f"Error encoding {path}: {e}")
                
        if not images_base64:
            print("No valid images encoded.")
            return None
            
        prompt = """
        You are an expert photography curator and social media manager.
        I have provided a batch of my final, edited photographs.
        
        Please analyze all of these images together and do the following:
        1. Cluster them into thematic series (e.g., "Neon Shadows", "Urban Solitude", "Street Portraits").
        2. Write a captivating Instagram/Social Media caption to introduce each series, along with a few relevant hashtags.
        3. Identify the absolute strongest 1 to 3 images from the entire batch to add to my online portfolio.
        
        Return your response strictly in JSON format matching the schema below.
        """
        
        response_schema = {
            "type": "object",
            "properties": {
                "themes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "theme_name": {"type": "string"},
                            "social_media_caption": {"type": "string", "description": "Engaging text with hashtags for posting this series."},
                            "included_filenames": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["theme_name", "social_media_caption", "included_filenames"]
                    }
                },
                "portfolio_recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string"},
                            "title": {"type": "string", "description": "A poetic or descriptive title for the photo."},
                            "description": {"type": "string", "description": "Why this photo stands out and belongs in the portfolio."},
                            "tags": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["filename", "title", "description", "tags"]
                    }
                }
            },
            "required": ["themes", "portfolio_recommendations"]
        }
        
        url = f"{host.rstrip('/')}/api/chat"
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": images_base64
                }
            ],
            "format": response_schema,
            "options": {
                "temperature": 0.7
            },
            "stream": False
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        print(f"Running curation with local model '{model_name}'...")
        try:
            # Multi-image curation can take a very long time locally, set timeout to 300s
            with urllib.request.urlopen(req, timeout=300) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                content = res_data["message"]["content"].strip()
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                return json.loads(content.strip())
        except urllib.error.URLError as e:
            print(f"Connection to Ollama failed: {e}")
            return None
        except Exception as e:
            print(f"Error during Ollama curation: {e}")
            return None

    # Gemini (cloud) curation workflow:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
        
    client = genai.Client(api_key=api_key)
    
    # Upload all files
    print(f"Uploading {len(image_paths)} images to Gemini...")
    uploaded_files = []
    for path in tqdm(image_paths, desc="Uploading"):
        f = client.files.upload(file=path, config={'display_name': os.path.basename(path)})
        uploaded_files.append(f)
        
    prompt = """
    You are an expert photography curator and social media manager.
    I have provided a batch of my final, edited photographs.
    
    Please analyze all of these images together and do the following:
    1. Cluster them into thematic series (e.g., "Neon Shadows", "Urban Solitude", "Street Portraits").
    2. Write a captivating Instagram/Social Media caption to introduce each series, along with a few relevant hashtags.
    3. Identify the absolute strongest 1 to 3 images from the entire batch to add to my online portfolio.
    
    Return your response strictly in JSON format matching the schema below.
    """
    
    response_schema = {
        "type": "object",
        "properties": {
            "themes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "theme_name": {"type": "string"},
                        "social_media_caption": {"type": "string", "description": "Engaging text with hashtags for posting this series."},
                        "included_filenames": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["theme_name", "social_media_caption", "included_filenames"]
                }
            },
            "portfolio_recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string"},
                        "title": {"type": "string", "description": "A poetic or descriptive title for the photo."},
                        "description": {"type": "string", "description": "Why this photo stands out and belongs in the portfolio."},
                        "tags": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["filename", "title", "description", "tags"]
                }
            }
        },
        "required": ["themes", "portfolio_recommendations"]
    }
    
    print("Analyzing batch...")
    try:
        contents = uploaded_files + [prompt]
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=response_schema
            )
        )
        
        # Cleanup
        print("Cleaning up files...")
        for f in uploaded_files:
            client.files.delete(name=f.name)
            
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
        
    except Exception as e:
        print(f"Error during curation: {e}")
        # Cleanup on failure
        for f in uploaded_files:
            try:
                client.files.delete(name=f.name)
            except:
                pass
        return None

def main():
    parser = argparse.ArgumentParser(description="AI Portfolio Curator")
    parser.add_argument("source_dir", help="Directory containing exported JPEG files")
    parser.add_argument("--output", default="curation_results.json", help="Output JSON file path")
    parser.add_argument("--provider", default="gemini", choices=["gemini", "ollama"], help="AI provider (gemini or ollama)")
    parser.add_argument("--model", help="AI model name")
    parser.add_argument("--ollama-host", default="http://localhost:11434", help="Ollama Host URL")
    args = parser.parse_args()
    
    model_name = args.model
    if not model_name:
        model_name = "gemini-2.5-pro" if args.provider == "gemini" else "gemma4:12b"
        
    if not os.path.exists(args.source_dir):
        print(f"Directory not found: {args.source_dir}")
        return
        
    image_paths = []
    for f in os.listdir(args.source_dir):
        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_paths.append(os.path.join(args.source_dir, f))
            
    if not image_paths:
        print("No JPEG/PNG files found in the directory.")
        return
        
    print(f"Found {len(image_paths)} images for curation.")
    # Sort files just so they are consistent
    image_paths.sort()
    
    results = analyze_portfolio_batch(image_paths, model_name=model_name, provider=args.provider, host=args.ollama_host)
    if results:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nCuration complete! Results saved to {args.output}")
        print("\n=== Social Media Themes ===")
        for theme in results.get("themes", []):
            print(f"\nTheme: {theme['theme_name']}")
            print(f"Caption: {theme['social_media_caption']}")
            print(f"Files: {', '.join(theme['included_filenames'])}")
            
        print("\n=== Portfolio Recommendations ===")
        for rec in results.get("portfolio_recommendations", []):
            print(f"\nFile: {rec['filename']}")
            print(f"Title: {rec['title']}")
            print(f"Why: {rec['description']}")
            print(f"Tags: {', '.join(rec['tags'])}")

if __name__ == "__main__":
    main()

