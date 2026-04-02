"""
Package for generating .methods files for APKs.

This package contains tools for analyzing APKs and generating .methods CSV files
that contain method reachability analysis for Runtime Verification coverage calculation.
"""

from .reachability import generate_all_methods_file
from .package_detector import PackageDetector

__all__ = ['generate_all_methods_file']
