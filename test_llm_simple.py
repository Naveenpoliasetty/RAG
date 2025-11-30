#!/usr/bin/env python3
"""
Simple test script to debug RunPod endpoint issues.
Tests with minimal configuration and detailed error output.
"""

import sys
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file
load_dotenv()

from src.utils.llm_client import load_llm_config, get_openai_client, get_llm_model

def main():
    print("=" * 70)
    print("Simple RunPod LLM Test")
    print("=" * 70)
    
    # Load config and check environment variables (same priority as get_openai_client)
    try:
        config = load_llm_config()
        
        # Check environment variables first (same priority as get_openai_client)
        base_url = os.getenv("RUNPOD_BASE_URL") or config.get("base_url")
        api_key = (
            os.getenv("RUNPOD_API_KEY") 
            or os.getenv("OPENAI_API_KEY")
            or config.get("api_key")
        )
        model = get_llm_model()
        
        print("\nConfiguration:")
        print(f"  Base URL: {base_url}")
        print(f"  Model: {model}")
        
        # Show where API key is coming from
        api_key_source = "Not set"
        if os.getenv("RUNPOD_API_KEY"):
            api_key_source = "Set (from RUNPOD_API_KEY env var)"
        elif os.getenv("OPENAI_API_KEY"):
            api_key_source = "Set (from OPENAI_API_KEY env var)"
        elif config.get("api_key"):
            api_key_source = "Set (from config.yaml)"
        print(f"  API Key: {api_key_source}")
        
        if not base_url:
            print("\n❌ No base_url configured!")
            return
        
        if not api_key:
            print("\n⚠️  Warning: No API key found in environment variables or config.yaml")
            print("   Make sure RUNPOD_API_KEY is set in your .env file")
        
        # Use get_openai_client() which handles environment variable priority correctly
        client = get_openai_client()
        
        print(f"\nTesting endpoint: {client.base_url}")
        print(f"Full URL will be: {client.base_url}/chat/completions")
        
        # Try a very simple request
        print("\nSending simple test request...")
        print(f"Model: {model}")
        print("Message: 'Hello, respond with just OK'")
        
        # Build request parameters
        request_params = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Hello, respond with just OK"}
            ],
            "max_tokens": 10,
            "temperature": 0.1
        }
        
        try:
            response = client.chat.completions.create(**request_params)
            
            print("\n✅ SUCCESS!")
            print(f"Response: {response.choices[0].message.content}")
            if response.usage:
                print(f"Tokens used: {response.usage.total_tokens}")
                
        except Exception as e:
            print(f"\n❌ ERROR: {type(e).__name__}")
            print(f"Message: {str(e)}")
            
            # Try to get response details
            if hasattr(e, 'response'):
                try:
                    print(f"\nResponse status: {e.response.status_code}")
                    print(f"Response headers: {dict(e.response.headers)}")
                    if hasattr(e.response, 'text'):
                        print(f"Response body: {e.response.text}")
                except Exception:
                    pass
            
            # Try with requests library for more details
            try:
                import requests
                print("\n" + "=" * 70)
                print("Testing with requests library for more details...")
                print("=" * 70)
                
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key or 'dummy-key'}"
                }
                
                # For direct requests, we can omit model (endpoint uses default)
                payload = {
                    "messages": [
                        {"role": "user", "content": "Hello"}
                    ],
                    "max_tokens": 10
                }
                # Note: Direct HTTP requests don't require model, but OpenAI client does
                
                url = f"{base_url.rstrip('/')}/chat/completions"
                print(f"\nPOST {url}")
                print(f"Headers: {json.dumps({k: v if k != 'Authorization' else 'Bearer ***' for k, v in headers.items()}, indent=2)}")
                print(f"Payload: {json.dumps(payload, indent=2)}")
                
                resp = requests.post(url, json=payload, headers=headers, timeout=30)
                print(f"\nStatus Code: {resp.status_code}")
                print(f"Response: {resp.text}")
                
            except ImportError:
                print("\n(Install 'requests' library for detailed debugging)")
            except Exception as req_e:
                print(f"\nRequests test error: {req_e}")
    
    except Exception as e:
        print(f"\n❌ Configuration error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

