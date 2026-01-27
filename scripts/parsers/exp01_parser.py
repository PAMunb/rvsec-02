#!/usr/bin/env python
"""
Exp01 Parser for RV-Android data processing.

ADAPTED FROM: /home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec/rv-android/rvandroid/parser/log/logcat_parser_exp01.py
CHANGES: Preserve full signatures + signature normalization
FORMAT: -v tag (NO timestamps)
"""

from typing import Optional
from parsers.base_parser import BaseLogcatParser
from domain.models import RvErrorLog, RvCoverageLog, LogcatFile


class Exp01Parser(BaseLogcatParser):

    def __init__(self, logcat_file: LogcatFile):
        super().__init__(logcat_file)

    def parse_coverage_line(self, line: str) -> Optional[RvCoverageLog]:
        """
        Parse RVSEC-COV line preserving complete signatures.
        ORIGINAL: Only method name
        NEW: Complete class:::method:::parameters
        """
        tag, right_term = self._get_tag(line)
        if tag == self.TAG_COV:
            return self._parse_coverage_method_sig(right_term)
        return None

    def parse_error_line(self, line: str) -> Optional[RvErrorLog]:
        """Parse RVSEC error line."""
        tag, right_term = self._get_tag(line)
        if tag == self.TAG_MOP_ERR:
            return self._parse_error(right_term)
        return None

    def _parse_error(self, s: str) -> RvErrorLog:
        """
        Parse an error log line into an RvErrorLog object.
        ADAPTED from original to_error function.
        """
        if "FSM" in s:
            split = s.split(":::")
            tmp = split[0]
            tmp = tmp[:tmp.find("(")]
            dot_idx = tmp.rfind(".")
            clazz = tmp[:dot_idx]
            method = tmp[dot_idx + 1:]
            message = split[1].strip()
            spec = message.split(" ")[0]
        else:
            split = s.split(",")
            spec = split[0]
            clazz = split[1]
            method = split[3]
            # source = split[4]
            # error_type = split[5]
            msg_idx = self._find_sixth_comma(s)
            message = s[msg_idx + 1:].strip()

        # Apply normalization to class name (for inner classes)
        # IMPORTANT: Use normalize_class_name for class names, not normalize_signature
        normalized_class = self.normalizer.normalize_class_name(clazz)

        unique_msg = f"{normalized_class}:::{method}:::{spec}:::{spec}:::{message}"
        return RvErrorLog(
            apk=self.logcat_file.apk,
            rep=self.logcat_file.repetition,
            timeout=self.logcat_file.timeout,
            tool=self.logcat_file.tool,
            time=0,  # exp01 has no timestamps
            spec=spec,
            class_name=normalized_class,
            original_class_name=clazz,
            method=method,
            message=message,
            unique_msg=unique_msg
        )

    def _find_sixth_comma(self, text: str) -> int:
        """Find the position of the sixth comma in a text."""
        idx = -1
        for _ in range(6):
            idx = text.find(',', idx + 1)
            if idx == -1:
                break
        return idx

    def _parse_coverage_method_sig(self, text: str) -> RvCoverageLog:
        """
        Parse a coverage log line into an RvCoverageLog object.
        ENHANCED: Preserve complete signatures with normalization.
        """
        sp = text.split(":::")

        clazz = sp[0].strip()
        method = sp[1].strip()
        params = sp[2].strip() if len(sp) > 2 else ""

        # Create complete signature
        # NOTE: params already come with parentheses from logcat: (android.content.Context)
        # So we just append them directly, not add extra parentheses
        if params:
            signature = f"{method}{params.replace(" ", "")}"
        else:
            signature = f"{method}()"
        signature = clazz + "." + signature

        # Apply signature normalization for inner classes
        normalized_signature = self._normalize_signature(signature)

        # Apply normalization to class name as well (for inner classes)
        # IMPORTANT: Use normalize_class_name for class names, not normalize_signature
        normalized_class = self.normalizer.normalize_class_name(clazz)

        return RvCoverageLog(
            apk=self.apk,
            rep=self.repetition,
            timeout=self.timeout,
            tool=self.tool,
            time=0,  # exp01 has no timestamps
            class_name=normalized_class,
            original_class_name=clazz,
            method=method,
            signature=normalized_signature,
            original_signature=signature,
        )

    def _get_tag(self, line: str):
        """Extract the tag and content from a logcat line."""
        tag = ""
        text = ""

        if ":" in line:
            idx = line.index(":")
            tag = line[2:idx].strip()
            text = line[idx + 1:].strip()

        return tag, text
