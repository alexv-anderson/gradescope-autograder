
import json
import os
import re
import subprocess
import sys


class Criterion:
    def __init__(self, d: dict):
        if "lines" not in d:
            d["lines"] = 1
        self._datum = d

        self.endsWithInput = "endsWithInput" in d and d["endsWithInput"]
    
    def __str__(self) -> str:
        return json.dumps(self._datum)
    
    def apply(self, num: int, l: str) -> tuple:
        msg = None

        req = self._datum["requirement"]
        if req == "ignore":
            # No requirements for this line
            pass
        elif req == "exact":
            exp = self._datum["expected"]
            
            match_prefix_with_input = self.endsWithInput and l.startswith(exp)
            full_match = not self.endsWithInput and l == exp

            if not (full_match or match_prefix_with_input):
                msg = f"At line {num} expected '{exp}' but got '{l}'"

        elif req == "pattern":
            if not re.match(self._datum["expected"], l):
                msg = f"'{l}' on line {num} has an incorrect pattern"
        else:
            msg = f"ERROR: Unrecognized requirement for line {num}"
        
        return (msg is None, msg)
    
    def consume(self, l: str) -> str:
        pattern = self._datum["expected"]
        if re.match(pattern, l):
            remain = l[re.search(pattern, l).span()[1]:]
            if len(remain) > 0:
                return remain
        return None

    def update(self):
        self._datum["lines"] -= 1
    
    def is_exhausted(self):
        return self._datum["lines"] < 1
    

class OutputValidator:
    def __init__(self, fp: str):
        if isinstance(fp, list):
            self._output = fp
        else:
            with open(fp, "r") as f:
                data = json.load(f)
            
            self._output = data["output"]
    
    def grade(self, out_fp: str) -> tuple:
        print("\n----------------------\n\n")

        criterion = self._load_next_criterion()

        with open(out_fp, "r") as f:
            line_num = 1
            for l in f:
                while True:
                    if criterion is None:
                        return (False, f"No criterion for '{l}' on line {line_num}")

                    # print(f"Line {line_num}: '{l}' -> {criterion}")

                    result = criterion.apply(line_num, l)
                    # print(f"\tResult: {result}")
                    if not result[0]:
                        return result
                    
                    line_num += 1
                    
                    criterion.update()
            
                    get_next_line = True
                    if criterion.endsWithInput:
                        l = criterion.consume(l)
                        get_next_line = False
                        print(l)
                    
                    if criterion.is_exhausted():
                        # print(f"\tExhausted criterion: {criterion}")
                        criterion = self._load_next_criterion()
                        # print(f"\tLoaded: {criterion}")

                    end_of_rubric = criterion is None

                    if get_next_line or end_of_rubric:
                        break

        return (True, None)
    
    def _load_next_criterion(self):
        if len(self._output) == 0:
            return None

        req = self._output.pop(0)
        
        return Criterion(req)


def find_match_pattern_index(patterns: list, s: str) -> int | None:
    for i, pattern in enumerate(patterns):
        if re.match(pattern, s):
            return i
    return None


def find_search_pattern_index(patterns: list, s: str) -> int | None:
    for i, pattern in enumerate(patterns):
        if re.search(pattern, s):
            return i
    return None


class FileValidator:
    def __init__(self, fp: str):
        with open(fp, "r") as f:
            data = json.load(f)
        
        self._files = data["files"] if "files" in data else {}
        self._content = data["content"] if "content" in data else {}
    
    def validate(self, dir_path: str) -> tuple:
        res = self._validate_files(dir_path)
        if not res[0]:
            return res
        
        feedback = []
        for fn in os.listdir(dir_path):
            fp = os.path.join(dir_path, fn)
            feedback += self._validate_file_content(fp)
        
        has_feedback = len(feedback) > 0
        return (
            not has_feedback,
            feedback if has_feedback else None
        )
    
    def _validate_files(self, dir_path: str) -> tuple:
        feedback = []

        has_requirements = "required" in self._files
        has_required_names = has_requirements and "names" in self._files["required"]
        has_required_patterns = has_requirements and "patterns" in self._files["required"]
        has_allowed_patterns = "allowed" in self._files
        has_forbidden_patterns = "forbidden" in self._files
        has_forbidden_patterns_exceptions = has_forbidden_patterns and "exceptions" in self._files["forbidden"]

        required_patterns = [pattern["regex"] for pattern in self._files["required"]["patterns"]] if has_required_patterns else []

        print(f"------- {dir_path}")
        for fn in sorted(os.listdir(dir_path)):
            print(f"\t+{fn}")

            pattern_match = False

            if has_requirements:
                if "names" in self._files["required"]:
                    if fn in self._files["required"]["names"]:
                        self._files["required"]["names"].remove(fn)
                        continue
                
                if not (has_required_patterns or has_allowed_patterns):
                    feedback.append(f"Submission cannot contain file named {fn}")
                    continue

                if has_required_patterns:
                    match_pattern_i = find_match_pattern_index(required_patterns, fn)
                    if match_pattern_i is not None:
                        pattern = self._files["required"]["patterns"][match_pattern_i]
                        cnt = pattern["count"]
                        if cnt > 0:
                            pattern["count"] -= 1
                        else:
                            feedback.append(f"Too many {pattern['regex']} files")
                        pattern_match = True
                    if pattern_match:
                        continue
            
            if has_allowed_patterns:
                match_pattern_i = find_match_pattern_index(self._files["allowed"], fn)
                if match_pattern_i is not None:
                    pattern_match = True
                    continue
            
            print(f"\t({has_required_patterns} {has_allowed_patterns}) {pattern_match}")
            if (has_required_patterns or has_allowed_patterns) and not pattern_match:
                feedback.append(f"{fn} is not allowed in the submission")
                continue
            
            if has_forbidden_patterns:
                match_pattern_i = find_match_pattern_index(self._files["forbidden"]["patterns"], fn)
                if match_pattern_i is not None:
                    if has_forbidden_patterns_exceptions and fn in self._files["forbidden"]["exceptions"]:
                        continue
                    feedback.append(f"{fn} is not allowed in the submission")
        
        if has_required_names and len(self._files["required"]["names"]) > 0:
            feedback.append(f"Submission is missing {self._files['required']['names']}")
        
        has_feedback = len(feedback) > 0
        return (
            not has_feedback,
            feedback if has_feedback else None
        )

    def _validate_file_content(self, fp: str) -> list:
        has_forbidden_patterns = "forbidden" in self._content

        if not has_forbidden_patterns:
            return []
        
        forbidden_patterns = self._content["forbidden"]["patterns"]

        feedback = []

        with open(fp, "r") as f:
            for i, l in enumerate(f):
                search_pattern_i = find_search_pattern_index(forbidden_patterns, l)
                if search_pattern_i is not None:
                    pattern = forbidden_patterns[search_pattern_i]
                    feedback.append(f"{pattern} on line {i+1} is not allowed")
        
        return feedback


def execute(args: list, if_fp=None, dir_path=None) -> tuple:
    cwd = os.getcwd()
    if dir_path is not None:
        os.chdir(dir_path)
    
    print(os.getcwd())

    of_fn = "out.txt"
    ef_fn = "err.txt"
    with open(of_fn, "w") as of, open(ef_fn, "w") as ef:
        if if_fp is None:
            subprocess.run(args, stdout=of, stderr=ef)
        else:
            f = open(os.path.join(cwd, if_fp), "r")
            subprocess.run(args, stdin=f, stdout=of, stderr=ef)
            f.close()
    
    if dir_path is not None:
        os.chdir(cwd)

    return (
        of_fn if dir_path is None else os.path.join(dir_path, of_fn),
        ef_fn if dir_path is None else os.path.join(dir_path, ef_fn)
    )


def get_contets(fp: str) -> str:
    if os.path.getsize(fp) > 0:
        with open(fp, "r") as f:
            return f.read()


class Rubric:
    def __init__(self, fp: str):
        self._fv = FileValidator(fp)

        with open(fp, "r") as f:
            data = json.load(f)

        self._compile = data["compile"] if "compile" in data else None
        self._runs = data["runs"]

    def grade(self, submission_dir_path: str) -> dict:
        res = self._fv.validate(submission_dir_path)

        if not res[0]:
            return {
                "score": 0,
                "output": "\n\n".join(res[1])
            }
        
        tests = []
        
        if self._compile is not None:
            out_fp, err_fp = execute(self._compile["cmd"], dir_path=submission_dir_path)

            s_cmd = " ".join(self._compile["cmd"])
            prefix = f"Compiling with: {s_cmd}"

            err = get_contets(err_fp)
            if err is not None and len(err) > 0:
                return {
                    "tests": [
                        {
                            "name": "Compile",
                            "score": 0,
                            "max_score": self._compile["points"],
                            "status": "failed",
                            "output": f"{prefix}\n\n{err}"
                        }
                    ]
                }
            else:
                tests.append({
                    "name": "Compile",
                    "score": self._compile["points"],
                    "max_score": self._compile["points"],
                    "status": "passed",
                    "output": prefix
                })

        for i, run in enumerate(self._runs):
            # Run submission and get file path to output
            if "input" in run:
                out_fp, err_fp = execute(run["cmd"], run["input"], dir_path=submission_dir_path)
            else:
                out_fp, err_fp = execute(run["cmd"], dir_path=submission_dir_path)

            prefix = "Running with: " + " ".join(run["cmd"])

            err = get_contets(err_fp)
            if err is not None and len(err) > 0:
                tests.append({
                    "name": run["name"],
                    "score": 0,
                    "max_score": run["points"],
                    "status": "failed",
                    "output": f"{prefix}\n\n{err}"
                })
                continue

            ov = OutputValidator(run["criteria"])
            print("?\t" + out_fp)
            res = ov.grade(out_fp)
            if not res[0]:
                tests.append({
                    "name": run["name"],
                    "score": 0,
                    "max_score": run["points"],
                    "status": "failed",
                    "output": res[1]
                })
            else:
                tests.append({
                    "name": run["name"],
                    "score": run["points"],
                    "max_score": run["points"],
                    "status": "passed",
                    "output": "Congratulations!"
                })

        return {"tests": tests}


def grade_submission(rubric_fp: str, submission_dir_path: str, results_fp: str):
    rubric = Rubric(rubric_fp)
    results = rubric.grade(submission_dir_path)
    with open(results_fp, "w+") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    correct_num = len(sys.argv) == 4
    correct_files = correct_num and sys.argv[1].endswith(".json") and sys.argv[3].endswith(".json")
    correct_dir = correct_num and os.path.isdir(sys.argv[2])

    if correct_num and correct_files and correct_dir:
        grade_submission(
            sys.argv[1],    # path to rubric.json
            sys.argv[2],    # path to submission directory
            sys.argv[3]     # path to save results
        )
    else:
        print("ERROR: expected: grader.py <rubric.json> <submission_dir> <results.json>")
        print(f"\tInstead got {sys.argv}")
