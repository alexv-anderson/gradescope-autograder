
import json
import re


class Rubric:
    def __init__(self, fp: str):
        with open(fp, "r") as f:
            data = json.load(f)
        
        self._output = data["output"]
    
    def grade(self, out_fp: str) -> dict:
        line_feedback = []

        criterion = self._load_next_criterion()

        with open(out_fp, "r") as f:
            for i, l in enumerate(f):
                if criterion["lines"] < 1:
                    criterion = self._load_next_criterion()
                
                print(f"Line {i+1}: '{l}' -> {json.dumps(criterion)}")

                req = criterion["requirement"]
                if req == "ignore":
                    # No requirements for this line
                    pass
                elif req == "exact":
                    exp = criterion["expected"]
                    if l != exp:
                        return (False, f"At line {i+1} expected '{exp}' but got '{l}'")
                elif req == "pattern":
                    if not re.match(criterion["expected"], l):
                        return (False, f"'{l}' on line {i+1} has an incorrect pattern")
                
                criterion["lines"] -= 1
        
        return (True, None)
    
    def _load_next_criterion(self):
        if len(self._output) == 0:
            return None

        req = self._output.pop(0)
        if "lines" not in req:
            req["lines"] = 1
        
        return req


if __name__ == "__main__":
    rubric = Rubric("output.json")
    print(rubric.grade("out.txt"))