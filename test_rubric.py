
import os
import unittest

from main import Rubric


def load_rubric_results(name: str) -> Rubric:
    rubric_path = os.path.join("test_res/rubric", name, "rubric.json")
    submission_dir_path = os.path.join("test_res/rubric", name, "submission")

    rubric = Rubric(rubric_path)
    return rubric.grade(submission_dir_path)


class TestRubric(unittest.TestCase):
    def test_invalid_submission(self):
        res = load_rubric_results("invalid_submission")
        
        self.assertEqual(
            {
                "score": 0,
                "output": "Submission cannot contain file named Helper.java" +
                    "\n\n" + "Submission cannot contain file named data.txt"
            },
            res
        )

    def test_compile_error(self):
        res = load_rubric_results("compile_error")

        print(res["tests"][0]["output"])
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