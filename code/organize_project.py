import argparse
import shutil
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

# File extensions grouped by destination preference.
CODE_EXT = {
    ".py",
    ".ipynb",
    ".r",
    ".jl",
    ".m",
    ".do",
    ".sh",
}
DATA_EXT = {
    ".csv",
    ".tsv",
    ".txt",
    ".json",
    ".xlsx",
    ".xls",
    ".feather",
    ".parquet",
    ".sav",
    ".dta",
}
TABLE_EXT = {
    ".csv",
    ".tsv",
    ".xlsx",
    ".xls",
    ".ods",
}
FIGURE_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".tif",
    ".tiff",
    ".svg",
    ".gif",
    ".bmp",
    ".pdf",
    ".eps",
    ".html",
}
DOCUMENT_EXT = {
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".rtf",
}
RESULT_KEYWORDS = {
    "analysis",
    "result",
    "summary",
    "output",
    "centrality",
    "growth",
    "report",
    "table",
    "timeseries",
}
RESULT_PATH_HINTS = {
    "output",
    "outputs",
    "result",
    "results",
    "tables",
    "figures",
}
SKIP_DIR_NAMES = {".git", "__pycache__", ".venv"}


def ensure_structure(root: Path) -> Dict[str, Path]:
    """Ensure the required directory structure exists."""
    data_dir = root / "data"
    code_dir = root / "code"
    results_dir = root / "results"
    tables_dir = results_dir / "tables"
    figures_dir = results_dir / "figures"

    for path in (data_dir, code_dir, results_dir, tables_dir, figures_dir):
        path.mkdir(parents=True, exist_ok=True)

    return {
        "data": data_dir,
        "code": code_dir,
        "results": results_dir,
        "tables": tables_dir,
        "figures": figures_dir,
    }


def has_result_hint(path: Path) -> bool:
    """Return True if the path hints that it is an analysis output."""
    parts = {part.lower() for part in path.parts}
    if parts & RESULT_PATH_HINTS:
        return True
    stem = path.stem.lower()
    return any(keyword in stem for keyword in RESULT_KEYWORDS)


def classify_file(path: Path, root: Path, targets: Dict[str, Path]) -> Optional[Path]:
    """Determine the appropriate destination directory for a file."""
    ext = path.suffix.lower()

    if ext in CODE_EXT:
        return targets["code"]

    if ext in FIGURE_EXT:
        return targets["figures"]

    if ext in TABLE_EXT:
        return targets["tables"] if has_result_hint(path.relative_to(root)) else targets["data"]

    if ext in DATA_EXT:
        return targets["data"]

    if ext in DOCUMENT_EXT:
        return targets["results"]

    return None


def iter_files(root: Path) -> Iterable[Path]:
    """Yield all files under root, skipping special directories."""
    for path in root.rglob("*"):
        if path.is_dir():
            if path.name in SKIP_DIR_NAMES:
                # Skip walking into ignored directories.
                skip_subtree(path)
            continue
        yield path


def skip_subtree(directory: Path) -> None:
    """Prevent rglob from descending into collapsed directories by renaming temporarily."""
    # Path.rglob does not expose a native skip, so this helper is a placeholder.
    # We keep the function for readability although we cannot prevent descent here.
    return None


def unique_destination(dest_dir: Path, file_name: str) -> Path:
    """Return a unique destination path to avoid overwriting existing files."""
    candidate = dest_dir / file_name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        new_name = f"{stem}_{counter}{suffix}"
        candidate = dest_dir / new_name
        if not candidate.exists():
            return candidate
        counter += 1


def move_file(source: Path, destination_dir: Path) -> Optional[Tuple[Path, Path]]:
    """Move a file to the destination directory and return the move record."""
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = unique_destination(destination_dir, source.name)
    if destination == source:
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(destination))
    return source, destination


def print_directory_tree(root: Path) -> None:
    """Print the directory tree using ASCII connectors."""
    def _walk(current: Path, prefix: str) -> None:
        entries = sorted(
            [p for p in current.iterdir() if p.name not in SKIP_DIR_NAMES],
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )
        for index, entry in enumerate(entries):
            connector = "`-- " if index == len(entries) - 1 else "|-- "
            print(f"{prefix}{connector}{entry.name}")
            if entry.is_dir():
                extension = "    " if index == len(entries) - 1 else "|   "
                _walk(entry, prefix + extension)

    print(f"Project tree for {root}")
    print("."
    )
    _walk(root, "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize project files into data, code, and results folders.")
    parser.add_argument(
        "root",
        nargs="?",
        default=Path.cwd(),
        type=Path,
        help="Project root directory. Defaults to current working directory.",
    )
    args = parser.parse_args()
    root = args.root.resolve()

    targets = ensure_structure(root)
    move_log = []

    files = [path for path in root.rglob("*") if path.is_file()]
    files.sort()

    for file_path in files:
        if any(part in SKIP_DIR_NAMES for part in file_path.parts):
            continue
        destination_dir = classify_file(file_path, root, targets)
        if destination_dir is None:
            continue
        if file_path.parent == destination_dir:
            continue
        move_record = move_file(file_path, destination_dir)
        if move_record is not None:
            move_log.append(
                (
                    move_record[0].relative_to(root),
                    move_record[1].relative_to(root),
                )
            )

    if move_log:
        print("File moves:")
        for src, dst in move_log:
            print(f"- {src} -> {dst}")
    else:
        print("No files required moving.")

    print()
    print_directory_tree(root)


if __name__ == "__main__":
    main()
