"""Kiso version information."""

from pathlib import Path

THIS_DIR = Path(__file__).parent
__version__ = (THIS_DIR / "version.txt").read_text()
__homepage__ = "https://pegasus.isi.edu"
__source__ = "https://github.com/pegasus-isi/kiso.git"
__issues__ = "https://github.com/pegasus-isi/kiso/issues"
__changelog__ = "https://github.com/pegasus-isi/kiso/blob/main/CHANGELOG.md"
__documentation__ = f"https://kiso.readthedocs.io/en/v{__version__}/"
__contact__ = "https://pegasus.isi.edu/contact/"
