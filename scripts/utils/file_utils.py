"""
File utilities for RVSec experiment results processing.

This module provides utilities for discovering, indexing, and managing logcat files
and method analysis files generated during runtime verification experiments.

### Architectural Overview:
The module implements a discovery-and-caching pattern where file systems are scanned
once during initialization and results are indexed by multiple dimensions (filename,
APK name, experiment type, spec type) to enable fast lookups. This design supports
efficient batch processing of experiment results across multiple specifications.

### Key Architectural Decisions:
- **Initialization-Time Discovery**: File system is scanned once during object construction to avoid repeated I/O
- **Multi-dimensional Indexing**: Results indexed by filename and APK to support diverse query patterns
- **Metadata Extraction**: Filename parsing extracts execution parameters (repetition, timeout, tool) without requiring separate metadata files
- **Lazy Loading**: Methods files are loaded on-demand when requested via find_all_methods()

### Role in the System:
- Discovers logcat files from experiment execution results across multiple batches
- Provides indexed access to execution logs for analysis and parsing
- Loads APK method inventories (.methods files) for coverage calculation
- Enables downstream parsers and generators to retrieve relevant data by APK or filename

### Integration Points:
- Input: Directory structures containing logcat files and .methods files from experiment execution
- Input: Configuration module for directory paths and file extensions
- Output: LogcatFile objects and AllMethods objects consumed by parsers and generators
- Integration: Works with domain.models (LogcatFile, ExperimentType, SpecType)
"""

import os
from pathlib import Path
from typing import List, Optional

import config
from domain.models import LogcatFile, ExperimentType, SpecType
from parsers.all_methods import AllMethods


class LogcatFileManager:
    """
    Manages logcat files from a single experiment execution directory.

    Scans a directory for logcat files and indexes them by filename and APK name
    to enable efficient lookup and retrieval during analysis.

    ### Architectural Decisions:
    - Scans directory once at initialization and maintains in-memory indexes
    - Indexes by both filename and APK name to support different query patterns
    - Raises FileNotFoundError if directory does not exist

    ### Role in the System:
    - Provides indexed access to logcat files from a single experiment batch
    - Enables APK-based lookup for parsing and coverage analysis
    - Supports retrieval of all files or files for a specific APK

    ### Key Features:
    - Fast O(1) lookup by APK name or filename
    - Handles multiple logcat files per APK (multiple runs)
    - Directory validation during initialization
    """

    def __init__(self, logcat_dir: str):
        """
        Initialize the logcat file manager with a directory.

        Args:
            logcat_dir: Path to directory containing logcat files.

        Raises:
            FileNotFoundError: If the specified directory does not exist.
        """
        self.logcat_dir = logcat_dir
        self.logcat_files_by_filename = {}
        self.logcat_files_by_apk = {}
        self._initialize()

    def _initialize(self):
        """
        Scan logcat directory and build indexed maps.

        Raises:
            FileNotFoundError: If the logcat directory does not exist.
        """
        if not os.path.exists(self.logcat_dir):
            raise FileNotFoundError(f"Logcat directory not found: {self.logcat_dir}")
        files = search_logcat_files(self.logcat_dir)
        for file in files:
            self.logcat_files_by_filename[file.file_name] = file
            if file.apk not in self.logcat_files_by_apk:
                self.logcat_files_by_apk[file.apk] = []
            self.logcat_files_by_apk[file.apk].append(file)

    def get_by_apk(self, apk: str) -> Optional[List[LogcatFile]]:
        """
        Retrieve all logcat files for a specific APK.

        Args:
            apk: APK filename or name (e.g., "com.example.app_24.apk").

        Returns:
            List of LogcatFile objects for the APK, or None if APK not found.
        """
        if apk in self.logcat_files_by_apk:
            return self.logcat_files_by_apk[apk]
        return None

    def get_all_apks(self) -> List[str]:
        """
        Get list of all APKs with logcat files in this directory.

        Returns:
            List of APK names.
        """
        return list(self.logcat_files_by_apk.keys())

    def get_all_files(self) -> List[LogcatFile]:
        """
        Get all logcat files indexed in this manager.

        Returns:
            List of all LogcatFile objects.
        """
        return list(self.logcat_files_by_filename.values())


class LogcatFileDiscovery:
    """
    Discovers and indexes logcat files across all configured experiment and spec combinations.

    Scans directories for all experiment/spec pairs defined in configuration and maintains
    multi-dimensional indexes for fast lookup by experiment, spec type, filename, or APK.

    ### Architectural Decisions:
    - Discovers all files for all combinations at initialization to enable efficient queries
    - Maintains nested dictionaries indexed by experiment then spec type for logical organization
    - Caches discovered files to avoid repeated file system scans
    - Supports lookup by filename, APK name, or directory listing

    ### Role in the System:
    - Provides unified access to logcat files from all experiment configurations
    - Enables queries across experiment and spec type dimensions
    - Generates summaries of available logcat coverage per configuration
    - Used by analysis pipelines to retrieve relevant execution logs

    ### Key Features:
    - Supports multiple experiment types and spec types (extensible)
    - Fast lookup by filename or APK across all configurations
    - Summary statistics for experiment coverage
    - Caching to avoid redundant file system access
    """

    def __init__(self):
        """
        Initialize discovery by scanning all configured experiment/spec directories.

        Raises:
            FileNotFoundError: If any configured directory does not exist.
            ValueError: If experiment or spec type is not supported.
        """
        self.all_logcat_files = {}
        self.all_logcat_files_by_filename = {}
        self.all_logcat_files_by_apk = {}
        self._initialize()

    def _initialize(self):
        """
        Scan all configured experiment/spec directories and build indexed maps.

        For each combination in config.COMBINATIONS, discovers logcat files and indexes
        them by filename and APK name for fast lookup.
        """
        for combo in config.COMBINATIONS:
            experiment = combo[0]
            spec = combo[1]
            if experiment not in self.all_logcat_files:
                self.all_logcat_files[experiment] = {}
                self.all_logcat_files_by_filename[experiment] = {}
                self.all_logcat_files_by_apk[experiment] = {}
            files = self.discover_logcat_files(experiment, spec)
            self.all_logcat_files[experiment][spec] = files
            self.all_logcat_files_by_filename[experiment][spec] = {}
            self.all_logcat_files_by_apk[experiment][spec] = {}
            for file in files:
                self.all_logcat_files_by_filename[experiment][spec][file.file_name] = file
                if file.apk not in self.all_logcat_files_by_apk[experiment][spec]:
                    self.all_logcat_files_by_apk[experiment][spec][file.apk] = []
                self.all_logcat_files_by_apk[experiment][spec][file.apk].append(file)

    def get_logcat(self, logcat_filename: str, experiment: ExperimentType, spec_type: SpecType) -> Optional[LogcatFile]:
        """
        Retrieve a specific logcat file by filename.

        Args:
            logcat_filename: Name of the logcat file (e.g., "com.example.app_1.apk__1__300__fastbot.logcat").
            experiment: Experiment type (e.g., ExperimentType.EXP02).
            spec_type: Specification type (e.g., SpecType.GENERIC).

        Returns:
            LogcatFile object if found, None otherwise.
        """
        if (experiment in self.all_logcat_files_by_filename
                and spec_type in self.all_logcat_files_by_filename[experiment]
                and logcat_filename in self.all_logcat_files_by_filename[experiment][spec_type]):
            return self.all_logcat_files_by_filename[experiment][spec_type][logcat_filename]
        return None

    def get_by_apk(self, apk: str, experiment: ExperimentType, spec_type: SpecType) -> Optional[List[LogcatFile]]:
        """
        Retrieve all logcat files for a specific APK.

        Args:
            apk: APK filename or name.
            experiment: Experiment type.
            spec_type: Specification type.

        Returns:
            List of LogcatFile objects for the APK, or None if not found.
        """
        if (experiment in self.all_logcat_files_by_apk
                and spec_type in self.all_logcat_files_by_apk[experiment]
                and apk in self.all_logcat_files_by_apk[experiment][spec_type]):
            return self.all_logcat_files_by_apk[experiment][spec_type][apk]
        return None

    def discover_logcat_files(self, experiment: ExperimentType, spec_type: SpecType) -> List[LogcatFile]:
        """
        Discover all logcat files for a specific experiment/spec combination.

        Args:
            experiment: Experiment type.
            spec_type: Specification type.

        Returns:
            List of LogcatFile objects found in the directory.

        Raises:
            FileNotFoundError: If the logcat directory does not exist.
            ValueError: If experiment or spec type is not supported.
        """
        if experiment in self.all_logcat_files and spec_type in self.all_logcat_files[experiment]:
            return self.all_logcat_files[experiment][spec_type]

        logcat_dir = ""
        if experiment == ExperimentType.EXP02:
            if spec_type == SpecType.GENERIC:
                logcat_dir = config.LOGCAT_EXP02_GENERIC_DIR
        else:
            raise ValueError(f"Unsupported experiment: {experiment}")

        if not logcat_dir:
            raise ValueError(
                f"Error retrieving logcat directory for exp: {experiment} and spec type: {spec_type}")

        if not os.path.exists(logcat_dir):
            raise FileNotFoundError(f"Logcat directory not found: {logcat_dir}")

        logcat_file_paths = list(Path(logcat_dir).glob("**/*.logcat"))
        return [self.create_logcat_file(str(path)) for path in logcat_file_paths]

    def summary(self) -> List[dict]:
        """
        Generate summary of logcat files across all configurations.

        Returns:
            List of dicts with keys: exp (experiment type), spec (spec type), files (count).
        """
        result = []
        for experiment in self.all_logcat_files:
            for spec in self.all_logcat_files[experiment]:
                result.append({
                    "exp": experiment,
                    "spec": spec,
                    "files": len(self.all_logcat_files[experiment][spec])
                })
        return result

    def create_logcat_file(self, logcat_file_path: str) -> LogcatFile:
        """
        Create a LogcatFile object from a file path.

        Extracts metadata from the filename and retrieves file size.

        Args:
            logcat_file_path: Absolute path to the logcat file.

        Returns:
            LogcatFile object with parsed metadata.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not os.path.exists(logcat_file_path):
            raise FileNotFoundError(f"Logcat file not found: {logcat_file_path}")

        logcat_file_name = os.path.basename(logcat_file_path)
        metadata = _extract_metadata_from_filename(logcat_file_name)

        return LogcatFile(
            apk=metadata['apk'],
            file_path=logcat_file_path,
            file_name=logcat_file_name,
            repetition=metadata['rep'],
            timeout=metadata['timeout'],
            tool=metadata['tool'],
            size_bytes=os.path.getsize(logcat_file_path)
        )


class AllMethodsDiscovery:
    """
    Discovers and caches .methods files generated by static analysis.

    Loads method inventory files (.methods) that contain the complete set of methods
    and their reachability information for each APK, enabling coverage calculation
    against the static analysis baseline.

    ### Architectural Decisions:
    - Loads all .methods files at initialization to enable fast lookups
    - Caches AllMethods objects in memory indexed by APK name
    - Supports multiple spec types through extensible initialization
    - Currently loads only GENERIC spec type (can be extended)

    ### Role in the System:
    - Provides access to static method inventories for all APKs
    - Enables coverage metrics calculation by matching runtime logs to all available methods
    - Supports reachability analysis and method signature normalization

    ### Key Features:
    - O(1) lookup of method inventory by APK name
    - Lazy caching of AllMethods objects
    - Support for multiple specification types
    """

    def __init__(self):
        """
        Initialize discovery by loading all .methods files for configured specs.

        Raises:
            FileNotFoundError: If the configured .methods directory does not exist.
        """
        self._methods_cache = {}
        self._cache_by_name = {}
        self._initialize()

    def _initialize(self):
        """
        Initialize all configured specification types.

        Currently initializes GENERIC spec type; can be extended for additional types.
        """
        self._init_spec(SpecType.GENERIC)

    def _init_spec(self, spec: SpecType):
        """
        Load and cache all .methods files for a specific spec type.

        Args:
            spec: Specification type (e.g., SpecType.GENERIC).

        Raises:
            FileNotFoundError: If the .methods directory for the spec does not exist.
        """
        all_methods_dir = config.ALL_METHODS_GENERIC

        files = search_files_by_extension(all_methods_dir, config.EXTENSION_METHODS)
        self._methods_cache[spec] = [AllMethods(f) for f in files]
        self._cache_by_name[spec] = {}
        for method in self._methods_cache[spec]:
            self._cache_by_name[spec][method.apk] = method

    def find_all_methods(self, apk_name: str, spec_type: SpecType = SpecType.GENERIC) -> Optional:
        """
        Retrieve the method inventory for a specific APK.

        Args:
            apk_name: APK filename or name.
            spec_type: Specification type (default: GENERIC).

        Returns:
            AllMethods object containing the method inventory, or None if not found.
        """
        if apk_name in self._cache_by_name.get(spec_type, {}):
            return self._cache_by_name[spec_type][apk_name]
        return None


def create_logcat_file(logcat_file_path: str) -> LogcatFile:
    """
    Create a LogcatFile object from a file path.

    Parses the filename to extract execution metadata and retrieves file size.

    Args:
        logcat_file_path: Absolute path to a logcat file.

    Returns:
        LogcatFile object with metadata and file information.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(logcat_file_path):
        raise FileNotFoundError(f"Logcat file not found: {logcat_file_path}")

    logcat_file_name = os.path.basename(logcat_file_path)
    metadata = _extract_metadata_from_filename(logcat_file_name)

    return LogcatFile(
        apk=metadata['apk'],
        file_path=logcat_file_path,
        file_name=logcat_file_name,
        repetition=metadata['rep'],
        timeout=metadata['timeout'],
        tool=metadata['tool'],
        size_bytes=os.path.getsize(logcat_file_path)
    )


def _extract_metadata_from_filename(logcat_filename: str) -> dict:
    """
    Extract execution metadata from a logcat filename.

    Parses filename with format: apk_name__rep__timeout__tool.logcat
    and extracts individual components into a metadata dictionary.

    ### Implementation Notes:
    - Handles malformed filenames by returning defaults with 'unknown' tool
    - Errors in parsing are logged to console but do not raise exceptions
    - The 'time' field is always set to 0 (not extracted from filename)

    Args:
        logcat_filename: Logcat filename (e.g., "com.example.app_24.apk__1__300__fastbot.logcat").

    Returns:
        Dictionary with keys: 'apk', 'rep' (int), 'timeout' (int), 'tool', 'time' (int).
        On parse error, returns dict with 'apk' as filename and defaults for other fields.
    """
    filename = logcat_filename.replace('.logcat', '')

    try:
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
                'time': 0
            }
        else:
            print(f"Warning: Could not parse filename format: {logcat_filename}")
            return {
                'apk': filename,
                'rep': 0,
                'timeout': 0,
                'tool': 'unknown',
                'time': 0
            }
    except Exception as e:
        print(f"Error parsing filename {logcat_filename}: {e}")
        return {
            'apk': filename,
            'rep': 0,
            'timeout': 0,
            'tool': 'unknown',
            'time': 0
        }


# =============================================================================
# FILE DISCOVERY HELPERS
# =============================================================================

def search_files_by_extension(base_dir: str, extension: str) -> List[Path]:
    """
    Search for files with a specific extension in a directory tree.

    Args:
        base_dir: Root directory to search.
        extension: File extension to match (e.g., ".logcat", ".methods").

    Returns:
        List of Path objects matching the extension.
    """
    return list(Path(base_dir).glob(f"**/*{extension}"))


def search_logcat_files(base_dir: str) -> List[LogcatFile]:
    """
    Search for all logcat files in a directory tree.

    Recursively scans the directory for files with the configured EXTENSION_LOGCAT
    and creates LogcatFile objects with parsed metadata.

    Args:
        base_dir: Root directory to search.

    Returns:
        List of LogcatFile objects.
    """
    logcat_file_paths = search_files_by_extension(base_dir, config.EXTENSION_LOGCAT)
    return [create_logcat_file(str(path)) for path in logcat_file_paths]


def search_logcat_by_name(base_dir: str, filename: str) -> List[LogcatFile]:
    """
    Search for logcat files matching a specific filename.

    Searches the directory tree and filters results by exact filename match.

    Args:
        base_dir: Root directory to search.
        filename: Target filename to match.

    Returns:
        List of LogcatFile objects with matching filename.
    """
    logcat_files = search_logcat_files(base_dir)
    return [logcat_file for logcat_file in logcat_files if logcat_file.file_name == filename]


# =============================================================================
# TEXT FILE UTILITIES
# =============================================================================

def read_valid_apks_file(file_path: str) -> List[str]:
    """
    Read a file containing a list of APK names.

    Each line in the file is treated as one APK name. Empty lines are skipped.
    Results are returned in sorted order for deterministic processing.

    Args:
        file_path: Path to file containing APK names (one per line).

    Returns:
        Sorted list of APK names.

    Raises:
        FileNotFoundError: If the file does not exist.
        IOError: If the file cannot be read.
    """
    valid_apks = []
    with open(file_path, 'r') as file:
        for line in file:
            stripped_line = line.strip()
            if stripped_line:
                valid_apks.append(stripped_line)
    return sorted(valid_apks)


if __name__ == "__main__":
    # Test the utilities
    print("Testing LogcatFileManager...")
    manager = LogcatFileManager(config.LOGCAT_EXP02_GENERIC_DIR)
    print(f"Total APKs: {len(manager.get_all_apks())}")
    print(f"Total files: {len(manager.get_all_files())}")
