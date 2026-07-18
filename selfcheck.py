"""Run your solution against the practice sandbox and print a report."""
import sys
from public_scorer import check
sys.path.insert(0, "starter")
import my_solution   # noqa: E402

if __name__ == "__main__":
    ok = check(my_solution.ingest)
    sys.exit(0 if ok else 1)
