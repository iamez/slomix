import runpy
from pathlib import Path

if __name__ == "__main__":
    cli = Path(__file__).with_name("etl_demo_scan")
    runpy.run_path(str(cli), run_name="__main__")
