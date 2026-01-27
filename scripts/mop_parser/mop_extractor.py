#!/usr/bin/env python3
"""
MOP spec parser for RV-Android framework.

This module provides parsing functionality for JavaMOP specification files,
extracting monitored method references and exporting them in structured formats.

### Architectural Overview:
This parser implements a regex-based extraction approach optimized for the
standard JavaMOP specification format. It handles both explicit imports and
wildcard imports through a built-in Java class mapping. The module extracts
method references from AspectJ pointcut expressions (call patterns) and
constructs a static mapping of fully qualified class names.

### Key Architectural Decisions:
- **Regex-Based Parsing**: Uses pattern matching for call pattern extraction
  instead of formal parsing, enabling simple and maintainable implementation
- **Import Resolution**: Resolves wildcard imports via static class mapping
  for commonly used Java standard library classes
- **CSV Export**: Outputs class.method pairs as CSV for downstream processing,
  matching the format of the original mop-extractor.jar tool

### Role in the System:
- Extracts monitored methods from MOP specifications into structured format
- Generates input for reachability analysis to identify relevant methods
- Provides the method inventory for instrumentation pipeline

### Integration Points:
- Input: .mop specification files from specs/ directory
- Output: CSV files consumed by batch_generator and reachability modules
- Handles method references used in AspectJ pointcut expressions
"""

import re
import os
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple


@dataclass
class MopMethod:
    """Represents a method reference extracted from a MOP specification.

    Stores a single class.method pair identified in AspectJ pointcut expressions
    within a MOP specification file.
    """
    class_name: str           # Fully qualified class name (e.g., "java.util.Iterator")
    method_name: str          # Method name (e.g., "next", "new" for constructors)


@dataclass
class MopSpec:
    """Represents a parsed MOP specification file with extracted components.

    Contains the specification name, import declarations, and all monitored
    method references identified in the specification.
    """
    name: str                                    # Specification name (e.g., "Iterator_HasNext")
    file_path: str                               # Source .mop file path
    package: str = ""                            # Package declaration from spec
    imports: List[str] = field(default_factory=list)   # Import statements
    methods: List[MopMethod] = field(default_factory=list)  # Extracted method references


# Maps simple class names to fully qualified Java standard library names.
# Used for resolving wildcard imports in MOP specifications.
# Organized by package for maintainability and covers commonly used classes.
JAVA_CLASS_MAP: Dict[str, str] = {
    # java.lang (always implicitly imported)
    'Object': 'java.lang.Object',
    'String': 'java.lang.String',
    'Integer': 'java.lang.Integer',
    'Long': 'java.lang.Long',
    'Double': 'java.lang.Double',
    'Float': 'java.lang.Float',
    'Boolean': 'java.lang.Boolean',
    'Character': 'java.lang.Character',
    'Byte': 'java.lang.Byte',
    'Short': 'java.lang.Short',
    'Number': 'java.lang.Number',
    'Math': 'java.lang.Math',
    'System': 'java.lang.System',
    'Class': 'java.lang.Class',
    'Thread': 'java.lang.Thread',
    'Runnable': 'java.lang.Runnable',
    'Exception': 'java.lang.Exception',
    'Error': 'java.lang.Error',
    'Throwable': 'java.lang.Throwable',
    'StringBuilder': 'java.lang.StringBuilder',
    'StringBuffer': 'java.lang.StringBuffer',
    'CharSequence': 'java.lang.CharSequence',
    'Comparable': 'java.lang.Comparable',
    'Iterable': 'java.lang.Iterable',
    'AutoCloseable': 'java.lang.AutoCloseable',
    'Cloneable': 'java.lang.Cloneable',
    'Enum': 'java.lang.Enum',
    'Void': 'java.lang.Void',
    'Process': 'java.lang.Process',
    'ProcessBuilder': 'java.lang.ProcessBuilder',
    'Runtime': 'java.lang.Runtime',
    'NullPointerException': 'java.lang.NullPointerException',
    'IllegalArgumentException': 'java.lang.IllegalArgumentException',
    'IllegalStateException': 'java.lang.IllegalStateException',
    'ClassCastException': 'java.lang.ClassCastException',
    'IndexOutOfBoundsException': 'java.lang.IndexOutOfBoundsException',
    'Modifier': 'java.lang.reflect.Modifier',

    # java.util
    'Collection': 'java.util.Collection',
    'List': 'java.util.List',
    'Set': 'java.util.Set',
    'Map': 'java.util.Map',
    'Queue': 'java.util.Queue',
    'Deque': 'java.util.Deque',
    'Iterator': 'java.util.Iterator',
    'ListIterator': 'java.util.ListIterator',
    'Enumeration': 'java.util.Enumeration',
    'ArrayList': 'java.util.ArrayList',
    'LinkedList': 'java.util.LinkedList',
    'HashSet': 'java.util.HashSet',
    'TreeSet': 'java.util.TreeSet',
    'HashMap': 'java.util.HashMap',
    'TreeMap': 'java.util.TreeMap',
    'LinkedHashMap': 'java.util.LinkedHashMap',
    'LinkedHashSet': 'java.util.LinkedHashSet',
    'Vector': 'java.util.Vector',
    'Stack': 'java.util.Stack',
    'Hashtable': 'java.util.Hashtable',
    'Properties': 'java.util.Properties',
    'Arrays': 'java.util.Arrays',
    'Collections': 'java.util.Collections',
    'Comparator': 'java.util.Comparator',
    'Optional': 'java.util.Optional',
    'Random': 'java.util.Random',
    'Scanner': 'java.util.Scanner',
    'Timer': 'java.util.Timer',
    'TimerTask': 'java.util.TimerTask',
    'Calendar': 'java.util.Calendar',
    'Date': 'java.util.Date',
    'TimeZone': 'java.util.TimeZone',
    'Locale': 'java.util.Locale',
    'Currency': 'java.util.Currency',
    'UUID': 'java.util.UUID',
    'BitSet': 'java.util.BitSet',
    'PriorityQueue': 'java.util.PriorityQueue',
    'EnumSet': 'java.util.EnumSet',
    'EnumMap': 'java.util.EnumMap',
    'WeakHashMap': 'java.util.WeakHashMap',
    'IdentityHashMap': 'java.util.IdentityHashMap',
    'NavigableMap': 'java.util.NavigableMap',
    'NavigableSet': 'java.util.NavigableSet',
    'SortedMap': 'java.util.SortedMap',
    'SortedSet': 'java.util.SortedSet',
    'Spliterator': 'java.util.Spliterator',
    'StringTokenizer': 'java.util.StringTokenizer',

    # java.io
    'File': 'java.io.File',
    'InputStream': 'java.io.InputStream',
    'OutputStream': 'java.io.OutputStream',
    'Reader': 'java.io.Reader',
    'Writer': 'java.io.Writer',
    'BufferedInputStream': 'java.io.BufferedInputStream',
    'BufferedOutputStream': 'java.io.BufferedOutputStream',
    'BufferedReader': 'java.io.BufferedReader',
    'BufferedWriter': 'java.io.BufferedWriter',
    'ByteArrayInputStream': 'java.io.ByteArrayInputStream',
    'ByteArrayOutputStream': 'java.io.ByteArrayOutputStream',
    'CharArrayReader': 'java.io.CharArrayReader',
    'CharArrayWriter': 'java.io.CharArrayWriter',
    'DataInputStream': 'java.io.DataInputStream',
    'DataOutputStream': 'java.io.DataOutputStream',
    'FileInputStream': 'java.io.FileInputStream',
    'FileOutputStream': 'java.io.FileOutputStream',
    'FileReader': 'java.io.FileReader',
    'FileWriter': 'java.io.FileWriter',
    'FilterInputStream': 'java.io.FilterInputStream',
    'FilterOutputStream': 'java.io.FilterOutputStream',
    'FilterReader': 'java.io.FilterReader',
    'FilterWriter': 'java.io.FilterWriter',
    'InputStreamReader': 'java.io.InputStreamReader',
    'OutputStreamWriter': 'java.io.OutputStreamWriter',
    'LineNumberReader': 'java.io.LineNumberReader',
    'ObjectInputStream': 'java.io.ObjectInputStream',
    'ObjectOutputStream': 'java.io.ObjectOutputStream',
    'PipedInputStream': 'java.io.PipedInputStream',
    'PipedOutputStream': 'java.io.PipedOutputStream',
    'PipedReader': 'java.io.PipedReader',
    'PipedWriter': 'java.io.PipedWriter',
    'PrintStream': 'java.io.PrintStream',
    'PrintWriter': 'java.io.PrintWriter',
    'PushbackInputStream': 'java.io.PushbackInputStream',
    'PushbackReader': 'java.io.PushbackReader',
    'RandomAccessFile': 'java.io.RandomAccessFile',
    'SequenceInputStream': 'java.io.SequenceInputStream',
    'StreamTokenizer': 'java.io.StreamTokenizer',
    'StringBufferInputStream': 'java.io.StringBufferInputStream',
    'StringReader': 'java.io.StringReader',
    'StringWriter': 'java.io.StringWriter',
    'Closeable': 'java.io.Closeable',
    'Flushable': 'java.io.Flushable',
    'Serializable': 'java.io.Serializable',
    'Externalizable': 'java.io.Externalizable',
    'DataInput': 'java.io.DataInput',
    'DataOutput': 'java.io.DataOutput',
    'ObjectInput': 'java.io.ObjectInput',
    'ObjectOutput': 'java.io.ObjectOutput',
    'Console': 'java.io.Console',
    'FileDescriptor': 'java.io.FileDescriptor',
    'IOException': 'java.io.IOException',
    'FileNotFoundException': 'java.io.FileNotFoundException',
    'EOFException': 'java.io.EOFException',

    # java.nio
    'Buffer': 'java.nio.Buffer',
    'ByteBuffer': 'java.nio.ByteBuffer',
    'CharBuffer': 'java.nio.CharBuffer',
    'ShortBuffer': 'java.nio.ShortBuffer',
    'IntBuffer': 'java.nio.IntBuffer',
    'LongBuffer': 'java.nio.LongBuffer',
    'FloatBuffer': 'java.nio.FloatBuffer',
    'DoubleBuffer': 'java.nio.DoubleBuffer',
    'MappedByteBuffer': 'java.nio.MappedByteBuffer',
    'ByteOrder': 'java.nio.ByteOrder',
    'Channels': 'java.nio.channels.Channels',
    'Charset': 'java.nio.charset.Charset',
    'Path': 'java.nio.file.Path',
    'Paths': 'java.nio.file.Paths',
    'Files': 'java.nio.file.Files',

    # java.net
    'URL': 'java.net.URL',
    'URI': 'java.net.URI',
    'Socket': 'java.net.Socket',
    'ServerSocket': 'java.net.ServerSocket',
    'DatagramSocket': 'java.net.DatagramSocket',
    'DatagramPacket': 'java.net.DatagramPacket',
    'InetAddress': 'java.net.InetAddress',
    'Inet4Address': 'java.net.Inet4Address',
    'Inet6Address': 'java.net.Inet6Address',
    'InetSocketAddress': 'java.net.InetSocketAddress',
    'SocketAddress': 'java.net.SocketAddress',
    'NetworkInterface': 'java.net.NetworkInterface',
    'URLConnection': 'java.net.URLConnection',
    'HttpURLConnection': 'java.net.HttpURLConnection',
    'URLEncoder': 'java.net.URLEncoder',
    'URLDecoder': 'java.net.URLDecoder',
    'Proxy': 'java.net.Proxy',
    'MulticastSocket': 'java.net.MulticastSocket',

    # javax.crypto
    'Cipher': 'javax.crypto.Cipher',
    'SecretKey': 'javax.crypto.SecretKey',
    'SecretKeyFactory': 'javax.crypto.SecretKeyFactory',
    'KeyGenerator': 'javax.crypto.KeyGenerator',
    'KeyAgreement': 'javax.crypto.KeyAgreement',
    'Mac': 'javax.crypto.Mac',
    'CipherInputStream': 'javax.crypto.CipherInputStream',
    'CipherOutputStream': 'javax.crypto.CipherOutputStream',
    'SealedObject': 'javax.crypto.SealedObject',
    'SecretKeySpec': 'javax.crypto.spec.SecretKeySpec',

    # java.security
    'KeyStore': 'java.security.KeyStore',
    'MessageDigest': 'java.security.MessageDigest',
    'Signature': 'java.security.Signature',
    'SecureRandom': 'java.security.SecureRandom',
    'KeyPair': 'java.security.KeyPair',
    'KeyPairGenerator': 'java.security.KeyPairGenerator',
    'KeyFactory': 'java.security.KeyFactory',
    'AlgorithmParameters': 'java.security.AlgorithmParameters',
    'Provider': 'java.security.Provider',
    'Security': 'java.security.Security',
    'Certificate': 'java.security.cert.Certificate',
    'PublicKey': 'java.security.PublicKey',
    'PrivateKey': 'java.security.PrivateKey',
    'Key': 'java.security.Key',
}


class MopParser:
    """Parses JavaMOP specification files to extract monitored method references.

    Implements regex-based extraction of method calls from AspectJ pointcut
    expressions. Resolves class names through explicit imports and fallback
    to the standard Java class map for wildcard imports.

    ### Architectural Decisions:
    - Regex patterns for call() and target() AspectJ expressions
    - Two-phase resolution: explicit imports first, then standard class map
    - Deduplication of extracted methods to avoid duplicates in output

    ### Role in the System:
    - Parses individual .mop files and directories of specifications
    - Extracts method references that will be monitored at runtime
    - Enables identification of relevant methods in instrumentation pipeline

    ### Key Features:
    - Handles call(ReturnType ClassName.methodName(...)) patterns
    - Supports constructor patterns: call(ClassName.new(...))
    - Resolves method name wildcards (e.g., add*, write*)
    - Strips AspectJ type qualifiers (+ for subtypes)
    """

    def __init__(self):
        self.import_map: Dict[str, str] = {}

    def _build_import_map(self, imports: List[str]) -> Dict[str, str]:
        """Build a map from simple class name to fully qualified name from explicit imports.

        Processes import statements to create a lookup table for non-wildcard imports.
        Filters out wildcard imports (ending with .*) since those are resolved
        via JAVA_CLASS_MAP.

        Args:
            imports: List of import statement strings from the specification.

        Returns:
            Dictionary mapping simple class names to fully qualified names.
        """
        import_map = {}
        for imp in imports:
            imp = imp.strip().rstrip(';')
            if not imp.endswith('.*'):
                # Specific import: java.util.List -> List: java.util.List
                parts = imp.split('.')
                simple_name = parts[-1]
                import_map[simple_name] = imp
        return import_map

    def _resolve_class_name(self, simple_name: str, imports: List[str]) -> str:
        """Resolve a simple class name to its fully qualified name.

        Performs multi-level resolution: explicit imports, JAVA_CLASS_MAP,
        and returns the name as-is if unresolvable (for spec-local types).

        ### Implementation Notes:
        - Strips AspectJ subtype indicator (+) from class names
        - Skips primitive types and empty strings
        - Preserves already fully-qualified names (contain .)
        - Falls back to unqualified name for custom/unresolvable types

        Args:
            simple_name: Class name to resolve (may contain +, may be primitive).
            imports: List of import statements for context-specific resolution.

        Returns:
            Fully qualified class name if resolvable, otherwise simple name or empty string.
        """
        # Remove any + suffix (AspectJ subtype indicator)
        simple_name = simple_name.rstrip('+').strip()

        # Skip if empty or primitive type
        if not simple_name or simple_name in ('int', 'long', 'float', 'double', 'boolean', 'byte', 'short', 'char', 'void'):
            return ""

        # Check if already fully qualified
        if '.' in simple_name:
            return simple_name

        # Check explicit imports first
        import_map = self._build_import_map(imports)
        if simple_name in import_map:
            return import_map[simple_name]

        # Check global class map (resolves wildcard imports)
        if simple_name in JAVA_CLASS_MAP:
            return JAVA_CLASS_MAP[simple_name]

        # Return as-is if can't resolve (might be a spec-local type)
        return simple_name

    def _extract_from_call_patterns(self, content: str, imports: List[str]) -> List[MopMethod]:
        """Extract class.method references from call() pointcut patterns.

        Matches AspectJ call patterns to identify method references that will be
        monitored at runtime. Handles both method calls and constructors, including
        wildcard patterns and subtype indicators.

        ### Implementation Notes:
        - Pattern 1 matches: call(ReturnType ClassName[+].methodName(...))
          where ReturnType can be *, void, primitive, or class name
          and method name can include wildcards (add*, write*)
        - Pattern 2 matches: call(ClassName.new(...)) for constructors
        - Validates that extracted class names start with uppercase letter
        - Resolves simple class names to fully qualified names via imports

        Args:
            content: MOP specification file content.
            imports: List of import statements for name resolution.

        Returns:
            List of MopMethod objects extracted from call patterns.
        """
        methods = []

        # Pattern 1: call(ReturnType ClassName[+].methodName(...))
        # Extracts: ReturnType (can be * or type), ClassName (with optional +), methodName
        # Examples found in specs:
        #   call(* Set+.add(..))
        #   call(* Collections.synchronizedCollection(Collection))
        #   call(Set Map+.keySet())
        #   call(* Iterator.*(..))
        #   call(boolean Collection+.addAll(..))
        call_pattern = r'call\s*\(\s*(?:public\s+|private\s+|protected\s+)?(\*|[\w.]+(?:\[\])?)\s+([\w.]+)\s*\+?\s*\.\s*(\*|\w+\*?)\s*\([^)]*\)\s*\)'

        for match in re.finditer(call_pattern, content):
            return_type = match.group(1)
            class_name = match.group(2)
            method_name = match.group(3)

            full_class = self._resolve_class_name(class_name, imports)
            # Validate class name starts with uppercase (filter out variables)
            simple_class = full_class.split('.')[-1] if '.' in full_class else full_class
            if full_class and simple_class and simple_class[0].isupper():
                methods.append(MopMethod(
                    class_name=full_class,
                    method_name='new' if method_name == 'new' else method_name
                ))

        # Pattern 2: call(ClassName.new(...)) - constructors without explicit return type
        constructor_pattern = r'call\s*\(\s*([\w.]+)\s*\.\s*new\s*\([^)]*\)\s*\)'
        for match in re.finditer(constructor_pattern, content):
            class_name = match.group(1)
            full_class = self._resolve_class_name(class_name, imports)
            simple_class = full_class.split('.')[-1] if '.' in full_class else full_class
            if full_class and simple_class and simple_class[0].isupper():
                methods.append(MopMethod(
                    class_name=full_class,
                    method_name='new'
                ))

        return methods

    def _extract_from_target_patterns(self, content: str, imports: List[str]) -> List[MopMethod]:
        """Extract classes from target() pointcut patterns.

        Parses target(ClassName) patterns to identify monitored class types.
        Note: This method is currently reserved for future use. Specific method
        references are extracted via call() patterns instead.

        Args:
            content: MOP specification file content.
            imports: List of import statements for name resolution.

        Returns:
            Empty list (method reserved for future implementation).
        """
        methods = []

        # Pattern: target(ClassName) or !target(ClassName)
        # Negative lookahead (?!!) excludes negated patterns (!target(...))
        target_pattern = r'(?<!!)\s*target\s*\(\s*(\w+)\s*\)'

        for match in re.finditer(target_pattern, content):
            class_name = match.group(1)

            # Skip variable names (lowercase first letter)
            if not class_name or class_name[0].islower():
                continue

            full_class = self._resolve_class_name(class_name, imports)
            if full_class and full_class[0].isupper():
                # For target patterns, we identify monitored types but don't add
                # specific method entries - those come from call patterns instead
                pass

        return methods

    def parse_file(self, file_path: str) -> MopSpec:
        """Parse a MOP specification file to extract structure and method references.

        Reads a .mop file and extracts: package declaration, import statements,
        and method references from call patterns. Returns a complete MopSpec object
        with deduplicated method entries.

        Args:
            file_path: Path to the .mop specification file.

        Returns:
            MopSpec object containing parsed specification data.
        """
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        spec_name = Path(file_path).stem

        # Extract package declaration from file
        package_match = re.search(r'package\s+([\w.]+)\s*;', content)
        package = package_match.group(1) if package_match else ""

        # Extract all import statements
        imports = re.findall(r'import\s+([\w.*]+)\s*;', content)

        # Extract methods from call patterns
        methods = self._extract_from_call_patterns(content, imports)

        # Deduplicate methods to avoid duplicate entries in output
        seen = set()
        unique_methods = []
        for m in methods:
            key = (m.class_name, m.method_name)
            if key not in seen:
                seen.add(key)
                unique_methods.append(m)

        return MopSpec(
            name=spec_name,
            file_path=file_path,
            package=package,
            imports=imports,
            methods=unique_methods
        )

    def parse_directory(self, dir_path: str) -> List[MopSpec]:
        """Parse all MOP files in a directory.

        Processes all .mop specification files in the given directory
        in sorted order for deterministic results.

        Args:
            dir_path: Path to directory containing .mop files.

        Returns:
            List of MopSpec objects, one per file. Files with parsing
            errors are skipped with error messages printed to stdout.
        """
        specs = []
        dir_path = Path(dir_path)

        # Process in sorted order for deterministic output
        for mop_file in sorted(dir_path.glob('*.mop')):
            try:
                spec = self.parse_file(str(mop_file))
                specs.append(spec)
            except Exception as e:
                print(f"Error parsing {mop_file}: {e}")

        return specs


def export_to_csv(specs: List[MopSpec], output_path: str) -> None:
    """Export parsed specifications to CSV with class.method pairs.

    Aggregates all method references from parsed specifications,
    deduplicates them, and writes to CSV in the same format as
    the original mop-extractor.jar tool.

    Args:
        specs: List of MopSpec objects to export.
        output_path: Path to output CSV file.
    """
    # Collect all unique (class, method) pairs across all specs
    all_methods: Set[Tuple[str, str]] = set()

    for spec in specs:
        for method in spec.methods:
            all_methods.add((method.class_name, method.method_name))

    # Write to CSV in sorted order for deterministic output
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['class', 'method'])

        for class_name, method_name in sorted(all_methods):
            writer.writerow([class_name, method_name])


def main() -> None:
    """Command-line entry point for MOP spec parser.

    Parses MOP specifications from a directory, extracts method references,
    and exports results to CSV. Supports verbose output for debugging.
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Extract classes and methods from MOP specs'
    )
    parser.add_argument('--specs-dir', '-d', required=True, help='Directory containing .mop files')
    parser.add_argument('--output', '-o', required=True, help='Output CSV file')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    mop_parser = MopParser()
    specs = mop_parser.parse_directory(args.specs_dir)

    # Collect all unique method references across all specifications
    all_methods: Set[Tuple[str, str]] = set()
    for spec in specs:
        for method in spec.methods:
            all_methods.add((method.class_name, method.method_name))

    print(f"Parsed {len(specs)} specs")
    print(f"Found {len(all_methods)} unique class.method pairs")

    if args.verbose:
        print("\nMethods found:")
        for class_name, method_name in sorted(all_methods):
            print(f"  {class_name}.{method_name}")

    # Export to CSV
    export_to_csv(specs, args.output)
    print(f"Exported to: {args.output}")


if __name__ == '__main__':
    main()
