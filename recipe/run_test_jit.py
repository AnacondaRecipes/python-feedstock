import os
import sys

if os.getenv("PYTHON_JIT") is None:
    print("WARNING: PYTHON_JIT unset", file=sys.stderr)

# Strictly, sys._jit was added in 3.14
if (sys.version_info[0] == 3 and sys.version_info[1] >= 14) or sys.version_info[0] > 3:
    if sys._jit.is_available():
        if sys._jit.is_enabled():
            print("JIT available and enabled")
            sys.exit(0)
        else:
            print("JIT available but not enabled", file=sys.stderr)
            sys.exit(1)
    else:
        # python-jit is noarch and PBP tests it against every python variant.
        # configure disables JIT for debug, freethreading, and some arches;
        # the metapackage is a no-op there.
        print("JIT not compiled into this interpreter; skip")
        sys.exit(0)
else:
    print(f"WARNING: cannot validate JIT using Python {sys.version}", file=sys.stderr)
    print("WARNING: validate using Python >= 3.14", file=sys.stderr)
    sys.exit(1)
