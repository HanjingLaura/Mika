#!/usr/bin/env python3
"""Check translation keys and export review CSV using only Python's stdlib."""

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


DEFAULT_RES = Path(__file__).resolve().parents[2] / "app/src/main/res"
LANGUAGE_FOLDER = re.compile(r"values-(?:[a-z]{2,3}(?:-r[A-Z]{2})?|b\+[A-Za-z0-9]+(?:\+[A-Za-z0-9]+)*)")
TYPES = {"string", "plurals", "string-array"}
QUANTITIES = ("zero", "one", "two", "few", "many", "other")
ET.register_namespace("xliff", "urn:oasis:names:tc:xliff:document:1.2")


@dataclass
class Resource:
    source: str
    context: str
    translatable: bool
    items: dict[str, str]


def inner_xml(node: ET.Element) -> str:
    # Keep inline markup, Android escapes, and whitespace for translator review.
    return (node.text or "") + "".join(ET.tostring(child, encoding="unicode") for child in node)


def read_folder(folder: Path) -> dict[tuple[str, str], Resource]:
    resources = {}
    for path in sorted(folder.glob("strings*.xml")):
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        try:
            root = ET.parse(path, parser=parser).getroot()
        except ET.ParseError as error:
            raise ValueError(f"{path}: {error}") from error
        if root.tag != "resources":
            raise ValueError(f"{path}: expected <resources>")
        comments = []
        for node in root:
            if node.tag is ET.Comment:
                comments.append((node.text or "").strip())
                continue
            context = "\n".join(comments)
            comments = []
            if node.tag not in TYPES:
                continue
            name = node.get("name")
            if not name:
                raise ValueError(f"{path}: unnamed {node.tag}")
            key = (node.tag, name)
            if key in resources:
                raise ValueError(f"{path}: duplicate {node.tag}/{name} (also in {resources[key].source})")
            if node.tag == "string":
                items = {"": inner_xml(node)}
            else:
                items = {}
                for index, item in enumerate(node.findall("item")):
                    label = item.get("quantity", "") if node.tag == "plurals" else str(index)
                    if node.tag == "plurals" and label not in QUANTITIES:
                        raise ValueError(f"{path}: invalid quantity in {name}")
                    if label in items:
                        raise ValueError(f"{path}: duplicate {name}/{label}")
                    items[label] = inner_xml(item)
                if not items or (node.tag == "plurals" and "other" not in items):
                    raise ValueError(f"{path}: {name} needs items (plurals require other)")
            resources[key] = Resource(
                f"{folder.name}/{path.name}", context,
                node.get("translatable") != "false", items,
            )
    return resources


def load_resources(res_dir: Path) -> dict[str, dict[tuple[str, str], Resource]]:
    base = read_folder(res_dir / "values")
    if not base:
        raise ValueError(f"{res_dir / 'values'}: no string resources found")
    folders = sorted(
        folder for folder in res_dir.iterdir()
        if folder.is_dir() and LANGUAGE_FOLDER.fullmatch(folder.name)
        and any(folder.glob("strings*.xml"))
    )
    # Keep the original three reference languages together, then sort the rest.
    folders.sort(key=lambda f: (0 if f.name == "values-zh" else 1 if f.name == "values-b+zh+Hant" else 2, f.name))
    return {"values": base, **{folder.name: read_folder(folder) for folder in folders}}


def check(catalogs: dict) -> int:
    base = catalogs["values"]
    expected = {key for key, resource in base.items() if resource.translatable}
    failures = 0
    for folder, resources in catalogs.items():
        if folder == "values":
            continue
        for kind, keys in (("missing", expected - resources.keys()), ("extra", resources.keys() - expected)):
            for tag, name in sorted(keys):
                print(f"{folder}: {kind} {tag}/{name}")
                failures += 1
    if failures:
        print(f"{failures} translation key issue(s).")
        return 1
    print(f"Translation keys match: {len(expected)} resources, {len(catalogs) - 1} translation folders.")
    return 0


def export(catalogs: dict, output: Path) -> None:
    locales = list(catalogs)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["key", "type", "item", "source", "context", *locales])
        for (tag, name), resource in sorted(catalogs["values"].items()):
            if not resource.translatable:
                continue
            translations = [catalogs[locale].get((tag, name)) for locale in locales]
            labels = set().union(*(entry.items.keys() for entry in translations if entry))
            if tag == "plurals":
                labels = [quantity for quantity in QUANTITIES if quantity in labels]
            elif tag == "string-array":
                labels = sorted(labels, key=int)
            else:
                labels = [""]
            for label in labels:
                writer.writerow([
                    name, tag, label, resource.source, resource.context,
                    *(entry.items.get(label, "") if entry else "" for entry in translations),
                ])
    print(f"Exported translation reference to {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--res-dir", type=Path, default=DEFAULT_RES, help="Android resource directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Report missing and extra translation keys")
    export_parser = commands.add_parser("export", help="Export a translation reference CSV (not an import format)")
    export_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        catalogs = load_resources(args.res_dir)
        if args.command == "check":
            return check(catalogs)
        export(catalogs, args.output)
        return 0
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
