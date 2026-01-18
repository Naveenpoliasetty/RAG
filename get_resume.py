#!/usr/bin/env python3
"""
Script to retrieve and display the entire resume for a given resume_id.
"""

import sys
import json
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.resume_ingestion.database import MongoDBManager


def get_resume(resume_id: str, output_file: str = None):
    """
    Retrieve and display the entire resume for a given resume_id.
    
    Args:
        resume_id: The resume ID to fetch
        output_file: Optional path to save the resume as JSON
    """
    # Initialize MongoDB manager
    manager = MongoDBManager()
    
    try:
        # Fetch the complete resume
        resume = manager.get_resume_by_id(resume_id)
        
        if resume is None:
            print(f"❌ Resume not found for ID: {resume_id}")
            return None
        
        # Remove MongoDB's _id field for cleaner output
        resume.pop('_id', None)
        
        # Display resume information
        print("=" * 80)
        print(f"📄 Resume ID: {resume_id}")
        print("=" * 80)
        
        # Print key fields
        if 'resume_id' in resume:
            print(f"\n🆔 Resume ID: {resume['resume_id']}")
        
        if 'qdrant_status' in resume:
            print(f"📊 Status: {resume['qdrant_status']}")
        
        # Print all sections
        print("\n" + "=" * 80)
        print("📋 Resume Sections:")
        print("=" * 80)
        
        for key, value in resume.items():
            if key not in ['resume_id', 'qdrant_status', '_id', 'ingested_at', 
                          'last_processed', 'processing_started', 'failed_at', 'error']:
                print(f"\n🔹 {key.upper().replace('_', ' ')}:")
                if isinstance(value, dict):
                    print(json.dumps(value, indent=2, ensure_ascii=False))
                elif isinstance(value, list):
                    if value:
                        print(json.dumps(value, indent=2, ensure_ascii=False))
                    else:
                        print("  (empty)")
                elif isinstance(value, str):
                    # Print first 500 chars if very long
                    if len(value) > 500:
                        print(f"  {value[:500]}...")
                        print(f"  ... (truncated, total length: {len(value)} characters)")
                    else:
                        print(f"  {value}")
                else:
                    print(f"  {value}")
        
        # Save to file if requested
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(resume, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n✅ Resume saved to: {output_file}")
        
        return resume
        
    except Exception as e:
        print(f"❌ Error retrieving resume: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        manager.close()


if __name__ == "__main__":
    # Default resume_id from user's request
    resume_id = "bb5fd9e7-a57a-4c3e-af0e-88a90445aaf1"
    
    # Allow resume_id to be passed as command line argument
    if len(sys.argv) > 1:
        resume_id = sys.argv[1]
    
    # Optional output file
    output_file = None
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    print(f"🔍 Fetching resume for ID: {resume_id}\n")
    get_resume(resume_id, output_file)

