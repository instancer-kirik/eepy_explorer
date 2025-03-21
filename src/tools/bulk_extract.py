#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

def bulk_extract(archives, output_base=None):
    """Extract multiple archives using varchiver CLI"""
    if output_base is None:
        output_base = os.getcwd()

    for archive in archives:
        archive_path = Path(archive)
        if not archive_path.exists():
            print(f"Skipping non-existent archive: {archive}")
            continue

        # Create output directory based on archive name
        output_dir = Path(output_base) / archive_path.stem
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\nExtracting {archive_path.name} to {output_dir}...")
        try:
            # Run varchiver with extraction flags
            cmd = [
                "varchiver",
                "-x",  # Extract mode
                "--output", str(output_dir),
                "--collision", "rename",  # Rename on collision
                "--preserve-permissions",
                str(archive_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"Successfully extracted {archive_path.name}")
            else:
                print(f"Failed to extract {archive_path.name}: {result.stderr}")
        except Exception as e:
            print(f"Error extracting {archive_path.name}: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: bulk_extract.py archive1 archive2 ... [--output /path/to/output]")
        sys.exit(1)

    # Parse arguments
    archives = []
    output_dir = None
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--output":
            if i + 1 < len(sys.argv):
                output_dir = sys.argv[i + 1]
                i += 2
            else:
                print("Error: --output requires a directory path")
                sys.exit(1)
        else:
            archives.append(sys.argv[i])
            i += 1

    bulk_extract(archives, output_dir) 