import subprocess
import sys


def main():
    print("Running linting check...")
    try:
        import ruff  # noqa: F401
        has_ruff = True
    except ImportError:
        has_ruff = False

    if has_ruff:
        res = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "apps/api", "tests"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print("Ruff lint check passed!")
            sys.exit(0)
        else:
            print(res.stdout or res.stderr)
            sys.exit(res.returncode)
    else:
        # Fallback to compiler verification
        print("Ruff not found, falling back to python syntax & bytecode verification...")
        res = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", "apps/api", "tests", "scripts"],
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            print("Syntax and bytecode compilation verified successfully (0 errors).")
            sys.exit(0)
        else:
            print(res.stdout or res.stderr)
            sys.exit(res.returncode)



if __name__ == "__main__":
    main()
