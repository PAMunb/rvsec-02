"""
Base parser for Android logcat files in RV-Android framework.

This module provides the abstract base class for parsing runtime verification
output from Android logcat, extracting coverage information and property violations.

### Architectural Overview:
The parser implements a template method pattern where subclasses override
parse_coverage_line() and parse_error_line() to handle format-specific parsing.
The base class handles file I/O, line iteration, metadata extraction from filenames,
and signature normalization. Two log tags are monitored: RVSEC-COV for method coverage
and RVSEC for property violations.

### Key Architectural Decisions:
- **Abstract Methods for Format Handling**: Subclasses implement parse_coverage_line()
  and parse_error_line() to support different logcat formats (with/without timestamps)
- **Signature Normalization**: Applies inner class corrections (e.g., TabLayout$Tab vs TabLayout.Tab)
  to enable matching between static analysis and runtime data
- **Metadata Extraction from Filename**: Parses execution context from logcat filename format
  (apk_name__repetition__timeout__tool.logcat) without requiring separate metadata files

### Role in the System:
- Provides base parsing functionality for logcat files from instrumented APKs
- Extracts coverage metrics (executed methods) and violations for analysis
- Serves as the foundation for format-specific parser implementations
- Normalizes method signatures for consistency with static analysis output

### Integration Points:
- Input: Logcat files from results/{batch}/{timestamp}/{apk_name}/*.logcat
- Output: RvCoverageLog and RvErrorLog objects for downstream processing
- Dependencies: domain.models for data classes, processors.signature_normalizer for normalization
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from domain.models import RvErrorLog, RvCoverageLog, LogcatFile
from processors.signature_normalizer import SignatureNormalizer


class BaseLogcatParser(ABC):
    """
    Abstract base class for parsing Android logcat files and extracting runtime verification data.

    This class defines the interface and common functionality for parsing logcat output,
    handling file I/O, metadata extraction, and signature normalization.

    ### Architectural Decisions:
    - Uses class constants for tag identification to avoid magic strings
    - Delegates format-specific parsing to abstract methods for subclass implementation
    - Maintains state for all parsed data in instance variables
    - Performs signature normalization on all extracted method references

    ### Role in the System:
    - Parses runtime verification output from instrumented Android applications
    - Extracts coverage data (method executions) for metrics computation
    - Extracts violation data (property violations) for security analysis
    - Provides metadata about the execution (APK, tool, timeout, repetition)

    ### Key Features:
    - Multi-line parsing with configurable verbosity for debugging
    - Automatic metadata extraction from logcat filename format
    - Crash detection and counting from logcat messages
    - Error line collection for anomaly detection
    - Signature normalization to handle inner class notation differences
    """

    # Logcat tag for coverage events (method execution logs)
    TAG_COV = "RVSEC-COV"
    # Logcat tag for property violation events
    TAG_MOP_ERR = "RVSEC"

    def __init__(self, logcat_file: LogcatFile) -> None:
        """
        Initialize parser with a logcat file.

        Args:
            logcat_file: LogcatFile object containing file path and name.

        Initializes signature normalizer and extracts execution metadata from filename.
        """
        self.logcat_file = logcat_file
        self.normalizer = SignatureNormalizer()

        # Extract execution context from filename format: apk__rep__timeout__tool.logcat
        metadata = self._extract_metadata_from_filename(logcat_file.file_name)
        self.apk = metadata['apk']
        self.repetition = metadata['rep']
        self.timeout = metadata['timeout']
        self.tool = metadata['tool']

    def parse_all_lines(self, verbose: bool = True) -> Tuple[List[RvCoverageLog], set, set, int]:
        """
        Parse all lines from logcat file and extract coverage, violations, and errors.

        Iterates through logcat file line-by-line, identifying logs by tag (RVSEC-COV or RVSEC)
        and delegating to format-specific parse methods. Also counts crashes and collects
        anomalous lines for error analysis.

        ### Implementation Notes:
        - Coverage logs are returned as a list (order matters for analysis)
        - Violation and error logs are returned as sets (duplicates removed)
        - Crashes are detected by "beginning of crash" string in logcat
        - Lines with "beginning of main" or "beginning of system" are skipped (logcat headers)
        - All whitespace is normalized (newlines, tabs, carriage returns removed)

        Args:
            verbose: If True, prints detailed progress for each line during parsing.

        Returns:
            Tuple of (coverage_list, violations_set, errors_set, crash_count):
                - coverage_list: List of RvCoverageLog objects in chronological order
                - violations_set: Set of RvErrorLog objects from RVSEC tags
                - errors_set: Set of unexpected/anomalous logcat lines
                - crash_count: Integer count of application crashes detected
        """
        if verbose:
            print(f"Parsing logcat file: {self.logcat_file.file_path}")
        coverage = []
        mop_errors = set()
        errors = set()
        crashes_count = 0

        with open(self.logcat_file.file_path, 'r') as f:
            for linha in f.readlines():
                # Normalize line by removing whitespace characters
                line = linha.replace('\n', '').replace('\t', '').replace('\r', '').strip()
                if verbose:
                    print(f"\nLine: {line}")

                tag, _ = self._get_tag(line)

                if tag == self.TAG_COV:
                    # Parse coverage (method execution) log
                    cov = self.parse_coverage_line(line)
                    if cov:
                        coverage.append(cov)
                    if verbose:
                        print(f"Coverage: {cov}")
                elif tag == self.TAG_MOP_ERR:
                    # Parse violation (property error) log
                    err = self.parse_error_line(line)
                    if err:
                        mop_errors.add(err)
                    if verbose:
                        print(f"MOP: {err}")
                elif "beginning of crash" in line:
                    # Count application crash
                    crashes_count += 1
                    if verbose:
                        print(f"Crash: {crashes_count}")
                else:
                    # Skip logcat system headers and collect other unexpected lines
                    if "beginning of main" in line or "beginning of system" in line:
                        continue
                    errors.add(line)
                    if verbose:
                        print(f"ERRO: {line}")

        return coverage, mop_errors, errors, crashes_count


    @abstractmethod
    def parse_coverage_line(self, line: str) -> Optional[RvCoverageLog]:
        """
        Parse a coverage log line (RVSEC-COV tag) to extract method execution data.

        Subclasses implement format-specific parsing for different logcat formats
        (e.g., with or without timestamps).

        Args:
            line: A single logcat line tagged with RVSEC-COV.

        Returns:
            RvCoverageLog object representing the method execution, or None if parsing fails.
        """
        pass

    @abstractmethod
    def parse_error_line(self, line: str) -> Optional[RvErrorLog]:
        """
        Parse a violation log line (RVSEC tag) to extract property violation data.

        Subclasses implement format-specific parsing for different violation formats.

        Args:
            line: A single logcat line tagged with RVSEC.

        Returns:
            RvErrorLog object representing the property violation, or None if parsing fails.
        """
        pass

    def _normalize_signature(self, signature: str) -> str:
        """
        Apply inner class corrections to method signatures for matching with static analysis.

        Normalizes inner class notation from runtime format (TabLayout.Tab) to static
        analysis format (TabLayout$Tab) to enable correct matching in coverage analysis.

        Args:
            signature: Method signature string from logcat.

        Returns:
            Normalized signature with corrected inner class notation.
        """
        return self.normalizer.normalize_signature(signature)

    def _extract_metadata_from_filename(self, logcat_filename: str) -> dict:
        """
        Extract execution metadata from logcat filename.

        Parses filename format: {apk_name}__{repetition}__{timeout}__{tool}.logcat
        Example: com.example.app_24.apk__1__10800__fastbot.logcat

        ### Implementation Notes:
        - Double underscores (__) separate filename components
        - Repetition and timeout are parsed as integers
        - Tool name is the last component before .logcat extension
        - Graceful fallback with defaults if parsing fails

        Args:
            logcat_filename: Filename to parse (with or without .logcat extension).

        Returns:
            Dictionary with keys: 'apk', 'rep', 'timeout', 'tool', 'time'
            On parse failure, returns dict with defaults (rep=1, timeout=10800, tool='unknown').
        """
        # Remove .logcat extension if present
        filename = logcat_filename.replace('.logcat', '')

        try:
            # Split by double underscore to get components
            parts = filename.split('__')

            if len(parts) >= 4:
                apk_name = parts[0]
                rep = int(parts[1])
                timeout = int(parts[2])
                tool = parts[3]

                return {
                    'apk': apk_name,
                    'rep': rep,
                    'timeout': timeout,
                    'tool': tool,
                    'time': None  # Timestamp extracted from logcat lines if available
                }
            else:
                print(f"Warning: Could not parse filename format: {logcat_filename}")
                return {
                    'apk': filename,
                    'rep': 1,
                    'timeout': 10800,
                    'tool': 'unknown',
                    'time': None
                }
        except Exception as e:
            print(f"Error parsing filename {logcat_filename}: {e}")
            return {
                'apk': filename,
                'rep': 1,
                'timeout': 10800,
                'tool': 'unknown',
                'time': None
            }

    @abstractmethod
    def _get_tag(self, line: str) -> Tuple[Optional[str], str]:
        """
        Extract logcat tag from a line.

        Parses the logcat line format to identify and return the tag portion.
        Subclasses implement format-specific tag extraction (e.g., handling timestamps).

        Args:
            line: A single logcat line.

        Returns:
            Tuple of (tag, remaining_content) where tag is one of TAG_COV, TAG_MOP_ERR,
            or None if line does not start with a recognized tag.
        """
        pass

