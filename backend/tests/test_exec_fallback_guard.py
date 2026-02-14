from app.handler import _is_exec_intent


def test_shopping_list_is_not_exec_intent():
    assert _is_exec_intent("Make a shopping list, add sweet popcorn and Ben and Jerry icecream") is False


def test_apple_notes_is_exec_intent():
    assert _is_exec_intent("Can you see my Apple notes?") is True
