#!/usr/bin/env python3
"""
Parallel batch generator for .methods files in RV-Android framework.

This module generates .methods files for APKs by analyzing bytecode and
determining reachability and MOP specification coverage. It orchestrates
parallel processing across multiple APKs with configurable batch sizes.

### Architectural Overview:
The generator uses a ProcessPoolExecutor to distribute APK analysis across
multiple worker processes. Each worker invokes the reachability analyzer to
generate a complete method inventory with signatures, reachability information,
and MOP method usage analysis. The batch-based approach enables processing of
large APK datasets while managing resource constraints through configurable
parallelism levels.

### Key Architectural Decisions:
- **Process-Based Parallelism**: Uses ProcessPoolExecutor for CPU-bound analysis tasks
- **Batch Processing**: Splits APKs into configurable batches to control resource usage
- **Package Detection**: Leverages PackageDetector to resolve manifest vs code package discrepancies
- **Worker Isolation**: Each worker imports required modules independently to support multiprocessing

### Role in the System:
- Generates static analysis baseline (.methods files) for coverage measurement
- Enables parallel processing of large APK datasets for experimental efficiency
- Produces input for downstream coverage analysis and violation detection
- Provides progress tracking and error reporting for batch execution

### Integration Points:
- Input: APK files from config.ALL_APKS directory and specs from config.GENERIC_SPECS_DIR
- Output: .methods CSV files in config.ALL_METHODS_GENERIC directory
- Depends on: reachability.generate_all_methods_file() for individual APK analysis
- Depends on: PackageDetector for package name detection
- Depends on: config module for directory paths and settings
"""

import os
import sys
import argparse
import time
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

# Add parent directory (scripts/) to path for config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def process_single_apk_worker(args: Tuple[str, str, str, str]) -> Tuple[bool, str, str]:
    """
    Worker function for parallel processing of a single APK.

    Invokes the reachability analyzer to generate a .methods file for the
    given APK. This function runs in a separate worker process and handles
    module imports independently to support multiprocessing isolation.

    Args:
        args: Tuple of (apk_path, package_name, output_file, specs_dir).
            - apk_path: Absolute path to the APK file to analyze.
            - package_name: Detected package name for the APK.
            - output_file: Absolute path where .methods CSV will be written.
            - specs_dir: Directory containing JavaMOP specification files.

    Returns:
        Tuple of (success, apk_name, message) where:
            - success: Boolean indicating successful .methods generation.
            - apk_name: Filename of the processed APK.
            - message: Status message including method count or error details.

    Raises:
        No exceptions are raised; errors are caught and returned in message.
    """
    apk_path, package_name, output_file, specs_dir = args
    apk_name = Path(apk_path).name

    try:
        start_time = time.time()

        # Import reachability module in worker process for isolation
        # Each worker must import independently to avoid multiprocessing issues
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from all_methods.reachability import generate_all_methods_file

        generate_all_methods_file(
            apk_path=apk_path,
            apk_package=package_name,
            mop_specs_dir=specs_dir,
            output_file=output_file
        )

        end_time = time.time()
        duration = end_time - start_time

        # Verify output file was created and contains methods beyond header line
        if Path(output_file).exists() and Path(output_file).stat().st_size > 0:
            with open(output_file, 'r') as f:
                # Subtract header line to get method count
                line_count = sum(1 for _ in f) - 1

            message = f"SUCCESS: {line_count} methods in {duration:.1f}s"
            return True, apk_name, message
        else:
            message = "FAILED: Output file empty or not created"
            return False, apk_name, message

    except Exception as e:
        import traceback
        message = f"ERROR: {e}\n{traceback.format_exc()}"
        return False, apk_name, message


class ParallelBatchMethodsGenerator:
    """
    Parallel batch processor for generating .methods files from APKs.

    Orchestrates analysis of multiple APKs using ProcessPoolExecutor, managing
    package detection, batch organization, and progress tracking. Generates
    .methods CSV files containing method inventories with reachability and MOP
    specification coverage information.

    ### Architectural Decisions:
    - Uses ProcessPoolExecutor for CPU-bound APK analysis with configurable parallelism
    - Discovers and detects package names before processing to enable correct analysis
    - Batches APKs to manage peak resource usage during parallel processing
    - Tracks success/failure statistics for reporting and debugging

    ### Role in the System:
    - Provides the main execution interface for batch .methods generation
    - Orchestrates parallel worker processes for large-scale APK analysis
    - Generates static analysis baseline for runtime coverage measurement
    - Reports progress and statistics for experiment execution monitoring

    ### Key Features:
    - Package detection via PackageDetector for manifest vs code package resolution
    - Configurable batch size and parallelism level for resource management
    - Progress tracking with APK/minute rates and cumulative statistics
    - Error handling and reporting with per-APK status messages
    """

    def __init__(self, apks_dir: str, output_dir: str, specs_dir: str, batch_size: int = 5) -> None:
        """
        Initialize the parallel batch processor.

        Args:
            apks_dir: Directory containing APK files to analyze.
            output_dir: Directory where .methods CSV files will be written.
            specs_dir: Directory containing JavaMOP specification files.
            batch_size: Number of parallel workers per batch (default: 5).

        Returns:
            None
        """
        self.apks_dir = Path(apks_dir)
        self.output_dir = Path(output_dir)
        self.specs_dir = specs_dir
        self.batch_size = batch_size

        # Create output directory if it does not exist
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize PackageDetector for manifest vs code package resolution
        from processors.package_detector import PackageDetector
        self.package_detector = PackageDetector()
        print("PackageDetector initialized")

        # Track processing statistics for final reporting
        self.processed = 0
        self.failed = 0
        self.start_time = None

    def find_apk_package_pairs(self, test_mode: bool = False) -> List[Tuple[str, str]]:
        """
        Find APK files and detect their actual package names.

        Scans the APKs directory for .apk files and uses PackageDetector to
        resolve the actual package name for each APK. Detects cases where the
        manifest package differs from the code package (common in apps with
        application ID suffixes or build variants).

        Args:
            test_mode: If True, process only first 10 APKs; if False, process all.

        Returns:
            List of (apk_path, detected_package) tuples for all APKs with
            successfully detected package names.

        Raises:
            No exceptions; errors are logged and APKs are skipped.
        """
        print("Discovering APK files and detecting package names...")

        # Sort APK files for deterministic processing order
        apk_files = sorted(self.apks_dir.glob("*.apk"))

        print(f"Found {len(apk_files)} total APKs in directory")

        if test_mode:
            print(f"TEST MODE: Processing first 10 APKs out of {len(apk_files)}")
            apk_files = apk_files[:10]
        else:
            print(f"FULL MODE: Processing all {len(apk_files)} APKs")

        apk_package_pairs = []

        for i, apk_path in enumerate(apk_files, 1):
            try:
                # Detect package using PackageDetector heuristic
                manifest_pkg, detected_pkg, stats = self.package_detector.detect_package(str(apk_path))

                if detected_pkg:
                    apk_package_pairs.append((str(apk_path), detected_pkg))

                    # Show detection result (abbreviated)
                    if manifest_pkg != detected_pkg:
                        print(f"[{i}/{len(apk_files)}] {apk_path.name}: {manifest_pkg} -> {detected_pkg}")
                    else:
                        print(f"[{i}/{len(apk_files)}] {apk_path.name}: {detected_pkg}")
                else:
                    print(f"[{i}/{len(apk_files)}] {apk_path.name}: FAILED to detect package")

            except Exception as e:
                print(f"[{i}/{len(apk_files)}] {apk_path.name}: ERROR - {e}")
                continue

        print(f"Found {len(apk_package_pairs)} valid APK-package pairs")
        return apk_package_pairs

    def process_batch_parallel(self, apk_package_pairs: List[Tuple[str, str]], batch_num: int, total_batches: int) -> Tuple[int, int]:
        """
        Process a batch of APKs in parallel using ProcessPoolExecutor.

        Submits all APKs in the batch to worker processes and collects results
        as they complete. Reports progress and status for each APK.

        Args:
            apk_package_pairs: List of (apk_path, package_name) tuples to process.
            batch_num: Current batch number for reporting.
            total_batches: Total number of batches for reporting.

        Returns:
            Tuple of (successful_count, failed_count) indicating the number of
            APKs processed successfully and the number that failed.

        Raises:
            No exceptions; errors are caught and counted in failed_count.
        """
        print(f"\nProcessing batch {batch_num}/{total_batches} ({len(apk_package_pairs)} APKs) in parallel...")

        # Prepare arguments for worker processes
        worker_args = []
        for apk_path, package_name in apk_package_pairs:
            apk_name = Path(apk_path).name
            output_file = str(self.output_dir / f"{apk_name}.methods")
            worker_args.append((apk_path, package_name, output_file, self.specs_dir))

        successful = 0
        failed = 0

        # Submit all tasks to worker pool for concurrent execution
        with ProcessPoolExecutor(max_workers=self.batch_size) as executor:
            # Map futures to APK paths for result tracking
            future_to_apk = {executor.submit(process_single_apk_worker, args): args[0] for args in worker_args}

            # Collect results in completion order to enable early error detection
            for future in as_completed(future_to_apk):
                apk_path = future_to_apk[future]
                try:
                    success, apk_name, message = future.result()
                    if success:
                        print(f"  OK {apk_name}: {message}")
                        successful += 1
                    else:
                        print(f"  FAIL {apk_name}: {message}")
                        failed += 1
                except Exception as exc:
                    print(f"  FAIL {Path(apk_path).name}: Exception in worker: {exc}")
                    failed += 1

        print(f"Batch {batch_num} completed: {successful} successful, {failed} failed")
        return successful, failed

    def process_batch(self, test_mode: bool = False) -> None:
        """
        Main entry point for processing all APKs in parallel batch mode.

        Discovers APKs and package names, organizes them into configurable
        batches, and processes each batch in parallel. Tracks statistics and
        reports progress throughout execution.

        Args:
            test_mode: If True, process only 10 sample APKs; if False, process all.

        Returns:
            None

        Raises:
            No exceptions; errors are caught and reported in statistics.
        """
        self.start_time = time.time()

        print("=" * 80)
        print("PARALLEL BATCH ALL_METHODS GENERATION")
        print("=" * 80)

        # Find APK-package pairs
        apk_package_pairs = self.find_apk_package_pairs(test_mode)

        if not apk_package_pairs:
            print("No valid APK files found!")
            return

        print(f"\nProcessing {len(apk_package_pairs)} APKs in batches of {self.batch_size}...")
        print(f"Output directory: {self.output_dir}")
        print(f"Specs directory: {self.specs_dir}")
        print(f"Max parallel workers per batch: {self.batch_size}")
        print("-" * 80)

        # Organize APKs into configurable batch sizes for resource management
        batches = []
        for i in range(0, len(apk_package_pairs), self.batch_size):
            batch = apk_package_pairs[i:i + self.batch_size]
            batches.append(batch)

        total_batches = len(batches)
        print(f"Split into {total_batches} batches")

        # Process each batch sequentially while running workers in parallel
        for batch_num, batch_apks in enumerate(batches, 1):
            batch_start = time.time()

            successful, failed = self.process_batch_parallel(batch_apks, batch_num, total_batches)

            self.processed += successful
            self.failed += failed

            batch_end = time.time()
            batch_duration = batch_end - batch_start

            # Calculate progress metrics for current batch
            total_processed = batch_num * self.batch_size
            if total_processed > len(apk_package_pairs):
                total_processed = len(apk_package_pairs)

            elapsed_total = time.time() - self.start_time
            # Calculate throughput in APKs per minute for progress estimation
            rate = total_processed / elapsed_total * 60

            print(f"Progress: {total_processed}/{len(apk_package_pairs)} ({total_processed/len(apk_package_pairs)*100:.1f}%) | "
                  f"Success: {self.processed} | Failed: {self.failed} | "
                  f"Batch time: {batch_duration:.1f}s | Rate: {rate:.1f} APKs/min")

        # Final statistics
        self.print_final_statistics(len(apk_package_pairs))

    def print_final_statistics(self, total_apks: int) -> None:
        """
        Print final processing statistics to console.

        Displays cumulative results including success/failure counts, success
        rates, processing time, and throughput metrics.

        Args:
            total_apks: Total number of APKs in the complete dataset.

        Returns:
            None

        Raises:
            No exceptions.
        """
        elapsed = time.time() - self.start_time

        print("\n" + "=" * 80)
        print("FINAL STATISTICS")
        print("=" * 80)
        print(f"Total APKs: {total_apks}")
        print(f"Successful: {self.processed}")
        print(f"Failed: {self.failed}")
        print(f"Success Rate: {self.processed/total_apks*100:.1f}%")
        print(f"Total Time: {elapsed/60:.1f} minutes")
        print(f"Average Rate: {total_apks/elapsed*60:.1f} APKs/minute")
        print(f"Batch Size: {self.batch_size} parallel workers")
        print(f"Output: {self.output_dir}")

        if self.failed > 0:
            print(f"\n{self.failed} APKs failed processing. Check logs above for details.")

        print("=" * 80)


def main() -> None:
    """
    Parse command-line arguments and execute parallel batch processing.

    Supports two modes:
    - --test: Process 10 sample APKs for validation
    - --all: Process all APKs in the configured dataset

    Returns:
        None

    Raises:
        SystemExit: If neither --test nor --all is specified.
    """
    parser = argparse.ArgumentParser(description="Parallel batch .methods generation for rvsec-02")
    parser.add_argument("--test", action="store_true", help="Test mode: process only 10 APKs")
    parser.add_argument("--all", action="store_true", help="Full mode: process all 557 APKs in batches")
    parser.add_argument("--batch-size", type=int, default=2, help="Number of parallel workers per batch (default: 2, conservative)")
    parser.add_argument("--sequential", action="store_true", help="Run sequentially (batch-size=1)")

    args = parser.parse_args()

    if not (args.test or args.all):
        print("Please specify --test or --all mode")
        parser.print_help()
        return

    # Sequential mode overrides batch_size for single-process debugging
    batch_size = 1 if args.sequential else args.batch_size

    # Use config values
    apks_dir = config.ALL_APKS
    specs_dir = config.GENERIC_SPECS_DIR
    output_dir = config.ALL_METHODS_GENERIC

    print(f"Using Generic Specs from: {specs_dir}")
    print(f"APKs directory: {apks_dir}")
    print(f"Output directory: {output_dir}")

    # Check if APKs directory exists
    if not os.path.exists(apks_dir):
        print(f"APKs directory not found: {apks_dir}")
        return

    # Initialize and run parallel batch processor
    batch_processor = ParallelBatchMethodsGenerator(
        apks_dir=apks_dir,
        output_dir=output_dir,
        specs_dir=specs_dir,
        batch_size=batch_size
    )

    batch_processor.process_batch(test_mode=args.test)


if __name__ == "__main__":
    # Use 'spawn' start method for compatibility with Androguard libraries
    # in worker processes and to ensure clean process state
    multiprocessing.set_start_method('spawn', force=True)
    main()
