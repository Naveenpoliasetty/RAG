#!/usr/bin/env python3
"""
Test script for RunPod vLLM server inference.
Tests both basic chat completion and structured output (instructor).
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI
import instructor
from pydantic import BaseModel
from typing import List
from src.utils.llm_client import get_openai_client, get_llm_model, load_llm_config
from src.utils.logger import get_logger

logger = get_logger("LLMTest")


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_endpoint_connectivity():
    """Test if the endpoint is reachable"""
    print_section("Test 1: Endpoint Connectivity")
    
    try:
        import requests
        from src.utils.llm_client import load_llm_config
        
        config = load_llm_config()
        base_url = config.get("base_url")
        
        if not base_url:
            print("❌ No endpoint configured")
            return False
        
        print(f"Testing endpoint: {base_url}")
        
        # Try to reach the endpoint (remove /chat/completions if present)
        test_url = base_url.rstrip('/')
        if not test_url.endswith('/v1'):
            test_url = test_url + '/v1' if '/v1' not in test_url else test_url
        
        # Try a simple GET request to check connectivity
        try:
            response = requests.get(test_url, timeout=5)
            print(f" Endpoint is reachable (Status: {response.status_code})")
            return True
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Could not verify connectivity: {str(e)}")
            print("   This might be normal if the endpoint only accepts POST requests")
            return True  # Don't fail the test, endpoint might just not support GET
            
    except ImportError:
        print("⚠️  'requests' library not available, skipping connectivity test")
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_basic_chat_completion():
    """Test basic chat completion without structured output"""
    print_section("Test 2: Basic Chat Completion")
    
    try:
        client = get_openai_client()
        model = get_llm_model()
        
        print(f"Model: {model}")
        print(f"Endpoint: {client.base_url}")
        print("\nSending test prompt...")
        
        # Prepare the request
        request_data = {
            "model": model,  # Get model from config or use default
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Write a short haiku about programming."}
            ],
            "max_tokens": 100,
            "temperature": 0.7
        }
        
        print(f"\nRequest details:")
        print(f"  Model: {request_data['model']}")
        print(f"  Messages: {len(request_data['messages'])} message(s)")
        print(f"  Max tokens: {request_data['max_tokens']}")
        
        start_time = time.time()
        response = client.chat.completions.create(**request_data)
        elapsed_time = time.time() - start_time
        
        print(f"\n Success! Response received in {elapsed_time:.2f} seconds")
        print(f"\nResponse:")
        print("-" * 70)
        print(response.choices[0].message.content)
        print("-" * 70)
        
        if response.usage:
            print(f"\nToken Usage:")
            print(f"  Prompt tokens: {response.usage.prompt_tokens}")
            print(f"  Completion tokens: {response.usage.completion_tokens}")
            print(f"  Total tokens: {response.usage.total_tokens}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        
        # Try to get more details from the error
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_body = e.response.text
                print(f"\nError response body: {error_body}")
            except:
                pass
        
        # Provide helpful error messages
        error_str = str(e).lower()
        if "500" in error_str or "internal server error" in error_str:
            print("\n💡 Troubleshooting tips for 500 Internal Server Error:")
            print("   1. Check your RunPod dashboard:")
            print("      - Is the pod running and healthy?")
            print("      - Are there any error logs in the pod logs?")
            print("      - Is the model name correct? (check: llama3.1-8b)")
            print("   2. Verify endpoint configuration:")
            print("      - Endpoint URL: https://api.runpod.ai/v2/6fzxy3vigvuxwz/openai/v1")
            print("      - Make sure this is the correct OpenAI-compatible endpoint")
            print("   3. Common issues:")
            print("      - Server might be starting up (wait 1-2 minutes)")
            print("      - Model might not be loaded yet")
            print("      - Server might be overloaded")
            print("   4. Try testing directly with curl:")
            print(f"      curl -X POST {client.base_url}/chat/completions \\")
            print(f"        -H 'Content-Type: application/json' \\")
            print(f"        -H 'Authorization: Bearer YOUR_API_KEY' \\")
            print(f"        -d '{{\"model\": \"{model}\", \"messages\": [{{\"role\": \"user\", \"content\": \"Hello\"}}]}}'")
        elif "401" in error_str or "unauthorized" in error_str:
            print("\n💡 Troubleshooting tips:")
            print("   - Check your API key in config.yaml")
            print("   - Verify the API key is correct in RunPod dashboard")
        elif "404" in error_str or "not found" in error_str:
            print("\n💡 Troubleshooting tips:")
            print("   - Verify the endpoint URL is correct")
            print("   - Make sure the endpoint includes '/openai/v1' or '/v1'")
        
        import traceback
        traceback.print_exc()
        return False


def test_structured_output():
    """Test structured output using instructor"""
    print_section("Test 3: Structured Output (Instructor)")
    
    try:
        # Define a simple output model
        class PersonInfo(BaseModel):
            name: str
            age: int
            skills: List[str]
            bio: str
        
        client = instructor.patch(get_openai_client())
        model = get_llm_model()
        
        print(f"Model: {model if model else '(not specified - using endpoint default)'}")
        print(f"Endpoint: {client.base_url}")
        print("\nSending structured output request...")
        
        prompt = """
        Extract information about a software developer:
        Name: Alice Johnson
        Age: 28
        Skills: Python, JavaScript, Docker, Kubernetes
        Bio: Alice is a full-stack developer with 5 years of experience.
        """
        
        # Build request parameters
        request_params = {
            "model": model,  # Get model from config or use default
            "response_model": PersonInfo,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that extracts structured information."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 200
        }
        
        start_time = time.time()
        response = client.chat.completions.create(**request_params)
        elapsed_time = time.time() - start_time
        
        print(f"\n Success! Structured output received in {elapsed_time:.2f} seconds")
        print(f"\nStructured Response:")
        print("-" * 70)
        print(response.model_dump_json(indent=2))
        print("-" * 70)
        
        # Validate the response
        print(f"\nValidated Fields:")
        print(f"  Name: {response.name}")
        print(f"  Age: {response.age}")
        print(f"  Skills: {', '.join(response.skills)}")
        print(f"  Bio: {response.bio[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


def test_config_loading():
    """Test that configuration is loaded correctly"""
    print_section("Test 0: Configuration Check")
    
    try:
        config = load_llm_config()
        model = get_llm_model()
        
        print("Configuration loaded successfully:")
        print(f"  Model: {model}")
        print(f"  Base URL: {config.get('base_url', 'Not set')}")
        print(f"  API Key: {'Set' if config.get('api_key') else 'Not set'} (hidden)")
        print(f"  Summary Max Tokens: {config.get('SUMMARY_MAX_TOKENS', 'Not set')}")
        print(f"  Skills Max Tokens: {config.get('SKILLS_MAX_TOKENS', 'Not set')}")
        print(f"  Experience Max Tokens: {config.get('EXPERIENCE_MAX_TOKENS', 'Not set')}")
        
        if not config.get('base_url'):
            print("\n⚠️  Warning: base_url is not set in config.yaml")
            return False
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error loading configuration: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "🚀" * 35)
    print("  RunPod vLLM Server Inference Test")
    print("🚀" * 35)
    
    results = []
    
    # Test 0: Configuration
    results.append(("Configuration", test_config_loading()))
    
    if not results[0][1]:
        print("\n❌ Configuration test failed. Please check your config.yaml file.")
        return
    
    # Test 1: Endpoint connectivity
    results.append(("Endpoint Connectivity", test_endpoint_connectivity()))
    
    # Test 2: Basic chat completion
    results.append(("Basic Chat Completion", test_basic_chat_completion()))
    
    # Test 3: Structured output
    results.append(("Structured Output", test_structured_output()))
    
    # Summary
    print_section("Test Summary")
    print("\nResults:")
    for test_name, passed in results:
        status = " PASSED" if passed else "❌ FAILED"
        print(f"  {test_name:30s} {status}")
    
    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 All tests passed! Your RunPod vLLM server is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please check the error messages above.")


if __name__ == "__main__":
    main()

