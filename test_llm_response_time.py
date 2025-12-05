"""
Test script to communicate with the LLM and track response time.
"""
import asyncio
import time
from src.utils.llm_client import get_openai_client, get_llm_model
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_llm_response_time():
    """Test LLM communication and measure response time."""
    
    # Get client and model
    client = get_openai_client()
    model = get_llm_model()
    
    # Test prompt
    test_prompt = "Hello! Please respond with a brief greeting and confirm you're working."
    
    print("\n" + "="*60)
    print("LLM Response Time Test")
    print("="*60)
    print(f"Model: {model}")
    print(f"Prompt: {test_prompt}")
    print("="*60)
    
    # Track response time
    start_time = time.time()
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": test_prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        end_time = time.time()
        response_time = end_time - start_time
        
        # Extract response
        response_text = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        
        # Display results
        print("\n✅ SUCCESS!")
        print(f"⏱️  Response Time: {response_time:.2f} seconds")
        print(f"📝 Response: {response_text}")
        print(f"🏁 Finish Reason: {finish_reason}")
        
        # Token usage if available
        if hasattr(response, 'usage') and response.usage:
            print(f"🔢 Tokens Used:")
            print(f"   - Prompt: {response.usage.prompt_tokens}")
            print(f"   - Completion: {response.usage.completion_tokens}")
            print(f"   - Total: {response.usage.total_tokens}")
        
        print("="*60)


        def print_class_inheritence(response_text):
            print("\n Class Inheritence: Checking whether we have pydantic classes or not using type(response_text).mro()")
            for cls in type(response_text).mro():
                print(f"{cls.__module__}.{cls.__name__}")

        print_class_inheritence(response_text)
                
    except Exception as e:
        end_time = time.time()
        response_time = end_time - start_time
        print(f"\n❌ ERROR after {response_time:.2f} seconds")
        print(f"Error: {str(e)}")
        print("="*60)
        raise


if __name__ == "__main__":
    asyncio.run(test_llm_response_time())
