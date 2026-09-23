#!/usr/bin/env python3
"""Read-only structural checks for a transparent sticker PNG."""

import argparse
import json
import sys
from pathlib import Path

VISIBLE_ALPHA_THRESHOLD = 8


def report(path: Path, min_padding: int) -> tuple[dict, int]:
    result = {
        "path": str(path),
        "format": None,
        "width": None,
        "height": None,
        "has_alpha": False,
        "alpha_min": None,
        "alpha_max": None,
        "transparent_fraction": None,
        "visible_bbox": None,
        "padding": None,
        "status": "fail",
        "errors": [],
        "warnings": [],
    }

    if not path.is_file():
        result["errors"].append("文件不存在或不是普通文件；请提供可读取的 PNG 路径")
        return result, 1

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        result["errors"].append("缺少 Pillow；请在项目允许的虚拟环境运行 python -m pip install Pillow")
        return result, 1

    try:
        with Image.open(path) as image:
            result["format"] = image.format
            result["width"], result["height"] = image.size
            if image.format != "PNG":
                result["errors"].append("文件实际格式不是 PNG")
                return result, 1

            result["has_alpha"] = image.mode in ("RGBA", "LA") or "transparency" in image.info
            if not result["has_alpha"]:
                result["errors"].append("PNG 没有 Alpha 通道或调色板透明信息")
                return result, 1

            alpha = image.convert("RGBA").getchannel("A")
            minimum, maximum = alpha.getextrema()
            result["alpha_min"] = minimum
            result["alpha_max"] = maximum
            histogram = alpha.histogram()
            total = image.width * image.height
            result["transparent_fraction"] = round(sum(histogram[: VISIBLE_ALPHA_THRESHOLD + 1]) / total, 6)

            if minimum == 255:
                result["errors"].append("全部像素不透明；背景没有有效透明度")
            elif minimum > VISIBLE_ALPHA_THRESHOLD:
                result["errors"].append("没有透明背景像素；请确认输出是真正透明的贴纸")
            if maximum <= VISIBLE_ALPHA_THRESHOLD:
                result["errors"].append("全部像素透明或接近透明；没有可见主体")
            if result["errors"]:
                return result, 1

            visible = alpha.point(lambda value: 255 if value > VISIBLE_ALPHA_THRESHOLD else 0)
            bbox = visible.getbbox()
            if bbox is None:
                result["errors"].append("没有可见主体")
                return result, 1

            left, top, right, bottom = bbox
            padding = {
                "left": left,
                "top": top,
                "right": image.width - right,
                "bottom": image.height - bottom,
            }
            result["visible_bbox"] = [left, top, right, bottom]
            result["padding"] = padding
            if any(value < min_padding for value in padding.values()):
                result["warnings"].append(f"可见主体距至少一侧不足 {min_padding} 像素")

            result["status"] = "pass_with_warnings" if result["warnings"] else "pass"
            return result, 0
    except (OSError, UnidentifiedImageError, ValueError) as error:
        result["errors"].append(f"无法读取图片：{error}")
        return result, 1


def nonnegative_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("--min-padding 必须是非负整数") from error
    if number < 0:
        raise argparse.ArgumentTypeError("--min-padding 必须是非负整数")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description="只读检查贴纸 PNG 的格式、透明度和留白")
    parser.add_argument("path", type=Path, help="待检查的 PNG 文件")
    parser.add_argument("--min-padding", type=nonnegative_int, default=16, help="四边建议最小透明留白像素，默认 16")
    args = parser.parse_args()
    result, exit_code = report(args.path, args.min_padding)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
