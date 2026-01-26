#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def main():
    print("Testing Groq Inference...")
    # Set the provider to Groq for this run
    os.environ["LLM_PROVIDER"] = "groq"
    
    # Import the main test logic
    from tests.test_llm import main as run_tests
    run_tests()

if __name__ == "__main__":
    main()
