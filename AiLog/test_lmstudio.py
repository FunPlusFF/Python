# test_lmstudio.py - Быстрая проверка LM Studio
from lmstudio_client import LMStudioClient

print("Testing LM Studio connection...")
client = LMStudioClient()

# Проверка соединения
status = client.test_connection()
print(f"\nConnection status:")
print(f"  Connected: {status.get('connected')}")
print(f"  Models: {status.get('models', 'none')}")
if status.get('error'):
    print(f"  Error: {status['error']}")

if status.get('connected'):
    print("\nSending test request...")
    result = client.analyze_logs(
        system_prompt="You are a DBA expert. Answer in JSON: {\"status\": \"ok\"}",
        user_prompt="What is the most common cause of OOM in Greenplum?",
        max_tokens=200
    )
    
    if result.get('success'):
        print("✓ Test successful!")
        print(f"\nResponse: {result['analysis']}")
    else:
        print(f"✗ Test failed: {result.get('error')}")