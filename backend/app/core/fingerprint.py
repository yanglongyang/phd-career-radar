"""岗位指纹与相似度：去重不能只依赖 URL，组合单位/部门/职位/城市。"""

import hashlib
import json
import re
from difflib import SequenceMatcher

_PUNCT = re.compile(r"[\s，。、；：！？（）()【】\[\]「」·\-—_/\\,.:;!?#'\"*]+")


def normalize_text(value: str | None) -> str:
    """小写、去空白与常见中英文标点，用于归一化比较。"""
    if not value:
        return ""
    return _PUNCT.sub("", value).lower()


def normalize_org_name(value: str | None) -> str:
    """单位名归一化：额外去掉大学/学院前后的常见修饰词差异过大时会误伤，保守处理。"""
    return normalize_text(value)


def normalize_city(value: str | None) -> str:
    """城市归一化：去掉尾部"市"字（南京市/南京视为同城）。"""
    text = normalize_text(value)
    return text[:-1] if text.endswith("市") else text


def job_fingerprint(organization: str | None, department: str | None, title: str, city: str | None) -> str:
    parts = [
        normalize_org_name(organization),
        normalize_text(department),
        normalize_text(title),
        normalize_city(city),
    ]
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def content_hash(description_raw: str | None, salary_text: str | None, deadline) -> str:
    raw = json_dumps_fields({"description_raw": description_raw, "salary_text": salary_text, "deadline": deadline})
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def json_dumps_fields(data: dict) -> str:
    return json.dumps({k: (str(v) if v is not None else "") for k, v in sorted(data.items())}, ensure_ascii=False)


def description_similarity(a: str | None, b: str | None) -> float:
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()
