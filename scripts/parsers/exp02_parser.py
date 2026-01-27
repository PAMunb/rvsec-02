#!/usr/bin/env python
"""
Logcat parser for RVSec runtime verification data processing.

This module parses Android logcat output in threadtime format to extract
runtime verification events: method coverage logs and property violations.

### Architectural Overview:
The parser implements a line-by-line parsing strategy optimized for threadtime
format logcat (-v threadtime) that includes timestamps. It extracts two types
of events: RVSEC-COV logs (method execution) and RVSEC-MOP-ERR logs (property
violations). Each event is parsed into structured dataclasses with timestamp
normalization handling midnight rollover for long test executions.

### Key Architectural Decisions:
- **Timestamp-Based Parsing**: Extracts and normalizes timestamps for relative
  time calculation, accounting for midnight rollovers during extended testing
- **Multi-Format Support**: Handles three error message formats (generic spec,
  JCA, and FSM) and two coverage message formats (modern and legacy)
- **Class Name Normalization**: Applies runtime/static analysis name normalization
  for inner classes to ensure consistent matching with static analysis output
- **Integer Truncation**: Timestamps truncated to seconds to eliminate temporal
  ordering issues caused by concurrent thread logging

### Role in the System:
- Parses raw logcat output into structured coverage and error events
- Provides temporal information for event sequencing and analysis
- Handles Android-specific issues (midnight rollover, class name variance)
- Feeds parsed data into coverage analysis and violation reporting pipelines

### Integration Points:
- Input: Logcat files in threadtime format from experiment execution
- Consumes: BaseLogcatParser for common functionality
- Depends on: domain.models (RvCoverageLog, RvErrorLog, LogcatFile)
- Output: Parsed events consumed by generators and coverage analysis scripts
"""

import re
from datetime import datetime
from typing import Optional, Tuple
from parsers.base_parser import BaseLogcatParser
from domain.models import RvErrorLog, RvCoverageLog, LogcatFile


class Exp02Parser(BaseLogcatParser):
    """
    Parses Android logcat output in threadtime format for RVSec experiments.

    Processes logcat lines to extract method execution coverage and property
    violation events with timestamp information. Implements multi-format
    support for both modern and legacy event message formats.

    ### Architectural Decisions:
    - Inherits common parsing functionality from BaseLogcatParser
    - Maintains per-instance state for relative timestamp calculation
    - Normalizes class names to handle runtime vs static analysis variance
    - Supports three distinct error message formats for flexibility

    ### Role in the System:
    - Primary entry point for logcat event extraction in the experiment pipeline
    - Converts unstructured logcat text to structured event dataclasses
    - Handles temporal synchronization for long-running tests
    - Ensures consistency between runtime and static analysis naming conventions

    ### Key Features:
    - Timestamp normalization with midnight rollover detection
    - Coverage log parsing with signature extraction
    - Error log parsing supporting multiple specification formats
    - Class name normalization for inner classes (java.io.InputStream.ParameterList)
    """

    def __init__(self, logcat_file: LogcatFile):
        """Initialize with metadata extracted from filename"""
        super().__init__(logcat_file)

        self.first_timestamp = None  # Track first event for relative time calculation
        self.first_date = None       # Track first event date for midnight rollover detection

    def parse_coverage_line(self, line: str) -> Optional[RvCoverageLog]:
        """
        Parse a coverage log line and extract method execution information.

        Args:
            line: A single logcat line in threadtime format.

        Returns:
            RvCoverageLog with parsed method information and timestamp, or None
            if the line does not contain a valid coverage event.
        """
        entry = self._parse_logcat_line(line)
        if not entry or entry["tag"] != self.TAG_COV:
            return None

        coverage = self._parse_coverage_message(entry["message"])
        if coverage:
            # Add timestamp from parsed entry
            coverage.time = self._calculate_time_since_start(entry["date"], entry["time"])
            return coverage
        return None

    def parse_error_line(self, line: str) -> Optional[RvErrorLog]:
        """
        Parse an error log line and extract violation information.

        Args:
            line: A single logcat line in threadtime format.

        Returns:
            RvErrorLog with parsed violation details and timestamp, or None
            if the line does not contain a valid error event.
        """
        entry = self._parse_logcat_line(line)
        if not entry or entry["tag"] != self.TAG_MOP_ERR:
            return None

        error = self._parse_error_message(entry["message"])
        if error:
            # Add timestamp from parsed entry
            error.time = self._calculate_time_since_start(entry["date"], entry["time"])
            return error
        return None

    def _parse_logcat_line(self, line: str) -> Optional[dict]:
        """
        Parse a single logcat line in threadtime format.

        Extracts date, time, process ID, thread ID, log level, tag, and
        message content from a logcat line. Pattern matches the threadtime
        format: MM-DD HH:MM:SS.mmm PID TID LEVEL TAG: MESSAGE

        Args:
            line: A single logcat output line.

        Returns:
            Dictionary with keys: date, time, pid, tid, level, tag, message,
            original; or None if the line does not match the expected format.
        """
        pattern = r"(\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+(\w)\s+(\S+)\s*:\s*(.*)"
        match = re.match(pattern, line)
        if not match:
            return None

        date, time, pid, tid, level, tag, message = match.groups()
        return {
            "date": date,
            "time": time,
            "pid": pid,
            "tid": tid,
            "level": level,
            "tag": tag,
            "message": message,
            "original": line.strip()
        }

    def _parse_error_message(self, message: str) -> Optional[RvErrorLog]:
        """
        Parse an error log message to extract violation details.

        Handles three error message formats:
        1. Generic spec format: "class.method(file:line) ::: SPEC went into an error state."
        2. JCA format: "SPEC,class,param1,method,param2,errortype,message"
        3. FSM format: "class.method(...) ::: message"

        ### Implementation Notes:
        - Applies class name normalization for inner classes
        - Constructs unique_msg for deduplication across runs
        - Returns None for malformed messages

        Args:
            message: The message content from a logcat RVSEC-MOP-ERR tag.

        Returns:
            RvErrorLog with parsed violation details, or None if parsing fails.
        """
        # First check if this is a generic "went into an error state" message
        if message.endswith("went into an error state."):
            generic = self._parse_generic_spec_error(message)
            if generic:
                # Apply normalization to class name (for inner classes)
                normalized_class = self.normalizer.normalize_class_name(generic["class"])

                # Use normalized class in unique_msg
                unique_msg = f"{normalized_class}:::{generic['method']}:::{generic['spec']}:::{generic['spec']}:::{generic['message']}"
                return RvErrorLog(
                    apk=self.apk,
                    rep=self.repetition,
                    timeout=self.timeout,
                    tool=self.tool,
                    time=None,  # Will be set by caller
                    spec=generic["spec"],
                    class_name=normalized_class,
                    original_class_name=generic["class"],
                    method=generic["method"],
                    message=generic["message"],
                    unique_msg=unique_msg
                )

        # Try to parse JCA specification error format
        parts = message.split(",")

        # Check if we have enough parts for the expected format
        if len(parts) >= 6:
            spec = parts[0]
            clazz = parts[1]
            method = parts[3]
            error_type = parts[5]
            msg = ",".join(parts[6:]) if len(parts) > 6 else "No additional message"

            # Apply normalization to class name (for inner classes)
            normalized_class = self.normalizer.normalize_class_name(clazz)

            # Use normalized class in unique_msg
            unique_msg = f"{normalized_class}:::{method}:::{spec}:::{error_type}:::{msg}"
            return RvErrorLog(
                apk=self.apk,
                rep=self.repetition,
                timeout=self.timeout,
                tool=self.tool,
                time=None,  # Will be set by caller
                spec=spec,
                class_name=normalized_class,
                original_class_name=clazz,
                method=method,
                message=msg,
                unique_msg=unique_msg
            )

        # Alternative format with ::: separator (FSM format)
        if ":::" in message:
            split = message.split(":::")
            if len(split) >= 2:
                tmp = split[0]
                tmp = tmp[:tmp.find("(") if "(" in tmp else len(tmp)]
                dot_idx = tmp.rfind(".")
                if dot_idx != -1:
                    clazz = tmp[:dot_idx]
                    method = tmp[dot_idx + 1:]
                    message_text = split[1].strip()
                    spec = message_text.split(" ")[0]

                    # Apply normalization to class name (for inner classes)
                    normalized_class = self.normalizer.normalize_class_name(clazz)

                    # Use normalized class in unique_msg
                    unique_msg = f"{normalized_class}:::{method}:::{spec}:::{spec}:::{message_text}"
                    return RvErrorLog(
                        apk=self.apk,
                        rep=self.repetition,
                        timeout=self.timeout,
                        tool=self.tool,
                        time=None,  # Will be set by caller
                        spec=spec,
                        class_name=normalized_class,
                        original_class_name=clazz,
                        method=method,
                        message=message_text,
                        unique_msg=unique_msg
                    )

        # Fallback for malformed messages
        return None

    def _parse_generic_spec_error(self, log_line: str) -> Optional[dict]:
        """
        Parse a generic specification error message.

        Pattern: class.method(file:line) ::: SPEC went into an error state.

        Args:
            log_line: The error message content.

        Returns:
            Dictionary with keys: class, method, file_name, line_number, spec,
            message; or None if the message does not match the pattern.
        """
        pattern = r"(.*)\.(.*)\((.*):(.*)\) ::: (.*) went into an error state."
        match = re.match(pattern, log_line)

        if match:
            class_name, method_name, file_name, line_number, spec = match.groups()
            return {
                "class": class_name,
                "method": method_name,
                "file_name": file_name,
                "line_number": int(line_number) if line_number.isdigit() else 0,
                "spec": spec,
                "message": f"{spec} went into an error state."
            }
        return None

    def _parse_coverage_message(self, message: str) -> Optional[RvCoverageLog]:
        """
        Parse a coverage log message to extract method execution information.

        Supports two message formats:
        1. Modern format: <class: returntype method(params)>
        2. Legacy format: class:::method:::params

        ### Implementation Notes:
        - Constructs signature as "class.method(params)"
        - Applies signature normalization to handle inner class variance
        - Applies class name normalization separately
        - Removes whitespace from parameters for consistency

        Args:
            message: The message content from a logcat RVSEC-COV tag.

        Returns:
            RvCoverageLog with parsed method information, or None if parsing fails.
        """
        # First try the modern format with angle brackets
        match = re.match(r"<([^:]+):\s+([^ ]+)\s+([^:(]+)\(([^)]*)\)>", message)
        if match:
            class_name, return_type, method_name, parameters = match.groups()

            if parameters:
                signature = f"{method_name}{parameters.replace(" ", "")}"
            else:
                signature = f"{method_name}()"
            signature = class_name + "." + signature
            signature = signature.replace(" ", "")

            # signature = f"{method_name}({parameters})"
            normalized_signature = self._normalize_signature(signature)

            # Apply normalization to class name as well (for inner classes)
            normalized_class = self.normalizer.normalize_class_name(class_name)

            return RvCoverageLog(
                apk=self.apk,
                rep=self.repetition,
                timeout=self.timeout,
                tool=self.tool,
                time=None,  # Will be set by caller
                class_name=normalized_class,
                original_class_name=class_name,
                method=method_name,
                signature=normalized_signature,
                original_signature=signature
            )

        # Try the legacy format with ::: separators
        parts = message.split(":::")
        if len(parts) >= 2:
            class_name = parts[0].strip()
            method_name = parts[1].strip()
            params = parts[2].strip() if len(parts) > 2 else ""

            # Parameters already include parentheses in threadtime format
            if params.startswith('(') and params.endswith(')'):
                signature = f"{method_name}{params}"
            else:
                signature = f"{method_name}({params})"
            signature = class_name + "." + signature
            signature = signature.replace(" ", "")

            normalized_signature = self._normalize_signature(signature)

            # Apply normalization to class name as well (for inner classes)
            normalized_class = self.normalizer.normalize_class_name(class_name)

            return RvCoverageLog(
                apk=self.apk,
                rep=self.repetition,
                timeout=self.timeout,
                tool=self.tool,
                time=None,  # Will be set by caller
                class_name=normalized_class,
                original_class_name=class_name,
                method=method_name,
                signature=normalized_signature,
                original_signature=signature
            )

        # Fallback for malformed messages
        return None


    def _calculate_time_since_start(self, date: str, time: str) -> float:
        """
        Calculate seconds elapsed since the first event in the logcat.

        Converts logcat timestamps to relative time by tracking the first event
        timestamp and computing offsets from it. Handles midnight rollovers during
        extended test executions by detecting date changes and adding 86400 seconds
        per day.

        ### Implementation Notes:
        - Maintains per-instance state: first_timestamp and first_date
        - Date format MM-DD; time format HH:MM:SS.mmm
        - Truncates to integer seconds to handle concurrent thread logging where
          events may have sub-millisecond timestamp inversion (< 12ms differences)
        - Handles same-month, month-to-month, and year transitions

        Args:
            date: Date string in MM-DD format (e.g., "12-27").
            time: Time string in HH:MM:SS.mmm format.

        Returns:
            Seconds since first event, truncated to integer (first event = 0.0).
        """
        # Parse time to get seconds since midnight
        time_parts = time.split(':')
        hours = int(time_parts[0])
        minutes = int(time_parts[1])
        seconds_part = time_parts[2].split('.')
        seconds = int(seconds_part[0])
        milliseconds = int(seconds_part[1]) if len(seconds_part) > 1 else 0

        # Calculate absolute seconds since midnight of CURRENT day
        absolute_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0

        # Initialize first_timestamp and first_date on first call
        if self.first_timestamp is None:
            self.first_timestamp = absolute_seconds
            self.first_date = date  # Store first date (MM-DD format)

        # Detect day change and adjust for midnight rollover
        day_offset = 0
        if date != self.first_date:
            # Calculate day difference from MM-DD strings
            first_month, first_day = map(int, self.first_date.split('-'))
            current_month, current_day = map(int, date.split('-'))

            # Simple day difference (handles same month, next month, and year transition)
            if current_month == first_month:
                # Same month: simple subtraction
                day_offset = current_day - first_day
            elif current_month == first_month + 1 or (first_month == 12 and current_month == 1):
                # Next month or year transition (12 → 01)
                # Crude approximation: assume ~30 days per month
                if first_month == 12 and current_month == 1:
                    # Year transition: 12-31 → 01-01
                    day_offset = (31 - first_day) + current_day
                else:
                    # Regular month transition
                    day_offset = (30 - first_day) + current_day
            else:
                # Fallback: assume next day (shouldn't happen in normal tests)
                day_offset = 1

            # Apply day offset (86400 seconds per day)
            absolute_seconds += day_offset * 86400

        # Calculate relative time
        relative_time = absolute_seconds - self.first_timestamp

        # Truncate to integer seconds to eliminate temporal order breaks
        # caused by concurrent thread logging (< 12ms inversions observed)
        return float(int(relative_time))

    def _convert_to_datetime(self, date: str, time: str) -> datetime:
        """
        Convert date and time strings from logcat format to a datetime object.

        Handles year inference for logcat timestamps that lack year information.
        Accommodates year transitions where log month (12) is in the previous year
        relative to current month (1).

        Args:
            date: Date string in MM-DD format.
            time: Time string in HH:MM:SS.mmm format.

        Returns:
            datetime object representing the specified date and time.
        """
        current_year = datetime.now().year

        # Handle edge case for year transition
        current_month = datetime.now().month
        log_month = int(date.split('-')[0])

        # If current month is January (1) and log month is December (12),
        # it means the log is from the previous year
        year = current_year - 1 if current_month == 1 and log_month == 12 else current_year

        date_format = "%Y-%m-%d %H:%M:%S.%f"
        date_str = f"{year}-{date} {time}"
        return datetime.strptime(date_str, date_format)

    def _get_tag(self, line: str) -> Tuple[Optional[str], str]:
        """
        Extract the log tag from a logcat line.

        Args:
            line: A single logcat output line.

        Returns:
            Tuple of (tag_string, empty_string) if tag found, or (None, None).
        """
        entry = self._parse_logcat_line(line)
        if entry and "tag" in entry:
            return entry["tag"], ""
        return None, None

