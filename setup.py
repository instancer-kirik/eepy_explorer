from setuptools import setup, find_packages

setup(
    name="eepy_explorer",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "PyQt6",
        "qasync",
        "psutil",
    ],
    entry_points={
        "console_scripts": [
            "eepy_explorer=eepy_explorer.src.app:main",
        ],
    },
    author="Kirik",
    description="A modern file explorer for E development",
    python_requires=">=3.8",
) 