"""
Tests for Phase 2 Multi-Model Routing Logic
"""
import sys
import os
import pytest

# Ensure backend package is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models.registry import registry

def test_classify_task_reasoning():
    prompt = "Summarize the history of Ancient Rome in 3 paragraphs."
    task_type = registry.classify_task(prompt)
    assert task_type == "reasoning"

def test_classify_task_coding():
    prompt = "Write a python script to parse a CSV file."
    task_type = registry.classify_task(prompt)
    assert task_type == "coding"

def test_route_task_reasoning():
    prompt = "What is the capital of France?"
    model_id = registry.route_task(prompt)
    # The default value from os.getenv might be overridden if environment var is set
    # but in our test without env vars, it defaults to qwen2.5:1.5b
    assert model_id == "qwen2.5:1.5b"  

def test_route_task_coding():
    prompt = "Can you help me debug this bash script?"
    model_id = registry.route_task(prompt)
    assert model_id == "qwen2.5-coder:1.5b"
