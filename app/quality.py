from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re
import unicodedata

from app.config import MAX_ROWS
from app.errors import BusinessError
from app.reasons import LABELS

EMPTY = {"", "-", "N/A", "NULL", "未知"}
NUMBER = re.compile(r"[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?")


def token(value):
    if not isinstance(value, str) or value.strip() in EMPTY or len(value) > 160:
        raise ValueError("字段缺失或超长")
    return value.strip()


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("需要有限数值")
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if len(text) > 30 or not NUMBER.fullmatch(text):
        raise ValueError("数值格式无效")
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation as error:
        raise ValueError("需要有限数值") from error


def integer(value, lower, upper):
    parsed = number(value)
    if not lower <= parsed <= upper or parsed != parsed.to_integral_value():
        raise ValueError("整数超出范围")
    return int(parsed)


def instant(value):
    stamp = datetime.fromisoformat(token(value))
    if stamp.utcoffset() is None or stamp.microsecond or not 1970 <= stamp.year <= 2099:
        raise ValueError("时间须带偏移且精确到秒")
    return int(stamp.timestamp())


def utc(value):
    return (
        datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")
    )


def issue(code, row=None, raw=None, **extra):
    return {"code": code, "message": LABELS[code], "row": row, "raw": raw, **extra}


def rows(data, key):
    value = data.get(key)
    if not isinstance(value, list) or len(value) > MAX_ROWS:
        raise BusinessError("BAD_SECTION", f"{key} 须为不超过 {MAX_ROWS} 项的列表")
    return enumerate(value, 1)
