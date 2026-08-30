from app.models.academic_job_details import AcademicJobDetails
from app.models.enums import (
    APPLICATION_STATUS_TRANSITIONS,
    ApplicationStatus,
    ContractType,
    JobCategory,
    JobDisposition,
    PositionNature,
    TenureStatus,
    can_transition_application,
)


def test_application_transitions_forward_path():
    assert can_transition_application("new", "reviewed")
    assert can_transition_application("reviewed", "shortlist")
    assert can_transition_application("shortlist", "preparing")
    assert can_transition_application("preparing", "applied")
    assert can_transition_application("applied", "interview_1")
    assert can_transition_application("interview_1", "offer")


def test_application_transitions_reject_skips_and_reversals():
    assert not can_transition_application("new", "offer")
    assert not can_transition_application("applied", "new")
    assert not can_transition_application("offer", "applied")
    assert not can_transition_application("rejected", "interview_1")


def test_terminal_states_have_no_outgoing():
    for terminal in ("rejected", "withdrawn", "ignored"):
        assert APPLICATION_STATUS_TRANSITIONS[terminal] == set()


def test_same_state_allowed():
    assert can_transition_application("applied", "applied")


def test_position_nature_axes_are_orthogonal():
    """Phase 2.1 核心目标：预聘（tenure_track）与固定期限合同（fixed_term）
    必须能同时表达 —— 单一互斥枚举做不到，正交四轴可以。"""
    details = AcademicJobDetails(
        establishment_status="non_established",
        tenure_status=TenureStatus.tenure_track.value,
        contract_type=ContractType.fixed_term.value,
        funding_source="university",
    )
    assert details.tenure_status == "tenure_track"
    assert details.contract_type == "fixed_term"
    assert details.establishment_status == "non_established"
    assert details.funding_source == "university"


def test_pi_funded_is_funding_not_tenure():
    """PI 经费聘用是经费来源维度，与合同期限独立。"""
    details = AcademicJobDetails(
        tenure_status="non_tenure",
        contract_type="fixed_term",
        funding_source="pi",
    )
    assert details.funding_source == "pi"
    assert details.contract_type == "fixed_term"


def test_job_disposition_has_no_workflow_states():
    """Job 只负责信息筛选状态；求职流程状态（applied/interviewing/offer）
    不再属于 Job（Phase 2.1 状态拆分）。"""
    disposition_values = {d.value for d in JobDisposition}
    assert disposition_values == {"new", "reviewing", "shortlisted", "ignored", "closed"}
    workflow_states = {"preparing", "applied", "interviewing", "offer"}
    assert not (disposition_values & workflow_states)


def test_position_nature_legacy_still_readable():
    """legacy 字段保留读取兼容，供旧数据与 UI 展示。"""
    assert PositionNature("tenure_track").value == "tenure_track"
    assert PositionNature("unknown").value == "unknown"


def test_enum_values_cover_spec():
    # 岗位分类覆盖第六节全部取值
    assert {c.value for c in JobCategory} == {
        "university_faculty", "university_research", "postdoc",
        "research_institute", "industry_rnd", "other",
    }
    # 申请状态完整（14 个）
    assert len(list(ApplicationStatus)) == 14
