"""Retain upstream license files and versions in the portable application."""
from importlib.metadata import distributions
from pathlib import Path
import json
import shutil
import sys


def collect(package: Path):
    root = Path(__file__).resolve().parents[1]
    output = package / "app" / "licenses"
    output.mkdir(parents=True, exist_ok=True)
    inventory = []
    for dist in distributions():
        name = dist.metadata["Name"]
        for entry in dist.files or []:
            if any(word in entry.name.lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    # Keep vendor-relative paths so repeated LICENSE names do not collide.
                    safe_parts = [part for part in entry.parts if part not in ("..", ".")]
                    target = output / name / Path(*safe_parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
        inventory.append({"name": name, "version": dist.version,
                          "license": dist.metadata.get("License-Expression") or dist.metadata.get("License", ""),
                          "project_urls": dist.metadata.get_all("Project-URL", [])})
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    shutil.copy2(python_license, output / "Python-LICENSE.txt")
    import pynvml
    nvml = Path(pynvml.__file__).read_text(encoding="utf-8")
    (output / "NVIDIA-NVML-LICENSE.txt").write_text(nvml.split("#####", 2)[1], encoding="utf-8")
    shutil.copytree(root / "docs" / "licenses", output / "license-texts", dirs_exist_ok=True)
    for name in ("THIRD_PARTY.md", "LICENSE"):
        if (root / name).exists():
            shutil.copy2(root / name, output / name)
    (output / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    print(collect(Path(sys.argv[1])))
