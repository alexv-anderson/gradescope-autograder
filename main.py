
import json
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

                    print(f"Line {line_num}: '{l}' -> {criterion}")

                    result = criterion.apply(line_num, l)
                    print(f"\tResult: {result}")
                    if not result[0]:
                        return result
                    
                    line_num += 1
                    
                    criterion.update()
            
                    if criterion.endsWithInput:
                        l = criterion.consume(l)
                        print(l)
                    
                    if criterion.is_exhausted():
                        print(f"\tExhausted criterion: {criterion}")
                        criterion = self._load_next_criterion()
                        print(f"\tLoaded: {criterion}")

                    get_next_line = criterion is not None and not criterion.endsWithInput
                    end_of_rubric = criterion is None

                    if get_next_line or end_of_rubric:
                        break

        return (True, None)
    
    def _load_next_criterion(self):
        if len(self._output) == 0:
            return None

        req = self._output.pop(0)
        
        return Criterion(req)


if __name__ == "__main__":
    rubric = Rubric("output.json")
    print(rubric.grade("out.txt"))