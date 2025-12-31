#!/usr/bin/env python
"""
Generate .methods file for a single APK.
Adapted for rvsec-02 project with Generic Specs.
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
from all_methods.package_detector import PackageDetector



def generate_all_methods_file(apk_path: str, apk_package: str, mop_specs_dir: str, output_file: str):
    # Step 1: Get method signatures from methods-extractor
    signatures = _extract_method_signatures(apk_path, apk_package)

    # Step 2: Perform complete androguard analysis
    all_methods = _analyze_with_androguard(apk_path, mop_specs_dir, signatures)

    # Step 3: Write all_methods to CSV
    _write_complete_csv(all_methods, output_file)


def process_mop(node, mop_methods, mop_methods_dict):
    for clazz in mop_methods_dict:
        if clazz in str(node.get_class_name()):
            for method in mop_methods_dict[clazz]:
                # This handles method overloading per JavaMOP semantics
                if method == str(node.get_method().get_name()):
                    mop_methods.add(node)


def process_entrypoints(node, entrypoints, entrypoints_classes):
    for e in entrypoints_classes:
        # os entrypoints sao todos os metodos publicos e protected
        if e in str(node.get_class_name()) and str(node.get_access_flags_string()) in ["public", "protected"]:
            entrypoints.add(node)


def process_methods(node, signatures):
    node_class = get_type(node.get_class_name())
    if node_class in signatures and isinstance(node.get_method(), EncodedMethod): # nao trata ExternalMethod
        node_method_sig = get_method_sig(node)
        if node_method_sig in signatures[node_class]:
            signatures[node_class][node_method_sig]["found"] = True # marca como encontrado no callgraph (signatures "veio" do soot)
            signatures[node_class][node_method_sig]["node"] = node


def reachable(nodes, method, cg):
    # retorna true se o method eh alcancavel por algum dos nodes
    if method is None:
        return False
    return any(nx.has_path(cg, node, method) for node in nodes)

def reaches(nodes, method, cg):
    # retorna true se o method alcanca algum dos nodes
    if method is None:
        return False
    return any(nx.has_path(cg, method, node) for node in nodes)

def directly_reaches(nodes, method, cg):
    # retorna true se o method alcanca diretamente algum dos nodes
    if method is None:
        return False
    return any(cg.has_successor(method, node) for node in nodes)


def _analyze_with_androguard(apk_path: str, mop_specs_dir: str, signatures) -> List[Dict]:
    # print(f"Performing androguard analysis: {apk_path}")

    apk, _, analysis = AnalyzeAPK(apk_path)
    cg = analysis.get_call_graph()

    # Get MOP methods from specifications
    mop_methods_dict = _get_javamop_methods(mop_specs_dir)

    # Get entrypoints classes
    entrypoints_classes: Set[str] = _get_entrypoints_classes(apk)

    # call graph nodes
    mop_methods: Set[MethodAnalysis] = set()
    entrypoints: Set[MethodAnalysis] = set()

    all_methods = []

    # percorre o callgraph e "captura" nodes de interesse
    for node in cg.nodes:
        process_mop(node, mop_methods, mop_methods_dict)
        process_entrypoints(node, entrypoints, entrypoints_classes)
        process_methods(node, signatures)

    for clazz in signatures:
        for sig in signatures[clazz]:
            method = signatures[clazz][sig]
            method_data = {
                "class": clazz,
                "method": method["method"],
                "parameters": method["parameters"],
                "signature": method["signature"],
                "is_activity": (clazz in apk.get_activities()),
                "reachable": reachable(entrypoints, method["node"], cg),
                "reaches_mop": reaches(mop_methods, method["node"], cg),
                "directly_reaches_mop": directly_reaches(mop_methods, method["node"], cg),
                "androguard": method["found"]
            }
            all_methods.append(method_data)

    return all_methods


def _write_complete_csv(all_methods, output_file: str) -> None:
    # Ensure output directory exists
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
    Execute methods-extractor JAR to get full method signatures.
    Parse format: class;method(param1,param2) → separate components
    """
    # print("Extracting method signatures...")

    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
        temp_output = temp_file.name

    try:
        # Execute methods-extractor with correct parameters
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

        # Parse the output
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

                        # Extract method name and parameters
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
                            "found": False, # encontrou no callgraph
                            "node": None
                        }

        return signatures

    finally:
        # Clean up temp file
        if os.path.exists(temp_output):
            os.unlink(temp_output)

def _get_javamop_methods(mop_specs_dir: str) -> Dict[str, Set[str]]:
    """
    Extract MOP methods from JavaMOP specifications.
    ADAPTED from existing get_javamop_methods in rv-android
    """
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
        methods_file = temp_file.name

    try:
        # Use MOP_EXTRACTOR_JAR from config
        cmd = [
            'java', '-jar', config.MOP_EXTRACTOR_JAR,
            '-t', 'METHODS',
            '-d', mop_specs_dir,
            '-o', methods_file
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Warning: MOP extractor failed: {result.stderr}")
            return {}

        # Parse the methods file
        first_line = True
        methods = {}
        with open(methods_file, 'r') as data:
            for line in csv.reader(data):
                if first_line:
                    first_line = False
                    continue
                if len(line) >= 2:
                    class_name = line[0].replace('.', '/')
                    method_name = line[1]
                    if class_name not in methods:
                        methods[class_name] = set()
                    methods[class_name].add(method_name)

        return methods

    except Exception as e:
        print(f"Warning: Error extracting MOP methods: {e}")
        raise RuntimeError(f"Error extracting MOP methods: {e}")
        # return {}
    finally:
        # Clean up temp file
        if os.path.exists(methods_file):
            os.unlink(methods_file)

def _get_entrypoints_classes(apk: APK) -> Set[str]:
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

def get_method_sig(method: MethodAnalysis):
    params = ",".join(get_parameters(method.get_method()))
    params = f"({params})"
    return f"{method.get_method().get_name()}{params}"

def get_parameters(encoded_method: EncodedMethod):
    resultado_final = []

    # if isinstance(encoded_method, ExternalMethod):
    #     print(f"ExternalMethod: {encoded_method}")

    if "params" in encoded_method.get_information():
        resultado_final = [str(item[1]) for item in encoded_method.get_information()["params"]]
    return resultado_final


def main():
    """Test function - generates .methods for a single APK."""
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