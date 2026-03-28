import os
import argparse
import json
import datetime
from tqdm import tqdm
from dng_utils import extract_thumbnail, process_directory
from agent import analyze_photo

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Photo Curation Review</title>
    <style>
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background-color: #f5f5f7; color: #1d1d1f; margin: 0; padding: 40px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 50px; }}
        .filter-bar {{ display: flex; gap: 10px; justify-content: center; margin-bottom: 30px; }}
        .filter-btn {{ padding: 10px 20px; border-radius: 20px; border: 1px solid #ccc; background: white; cursor: pointer; font-size: 1rem; font-weight: 500; transition: all 0.2s; }}
        .filter-btn.active {{ background: #1a73e8; color: white; border-color: #1a73e8; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 30px; }}
        .card {{ background: white; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.05); transition: transform 0.2s; }}
        .card.hidden {{ display: none; }}
        .card:hover {{ transform: translateY(-5px); }}
        .card img {{ width: 100%; height: 260px; object-fit: cover; }}
        .card-content {{ padding: 24px; }}
        .filename {{ font-weight: 600; font-size: 1.2rem; margin-bottom: 8px; }}
        .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; margin-bottom: 16px; }}
        .badge.promising {{ background-color: #e3f2fd; color: #1565c0; }}
        .badge.not-promising {{ background-color: #fce4ec; color: #c2185b; }}
        .score {{ font-size: 1.1rem; font-weight: bold; margin-bottom: 16px; }}
        .critique {{ font-size: 0.95rem; line-height: 1.5; color: #424245; }}
        .critique ul {{ padding-left: 20px; margin-top: 8px; }}
        .critique li {{ margin-bottom: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Photo Selection Review</h1>
            <p>Scanned directory: {source_dir}</p>
        </div>
        <div class="filter-bar">
            <button class="filter-btn active" onclick="filterCards('all', event)">All Photos</button>
            <button class="filter-btn" onclick="filterCards('promising', event)">Promising Candidates</button>
        </div>
        <div class="grid">
            {cards}
        </div>
    </div>
    
    <script>
        function filterCards(filterType, event) {{
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            if(event) event.target.classList.add('active');
            
            document.querySelectorAll('.card').forEach(card => {{
                if (filterType === 'all') {{
                    card.classList.remove('hidden');
                }} else if (filterType === 'promising') {{
                    if (card.querySelector('.badge.promising')) {{
                        card.classList.remove('hidden');
                    }} else {{
                        card.classList.add('hidden');
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>
"""

CARD_TEMPLATE = """
            <div class="card">
                <img src="{thumbnail_path}" loading="lazy" alt="{filename}">
                <div class="card-content">
                    <div class="filename">{filename}</div>
                    <div class="badge {badge_class}">{badge_text}</div>
                    <div class="score">Score: {score} / 10</div>
                    <div class="critique">
                        <strong>Artistic Critique:</strong>
                        <ul>
                            {bullets}
                        </ul>
                    </div>
                </div>
            </div>
"""

INDEX_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photo Review History</title>
    <style>
        body {{ font-family: 'Inter', -apple-system, sans-serif; background-color: #f5f5f7; color: #1d1d1f; margin: 0; padding: 40px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 50px; }}
        .year-section {{ margin-bottom: 40px; }}
        .year-header {{ font-size: 1.5rem; font-weight: 700; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; margin-bottom: 20px; }}
        .run-list {{ display: flex; flex-direction: column; gap: 15px; }}
        .run-item {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); text-decoration: none; color: inherit; display: flex; justify-content: space-between; align-items: center; transition: transform 0.2s; }}
        .run-item:hover {{ transform: translateY(-3px); }}
        .run-title {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 4px; }}
        .run-meta {{ font-size: 0.9rem; color: #666; }}
        .run-stats {{ text-align: right; }}
        .badge {{ background-color: #e3f2fd; color: #1565c0; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; display: inline-block; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Photo Review History</h1>
            <p>Select a previous review to view the results.</p>
        </div>
        <div class="run-list">
            {run_items}
        </div>
    </div>
</body>
</html>
"""

def generate_master_index(output_dir):
    runs_dir = os.path.join(output_dir, "runs")
    if not os.path.exists(runs_dir):
        return
        
    # We will collect all runs, then group them by Year
    runs_data = []
    
    for run_name in os.listdir(runs_dir):
        run_path = os.path.join(runs_dir, run_name)
        if not os.path.isdir(run_path):
            continue
            
        meta_path = os.path.join(run_path, "metadata.json")
        num_photos = 0
        promising = 0
        source_dir = "Unknown Source"
        session_date = "Unknown Date"
        
        # Parse timestamp from run_name as fallback
        dt = None
        try:
            parts = run_name.split("_")
            if len(parts) >= 2:
                dt = datetime.datetime.strptime(f"{parts[0]}_{parts[1]}", "%Y%m%d_%H%M%S")
                session_date = dt.strftime("%Y-%m-%d")
        except Exception:
            pass
            
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as f:
                    data = json.load(f)
                    # Support dict metadata if we changed the format to save session_date
                    if isinstance(data, dict):
                        session_date = data.get("session_date", session_date)
                        photos = data.get("photos", [])
                        num_photos = len(photos)
                        promising = sum(1 for d in photos if d.get("is_promising", False))
                        if photos:
                            source_dir = os.path.dirname(photos[0].get("dng_path", ""))
                    elif isinstance(data, list):
                        num_photos = len(data)
                        promising = sum(1 for d in data if d.get("is_promising", False))
                        if data:
                            source_dir = os.path.dirname(data[0].get("dng_path", ""))
            except Exception:
                pass
                
        # Parse year for grouping
        year = "Unknown Year"
        try:
            # Assumes session_date is formatted as YYYY-MM-DD
            parsed_date = datetime.datetime.strptime(session_date, "%Y-%m-%d")
            year = str(parsed_date.year)
            formatted_date = parsed_date.strftime("%B %d, %Y")
        except Exception:
            formatted_date = session_date
            # Try to grab year from run_name
            if dt:
                year = str(dt.year)
                formatted_date = dt.strftime("%B %d, %Y")
                
        runs_data.append({
            "run_name": run_name,
            "session_date_str": session_date,
            "year": year,
            "formatted_date": formatted_date,
            "source_dir": source_dir,
            "num_photos": num_photos,
            "promising": promising,
            "comment": data.get("comment", "") if isinstance(data, dict) else ""
        })

    # Group by year
    runs_by_year = {}
    for r in runs_data:
        y = r["year"]
        if y not in runs_by_year:
            runs_by_year[y] = []
        runs_by_year[y].append(r)
        
    runs_html = []
    
    # Sort years descending
    for year in sorted(runs_by_year.keys(), reverse=True):
        runs_html.append(f'<div class="year-section"><div class="year-header">{year}</div><div class="run-list">')
        
        # Sort runs within the year descending by session_date (string comparison works for YYYY-MM-DD)
        year_runs = sorted(runs_by_year[year], key=lambda x: x["session_date_str"], reverse=True)
        
        for r in year_runs:
            html = f'''
        <a href="runs/{r["run_name"]}/review_results.html" class="run-item">
            <div>
                <div class="run-title">{r["formatted_date"]} {f'<span style="font-weight:normal; color:#666;">- {r["comment"]}</span>' if r.get("comment") else ''}</div>
                <div class="run-meta">{r["source_dir"]}</div>
            </div>
            <div class="run-stats">
                <div style="margin-bottom: 4px;"><strong>{r["num_photos"]}</strong> photos</div>
                <div class="badge">{r["promising"]} promising</div>
            </div>
        </a>
        '''
            runs_html.append(html)
            
        runs_html.append('</div></div>')
        
    index_html = INDEX_TEMPLATE.format(run_items="".join(runs_html))
    with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
        
def generate_html_report(source_dir, results, output_file="review_results.html"):
    cards_html = []
    
    # Sort results by score descending
    sorted_results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)
    
    for res in sorted_results:
        filename = res["filename"]
        # Use relative path for the thumbnail so the HTML is portable
        thumb_path = os.path.join("thumbnails", filename.replace(".dng", ".jpg").replace(".DNG", ".jpg"))
        
        is_promising = res.get("is_promising", False)
        score = res.get("score", 0)
        bullets = "".join([f"<li>{b}</li>" for b in res.get("critique_bullets", [])])
        
        badge_class = "promising" if is_promising else "not-promising"
        badge_text = "Promising Candidate" if is_promising else "Review Standard"
        
        card = CARD_TEMPLATE.format(
            thumbnail_path=thumb_path,
            filename=filename,
            badge_class=badge_class,
            badge_text=badge_text,
            score=score,
            bullets=bullets
        )
        cards_html.append(card)
        
    html = HTML_TEMPLATE.format(
        source_dir=source_dir,
        cards="\n".join(cards_html)
    )
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)
        
    print(f"\nReport generated successfully: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="AI Photography Curation Agent")
    parser.add_argument("source_dir", help="Directory containing DNG files")
    parser.add_argument("--output_dir", default="agent_output", help="Directory to save thumbnails and report")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of photos to process (for testing)")
    parser.add_argument("--date", type=str, help="Enforce a specific date for this session (YYYY-MM-DD). If omitted, inferred from path.")
    parser.add_argument("--comment", type=str, default="", help="Optional comment/title (e.g., 'Street Walk with Leica Q3') to display in the index.")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.source_dir):
        print(f"Error: Directory {args.source_dir} not found.")
        return
        
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable is missing.")
        print("Please run: export GEMINI_API_KEY='your-key-here'")
        return
        
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Setup structured run directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path_slug = os.path.basename(os.path.normpath(args.source_dir))
    run_name = f"{timestamp}_{path_slug}"
    
    # Determine the session date from args, or infer from path, or fallback to today
    session_date = None
    if args.date:
        session_date = args.date
    else:
        # Try to infer from a path matching something like .../YYYY/MM-DD
        normalized = os.path.normpath(args.source_dir)
        parts = normalized.split(os.sep)
        if len(parts) >= 2:
            try:
                # E.g parts[-2] = "2026", parts[-1] = "03-01"
                yr = int(parts[-2])
                if len(parts[-1]) == 5 and parts[-1][2] == '-':
                    mo = int(parts[-1][0:2])
                    da = int(parts[-1][3:5])
                    session_date = f"{yr:04d}-{mo:02d}-{da:02d}"
            except ValueError:
                pass
    if not session_date:
        session_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    runs_dir = os.path.join(args.output_dir, "runs")
    os.makedirs(runs_dir, exist_ok=True)
    
    run_dir = os.path.join(runs_dir, run_name)
    os.makedirs(run_dir, exist_ok=True)
    
    cache_dir = os.path.join(run_dir, "thumbnails")
    os.makedirs(cache_dir, exist_ok=True)
    
    print(f"Scanning {args.source_dir} for DNGs...")
    dng_files = [f for f in os.listdir(args.source_dir) if f.lower().endswith('.dng')]
    
    if args.limit > 0:
        dng_files = dng_files[:args.limit]
        
    print(f"Found {len(dng_files)} DNG files to process.")
    
    results = []
    
    for filename in tqdm(dng_files, desc="Processing Photos"):
        dng_path = os.path.join(args.source_dir, filename)
        
        # 1. Extract JPEG
        thumb_path = extract_thumbnail(dng_path, cache_dir)
        
        if not thumb_path:
            continue
            
        # 2. Analyze with Gemini
        analysis = analyze_photo(thumb_path)
        
        # 3. Store result
        result = {
            "filename": filename,
            "dng_path": dng_path,
            "thumb_path": thumb_path,
            "score": analysis.get("score", 0),
            "is_promising": analysis.get("is_promising", False),
            "critique_bullets": analysis.get("critique_bullets", [])
        }
        results.append(result)
        
        # Save intermediate JSON using a dictionary format to store root metadata
        run_metadata = {
            "session_date": session_date,
            "comment": args.comment,
            "photos": results
        }
        with open(os.path.join(run_dir, "metadata.json"), "w") as f:
            json.dump(run_metadata, f, indent=2)
            
    # 4. Generate HTML for this specific run
    report_path = os.path.join(run_dir, "review_results.html")
    generate_html_report(args.source_dir, results, output_file=report_path)
    
    # 5. Generate Master Index
    generate_master_index(args.output_dir)
    
if __name__ == "__main__":
    main()
