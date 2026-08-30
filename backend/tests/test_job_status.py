from app.models.enums import (
    APPLICATION_STATUS_TRANSITIONS,
    ApplicationStatus,
    JobCategory,
    JobStatus,
    PositionNature,
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


def test_enum_values_cover_spec():
    # 岗位性质无法判断时必须显式为 unknown（第六节）
    assert PositionNature("unknown").value == "unknown"
    # 岗位分类覆盖第六节全部取值
    assert {c.value for c in JobCategory} == {
        "university_faculty", "university_research", "postdoc",
        "research_institute", "industry_rnd", "other",
    }
    # 岗位状态 / 申请状态完整
    assert len(list(JobStatus)) == 9
    assert len(list(ApplicationStatus)) == 14
