"""
Comic Generator extension installer.

Called automatically by A1111 WebUI during extension setup.
Installs required Python packages that aren't part of A1111's defaults.
"""
import subprocess
import sys


def install_package(package: str):
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet", package],
        stdout=subprocess.DEVNULL,
    )


try:
    import rembg  # noqa: F401
except ImportError:
    print("[ComicGenerator] Installing rembg...")
    install_package("rembg[gpu]")

try:
    from PIL import Image  # noqa: F401
except ImportError:
    print("[ComicGenerator] Installing Pillow...")
    install_package("Pillow")
