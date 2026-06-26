
import json
import logging
import os
import re
import shutil
import subprocess
import sys

_version = [0, 2, 2]

logger = logging.getLogger(__name__)


class Criterion:
    def __init__(self, d: dict):
        self._datum = {}

        expected_keys = set(["requirement", "expected", "lines", "endsWithInput"])
        for k in d:
            if k not in expected_keys:
                logger.warning(f"Unrecogized criterion key {k} in {d}")
            else:
                self._datum[k] = d[k]

        if "lines" not in self._datum:
            self._datum["lines"] = 1

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
    
    def consume(self, l: str) -> str | None:
        req = self._datum["requirement"]

        if req == "exact":
            prefix = self._datum["expected"]
            if l.startswith(prefix):
                remain = l[len(prefix):]
                if len(remain) > 0:
                    return remain

        elif req == "pattern":
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
    
    def _gen_out_file_lines(self, out_fp: str):
        self._init_criteria_iteration()

        criterion = self._load_next_criterion()

        with open(out_fp, "r") as f:
            line_num = 1
            for l in f:
                while True:
                    if criterion is None:
                        yield (line_num, criterion, l)

                    get_next_line = True
                    if criterion.endsWithInput:
                        get_next_line = False
                        remainder = criterion.consume(l)
                        if remainder is not None:
                            line_len = len(l) - len(remainder)
                            yield (line_num, criterion, l[:line_len])
                            l = remainder
                        else:
                            logger.debug(f"{criterion} cannot consume line {line_num}: '{l}'")
                            yield (line_num, criterion, l.split("\n")[0] + "\n")
                    else:
                        yield (line_num, criterion, l)
                    
                    line_num += 1

                    criterion.update()

                    if criterion.is_exhausted():
                        criterion = self._load_next_criterion()

                    if get_next_line:
                        break
    
    def collate_input(self, out_fp: str, in_fp: str) -> str:
        collated = []

        with open(in_fp, "r") as f:
            previous_line_ends_with_input = False
            in_lines = f.readlines()
            for line_num, criterion, l in self._gen_out_file_lines(out_fp):
                if criterion is None:
                    break
                
                if re.match("\\s*\n", l) and previous_line_ends_with_input:
                    collated.append(f"line {line_num:02d}: {l}")
                    break

                if criterion.endsWithInput:
                    collated.append(f"line {line_num:02d}: {l}{in_lines.pop(0)}")
                else:
                    collated.append(f"line {line_num:02d}: {l}")
                
                previous_line_ends_with_input = criterion.endsWithInput

                if not criterion.apply(line_num, l)[0]:
                    break
        
        return "".join(collated)

    def grade(self, out_fp: str) -> tuple:
        previous_line_ends_with_input = False
        for line_num, criterion, l in self._gen_out_file_lines(out_fp):
            logger.debug(f"Evaluate {line_num}")

            logger.debug(f"\t\tLine: {repr(l)}")
            logger.debug(f"\t\tCriterion: {criterion}")

            if criterion is None:
                return (False, f"Unexpected output '{l}' at end of program")
            
            if re.match("\\s*\n", l) and previous_line_ends_with_input:
                return (False, f"Line {line_num} was empty because input was supposed to be collected on line {line_num-1}.")

            result = criterion.apply(line_num, l)
            previous_line_ends_with_input = criterion.endsWithInput

            logger.debug(f"\t\tResult: {result}")

            if not result[0]:
                return result

        return (True, None)

    def _init_criteria_iteration(self):
        self._criterion_i = -1
    
    def _load_next_criterion(self):
        self._criterion_i += 1

        if self._criterion_i >= len(self._output):
            return None

        return Criterion(self._output[self._criterion_i])


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


def found_forbidden_pattern(s: str, forbidden: dict) -> int | None:
    has_exceptions = "exceptions" in forbidden

    match_pattern_i = find_search_pattern_index(forbidden["patterns"], s)
    if match_pattern_i is not None:
        if has_exceptions and find_search_pattern_index(forbidden["exceptions"], s) is not None:
            return None
        return match_pattern_i
    
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

        for fn in sorted(os.listdir(dir_path)):

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
            
            if (has_required_patterns or has_allowed_patterns) and not pattern_match:
                feedback.append(f"{fn} is not allowed in the submission")
                continue
            
            if has_forbidden_patterns:
                match_pattern_i = found_forbidden_pattern(fn, self._files["forbidden"])
                if match_pattern_i is not None:
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
                match_pattern_i = found_forbidden_pattern(l, self._content["forbidden"])
                if match_pattern_i is not None:
                    pattern = forbidden_patterns[match_pattern_i]
                    feedback.append(f"{pattern} on line {i+1} is not allowed")
        
        return feedback


def execute(args: list, if_fp=None, dir_path=None) -> tuple:
    cwd = os.getcwd()
    if dir_path is not None:
        os.chdir(dir_path)
    
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


def get_contents(fp: str) -> str:
    if os.path.getsize(fp) > 0:
        with open(fp, "r") as f:
            return f.read()


def build_output(prefix: str, terminal: str, err: str = None) -> str:
    s = f"{prefix}\n\n--- Terminal ---\n\n{terminal}"
    if err is not None:
        s += f"\n\n--- Error ---\n\n{err}"
    return s


class Rubric:
    def __init__(self, fp: str):
        self._fv = FileValidator(fp)

        with open(fp, "r") as f:
            data = json.load(f)

        self._rubric_compatible = True
        logger.info(f"Grader version: v{'.'.join(list(map(lambda i: str(i), _version)))}")
        if "version" not in data:
            logger.warning("Rubric has no version")
        else:
            rubric_version = data["version"]
            logger.info(f"Rubric version: {rubric_version}")
            rubric_version = rubric_version[1:] if rubric_version.startswith("v") else rubric_version
            rubric_version = list(map(lambda s: int(s), rubric_version.split(".")))
            if rubric_version[0] != _version[0] or rubric_version[1] > _version[1]:
                self._rubric_compatible = False
                logger.error("Incompatible rubric version")

        if self._rubric_compatible:
            self._support = data["support"] if "support" in data else []
            self._compile = data["compile"] if "compile" in data else None
            self._runs = data["runs"]
        else:
            self._support = []
            self._compile = None
            self._runs = []

    def grade(self, submission_dir_path: str) -> dict:
        res = self._fv.validate(submission_dir_path)

        if not res[0]:
            return {
                "score": 0,
                "output": "\n\n".join(res[1])
            }
        
        tests = []

        msg = self._setup_support(submission_dir_path)
        if msg is not None:
            logger.error(f"Failed to copy support file: {msg}\nWorking directory is {os.getcwd()}")
            return {
                "score": 0,
                "output": "Submitted files are valid but could not setup supporting files.\nPlease contact course staff/instructor"
            }
        
        if self._compile is not None:
            out_fp, err_fp = execute(self._compile["cmd"], dir_path=submission_dir_path)

            s_cmd = " ".join(self._compile["cmd"])
            prefix = f"Compiling with: {s_cmd}"

            err = get_contents(err_fp)
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

        is_env_dirty = False
        for i, run in enumerate(self._runs):

            test = {
                "name": run["name"],
                "max_score": run["points"]
            }

            # Don't run test if a previous test polutted the environment
            if is_env_dirty:
                logger.error(f"Can't run {run['name']} because environment is dirty")
                test["score"] = 0
                test["status"] = "failed"
                test["output"] = "Autograder could not setup environment. Please contact course staff/instructor"
                tests.append(test)
                continue

            in_fp = run["input"] if "input" in run else None

            # Run setup scripts
            has_event_handers = "events" in run
            if has_event_handers and "before" in run["events"] and not self._run_scripts(run["events"]["before"]):
                logger.error(f"Setup script for {run['name']} failed")
                test["score"] = 0
                test["status"] = "failed"
                test["output"] = "Autograder could not setup environment. Please contact course staff/instructor"
                tests.append(test)
                continue

            # Run submission and get file path to output
            if in_fp is not None:
                out_fp, err_fp = execute(run["cmd"], run["input"], dir_path=submission_dir_path)
            else:
                out_fp, err_fp = execute(run["cmd"], dir_path=submission_dir_path)

            ov = OutputValidator(run["criteria"])

            # Build output
            prefix = "Running with: " + " ".join(run["cmd"])
            terminal = ov.collate_input(out_fp, in_fp) if in_fp is not None else get_contents(out_fp)
            err = get_contents(err_fp)
            output = build_output(prefix, terminal, err)

            test["output"] = output

            if err is not None and len(err) > 0:
                test["score"] = 0
                test["status"] = "failed"
            else:
                res = ov.grade(out_fp)
                if not res[0]:
                    test["score"] = 0
                    test["status"] = "failed"
                    test["output"] += f"\n\n--- Unexpected Output ---\n\n{res[1]}"
                else:
                    test["score"] = run["points"]
                    test["status"] = "passed"

            # Run teardown scripts
            if has_event_handers and "after" in run["events"] and not self._run_scripts(run["events"]["after"]):
                is_env_dirty = True

            tests.append(test)

        return {"tests": tests}

    def _setup_support(self, submission_dir_path: str) -> str | None:
        for file_meta in self._support:
            dst_fp = os.path.join(submission_dir_path, file_meta["dst"])
            if os.path.exists(file_meta["src"]):
                dst_dir_fp = os.path.dirname(dst_fp)
                os.makedirs(dst_dir_fp, exist_ok=True)
                shutil.copy(file_meta["src"], dst_fp)
            else:
                return str(file_meta)

    def _run_scripts(self, cmds: list) -> bool:
        for cmd in cmds:
            cp = subprocess.run(cmd)
            logger.debug(f"{' '.join(cmd)} -> {cp.returncode}")
            if cp.returncode != 0:
                logger.error(f"Command '{' '.join(cmd)}' exited with non-zero returned code: {cp.returncode}")
                return False
        return True


def grade_submission(rubric_fp: str, submission_dir_path: str, results_fp: str):
    rubric = Rubric(rubric_fp)
    results = rubric.grade(submission_dir_path)
    with open(results_fp, "w+") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

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
