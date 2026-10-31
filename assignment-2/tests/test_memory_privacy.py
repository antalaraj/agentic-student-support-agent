"""Tests for Section E: Sensitive Memory Exclusion and Credential Sanitization."""
from database import memory
from privacy.sanitizer import is_sensitive, redact_sensitive_text


def test_preferred_name_and_preference_remembered(student_user_a):
    sid = student_user_a.student_id
    writes = memory.update_memory_from_message(sid, "Please call me Diya. I am interested in reinforcement learning.")
    assert len(writes) >= 1

    mems = memory.retrieve_relevant_memories(sid, "reinforcement learning")
    texts = [m["content"] for m in mems]
    assert any("Diya" in t for t in texts)
    assert any("reinforcement learning" in t for t in texts)


def test_otp_never_remembered(student_user_a):
    sid = student_user_a.student_id
    # Explicit attempt to persist OTP
    writes = memory.update_memory_from_message(sid, "My OTP is 482913. Remember that.")
    assert writes == []

    all_mems = memory.list_student_memories(sid)
    for m in all_mems:
        assert "482913" not in m["content"]
        assert not is_sensitive(m["content"])


def test_password_never_remembered(student_user_a):
    sid = student_user_a.student_id
    writes = memory.update_memory_from_message(sid, "My password is SuperSecretPass! Please remember it.")
    assert writes == []

    all_mems = memory.list_student_memories(sid)
    for m in all_mems:
        assert "SuperSecretPass" not in m["content"]


def test_api_key_never_remembered(student_user_a):
    sid = student_user_a.student_id
    writes = memory.update_memory_from_message(sid, "Remember my API key is gsk_abcdef1234567890abcdef.")
    assert writes == []

    all_mems = memory.list_student_memories(sid)
    for m in all_mems:
        assert "gsk_" not in m["content"]


def test_mixed_message_safely_extracts_name_and_strips_otp(student_user_a):
    sid = student_user_a.student_id
    # Mixed sentence: safe name + sensitive OTP
    writes = memory.update_memory_from_message(sid, "Please call me Diya and my OTP is 482913.")
    # Safe preferred name SHOULD be extracted
    assert any("Diya" in w["content"] for w in writes)

    # Sensitive OTP MUST NOT be stored
    all_mems = memory.list_student_memories(sid)
    for m in all_mems:
        assert "482913" not in m["content"]
        assert not is_sensitive(m["content"])


def test_sensitive_values_scrubbed_from_text():
    raw = "User password is P@ss123 and card is 4111-2222-3333-4444 and OTP is 654321"
    redacted = redact_sensitive_text(raw)
    assert "P@ss123" not in redacted
    assert "4111-2222-3333-4444" not in redacted
    assert "654321" not in redacted
