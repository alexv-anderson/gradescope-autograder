
import json
import unittest

from main import FileValidator


def build_rubric_file_path(name: str) -> dict:
    return f"test_res/files/{name}/rubric.json"


def build_submission_dir_path(name: str) -> str:
    return f"test_res/files/{name}/submission"


def get_validator_results(name: str) -> Tuple:
        rubric_fp = build_rubric_file_path(name)
        fv = FileValidator(rubric_fp)
        return fv.validate(build_submission_dir_path(name))


class MyTestCase(unittest.TestCase):
    def test_required_name(self):
        res = get_validator_results("required_names")

        self.assertEqual((True, None), res)

    def test_required_name_missing(self):
        res = get_validator_results("required_names_missing")

        self.assertEqual(
            (False, ["Submission cannot contain file named App.java", "Submission is missing ['Main.java']"]),
            res
        )
    
    def test_required_patterns(self):
        res = get_validator_results("required_patterns")

        self.assertEqual((True, None), res)

    def test_required_patterns_missing(self):
        res = get_validator_results("required_patterns_missing")

        self.assertEqual(
            (False, ["App.java is not allowed in the submission"]),
            res
        )
        
    def test_required_patterns_too_many(self):
        res = get_validator_results("required_patterns_too_many")

        self.assertEqual(
            (False, ["Too many [A-Za-z0-9_]+.md files"]),
            res
        )
    
    def test_allowed_patterns(self):
        res = get_validator_results("allowed_patterns")

        self.assertEqual((True, None), res)
        
    def test_allowed_patterns_fail(self):
        res = get_validator_results("allowed_patterns_fail")

        self.assertEqual(
            (False, ["data.csv is not allowed in the submission"]),
            res
        )