#!/usr/bin/env python3
"""
Main script for regenerating rvsec-02 Phase 3 experiment results.

This module orchestrates the full results regeneration pipeline, processing
all logcat files from the Phase 3 experiment to produce coverage and error
analysis CSVs. It coordinates parsing, coverage calculation, and CSV export
for approximately 48,000 logcat files across 366 instrumented APKs.

### Architectural Overview:
The script implements a batch processing pattern where each APK's logcat files
are processed sequentially, accumulating coverage and error data. The pipeline
uses Exp02Parser for timestamp-aware parsing, CoverageManager for coverage
calculation against static analysis baseline, and MopErrorManager for
violation deduplication and tracking.

### Key Architectural Decisions:
- **APK-Centric Processing**: Groups logcats by APK to enable coverage baseline loading once per APK
- **Progressive Accumulation**: Collects all coverage and error data in memory before CSV export
- **Mismatch Tracking**: Records methods found at runtime but not in static analysis
- **Summary Generation**: Computes per-task final metrics using pandas aggregation

### Role in the System:
- Entry point for Phase 3 results regeneration
- Coordinates parsers, coverage managers, and CSV generators
- Produces final analysis artifacts (coverage.csv, errors.csv, logcat.csv, summary.csv)

### Integration Points:
- Input: Logcat files from results/ directory, .methods files from all_methods/
- Output: CSV files in results_final/ directory
- Dependencies: exp02_parser, coverage generators, file_utils
"""

import os
import time
from pathlib import Path

import config
from domain.models import ExperimentType, SpecType
from generators.coverage import CoverageManager, MopErrorManager
from parsers.all_methods import AllMethods
from parsers.exp02_parser import Exp02Parser
from utils.file_utils import LogcatFileManager


class ResultsGenerator:
    """
    Orchestrates Phase 3 results regeneration from logcat files.

    Processes all logcat files for instrumented APKs, calculating coverage
    metrics against static analysis baseline and extracting property violations.
    Generates four output CSVs: coverage, errors, logcat info, and summary.

    ### Architectural Decisions:
    - Loads .methods baseline once per APK to avoid redundant file I/O
    - Uses MopErrorManager across all APKs for global deduplication
    - Tracks processing statistics for progress reporting

    ### Role in the System:
    - Main execution class for results regeneration
    - Coordinates all component managers and parsers
    - Produces final CSV artifacts for analysis

    ### Key Features:
    - APK-by-APK processing with progress tracking
    - Coverage calculation across 6 metrics
    - Violation deduplication and export
    - Summary generation with final metrics per task
    """

    def __init__(self):
        """
        Initialize the results generator with configured paths.
        """
        self.logcat_dir = config.RESULTS_DIR
        self.all_methods_dir = config.ALL_METHODS_GENERIC
        self.output_dir = config.OUTPUT_DIR

    def generate_all_reports(self):
        """
        Generate all result CSVs from Phase 3 experiment logcats.

        Processes all logcat files, calculates coverage metrics, extracts
        violations, and exports four CSV files to the output directory.
        """
        print("=" * 80)
        print("RVSEC-02 Phase 3 Results Regeneration")
        print("=" * 80)
        start_time = time.time()

        # Initialize logcat manager to scan all logcat files
        print(f"\nScanning logcat directory: {self.logcat_dir}")
        logcat_manager = LogcatFileManager(self.logcat_dir)

        # Get list of unique APKs with logcat files
        apks = logcat_manager.get_all_apks()
        print(f"Found {len(apks)} APKs with logcat files")
        print(f"Total logcat files: {len(logcat_manager.logcat_files_by_filename)}")

        # Accumulators for all data
        logcat_data = []
        coverage_data = []
        mop_errors_data = []

        # Single error manager for global deduplication
        error_manager = MopErrorManager()

        # Process each APK
        skipped_apks = []
        for i, apk in enumerate(sorted(apks), 1):
            print(f"\nProcessing APK ({i}/{len(apks)}): {apk}")

            # Load .methods file for this APK
            methods_path = Path(self.all_methods_dir) / f"{apk}{config.EXTENSION_METHODS}"
            if not methods_path.exists():
                print(f"  WARNING: .methods not found, skipping")
                skipped_apks.append(apk)
                continue

            # Check if .methods file is valid (not empty/header-only)
            # Header line is 101 bytes, so files <= 105 bytes have no data
            if methods_path.stat().st_size <= 105:
                print(f"  WARNING: .methods file has only header ({methods_path.stat().st_size} bytes), skipping")
                skipped_apks.append(apk)
                continue

            try:
                all_methods = AllMethods(methods_path)
            except Exception as e:
                print(f"  ERROR loading .methods: {e}")
                skipped_apks.append(apk)
                continue

            coverage_manager = CoverageManager(all_methods)

            # Process each logcat file for this APK
            logcat_files = logcat_manager.get_by_apk(apk)
            print(f"  Logcat files: {len(logcat_files)}")

            for logcat_file in logcat_files:
                # Parse logcat with timestamp-aware parser
                parser = Exp02Parser(logcat_file)
                coverage, mop_errors, errors, crashes_count = parser.parse_all_lines(verbose=False)

                # Calculate coverage against static baseline
                cov_report = coverage_manager.process_cov_file(coverage, verbose=False)

                # Process MOP errors with deduplication
                mop_errors_report = error_manager.process_file(mop_errors, verbose=False)

                # Collect logcat info
                logcat_info = {
                    "apk": apk,
                    "rep": logcat_file.repetition,
                    "timeout": logcat_file.timeout,
                    "tool": logcat_file.tool,
                    "cov_items": len(coverage),
                    "cov_items_unique": len(cov_report["coverage_data"]),
                    "mop_errors": mop_errors_report["unique_errors"],
                    "crashes_count": crashes_count,
                    "mismatch_count": len(cov_report["mismatch"]),
                    "errors_count": len(errors),
                }

                logcat_data.append(logcat_info)
                coverage_data.extend(cov_report["coverage_data"])
                mop_errors_data.extend(mop_errors_report["errors_data"])

        # Save all CSVs
        print("\n" + "=" * 80)
        print("Saving CSV files...")
        self._save_csv("exp02_generic_coverage.csv", coverage_data)
        self._save_csv("exp02_generic_errors.csv", mop_errors_data)
        self._save_csv("exp02_generic_logcat.csv", logcat_data)

        # Generate and save summary
        summary_data = self._generate_summary(logcat_data, coverage_data, mop_errors_data)
        self._save_csv("exp02_generic_summary.csv", summary_data)

        # Final statistics
        end_time = time.time()
        elapsed = end_time - start_time

        print("\n" + "=" * 80)
        print("FINAL STATISTICS")
        print("=" * 80)
        print(f"APKs processed: {len(apks) - len(skipped_apks)}")
        print(f"APKs skipped: {len(skipped_apks)}")
        print(f"Total logcat entries: {len(logcat_data)}")
        print(f"Coverage data rows: {len(coverage_data)}")
        print(f"MOP errors rows: {len(mop_errors_data)}")
        print(f"Summary rows: {len(summary_data)}")
        print(f"Total time: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")

        if skipped_apks:
            print(f"\nSkipped APKs ({len(skipped_apks)}):")
            for apk in skipped_apks[:10]:
                print(f"  - {apk}")
            if len(skipped_apks) > 10:
                print(f"  ... and {len(skipped_apks) - 10} more")

    def _generate_summary(self, logcat_data: list, coverage_data: list, mop_errors_data: list) -> list:
        """
        Generate summary CSV combining coverage and error data.

        Creates one row per task (APK + rep + timeout + tool) with final
        coverage metrics and error counts.

        Args:
            logcat_data: List of logcat info dictionaries (BASE).
            coverage_data: List of coverage data rows.
            mop_errors_data: List of error data rows.

        Returns:
            List of summary dictionaries, one per task.
        """
        import pandas as pd

        task_keys = ['apk', 'rep', 'timeout', 'tool']
        cov_keys = ['cov_act', 'cov_class', 'cov_method', 'cov_reachable',
                    'cov_reaches_mop', 'cov_directly_reaches_mop']

        # BASE: All tasks from logcat_data
        df_logcat = pd.DataFrame(logcat_data)[task_keys].drop_duplicates()

        # COVERAGE: Get LAST row per task (final metrics)
        if coverage_data:
            df_coverage = pd.DataFrame(coverage_data)
            coverage_final = (df_coverage
                             .groupby(task_keys)
                             .last()
                             [cov_keys]
                             .reset_index())
        else:
            coverage_final = pd.DataFrame(columns=task_keys + cov_keys)

        # ERRORS: Count per task
        if mop_errors_data:
            df_errors = pd.DataFrame(mop_errors_data)
            errors_count = (df_errors
                           .groupby(task_keys)
                           .size()
                           .reset_index(name='errors'))
        else:
            errors_count = pd.DataFrame(columns=task_keys + ['errors'])

        # COMBINE: LEFT JOIN to include ALL tasks
        summary = (df_logcat
                  .merge(coverage_final, on=task_keys, how='left')
                  .merge(errors_count, on=task_keys, how='left'))

        # FILL: Tasks without coverage = 0, tasks without errors = 0
        for col in cov_keys:
            summary[col] = summary[col].fillna(0)
        summary['errors'] = summary['errors'].fillna(0).astype(int)

        # SORT
        summary = summary.sort_values(task_keys).reset_index(drop=True)

        return summary.to_dict('records')

    def _save_csv(self, filename: str, data: list):
        """
        Save data to CSV file in output directory.

        Args:
            filename: Name of CSV file to create.
            data: List of dictionaries to save as CSV rows.
        """
        import pandas as pd

        filepath = os.path.join(self.output_dir, filename)
        print(f"  Saving {filename} ({len(data)} rows)")
        pd.DataFrame(data).to_csv(filepath, index=False)


def main():
    """Entry point for results regeneration."""
    ResultsGenerator().generate_all_reports()


if __name__ == "__main__":
    main()
