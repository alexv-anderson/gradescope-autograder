
import unittest

from main import Rubric


def get_rubric_results(file_name: str) -> Tuple:
    rubric = Rubric(f"test_res/{file_name}.json")
    return rubric.grade(f"test_res/{file_name}.txt")



class MyTestCase(unittest.TestCase):
    def test_separate_lines(self):
        results = get_rubric_results("seperate_lines_a")

        self.assertTrue(results[0], results[1])
        self.assertIsNone(results[1], "Passing tests should not have warning messages")