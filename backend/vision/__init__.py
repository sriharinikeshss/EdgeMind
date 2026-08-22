"""
EdgeMind Vision & Multimodal Processing Module (Phase 5).
"""
from vision.multimodal_processor import (
    classify_image_type,
    process_multimodal_task,
    flag_low_confidence_regions,
    analyze_scanned_document,
    analyze_engineering_drawing,
    generate_visual_evidence
)

__all__ = [
    "classify_image_type",
    "process_multimodal_task",
    "flag_low_confidence_regions",
    "analyze_scanned_document",
    "analyze_engineering_drawing",
    "generate_visual_evidence",
]
