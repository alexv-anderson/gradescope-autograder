
import os
import unittest

from grader import Rubric


def load_rubric_results(name: str) -> Rubric:
    rubric_path = os.path.join("test_res/rubric", name, "rubric.json")
    submission_dir_path = os.path.join("test_res/rubric", name, "submission")

    rubric = Rubric(rubric_path)
    res = rubric.grade(submission_dir_path)
    
    for fn in os.listdir(submission_dir_path):
        if not fn.endswith(".java") and not fn.endswith(".csv"):
            os.remove(os.path.join(submission_dir_path, fn))

    return res


class TestRubric(unittest.TestCase):
    def test_invalid_submission(self):
        res = load_rubric_results("invalid_submission")
        
        self.maxDiff = None
        self.assertEqual(
            {
                "score": 0,
                "output": "Submission cannot contain file named Helper.java" +
                    "\n\n" + "Submission cannot contain file named data.csv"
            },
            res
        )

    def test_compile_error(self):
        res = load_rubric_results("compile_error")

        self.maxDiff = None
        self.assertEqual(
            {
                "tests": [
                    {
                        "name": "Compile",
                        "score": 0,
                        "max_score": 2,
                        "status": "failed",
                        "output": "Compiling with: javac Main.java\n\n" +
                            "Main.java:4: error: ';' expected\n" +
                            '        System.out.println("Hello, world")\n' +
                            "                                          ^\n" +
                            "1 error\n"
                    }
                ]
            },
            res
        )
    
    def test_runtime_error(self):
        res = load_rubric_results("runtime_error")

        self.maxDiff = None
        self.assertEqual(
            {
                "tests": [
                    {
                        "name": "Compile",
                        "score": 2,
                        "max_score": 2,
                        "status": "passed",
                        "output": "Compiling with: javac Main.java"
                    },
                    {
                        "name": "Greeting",
                        "score": 0,
                        "max_score": 5,
                        "status": "failed",
                        "output": "Running with: java Main\n\n" +
                            "--- Terminal ---\n\nHello, world\n\n\n" +
                            "--- Error ---\n\n"
                            'Exception in thread "main" java.lang.RuntimeException: Psych\n' +
                            "\tat Main.main(Main.java:5)\n"
                    }
                ]
            },
            res
        )

    def test_criteria_error(self):
        res = load_rubric_results("criteria_error")

        self.maxDiff = None
        self.assertEqual(
            {
                "tests": [
                    {
                        "name": "Compile",
                        "score": 2,
                        "max_score": 2,
                        "status": "passed",
                        "output": "Compiling with: javac Main.java"
                    },
                    {
                        "name": "Greeting",
                        "score": 0,
                        "max_score": 5,
                        "status": "failed",
                        "output": "Running with: java Main\n\n" +
                                "--- Terminal ---\n\nHello, world\n\n\n" +
                                "--- Unexpected Output ---\n\nAt line 1 expected 'Hello, world!\n' but got 'Hello, world\n'"
                    }
                ]
            },
            res
        )
    
    def test_criteria_success(self):
        res = load_rubric_results("criteria_success")

        self.maxDiff = None
        self.assertEqual(
            {
                "tests": [
                    {
                        "name": "Compile",
                        "score": 2,
                        "max_score": 2,
                        "status": "passed",
                        "output": "Compiling with: javac Main.java"
                    },
                    {
                        "name": "Greeting",
                        "score": 5,
                        "max_score": 5,
                        "status": "passed",
                        "output": "Running with: java Main\n\n--- Terminal ---\n\nHello, world!\n"
                    }
                ]
            },
            res
        )

    def test_support_no_directory(self):
        test_dir_path = "test_res/support/no_directory"
        rubic = Rubric(f"{test_dir_path}/rubric.json")

        cwd = os.getcwd()
        os.chdir(test_dir_path)
        res = rubic.grade(f"submission")
        os.chdir(cwd)

        self.assertEqual({"tests": []}, res)
        self.assertTrue(os.path.exists(f"{test_dir_path}/submission/data.csv"))

        os.remove(f"{test_dir_path}/submission/data.csv")

    def test_support_no_directory_missing(self):
        test_dir_path = "test_res/support/no_directory_missing"
        rubic = Rubric(f"{test_dir_path}/rubric.json")

        cwd = os.getcwd()
        os.chdir(test_dir_path)
        res = rubic.grade(f"submission")
        os.chdir(cwd)

        self.assertEqual({"score": 0, "output": "Submitted files are valid but could not setup supporting files.\nPlease contact course staff/instructor"}, res)

    def test_support_directory(self):
        test_dir_path = "test_res/support/directory"
        rubic = Rubric(f"{test_dir_path}/rubric.json")

        cwd = os.getcwd()
        os.chdir(test_dir_path)
        res = rubic.grade(f"submission")
        os.chdir(cwd)

        self.assertEqual({"tests": []}, res)
        self.assertTrue(os.path.exists(f"{test_dir_path}/submission/data/fancy.csv"))

        os.remove(f"{test_dir_path}/submission/data/fancy.csv")
    
    def test_version_unknown(self):
        rubric = Rubric("test_res/version/no_version.json")

        self.assertTrue(rubric._rubric_compatible)
    
    def test_version_incompatible(self):
        rubric = Rubric("test_res/version/incompatible.json")

        self.assertFalse(rubric._rubric_compatible)
