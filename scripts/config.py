#!/usr/bin/env python3
"""
Configuration for rvsec-02 project.
Paths adapted for generating .methods files for 557 APKs with Generic Specs.
"""

import os

# Project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# APKs directory (all 557 APKs)
# ALL_APKS = "/home/pedro/desenvolvimento/RV_ANDROID/NOVO/APKS"
ALL_APKS = "/home/pedro/desenvolvimento/RV_ANDROID/apks_mini"

# Tools paths
METHODS_EXTRACTOR_JAR = os.path.join(PROJECT_ROOT, 'tools', 'methods-extractor.jar')
MOP_EXTRACTOR_JAR = os.path.join(PROJECT_ROOT, 'tools', 'mop-extractor.jar')

# Specs directories
GENERIC_SPECS_DIR = os.path.join(PROJECT_ROOT, 'specs')
JCA_SPECS_DIR = "/home/pedro/desenvolvimento/RV_ANDROID/NOVO/dados/SPECS/jca"  # Not used in this project

# Output directories
ALL_METHODS_GENERIC = os.path.join(PROJECT_ROOT, 'all_methods')
ALL_METHODS_JCA = ALL_METHODS_GENERIC  # Not used in this project

# Results JSON (not used - we process all 557 APKs)
ALL_RESULTS_JSON = None

# Extension
EXTENSION_METHODS = ".methods"
