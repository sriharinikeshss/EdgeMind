import os
import sys

# Ensure backend package is on the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from models.registry import registry

coding_prompts = [
    "Write a python script to parse CSV.",
    "Debug this bash script.",
    "Create a react component for a login page.",
    "How do I use regex to extract emails?",
    "Write a SQL query to join these two tables.",
    "Explain this java function.",
    "Create a python loop that counts to 10.",
    "Write a unit test for my python code.",
    "How do I reverse a string in python?",
    "Generate a bash script to backup a directory."
]

reasoning_prompts = [
    "Summarize the history of Rome.",
    "Draft an email to my boss asking for vacation.",
    "What are the main causes of the French Revolution?",
    "Write a poem about a robot learning to love.",
    "Explain quantum computing to a 5 year old.",
    "Compare and contrast the characters of Hamlet and Macbeth.",
    "What is the capital of France?",
    "How does a combustion engine work?",
    "Give me a recipe for chocolate chip cookies.",
    "Translate this sentence to Spanish."
]

passed = 0
failed = 0
failed_prompts = []

for p in coding_prompts:
    if registry.classify_task(p) == "CODING":
        passed += 1
    else:
        failed += 1
        failed_prompts.append((p, "EXPECTED CODING"))

for p in reasoning_prompts:
    if registry.classify_task(p) == "REASONING":
        passed += 1
    else:
        failed += 1
        failed_prompts.append((p, "EXPECTED REASONING"))

print(f"Total: {len(coding_prompts) + len(reasoning_prompts)}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
if failed > 0:
    for f in failed_prompts:
        print(f"Failed: {f[0]} -> {f[1]}")
