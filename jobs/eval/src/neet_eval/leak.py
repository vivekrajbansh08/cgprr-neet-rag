"""Prompt-leak check used by the eval runner for `must_not_contain_file` (eval/golden/questions.yaml).

The implementation lives in neet_common.leak so the answer service's citation verifier and the eval
runner use the same rule. Re-exported here for existing callers.
"""

from neet_common.leak import MIN_LINE_LEN, leaked_lines, leaked_lines_from_file

__all__ = ["MIN_LINE_LEN", "leaked_lines", "leaked_lines_from_file"]
