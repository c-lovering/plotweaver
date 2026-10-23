"""Build the sample project: python make_sample.py <folder>  (default: "Sample Project")

The content lives in plotweaver/sample.py, which the app and the release builds also use."""
import sys
from pathlib import Path

from plotweaver.sample import SAMPLE_NAME, build_sample

root = Path(sys.argv[1] if len(sys.argv) > 1 else SAMPLE_NAME)
build_sample(root, replace="--replace" in sys.argv[2:])
print("Sample project written to", root.resolve())
