from app.handler import _is_exec_intent, _looks_like_reminder_set_request
from app.reminders import parse_reminder


def test_alarm_for_time_is_parsed():
    r = parse_reminder("set an alarm for 10 am", tz_str="Asia/Jerusalem")
    assert r is not None
    assert r.get("wake_up") is True


def test_set_reminder_for_tomorrow_is_parsed():
    r = parse_reminder("set a reminder for tomorrow 11am", tz_str="Asia/Jerusalem")
    assert r is not None


def test_reminder_set_intent_but_not_exec_intent():
    text = "Hi can you set an alarm for 10 am?"
    assert _looks_like_reminder_set_request(text) is True
    assert _is_exec_intent(text) is False


def test_reminder_list_question_not_set_intent():
    assert _looks_like_reminder_set_request("Do I have any reminders?") is False
