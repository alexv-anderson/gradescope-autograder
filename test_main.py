
import unittest

from main import Criterion, Rubric


class CriterionTest(unittest.TestCase):
    def test_lines_default(self):
        criterion = Criterion({})

        self.assertIn("lines", criterion._datum)
        self.assertEqual(1, criterion._datum["lines"])

        criterion = Criterion({"lines": 2})
        self.assertEqual(2, criterion._datum["lines"])

    def test_ends_with_input_default(self):
        criterion = Criterion({})
        self.assertFalse(criterion.endsWithInput)

        criterion = Criterion({"endsWithInput": False})
        self.assertFalse(criterion.endsWithInput)

        criterion = Criterion({"endsWithInput": True})
        self.assertTrue(criterion.endsWithInput)

    def test_apply_exact_with_no_input(self):
        criterion = Criterion({
            "requirement": "exact",
            "expected": "What is your favorite number?"
        })

        res = criterion.apply(5, "What is your favorite number?")
        self.assertTrue(res[0])
        self.assertIsNone(res[1])

        res = criterion.apply(5, "What is your favorite number")
        self.assertFalse(res[0])
        self.assertTrue(res[1].startswith("At line 5"))

    def test_apply_exact_with_input(self):
        criterion = Criterion({
            "requirement": "exact",
            "expected": "What is your favorite number?",
            "endsWithInput": True
        })

        res = criterion.apply(5, "What is your favorite number?Twice your favorite number is 32")
        self.assertEqual((True, None), res)

        res = criterion.apply(5, "What is your favorite numberTwice your favorite number is 32")
        self.assertFalse(res[0])
        self.assertTrue(res[1].startswith("At line 5"))
    
    def test_apply_pattern_with_no_input(self):
        criterion = Criterion({
            "requirement": "pattern",
            "expected": "Welcome to [A-Za-z\\']+ maze!"
        })

        res = criterion.apply(5, "Welcome to Alex's maze!")
        self.assertEqual((True, None), res)

        res = criterion.apply(5, "Welcome to Alex's maze")
        self.assertFalse(res[0])
        self.assertTrue("on line 5" in res[1])
    
    def test_apply_pattern_with_input(self):
        criterion = Criterion({
            "requirement": "pattern",
            "expected": "Welcome to [A-Za-z\\']+ maze!",
            "endsWithInput": True
        })

        res = criterion.apply(5, "Welcome to Alex's maze!Hello world")
        self.assertEqual((True, None), res)

        res = criterion.apply(5, "Welcome to Alex's mazeHello world")
        self.assertFalse(res[0])
        self.assertTrue("on line 5" in res[1])

    def test_apply_pattern_with_input_fail(self):
        criterion = Criterion({
            "requirement": "pattern",
            "expected": "Twice your favorite number is [0-9]+"
        })

        res = criterion.apply(5, "?Twice your favorite number is 32")
        self.assertFalse(res[0])

    def test_consume_exact(self):
        criterion = Criterion({
            "requirement": "exact",
            "expected": "Hello, world"
        })

        remain = criterion.consume("Hello, world!")
        self.assertEqual("!", remain)

        remain = criterion.consume("Hello, world")
        self.assertIsNone(remain)

    def test_consume_pattern(self):
        criterion = Criterion({
            "requirement": "pattern",
            "expected": "Hello, world"
        })

        remain = criterion.consume("Hello, world!")
        self.assertEqual("!", remain)

        remain = criterion.consume("Hello, world")
        self.assertIsNone(remain)

    def test_update_exhausted(self):
        criterion = Criterion({"lines": 2})

        self.assertFalse(criterion.is_exhausted())

        criterion.update()
        self.assertFalse(criterion.is_exhausted())

        criterion.update()
        self.assertTrue(criterion.is_exhausted())

        criterion.update()
        self.assertTrue(criterion.is_exhausted())


def get_rubric_results(file_name: str, ed=None) -> Tuple:
    rubric = Rubric(f"test_res/rubric/{file_name}.json")
    return rubric.grade(f"test_res/rubric/{file_name}{ed if ed is not None else ''}.txt")


class RubricTest(unittest.TestCase):
    def test_separate_lines_with_no_input(self):
        results = get_rubric_results("seperate_lines_a")

        self.assertTrue(results[0], results[1])
        self.assertIsNone(results[1], "Passing tests should not have warning messages")

    def test_separate_lines_with_no_input_fail_pattern(self):
        results = get_rubric_results("seperate_lines_a", 1)

        self.assertFalse(results[0], results[1])

    def test_separate_lines_with_input(self):
        results = get_rubric_results("seperate_lines_b")

        self.assertTrue(results[0], results[1])
        self.assertIsNone(results[1], "Passing tests should not have warning messages")

    def test_separate_lines_with_input_fail(self):
        results = get_rubric_results("seperate_lines_b", 1)

        self.assertFalse(results[0], results[1])