"""
Coverage analysis and aggregation for RV experiment execution.

This module provides tools for processing runtime coverage data extracted from logcat files,
matching executed methods against the static baseline, and computing coverage metrics
across multiple dimensions (activities, classes, methods, reachability, MOP usage).

### Architectural Overview:
The module uses a tracker-based approach to incrementally compute coverage metrics as
methods are encountered. CoverageTracker maintains sets of visited elements at each
coverage level (activities, classes, methods, reachable methods, MOP-related methods)
and calculates percentages against the static baseline. CoverageManager and MopErrorManager
orchestrate processing of logcat-derived logs across entire experiment datasets.

### Key Architectural Decisions:
- **Incremental Tracking**: Coverage metrics updated as each method is processed
- **Set-Based Deduplication**: Tracks unique visited elements to avoid double-counting
- **Percentage Normalization**: All coverage metrics expressed as percentages of baseline
- **Separation of Concerns**: Distinct managers for coverage and error processing

### Role in the System:
- Aggregates coverage data from parsed logcat files
- Validates executed methods against static analysis baseline (.methods files)
- Computes coverage metrics for APK/tool/timeout combinations
- Reports method mismatches between runtime and static analysis
- Extracts and deduplicates MOP property violations

### Integration Points:
- Input: RvCoverageLog and RvErrorLog instances from logcat parsers (Exp01Parser, Exp02Parser)
- Input: AllMethods instances containing static method inventory with reachability metadata
- Output: Coverage dictionaries with per-APK, per-tool, per-timeout metrics
- Output: Error lists and mismatch reports for analysis
"""

from pathlib import Path

from domain.models import LogcatFile, RvCoverageLog, SpecType, ExperimentType, RvErrorLog
from parsers.all_methods import AllMethods
from parsers.exp01_parser import Exp01Parser
from parsers.exp02_parser import Exp02Parser
from processors.package_detector import PackageDetector
from utils.file_utils import LogcatFileDiscovery, AllMethodsDiscovery
from typing import List


class MopErrorManager:
    """
    Deduplicates and aggregates MOP property violation reports from logcat parsing.

    Filters duplicate violations and maintains structured records for analysis,
    enabling identification of unique property violations across experiment execution.

    ### Architectural Decisions:
    - Deduplication based on unique_msg to identify semantically equivalent violations
    - Minimal state tracking to focus on aggregation task
    - Dictionary serialization for integration with CSV/JSON output pipelines

    ### Key Features:
    - Tracks unique violation messages across processed errors
    - Converts RvErrorLog objects to dictionary format for export
    - Optional verbose logging of violations during processing
    """

    def __init__(self):
        self.unique_errors = set()
        self.errors_data = []

    def process_file(self, mop_errors_list: List[RvErrorLog], verbose=True) -> dict:
        """
        Process a list of MOP errors and deduplicate by unique violation message.

        Args:
            mop_errors_list: List of RvErrorLog instances from logcat parsing.
            verbose: If True, prints each violation message encountered.

        Returns:
            Dictionary with keys:
            - unique_errors: Count of distinct violation messages
            - errors_data: List of dictionaries with violation details
        """
        self.unique_errors = set()
        self.errors_data = []
        for mop_error in mop_errors_list:
            # Skip duplicates based on violation message content
            if mop_error.unique_msg in self.unique_errors:
                continue
            if verbose:
                print(f"MOP error found: {mop_error.unique_msg}")
            self.unique_errors.add(mop_error.unique_msg)
            self.errors_data.append(mop_error.to_dict())
        return {
            "unique_errors": len(self.unique_errors),
            "errors_data": self.errors_data
        }

class CoverageManager:
    """
    Aggregates coverage data from logcat logs and matches against static baseline.

    Processes lists of executed method logs, validates them against the .methods file
    inventory, and computes coverage metrics across multiple dimensions. Tracks methods
    not found in the static baseline for mismatch analysis.

    ### Architectural Decisions:
    - Delegates coverage tracking to CoverageTracker for separation of concerns
    - Preserves full method execution context (APK, tool, timeout, execution time)
    - Deduplicates using CoverageTracker's visited_methods set

    ### Role in the System:
    - Orchestrates processing of logcat-derived coverage logs
    - Produces structured output with per-execution coverage metrics
    - Identifies mismatches for downstream validation and debugging

    ### Key Features:
    - Per-execution coverage context (APK, tool, timeout, repetition, timestamp)
    - Multi-dimensional coverage percentages (activities, classes, methods, reachability, MOP usage)
    - Mismatch detection and reporting for methods not in static baseline
    """

    def __init__(self, all_methods: AllMethods):
        self.all_methods = all_methods
        self.coverage_data = []
        self.mismatch = set()

    def process_cov_file(self, cov_list: List[RvCoverageLog], verbose=True) -> dict:
        """
        Process coverage logs from logcat parsing and compute metrics against baseline.

        Validates each executed method against the static AllMethods baseline,
        accumulates coverage metrics, and records methods not found in the baseline.

        ### Implementation Notes:
        - Coverage is computed cumulatively as methods are processed
        - Each method is only counted once via visited_methods tracking
        - Methods without signature matches are recorded in mismatch set
        - All coverage percentages are relative to the APK's static baseline

        Args:
            cov_list: List of RvCoverageLog instances from logcat parsing.
            verbose: If True, prints each method added to coverage and mismatches.

        Returns:
            Dictionary with keys:
            - coverage: Count of distinct methods matched to baseline
            - coverage_data: List of dictionaries with per-method coverage metrics
            - mismatch: List of method signatures not found in static baseline
        """
        # Coverage logs correspond to logcat lines. Normalizes method names
        # but does not validate package name boundaries.
        track = CoverageTracker(self.all_methods, verbose=verbose)
        self.coverage_data = []
        self.mismatch = set()
        for item in cov_list:
            cov = track.process(item)
            if cov:
                cov_item_data = {
                    "apk": item.apk,
                    "rep": item.rep,
                    "timeout": item.timeout,
                    "tool": item.tool,
                    "time": item.time,
                    "class": item.class_name,
                    "method": item.method,
                    "signature": item.signature,
                    "cov_act": cov["cov_activity"],
                    "cov_class": cov["cov_class"],
                    "cov_method": cov["cov_methods"],
                    "cov_reachable": cov["cov_reachable"],
                    "cov_reaches_mop": cov["cov_reaches_mop"],
                    "cov_directly_reaches_mop": cov["cov_directly_use_mop"]
                }
                self.coverage_data.append(cov_item_data)

        report = {
            "coverage": len(self.coverage_data),
            "coverage_data": self.coverage_data,
            "mismatch": list(track.mismatch_methods)
        }
        return report


class CoverageTracker:
    """
    Incrementally tracks method execution coverage against static analysis baseline.

    Maintains sets of executed methods at each coverage dimension (activities, classes,
    methods, reachability levels, MOP usage patterns) and computes coverage percentages
    as new methods are encountered. Deduplicates based on method signature.

    ### Architectural Decisions:
    - Segment coverage into distinct dimensions: activities, classes, methods, reachability, MOP usage
    - Lazy calculation of coverage percentages after each method update
    - Separate tracking sets for each coverage dimension to enable independent metrics
    - Deduplication via visited_methods to ensure each method counted once

    ### Role in the System:
    - Computes multi-dimensional coverage for a single logcat processing session
    - Validates executed methods against the static AllMethods baseline
    - Tracks mismatches between runtime and static method inventories
    - Reports coverage percentages for downstream aggregation

    ### Key Features:
    - Tracks unique methods across activity, class, and method levels
    - Segments coverage by reachability and MOP-relatedness
    - Deduplicates identical method invocations
    - Reports mismatches for methods not found in baseline
    """

    def __init__(self, all_methods: AllMethods, verbose=True):
        self.all_methods = all_methods
        self.verbose = verbose

        self.visited_methods = set()
        self.mismatch_methods = set()

        self.cov_activity = 0
        self.cov_class = 0
        self.cov_methods = 0
        self.cov_reachable = 0
        self.cov_reaches_mop = 0
        self.cov_directly_use_mop = 0

        self.called_activities = set()
        self.called_classes = set()
        self.called_methods = set()
        self.called_reachable_methods = set()
        self.called_reaches_mop_methods = set()
        self.called_directly_use_mop_methods = set()

    def process(self, cov: RvCoverageLog) -> dict | None:
        """
        Process a single coverage log entry and update coverage metrics.

        Validates the method signature against the AllMethods baseline, updates
        coverage sets if valid, and computes new coverage percentages.
        Records mismatches if the signature is not found in the baseline.

        Args:
            cov: RvCoverageLog instance representing a single method execution.

        Returns:
            Dictionary with coverage percentages if method is new and valid, None otherwise.
            Keys: cov_activity, cov_class, cov_methods, cov_reachable, cov_reaches_mop,
            cov_directly_use_mop (all as percentages).
        """
        if cov.signature in self.all_methods.signatures:
            # Skip duplicate executions of the same method
            if cov.signature not in self.visited_methods:
                self.visited_methods.add(cov.signature)
                method = self.all_methods.get_method(cov.signature)
                if method:
                    self._update_sets(method)
                    actual_cov = self._calculate_coverage()
                    if self.verbose:
                        print(f"Including {cov.signature}: {actual_cov}")
                    return actual_cov
        else:
            # Record methods not found in static baseline for mismatch analysis
            self.mismatch_methods.add(cov.signature)
            if self.verbose:
                print(f"Method: {cov.signature} not found in ALL_METHODS")
        return None

    def _safe_division(self, x: int, y: int) -> float:
        """
        Compute percentage (x/y * 100) with zero-division protection.

        Args:
            x: Numerator (count of executed elements).
            y: Denominator (total baseline elements).

        Returns:
            Percentage as float, or 0.0 if denominator is zero.
        """
        if y == 0:
            return 0.0
        return (x * 100) / y

    def _calculate_coverage(self) -> dict:
        """
        Compute coverage percentages for all tracked dimensions.

        Updates instance attributes and returns a dictionary with the same values.
        Each percentage is computed as (executed_count / baseline_count) * 100.

        Returns:
            Dictionary with keys:
            - cov_activity: Percentage of unique activity classes executed
            - cov_class: Percentage of unique classes executed
            - cov_methods: Percentage of unique methods executed
            - cov_reachable: Percentage of reachable methods executed
            - cov_reaches_mop: Percentage of MOP-related methods executed (direct or indirect)
            - cov_directly_use_mop: Percentage of methods directly using MOP APIs
        """
        self.cov_activity = self._safe_division(len(self.called_activities), len(self.all_methods.activities))
        self.cov_class = self._safe_division(len(self.called_classes), len(self.all_methods.classes))
        self.cov_methods = self._safe_division(len(self.called_methods), len(self.all_methods.methods))
        self.cov_reachable = self._safe_division(len(self.called_reachable_methods), self.all_methods.reachable_methods_count)
        self.cov_reaches_mop = self._safe_division(len(self.called_reaches_mop_methods), self.all_methods.reaches_mop_methods_count)
        self.cov_directly_use_mop = self._safe_division(len(self.called_directly_use_mop_methods), self.all_methods.directly_reaches_mop_methods_count)

        return {
            "cov_activity": self.cov_activity,
            "cov_class": self.cov_class,
            "cov_methods": self.cov_methods,
            "cov_reachable": self.cov_reachable,
            "cov_reaches_mop": self.cov_reaches_mop,
            "cov_directly_use_mop": self.cov_directly_use_mop
        }

    def _update_sets(self, method) -> None:
        """
        Update coverage tracking sets based on a method's properties.

        Adds the method to appropriate sets according to its static analysis attributes
        (is_activity, reachable, reaches_mop, directly_reaches_mop) to enable
        multi-dimensional coverage calculation.

        Args:
            method: Method object from AllMethods with class_name, signature, and boolean flags.
        """
        self.called_classes.add(method.class_name)
        if method.is_activity:
            self.called_activities.add(method.class_name)
        self.called_methods.add(method.signature)
        if method.reachable:
            self.called_reachable_methods.add(method.signature)
        if method.reaches_mop:
            self.called_reaches_mop_methods.add(method.signature)
        if method.directly_reaches_mop:
            self.called_directly_use_mop_methods.add(method.signature)


if __name__ == "__main__":
    # apk_name = "biz.gyrus.yaab_30.apk"
    apk_name = "byrne.utilities.hashpass_2.apk"
    # apk_name = "com.gianlu.dnshero_40.apk"
    # apk_name = "ca.farrelltonsolar.classic_314.apk"
    # apk_name = "com.euedge.openaviationmap.android_16.apk"
    # apk_name = "com.pindroid_69.apk"

# com.gianlu.dnshero_40.apk__1__10800__ape.logcat
# byrne.utilities.hashpass_2.apk__1__120__droidmate.logcat
    logcat_filename = f"{apk_name}__2__120__droidmate.logcat"
    logcat = LogcatFileDiscovery().get_logcat(logcat_filename, ExperimentType.EXP01, SpecType.JCA)

    # logcats = LogcatFileDiscovery().get_by_apk(apk_name, ExperimentType.EXP01, SpecType.JCA)
    # if not logcats:
    #     raise Exception("No logcat files found")
    # logcat = logcats[0]

    all_methods = AllMethodsDiscovery().find_all_methods(apk_name, SpecType.JCA)
    parser = Exp01Parser(logcat)
    # parser = Exp02Parser(logcat)
    coverage, mop_errors, errors, crashes_count = parser.parse_all_lines(verbose=True)

    # for cov in coverage:
    #     print(f"signature={cov.signature}")
    # print(f"coverage_len={len(coverage)}")
    # exit(1)

    # error_manager = MopErrorManager()
    # print(f"MOP ERRORS: {len(mop_errors)}")
    # if len(mop_errors) > 0:
    #     mop_report = error_manager.process_file(mop_errors)
    #     print(mop_report)
    # exit(1)


    print(f"COVERAGE: {len(coverage)}")
    tracker = CoverageTracker(all_methods)
    for cov_item in coverage:
        tracker.process(cov_item)

    for mis in tracker.mismatch_methods:
        if "hashpass" in mis:
            print(f"Mismatch: {mis}")

    print(f"*** RESULT: mismatch={len(tracker.mismatch_methods)} :: {tracker._calculate_coverage()}")
    exit(1)

    print("MANAGER *************")
    import pandas as pd
    manager = CoverageManager(all_methods)
    manager.process_cov_file(coverage)
    print(f">> {len(manager.coverage_data)}")
    if len(manager.coverage_data) > 0:
        df = pd.DataFrame(manager.coverage_data)
        coluna = ["method", "time", "cov_class", "cov_method"]#, "cov_reachable", "cov_reaches_mop", "cov_directly_reaches_mop"]
        print(df[coluna])


