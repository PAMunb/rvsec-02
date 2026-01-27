#!/usr/bin/env python3
"""
Instrumentation error aggregation for RV-Android experiment results.

This module consolidates instrumentation error reports from all batch
execution directories into a single JSON file for analysis. It also validates
consistency of error and execution counts against the total APK count.

### Architectural Overview:
The module implements a two-phase aggregation approach: first, it scans
batch directories and merges error dictionaries using a simple union
operation; second, it validates the aggregated data by cross-referencing
with logcat files to detect APKs that appear in both error and executed
sets. This ensures data completeness and identifies potential issues in
the experiment tracking.

### Key Architectural Decisions:
- **File-Based Input**: Reads individual batch JSON files rather than
  querying a database, enabling offline analysis and audit trails
- **Sorted Processing**: Processes files in sorted order for deterministic
  output and reproducible runs
- **Cross-Reference Validation**: Validates aggregated errors against
  logcat file inventory to ensure consistency with execution records

### Role in the System:
- Aggregates instrumentation failures from all experiment batches
- Produces consolidated error manifest for post-analysis investigation
- Validates data consistency across batch directories
- Supports troubleshooting of failed APK instrumentation attempts

### Integration Points:
- Input: Individual batch JSON files from results/batch-*/instrument_errors.json
- Input: Logcat files from results/**/*.logcat for validation
- Output: Consolidated JSON to results_final/exp02_generic_instrument_errors.json
- Depends on: config module for directory paths
"""

import json
from pathlib import Path

import config


def merge_instrument_errors() -> dict:
    """
    Aggregate instrumentation error records from all batch directories.

    Scans the results directory for batch-level JSON files containing
    instrumentation errors and merges them into a single consolidated
    dictionary keyed by APK name. Prints progress information for each
    batch processed.

    Returns:
        Dictionary mapping APK names to their instrumentation error records.
        Empty dict if no error files are found.

    Raises:
        FileNotFoundError: If results directory does not exist.
        json.JSONDecodeError: If an error JSON file is malformed.
    """
    merged = {}
    files_processed = 0

    json_files = sorted(Path(config.RESULTS_DIR).glob("*/instrument_errors.json"))

    print(f"Found {len(json_files)} instrument_errors.json files")

    for json_file in json_files:
        batch_name = json_file.parent.name
        with open(json_file) as f:
            data = json.load(f)
            print(f"  {batch_name}: {len(data)} APKs with errors")
            merged.update(data)
            files_processed += 1

    output_path = Path(config.OUTPUT_DIR) / "exp02_generic_instrument_errors.json"
    with open(output_path, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"\nMerged {len(merged)} APKs with instrument errors")
    print(f"Saved to: {output_path}")

    return merged


def validate_consistency(instrument_errors: dict) -> dict:
    """
    Validate data consistency between instrumentation errors and execution records.

    Compares APKs with instrumentation errors against APKs with logcat
    execution records to detect overlaps and count coverage. The experiment
    includes 557 total APKs, which should be partitioned into two disjoint
    sets: those that failed instrumentation and those that executed (with
    logcat output).

    ### Implementation Notes:
    - APK names are extracted from logcat filenames using "__" as delimiter
    - The first segment of logcat filename is the APK name
    - Overlap indicates APKs appearing in both sets (data integrity issue)
    - Expected total consistency: errors + executed - overlap = 557

    Args:
        instrument_errors: Dictionary from merge_instrument_errors() with
            APK names as keys.

    Returns:
        Dictionary containing:
        - "errors": Count of APKs with instrumentation failures
        - "executed": Count of APKs with logcat output
        - "overlap": Count of APKs in both sets (indicates inconsistency)
        - "total": Sum of errors and executed minus overlap
    """
    print("\n=== Instrumentation Error Consistency Validation ===")

    # Count APKs with instrument errors
    apks_with_errors = set(instrument_errors.keys())
    print(f"APKs with instrumentation errors: {len(apks_with_errors)}")

    # Count APKs that were executed (have logcats)
    apks_executed = set()
    for logcat in Path(config.RESULTS_DIR).glob("**/*.logcat"):
        apk_name = logcat.name.split("__")[0]
        apks_executed.add(apk_name)
    print(f"APKs executed (with logcats): {len(apks_executed)}")

    # Check overlap between error and execution sets
    overlap = apks_with_errors & apks_executed
    if overlap:
        print(f"Warning: {len(overlap)} APKs appear in both error and execution records!")
        for apk in sorted(overlap)[:5]:
            print(f"  - {apk}")
        if len(overlap) > 5:
            print(f"  ... and {len(overlap) - 5} more")

    # Total unique APKs
    total = len(apks_with_errors) + len(apks_executed) - len(overlap)
    print(f"\nTotal unique APKs: {total}")
    print(f"Expected: 557")

    if total == 557:
        print("Consistency check passed.")
    else:
        print(f"Consistency check failed: {557 - total} APKs unaccounted")

    return {
        "errors": len(apks_with_errors),
        "executed": len(apks_executed),
        "overlap": len(overlap),
        "total": total
    }


if __name__ == "__main__":
    errors = merge_instrument_errors()
    validate_consistency(errors)
