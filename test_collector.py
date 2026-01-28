#!/usr/bin/env python3
"""Test the ReportCollector parameter extraction"""

from llm_spec.reporting.collector import ReportCollector

print("=" * 60)
print("Testing ReportCollector._extract_param_paths()")
print("=" * 60)

# Test 1: OpenAI flat structure
print("\n1️⃣  OpenAI (flat structure):")
print("-" * 60)
params_openai = {
    'model': 'gpt-4',
    'temperature': 0.7,
    'max_tokens': 100
}
print(f"Input: {params_openai}")
result = ReportCollector._extract_param_paths(params_openai)
print(f"Output: {sorted(result)}")
print(f"Count: {len(result)} parameters")

# Test 2: Gemini nested structure
print("\n2️⃣  Gemini (nested structure):")
print("-" * 60)
params_gemini = {
    'contents': [{'parts': [{'text': 'Hello'}]}],
    'generationConfig': {
        'temperature': 0.7,
        'topP': 0.9,
        'topK': 40
    }
}
print(f"Input: {params_gemini}")
result = ReportCollector._extract_param_paths(params_gemini)
print(f"Output:")
for param in sorted(result):
    print(f"  - {param}")
print(f"Count: {len(result)} parameters")

# Test 3: Anthropic mixed structure
print("\n3️⃣  Anthropic (mixed structure):")
print("-" * 60)
params_anthropic = {
    'model': 'claude-3-5-sonnet-20241022',
    'max_tokens': 1024,
    'messages': [{'role': 'user', 'content': 'Hello'}],
    'tools': [{'name': 'get_weather', 'description': 'Get weather'}]
}
print(f"Input: {params_anthropic}")
result = ReportCollector._extract_param_paths(params_anthropic)
print(f"Output:")
for param in sorted(result):
    print(f"  - {param}")
print(f"Count: {len(result)} parameters")

# Test 4: Deep nesting (Gemini with safety settings)
print("\n4️⃣  Gemini (deep nesting with arrays):")
print("-" * 60)
params_complex = {
    'contents': [{'parts': [{'text': 'Hello'}]}],
    'generationConfig': {
        'temperature': 0.7,
        'topP': 0.9,
        'topK': 40,
        'maxOutputTokens': 2048
    },
    'safetySettings': [
        {'category': 'HARM_CATEGORY_HARASSMENT', 'threshold': 'BLOCK_MEDIUM_AND_ABOVE'},
        {'category': 'HARM_CATEGORY_HATE_SPEECH', 'threshold': 'BLOCK_ONLY_HIGH'}
    ]
}
print(f"Input (truncated): generationConfig + safetySettings")
result = ReportCollector._extract_param_paths(params_complex)
print(f"Output:")
for param in sorted(result):
    print(f"  - {param}")
print(f"Count: {len(result)} parameters")

print("\n" + "=" * 60)
print("✅ All tests completed successfully!")
print("=" * 60)
