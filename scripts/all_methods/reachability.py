#!/usr/bin/env python
"""
Reachability analysis for APK methods against JavaMOP specifications.

This module generates .methods files containing static method inventory and
reachability information for Android APKs. It combines Androguard call graph
analysis with JavaMOP specification matching to identify which methods are
reachable from entry points and which methods interact with monitored APIs.

### Architectural Overview:
The module uses a three-phase approach: (1) extract method signatures via
static analysis tool (methods-extractor JAR), (2) perform Androguard call graph
analysis to identify reachability and call relationships, and (3) cross-reference
methods against JavaMOP specifications to determine which methods call monitored
APIs. The resulting CSV output represents 100% coverage baseline for APK analysis.

### Key Architectural Decisions:
- **Dual-Source Method Discovery**: Uses methods-extractor JAR for comprehensive
  signature extraction combined with Androguard for reachability analysis
- **Call Graph-Based Reachability**: Leverages NetworkX graph algorithms to
  determine method reachability from Android entry points (Activities, Services,
  Receivers, BroadcastReceivers)
- **JavaMOP Specification Matching**: Integrates with Python MOP parser to extract
  monitored methods from specifications, supporting wildcard patterns

### Role in the System:
- Generates .methods files (one per APK) containing method metadata
- Provides reachability baseline for coverage calculations
- Identifies direct and transitive relationships to MOP-monitored APIs
- Supports the instrumentation pipeline in RV4ANDROID processing

### Integration Points:
- Input: APK files, JavaMOP specifications (.mop), Android SDK for static analysis
- Output: CSV .methods files consumed by batch_generator and analysis pipeline
- Dependencies: Androguard (call graph), methods-extractor JAR, MopParser
"""

import csv
import subprocess
import os
import sys
import tempfile
from typing import Dict, Set, Optional, List
from androguard.core.bytecodes.dvm import get_type, EncodedMethod
import networkx as nx
from androguard.core.analysis.analysis import MethodAnalysis
from androguard.core.bytecodes.apk import APK
from androguard.misc import AnalyzeAPK

# Add parent directory (scripts/) to path for config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from processors.package_detector import PackageDetector



def generate_all_methods_file(apk_path: str, apk_package: str, mop_specs_dir: str, output_file: str) -> None:
    """
    Generate complete .methods file for an APK with reachability analysis.

    Orchestrates the three-phase pipeline: (1) static method signature extraction,
    (2) call graph analysis with reachability computation, and (3) CSV output.

    Args:
        apk_path: Full path to APK file to analyze.
        apk_package: Package name of the APK (used by methods-extractor).
        mop_specs_dir: Directory containing JavaMOP specification files.
        output_file: Output path for .methods CSV file.

    Raises:
        RuntimeError: If method extraction or Androguard analysis fails.
    """
    # Phase 1: Extract method signatures from static analysis tool
    signatures = _extract_method_signatures(apk_path, apk_package)

    # Phase 2: Perform Androguard call graph analysis and reachability computation
    all_methods = _analyze_with_androguard(apk_path, mop_specs_dir, signatures)

    # Phase 3: Export results to CSV
    _write_complete_csv(all_methods, output_file)


def _method_matches(pattern: str, method_name: str) -> bool:
    """
    Check if method name matches a specification pattern with wildcard support.

    Supports exact matching and prefix wildcard patterns (e.g., 'write*' matches
    'write', 'writeBytes', etc. A single '*' matches any method name).

    Args:
        pattern: Method name pattern from specification (may contain trailing '*').
        method_name: Actual method name to match against.

    Returns:
        True if method_name matches pattern, False otherwise.
    """
    if pattern == '*':
        return True
    if pattern.endswith('*'):
        return method_name.startswith(pattern[:-1])
    return pattern == method_name


def process_mop(node: MethodAnalysis, mop_methods: Set[MethodAnalysis], mop_methods_dict: Dict[str, Set[str]]) -> None:
    """
    Check if a call graph node matches a monitored method and collect matches.

    Identifies methods from the call graph that correspond to JavaMOP-monitored
    methods by comparing against the specification method dictionary. Supports
    wildcard patterns in method names.

    Args:
        node: MethodAnalysis node from Androguard call graph.
        mop_methods: Set accumulating matched MOP methods (modified in place).
        mop_methods_dict: Mapping of class name -> set of method patterns.
    """
    for clazz in mop_methods_dict:
        if clazz in str(node.get_class_name()):
            for method_pattern in mop_methods_dict[clazz]:
                # Wildcard patterns like 'write*', 'add*', '*' are supported
                if _method_matches(method_pattern, str(node.get_method().get_name())):
                    mop_methods.add(node)


def process_entrypoints(node: MethodAnalysis, entrypoints: Set[MethodAnalysis], entrypoints_classes: Set[str]) -> None:
    """
    Collect entry point methods from application components.

    Identifies public and protected methods from Android component classes
    (Activities, Services, Receivers, BroadcastReceivers) that serve as
    potential program entry points for reachability analysis.

    Args:
        node: MethodAnalysis node from Androguard call graph.
        entrypoints: Set accumulating entry point methods (modified in place).
        entrypoints_classes: Set of component class names (slashes as separators).
    """
    for e in entrypoints_classes:
        # Entry point methods are public or protected in component classes
        if e in str(node.get_class_name()) and str(node.get_access_flags_string()) in ["public", "protected"]:
            entrypoints.add(node)


def process_methods(node: MethodAnalysis, signatures: Dict) -> None:
    """
    Link call graph nodes to static method signatures.

    Matches Androguard call graph nodes with statically-extracted method signatures,
    enabling cross-referencing between the two analysis approaches. Only processes
    EncodedMethod (actual application methods), not ExternalMethod stubs.

    Args:
        node: MethodAnalysis node from Androguard call graph.
        signatures: Dictionary of signatures from static extraction (modified in place).
    """
    node_class = get_type(node.get_class_name())
    if node_class in signatures and isinstance(node.get_method(), EncodedMethod):
        node_method_sig = get_method_sig(node)
        if node_method_sig in signatures[node_class]:
            # Mark as found in call graph (signatures came from static analysis)
            signatures[node_class][node_method_sig]["found"] = True
            signatures[node_class][node_method_sig]["node"] = node


def reachable(nodes: Set[MethodAnalysis], method: Optional[MethodAnalysis], cg: nx.DiGraph) -> bool:
    """
    Check if a method is reachable from any entry point node.

    Determines whether a method can be called (directly or indirectly) from any
    of the provided source nodes in the call graph. Returns False for None methods.

    Args:
        nodes: Set of source nodes (typically entry points).
        method: Target method to check for reachability.
        cg: Call graph (directed graph with methods as nodes).

    Returns:
        True if any path exists from nodes to method in the call graph.
    """
    if method is None:
        return False
    return any(nx.has_path(cg, node, method) for node in nodes)

def reaches(nodes: Set[MethodAnalysis], method: Optional[MethodAnalysis], cg: nx.DiGraph) -> bool:
    """
    Check if a method reaches any monitored methods.

    Determines whether a method can call (directly or indirectly) any of the
    provided target nodes in the call graph. Returns False for None methods.

    Args:
        nodes: Set of target nodes (typically MOP-monitored methods).
        method: Source method to check.
        cg: Call graph (directed graph with methods as nodes).

    Returns:
        True if any path exists from method to nodes in the call graph.
    """
    if method is None:
        return False
    return any(nx.has_path(cg, method, node) for node in nodes)

def directly_reaches(nodes: Set[MethodAnalysis], method: Optional[MethodAnalysis], cg: nx.DiGraph) -> bool:
    """
    Check if a method directly calls any monitored methods.

    Determines whether a method directly invokes (one-hop) any of the provided
    target nodes in the call graph. Returns False for None methods.

    Args:
        nodes: Set of target nodes (typically MOP-monitored methods).
        method: Source method to check.
        cg: Call graph (directed graph with methods as nodes).

    Returns:
        True if method directly succeeds (calls) any node in the graph.
    """
    if method is None:
        return False
    return any(cg.has_successor(method, node) for node in nodes)


def _analyze_with_androguard(apk_path: str, mop_specs_dir: str, signatures: Dict) -> List[Dict]:
    """
    Perform call graph analysis and compute method reachability metrics.

    Uses Androguard to construct call graph from APK bytecode, extracts entry
    point methods from Android components, identifies monitored methods from
    JavaMOP specifications, and computes reachability relationships for all methods.

    ### Implementation Notes:
    - Call graph nodes are MethodAnalysis objects with getter methods for class
      and method information
    - Reachability is computed using NetworkX shortest path algorithms
    - Methods are marked as reachable if any path exists from entry points to them
    - Three MOP relationship types are computed: transitive reach, direct reach

    Args:
        apk_path: Path to APK file for Androguard analysis.
        mop_specs_dir: Directory containing JavaMOP specification files.
        signatures: Method signatures from static analysis (modified in place with
                   linked call graph nodes).

    Returns:
        List of dictionaries with method metadata and computed metrics for CSV output.
    """
    apk, _, analysis = AnalyzeAPK(apk_path)
    cg = analysis.get_call_graph()

    # Extract monitored methods from JavaMOP specifications
    mop_methods_dict = _get_javamop_methods(mop_specs_dir)

    # Get Android component classes that serve as entry points
    entrypoints_classes: Set[str] = _get_entrypoints_classes(apk)

    # Accumulate call graph nodes matching entry points and MOP methods
    mop_methods: Set[MethodAnalysis] = set()
    entrypoints: Set[MethodAnalysis] = set()

    all_methods = []

    # Traverse call graph to identify entry points and MOP-monitored methods
    for node in cg.nodes:
        process_mop(node, mop_methods, mop_methods_dict)
        process_entrypoints(node, entrypoints, entrypoints_classes)
        process_methods(node, signatures)

    # Compute reachability and MOP relationship metrics for all methods
    for clazz in signatures:
        for sig in signatures[clazz]:
            method = signatures[clazz][sig]
            method_data = {
                "class": clazz,
                "method": method["method"],
                "parameters": method["parameters"],
                "signature": method["signature"],
                "is_activity": (clazz in apk.get_activities()),
                # Method is reachable if entry points can reach it in call graph
                "reachable": reachable(entrypoints, method["node"], cg),
                # Method reaches MOP if it can call monitored methods (transitive)
                "reaches_mop": reaches(mop_methods, method["node"], cg),
                # Method directly reaches MOP if it calls monitored methods (1-hop)
                "directly_reaches_mop": directly_reaches(mop_methods, method["node"], cg),
                # Method found in call graph (confirmed by Androguard analysis)
                "androguard": method["found"]
            }
            all_methods.append(method_data)

    return all_methods


def _write_complete_csv(all_methods: List[Dict], output_file: str) -> None:
    """
    Write method analysis results to CSV file with standard columns.

    Creates output directory if needed and writes all methods with their metadata
    and computed reachability metrics in deterministic column order.

    Args:
        all_methods: List of method data dictionaries to export.
        output_file: Output path for CSV file.

    Raises:
        IOError: If output directory cannot be created or file cannot be written.
    """
    # Ensure output directory exists before writing
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    columns = ["class", "method", "parameters", "signature", "is_activity", "reachable", "reaches_mop",
               "directly_reaches_mop", "androguard"]

    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in all_methods:
            writer.writerow(row)


def _extract_method_signatures(apk_path: str, apk_package: str) -> Dict:
    """
    Extract method signatures from APK bytecode using static analysis tool.

    Invokes methods-extractor JAR with appropriate Android SDK paths and parses
    the output to build a signature dictionary. Format from tool: "class;method(param1,param2)"
    Separates components for downstream reachability matching.

    ### Implementation Notes:
    - Uses ANDROID_HOME environment variable with fallback default path
    - Methods-extractor output is text format with header line (skipped)
    - Signature format includes optional parameters; empty params stored as empty string
    - Results organized as nested dict: class -> signature -> method metadata

    Args:
        apk_path: Path to APK file for extraction.
        apk_package: Package name for the APK (required by methods-extractor).

    Returns:
        Dictionary structure: {class_name: {signature: {method, parameters, signature, found, node}}}

    Raises:
        Exception: If methods-extractor JAR execution fails or returns error code.
    """
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
        temp_output = temp_file.name

    try:
        # Configure Android SDK path for methods-extractor tool
        android_home = os.environ.get('ANDROID_HOME', '/home/pedro/desenvolvimento/aplicativos/android/sdk')
        android_platforms = os.path.join(android_home, 'platforms')

        cmd = [
            'java', '-jar', config.METHODS_EXTRACTOR_JAR,
            '--apk', apk_path,
            '--apk-package', apk_package,
            '--android-dir', android_platforms,
            '--output', temp_output
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(f"Methods-extractor failed: {result.stderr}")

        # Parse tool output into structured signature dictionary
        first_line = True
        signatures = {}
        with open(temp_output, 'r') as f:
            for line in f:
                if first_line:
                    first_line = False
                    continue
                line = line.strip()
                if ';' in line:
                    parts = line.split(';', 1)
                    if len(parts) == 2:
                        class_name = parts[0]
                        method_with_params = parts[1]

                        # Parse method(params) format into components
                        if '(' in method_with_params:
                            method_name = method_with_params.split('(')[0]
                            params_part = method_with_params[method_with_params.find('(')+1:]
                            params_part = params_part.rstrip(')')
                            parameters = params_part if params_part else ''
                        else:
                            method_name = method_with_params
                            parameters = ''

                        signature = f"{method_name}({parameters})"

                        if class_name not in signatures:
                            signatures[class_name] = {}

                        signatures[class_name][signature] = {
                            'method': method_name,
                            'parameters': parameters,
                            'signature': signature,
                            # Marker for cross-referencing with Androguard call graph
                            "found": False,
                            "node": None
                        }

        return signatures

    finally:
        # Clean up temporary file
        if os.path.exists(temp_output):
            os.unlink(temp_output)

def _get_javamop_methods(mop_specs_dir: str) -> Dict[str, Set[str]]:
    """
    Extract monitored methods from JavaMOP specification directory.

    Parses all JavaMOP .mop files and collects class/method pairs that are
    monitored by the specifications. Uses Python MOP parser for improved handling
    of wildcard imports compared to the original Java tool.

    ### Implementation Notes:
    - Dynamically imports MopParser from mop_parser module
    - Converts class names from dot notation to slash notation for Androguard
      compatibility (e.g., "java.util.Iterator" -> "java/util/Iterator")
    - Returns structure: {class_name: {method_name, method_name, ...}}
    - Supports wildcard method names from specifications

    Args:
        mop_specs_dir: Directory containing JavaMOP specification files (.mop).

    Returns:
        Dictionary mapping class names (slash format) to sets of method names.

    Raises:
        RuntimeError: If MOP parser fails or specifications directory is invalid.
    """
    # Import Python MOP parser from sibling module
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from mop_parser.mop_extractor import MopParser

    try:
        parser = MopParser()
        specs = parser.parse_directory(mop_specs_dir)

        # Build methods dictionary in format expected by process_mop()
        # Key: class name with forward slashes, Value: set of method names
        methods = {}
        for spec in specs:
            for mop_method in spec.methods:
                # Convert Java dot notation to Androguard slash notation
                class_name = mop_method.class_name.replace('.', '/')
                method_name = mop_method.method_name

                if class_name not in methods:
                    methods[class_name] = set()
                methods[class_name].add(method_name)

        return methods

    except Exception as e:
        print(f"Warning: Error extracting MOP methods: {e}")
        raise RuntimeError(f"Error extracting MOP methods: {e}")

def _get_entrypoints_classes(apk: APK) -> Set[str]:
    """
    Extract Android component classes that serve as program entry points.

    Collects all Activity, Service, Receiver, and BroadcastReceiver classes
    declared in the APK manifest. These are potential entry points for call
    graph reachability analysis.

    Args:
        apk: Androguard APK object from AnalyzeAPK.

    Returns:
        Set of class names in Androguard slash format (e.g., "android/app/Activity").
    """
    entrypoints = set()

    if apk.get_main_activity() is not None:
        entrypoints.add(apk.get_main_activity().replace('.', '/'))

    for c in apk.get_activities():
        entrypoints.add(c.replace('.', '/'))
    for c in apk.get_receivers():
        entrypoints.add(c.replace('.', '/'))
    for c in apk.get_services():
        entrypoints.add(c.replace('.', '/'))

    return entrypoints

def get_method_sig(method: MethodAnalysis) -> str:
    """
    Generate normalized method signature from MethodAnalysis object.

    Constructs a canonical method signature in the format "methodName(param1,param2)"
    by extracting parameters from the method's information dictionary.

    Args:
        method: MethodAnalysis object from Androguard call graph.

    Returns:
        Method signature string with format "name(params)".
    """
    params = ",".join(get_parameters(method.get_method()))
    params = f"({params})"
    return f"{method.get_method().get_name()}{params}"

def get_parameters(encoded_method: EncodedMethod) -> List[str]:
    """
    Extract parameter type names from an EncodedMethod.

    Retrieves parameter information from the method's metadata dictionary and
    returns the type names as a list of strings.

    Args:
        encoded_method: EncodedMethod object from Androguard.

    Returns:
        List of parameter type names (empty list if no parameters).
    """
    resultado_final = []

    if "params" in encoded_method.get_information():
        # Extract parameter types from method information (item[1] is the type)
        resultado_final = [str(item[1]) for item in encoded_method.get_information()["params"]]
    return resultado_final


def main() -> None:
    """
    Generate .methods file for a single APK (entry point for testing).

    Command-line interface for analyzing individual APKs and generating their
    .methods files. Detects the APK package name, performs reachability analysis,
    and writes output to the configured directory.

    Usage:
        python reachability.py [apk_name]

    Arguments:
        apk_name: APK filename to analyze (must exist in config.ALL_APKS directory).
                 Defaults to "byrne.utilities.hashpass_2.apk" if not specified.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Generate .methods file for a single APK")
    parser.add_argument("apk_name", nargs="?", default="byrne.utilities.hashpass_2.apk",
                        help="APK filename (must exist in ALL_APKS directory)")
    args = parser.parse_args()

    apk_name = args.apk_name
    apk_path = os.path.join(config.ALL_APKS, apk_name)
    mop_specs_dir = config.GENERIC_SPECS_DIR
    output = os.path.join(config.ALL_METHODS_GENERIC, f"{apk_name}.methods")

    print(f"APK: {apk_path}")
    print(f"Specs: {mop_specs_dir}")
    print(f"Output: {output}")

    package_detector = PackageDetector()
    manifest_pkg, detected_pkg, stats = package_detector.detect_package(apk_path)
    if detected_pkg:
        if manifest_pkg != detected_pkg:
            print(f"  Package changed: {manifest_pkg} -> {detected_pkg} (confidence: {stats['confidence']}), reason={stats['reason']}")
        else:
            print(f"  Package: {detected_pkg} (confidence: {stats['confidence']}), reason={stats['reason']}")
    else:
        print(f"  Failed to detect package name")
        return

    package = detected_pkg
    generate_all_methods_file(apk_path, package, mop_specs_dir, output)
    print(f"Done! Output: {output}")


if __name__ == "__main__":
    main()