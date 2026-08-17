# Gradescope Autograder

Gradescope's autograder really only provides an OS and formatting for the results. This repo provides a framework to validate submission contents and automatically build test output.

## Usage

Each assignment, should have the following file structure
- `run_autograder`
- `grade.py`
- `rubric.json`
- ... any other files

The rubric file can be built by hand, but it is best to use the [eidtor](https://alexv-anderson.github.io/gradescope-autograder-editor/).

See the wiki for specific features available.
