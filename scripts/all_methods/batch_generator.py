#!/usr/bin/env python3
"""
Parallel Batch ALL_METHODS generation for the complete dataset.

This script processes APKs in parallel batches to generate .methods files
with complete signatures and MOP analysis.

Adapted for rvsec-02 project with Generic Specs (27 specs).

Usage:
    python3 -m all_methods.batch_generator --test  # Process 10 sample APKs
    python3 -m all_methods.batch_generator --all   # Process all 557 APKs in batches
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

    Args:
        args: (apk_path, package_name, output_file, specs_dir)

    Returns:
        (success, apk_name, message)
    """
    apk_path, package_name, output_file, specs_dir = args
    apk_name = Path(apk_path).name

    try:
        start_time = time.time()

        # Import here to avoid issues with multiprocessing
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from all_methods.novo import generate_all_methods_file

        generate_all_methods_file(
            apk_path=apk_path,
            apk_package=package_name,
            mop_specs_dir=specs_dir,
            output_file=output_file
        )

        end_time = time.time()
        duration = end_time - start_time

        # Check if file was created and has content
        if Path(output_file).exists() and Path(output_file).stat().st_size > 0:
            with open(output_file, 'r') as f:
                line_count = sum(1 for _ in f) - 1  # Subtract header

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
    Parallel batch processor for generating .methods files.

    Processes APKs in parallel batches with progress tracking and error handling.
    """

    def __init__(self, apks_dir: str, output_dir: str, specs_dir: str, batch_size: int = 5):
        self.apks_dir = Path(apks_dir)
        self.output_dir = Path(output_dir)
        self.specs_dir = specs_dir
        self.batch_size = batch_size

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize PackageDetector
        from all_methods.package_detector import PackageDetector
        self.package_detector = PackageDetector()
        print("PackageDetector initialized")

        # Statistics
        self.processed = 0
        self.failed = 0
        self.start_time = None

    def find_apk_package_pairs(self, test_mode: bool = False) -> List[Tuple[str, str]]:
        """
        Find APK files and detect their real package names using PackageDetector.

        Returns list of (apk_path, detected_package) tuples.
        """
        print("Discovering APK files and detecting package names...")

        # Get all APK files
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
        Process a batch of APKs in parallel.

        Returns (successful_count, failed_count)
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

        # Process in parallel
        with ProcessPoolExecutor(max_workers=self.batch_size) as executor:
            # Submit all tasks
            future_to_apk = {executor.submit(process_single_apk_worker, args): args[0] for args in worker_args}

            # Collect results as they complete
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
        Process all APKs in parallel batch mode.
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

        # Split APKs into batches
        batches = []
        for i in range(0, len(apk_package_pairs), self.batch_size):
            batch = apk_package_pairs[i:i + self.batch_size]
            batches.append(batch)

        total_batches = len(batches)
        print(f"Split into {total_batches} batches")

        # Process each batch
        for batch_num, batch_apks in enumerate(batches, 1):
            batch_start = time.time()

            successful, failed = self.process_batch_parallel(batch_apks, batch_num, total_batches)

            self.processed += successful
            self.failed += failed

            batch_end = time.time()
            batch_duration = batch_end - batch_start

            # Progress update
            total_processed = batch_num * self.batch_size
            if total_processed > len(apk_package_pairs):
                total_processed = len(apk_package_pairs)

            elapsed_total = time.time() - self.start_time
            rate = total_processed / elapsed_total * 60  # APKs per minute

            print(f"Progress: {total_processed}/{len(apk_package_pairs)} ({total_processed/len(apk_package_pairs)*100:.1f}%) | "
                  f"Success: {self.processed} | Failed: {self.failed} | "
                  f"Batch time: {batch_duration:.1f}s | Rate: {rate:.1f} APKs/min")

        # Final statistics
        self.print_final_statistics(len(apk_package_pairs))

    def print_final_statistics(self, total_apks: int) -> None:
        """Print final processing statistics."""
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


def main():
    parser = argparse.ArgumentParser(description="Parallel Batch ALL_METHODS generation for rvsec-02")
    parser.add_argument("--test", action="store_true", help="Test mode: process only 10 APKs")
    parser.add_argument("--all", action="store_true", help="Full mode: process all 557 APKs in batches")
    parser.add_argument("--batch-size", type=int, default=2, help="Number of parallel workers per batch (default: 2, conservative)")
    parser.add_argument("--sequential", action="store_true", help="Run sequentially (batch-size=1)")

    args = parser.parse_args()

    if not (args.test or args.all):
        print("Please specify --test or --all mode")
        parser.print_help()
        return

    # Handle sequential mode
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
    # Set multiprocessing start method for compatibility
    multiprocessing.set_start_method('spawn', force=True)
    main()
