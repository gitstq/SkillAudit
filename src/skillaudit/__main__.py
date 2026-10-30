# -*- coding: utf-8 -*-
"""Enable ``python -m skillaudit``."""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
