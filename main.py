
import json
import os
import re


class Criterion:
    def __init__(self, d: dict):
        if "lines" not in d:
            d["lines"] = 1
        self._datum = d

        self.endsWithInput = "endsWithInput" in d and d["endsWithInput"]
    
    def __str__(self) -> str:
        return json.dumps(self._datum)
    
    def apply(self, num: int, l: str) -> Tuple:
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
    

class Rubric:
    def __init__(self, fp: str):
        with open(fp, "r") as f:
            data = json.load(f)
        
        self._output = data["output"]
    
    def grade(self, out_fp: str) -> dict:
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


def find_match_pattern_index(patterns: list, s: str) -> Optional[int]:
    for i, pattern in enumerate(patterns):
        if re.match(pattern, s):
            return i
    return None


def find_search_pattern_index(patterns: list, s: str) -> Optional[int]:
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
    
    def validate(self, dir_path: str) -> Tuple:
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
    
    def _validate_files(self, dir_path: str) -> Tuple:
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
            feedback.append(f"Submission is missing {self._files["required"]["names"]}")
        
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


if __name__ == "__main__":
    rubric = Rubric("output.json")
    print(rubric.grade("out.txt"))