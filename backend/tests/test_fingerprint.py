from app.core.fingerprint import (
    description_similarity,
    job_fingerprint,
    normalize_text,
)


def test_normalize_text_strips_punct_and_case():
    assert normalize_text("A-大学 化学学院！") == normalize_text("a大学化学学院")


def test_same_job_from_different_sources_same_fingerprint():
    fp1 = job_fingerprint("示例大学", "化学学院", "青年研究员", "南京")
    fp2 = job_fingerprint("示例 大学", "化学学院。", "青年 研究员", "南京市")
    assert fp1 == fp2


def test_different_organization_different_fingerprint():
    fp1 = job_fingerprint("示例大学", "化学学院", "青年研究员", "南京")
    fp2 = job_fingerprint("另一所大学", "化学学院", "青年研究员", "南京")
    assert fp1 != fp2


def test_description_similarity_detects_near_duplicate():
    a = "招聘具有有机化学、荧光探针研究背景的青年人才，提供启动经费 50 万元。"
    b = "招聘具有有机化学、荧光探针研究背景的青年人才，提供启动经费50万元。"
    assert description_similarity(a, b) > 0.92


def test_description_similarity_low_for_different_text():
    a = "招聘具有有机化学、荧光探针研究背景的青年人才。"
    b = "诚聘计算数学方向博士后，从事数值模拟研究。"
    assert description_similarity(a, b) < 0.6
