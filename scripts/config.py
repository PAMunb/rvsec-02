#!/usr/bin/env python3
"""
Configuration module for RVSec-02 experiment infrastructure.

Centralizes all path configurations and experiment parameters for the Phase 3
runtime verification experiment with 557 F-Droid APKs and 27 generic JavaMOP
specifications. Defines directory structures, tool locations, and experiment
combinations used across all analysis pipelines.

### Architectural Overview:
This module implements a configuration-as-code pattern where all paths and
experiment parameters are defined in a single location. This enables consistent
path resolution across the static analysis, dynamic analysis, and results
generation workflows while maintaining flexibility for experimentation.

### Key Architectural Decisions:
- **Relative Path Resolution**: Project root is computed relative to this file
  location, enabling relocation without code changes
- **Environment Isolation**: Experiment type and specification type combinations
  are explicitly enumerated rather than implicitly derived
- **Lazy Directory Creation**: Output directories are created at module load time
  to ensure availability across all scripts

### Role in the System:
- Provides single source of truth for all filesystem paths
- Maintains experiment metadata and combination definitions
- Enables reproducible execution across different environments
- Supports filtering by experiment type, specification type, and APK sets

### Integration Points:
- Imported by batch_generator, parsers, and generators modules
- Defines expected structure for results directory and logcat files
- Referenced by instrumentation pipeline for tool locations
"""

import os

from domain.models import ExperimentType, SpecType

# =============================================================================
# PROJECT STRUCTURE
# =============================================================================

# Project root directory, computed relative to this file location.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# APK SOURCES
# =============================================================================

# Directory containing all 557 F-Droid APKs for the experiment.
ALL_APKS = "/home/pedro/desenvolvimento/RV_ANDROID/NOVO/APKS"

# =============================================================================
# TOOL LOCATIONS
# =============================================================================

# Methods extractor JAR for generating .methods files from APK bytecode.
METHODS_EXTRACTOR_JAR = os.path.join(PROJECT_ROOT, 'tools', 'methods-extractor.jar')

# MOP extractor JAR (legacy, replaced by Python mop_extractor.py).
MOP_EXTRACTOR_JAR = os.path.join(PROJECT_ROOT, 'tools', 'mop-extractor.jar')

# =============================================================================
# SPECIFICATION DIRECTORIES
# =============================================================================

# Directory containing 27 generic JavaMOP specifications for Phase 3.
GENERIC_SPECS_DIR = os.path.join(PROJECT_ROOT, 'specs')

# JCA specification directory (not used in Phase 3 experiment).
JCA_SPECS_DIR = "/home/pedro/desenvolvimento/RV_ANDROID/NOVO/dados/SPECS/jca"

# =============================================================================
# OUTPUT DIRECTORIES FOR STATIC ANALYSIS
# =============================================================================

# Output directory for generated .methods files from APK static analysis.
ALL_METHODS_GENERIC = os.path.join(PROJECT_ROOT, 'all_methods')

# JCA methods directory (not used in Phase 3 experiment).
ALL_METHODS_JCA = ALL_METHODS_GENERIC

# =============================================================================
# DYNAMIC ANALYSIS RESULTS
# =============================================================================

# Results directory containing logcat files from experiment execution across
# all 37 batches and 7 Docker containers.
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')

# Logcat directory for Phase 3 (EXP02 with generic specifications).
LOGCAT_EXP02_GENERIC_DIR = RESULTS_DIR

# =============================================================================
# FILE EXTENSIONS
# =============================================================================

# Extension for logcat files from Android device/emulator execution.
EXTENSION_LOGCAT = ".logcat"

# Extension for .methods files containing static analysis output.
EXTENSION_METHODS = ".methods"

# =============================================================================
# EXPERIMENT DEFINITION
# =============================================================================

# Experiment combinations for Phase 3. Each tuple specifies (ExperimentType,
# SpecType) pairs that define which parser and specification set to use.
# Phase 3 uses only EXP02 (logcat with timestamps) and GENERIC specs.
COMBINATIONS = [
    (ExperimentType.EXP02, SpecType.GENERIC),
]

# =============================================================================
# APK FILTERING (OPTIONAL)
# =============================================================================

# Optional filter for valid APKs. If set to a file path, only APKs listed
# in that file will be processed. Set to None to process all APKs in ALL_APKS.
VALID_APKS_FILE = None

# =============================================================================
# RESULTS AGGREGATION (NOT USED IN PHASE 3)
# =============================================================================

# Path to results JSON file (not used in Phase 3 experiment).
ALL_RESULTS_JSON = None

# =============================================================================
# FINAL OUTPUT
# =============================================================================

# Output directory for final analysis results (CSVs and JSON summaries).
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'results_final')
os.makedirs(OUTPUT_DIR, exist_ok=True)
