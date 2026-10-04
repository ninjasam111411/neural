"""Apply Neural update packages found in updates/pending/<version>/.

Each package is a folder named by version (e.g. 1.1.0) containing changed files
laid out like the project. Packages newer than VERSION are applied in order,
overwritten files are backed up to updates/backup/<version>/, and applied
packages move to updates/applied/.
"""
import json
import os
import re
import shutil
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
PENDING = os.path.join(BASE, "updates", "pending")
APPLIED = os.path.join(BASE, "updates", "applied")
BACKUP = os.path.join(BASE, "updates", "backup")
SKIP = {"manifest.json"}


def vt(s):
    return tuple(int(x) for x in s.split("."))


def main():
    with open(os.path.join(BASE, "VERSION"), encoding="utf-8") as f:
        current = f.read().strip()
    if not os.path.isdir(PENDING):
        print("No updates/pending folder. Nothing to do.")
        return 0
    pkgs = sorted(
        (d for d in os.listdir(PENDING) if re.fullmatch(r"\d+\.\d+\.\d+", d)
         and os.path.isdir(os.path.join(PENDING, d))),
        key=vt,
    )
    if not pkgs:
        print(f"No pending updates. You are on {current}.")
        return 0

    rerun = False
    for ver in pkgs:
        src = os.path.join(PENDING, ver)
        if vt(ver) <= vt(current):
            print(f"Skipping {ver}: not newer than {current}.")
            continue
        manifest = {}
        mpath = os.path.join(src, "manifest.json")
        if os.path.exists(mpath):
            with open(mpath, encoding="utf-8") as f:
                manifest = json.load(f)
        print(f"Applying {ver}: {manifest.get('title', '')}")
        n = 0
        for root, _dirs, files in os.walk(src):
            for name in files:
                if name in SKIP and root == src:
                    continue
                full = os.path.join(root, name)
                rel = os.path.relpath(full, src)
                dest = os.path.join(BASE, rel)
                if os.path.exists(dest):
                    bak = os.path.join(BACKUP, ver, rel)
                    os.makedirs(os.path.dirname(bak), exist_ok=True)
                    shutil.copy2(dest, bak)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(full, dest)
                n += 1
                print(f"  updated {rel}")
        with open(os.path.join(BASE, "VERSION"), "w", encoding="utf-8") as f:
            f.write(ver + "\n")
        current = ver
        os.makedirs(APPLIED, exist_ok=True)
        target = os.path.join(APPLIED, ver)
        if os.path.exists(target):
            target += "-" + time.strftime("%Y%m%d%H%M%S")
        shutil.move(src, target)
        rerun = rerun or bool(manifest.get("rerun_setup"))
        print(f"  {n} files. Now on {ver}.")

    if rerun:
        print("\nThis update adds new packages/models: run setup.bat once, then start.bat.")
    print(f"\nDone. Neural is now version {current}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
