
import json
import logging
from pathlib import Path

# Configure logging to see any hidden errors
logging.basicConfig(level=logging.DEBUG)

def debug_report_generation():
    # Use the report path provided by the user (update the timestamp if needed)
    # The user mentioned reports/20260130_161701 as the run dir
    # And report file at anthropic_v1_messages_20260130_161731/report.json
    
    # We need to find the actual latest report in ./reports directory because I don't know the exact random ID
    base_reports_dir = Path("reports")
    
    # Find the latest run directory
    try:
        run_dirs = sorted([d for d in base_reports_dir.iterdir() if d.is_dir()], key=lambda d: d.name, reverse=True)
        if not run_dirs:
            print("No report directories found in ./reports")
            return
        latest_run_dir = run_dirs[0]
        print(f"Checking run directory: {latest_run_dir}")
        
        # Find the anthropic report subdirectory
        subdirs = [d for d in latest_run_dir.iterdir() if d.is_dir() and "anthropic" in d.name]
        if not subdirs:
            print("No Anthropic report subdirectory found.")
            return
        
        report_subdir = subdirs[0]
        print(f"Checking report subdirectory: {report_subdir}")
        
        report_json_path = report_subdir / "report.json"
        
        if not report_json_path.exists():
            print(f"report.json missing at {report_json_path}")
            return
            
        print(f"Found report.json at {report_json_path}")
        
        with open(report_json_path, 'r') as f:
            report_data = json.load(f)
            
        # Try to import Formatter
        print("Importing ParameterTableFormatter...")
        from llm_spec.reporting.formatter import ParameterTableFormatter
        
        print("Initializing Formatter...")
        formatter = ParameterTableFormatter(report_data)
        
        print(f"Tested params count: {len(formatter.tested_params)}")
        print(f"Unsupported params count: {len(formatter.unsupported_params)}")
        
        print("Generating Markdown...")
        md_content = formatter.generate_markdown()
        print(f"Markdown content length: {len(md_content)}")
        if len(md_content) < 100:
            print("WARNING: Markdown content seems too short!")
            print(md_content)
            
        print("Generating HTML...")
        html_content = formatter.generate_html()
        print(f"HTML content length: {len(html_content)}")
        
        # Write files manually to test write permissions? 
        # Actually let's just see if generate works.
        
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_report_generation()
