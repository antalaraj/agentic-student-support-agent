from agent.graph import run_agent
from database import memory

SID = "MIM25001"


def contents(sid=SID):
    return [m["content"] for m in memory.list_memories(sid)]


def test_extracts_name_and_preference():
    saved = memory.update_memory_from_message(SID, "Please call me Aarav and I prefer machine learning electives.")
    assert {s["content"] for s in saved} == {"Preferred name: Aarav", "Preference: machine learning electives"}


def test_sensitive_information_is_never_stored():
    memory.update_memory_from_message(SID, "My OTP is 482913. Please call me Aarav.")
    memory.update_memory_from_message(SID, "My password is hunter2 and I prefer finance electives.")
    memory.update_memory_from_message(SID, "My card number is 4111 1111 1111 1111.")
    memory.update_memory_from_message(SID, "I like using key gsk_abcdefghijklmnop for experiments")
    joined = " ".join(contents()).lower()
    for bad in ("482913", "hunter2", "4111", "gsk_", "otp", "password"):
        assert bad not in joined
    assert "Preferred name: Aarav" in contents()


def test_questions_and_small_talk_are_not_stored():
    memory.update_memory_from_message(SID, "What is my fee status?")
    memory.update_memory_from_message(SID, "Hello, how are you?")
    memory.update_memory_from_message(SID, "Do I prefer cats?")
    assert contents() == []


def test_deduplication_and_keyed_update():
    memory.update_memory_from_message(SID, "I prefer machine learning electives.")
    memory.update_memory_from_message(SID, "I prefer machine learning electives.")
    memory.update_memory_from_message(SID, "I really prefer machine learning electives")
    assert len([c for c in contents() if c.startswith("Preference")]) == 1
    memory.update_memory_from_message(SID, "Call me Aarav.")
    memory.update_memory_from_message(SID, "Actually call me Rav.")
    assert [c for c in contents() if c.startswith("Preferred name")] == ["Preferred name: Rav"]


def test_retrieval_returns_only_relevant_memories():
    memory.update_memory_from_message(SID, "Call me Aarav. I prefer machine learning electives. Remember that I commute by train.")
    pref = memory.retrieve_relevant_memories(SID, "What are my academic preferences?")
    assert any("machine learning" in m["content"] for m in pref)
    assert not any("train" in m["content"] for m in pref)
    assert memory.retrieve_relevant_memories(SID, "What is the late fee policy?") == []


def test_memory_is_isolated_per_student():
    memory.update_memory_from_message("MIM25001", "I prefer cloud computing electives.")
    assert memory.retrieve_relevant_memories("MIM25002", "What are my preferences?") == []
    assert memory.retrieve_relevant_memories(None, "preferences") == []


def test_memory_persists_across_sessions_through_the_agent():
    run_agent("Please call me Neil and I prefer cloud data engineering electives.", "MIM25011", "session-A", [])
    # brand-new session, empty history -> memory must come from SQLite
    r = run_agent("What did I tell you about my academic preferences in our previous session?", "MIM25011", "session-B", [])
    assert "cloud data engineering" in r["response"].lower()
    assert r["memories_used"] and r["tools_used"] == []


def test_delete_and_clear():
    memory.update_memory_from_message(SID, "Call me Aarav. I prefer finance electives.")
    first = memory.list_memories(SID)[0]["id"]
    assert memory.delete_memory(first, SID) and not memory.delete_memory(first, "MIM25002")
    assert memory.clear_memories(SID) == 1 and contents() == []
