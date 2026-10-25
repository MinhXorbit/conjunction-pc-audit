"""Download ESA's Collision Avoidance Challenge dataset and verify its checksum.

Source: Zenodo record 4463683 (DOI 10.5281/zenodo.4463683), CC BY 4.0.
Only the raw CDM table used by the analysis is extracted.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import urllib.request
import zipfile

URL = (
    "https://zenodo.org/api/records/4463683/files/"
    "Collision%20Avoidance%20Challenge%20-%20Dataset.zip/content"
)
ZIP_MD5 = "d19dc8875229f2f6893253c38adddc87"
MEMBER = "Collision Avoidance Challenge - Dataset/raw_data/raw_data_2015-2019.gz"


def md5sum(path: pathlib.Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="data/raw", help="directory for the download (default: data/raw)")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / "kelvins_dataset.zip"

    if not zip_path.exists():
        print(f"Downloading {URL}")
        urllib.request.urlretrieve(URL, zip_path)

    got = md5sum(zip_path)
    if got != ZIP_MD5:
        print(f"Checksum mismatch: expected {ZIP_MD5}, got {got}", file=sys.stderr)
        return 1
    print(f"Checksum OK ({got})")

    with zipfile.ZipFile(zip_path) as z:
        z.extract(MEMBER, out)
    print(f"Raw CDM table: {out / MEMBER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
