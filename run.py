"""Top-level launcher — run this directly: python run.py"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from code.main import main

if __name__ == "__main__":
    main()
