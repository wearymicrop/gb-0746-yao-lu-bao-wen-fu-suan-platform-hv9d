from argparse import ArgumentParser
import json
from pathlib import Path

from app.modules.m7_archive.bundle import consistent


def main():
    parser = ArgumentParser(description="校验归档凭证摘要")
    parser.add_argument("file", type=Path, help="凭证文件")
    args = parser.parse_args()
    try:
        valid = consistent(json.loads(args.file.read_text(encoding="utf-8-sig")))
    except (OSError, UnicodeError, ValueError):
        valid = False
    print("摘要一致" if valid else "凭证无法读取或摘要不一致")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
