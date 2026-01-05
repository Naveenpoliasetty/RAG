
import sys
import os

# Add the project root to python path
sys.path.append(os.getcwd())

from src.data_acquisition.parser import parse_resume

def test_summary_regex():
    # Simulate data with "PROFESSIONAL SUMMARY" instead of just "SUMMARY"
    json_data = {
        "job_role": "Developer",
        "structured_content": [
            {"type": "p", "text": "PROFESSIONAL SUMMARY"},
            {"type": "ul", "items": ["Summary item 1", "Summary item 2"]},
            {"type": "p", "text": "TECHNICAL SKILLS"},
            {"type": "p", "text": "Python"},
            {"type": "p", "text": "PROFESSIONAL EXPERIENCE"},
            {"type": "p", "text": "Confidential"},
            {"type": "p", "text": "Dev"},
            {"type": "ul", "items": ["Work"]}
        ]
    }

    print("Parsing resume with PROFESSIONAL SUMMARY...")
    result = parse_resume(json_data)
    
    summary = result.get("professional_summary", [])
    print(f"Found {len(summary)} summary items.")
    
    if len(summary) > 0:
        print("SUCCESS: Summary found.")
        print(summary)
    else:
        print("FAILURE: No summary found.")

if __name__ == "__main__":
    test_summary_regex()
