"""Build both unpacked extensions and their ZIP archives without dependencies."""
import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

SOURCE = Path(__file__).resolve().parent
ASSETS = ("console.html", "console.css", "console.js", "reader.js", "core.js", "background.js")


def build(output, target):
    manifest = json.loads((SOURCE / "manifest.json").read_text("utf-8"))
    if target == "firefox":
        manifest["background"] = {"scripts": ["core.js", "reader.js", "background.js"]}
        manifest["browser_specific_settings"] = {"gecko": {
            "id": "checkin-desk@lankerr.github.io",
            "strict_min_version": "140.0",
            "data_collection_permissions": {"required": ["none"]},
        }}
    bundle = output / f"glados-desk-{target}-{manifest['version']}"
    files = {name: (SOURCE / name).read_bytes() for name in ASSETS}
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    for locale in ("en", "zh_CN"):
        path = f"_locales/{locale}/messages.json"
        files[path] = (SOURCE / path).read_bytes()
    for size in (16, 48, 128):
        path = f"icons/icon{size}.png"
        files[path] = (SOURCE.parent / "extension" / path).read_bytes()
    bundle.mkdir(parents=True, exist_ok=True)
    archive = output / (bundle.name + ".zip")
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zipfile:
        for name, data in files.items():
            path = bundle / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            zipfile.writestr(name, data)
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for browser in ("chromium", "firefox"):
        print(build(args.out.resolve(), browser))
