"""
Тесты логики update_feed_status — автоматическое отключение мёртвых лент.

Покрывает:
- успешный фетч: error_count обнуляется, last_fetched_at обновляется
- ошибочный фетч: error_count растёт
- авто-отключение: 24+ ошибки И last_fetched_at > 48ч → enabled = FALSE + warning в лог
- авто-отключение не срабатывает если условия не выполнены оба одновременно
- None conn: ранний выход без исключения

Запуск: python3 -m pytest tests/test_feed_status.py -v
"""
import pytest
from unittest.mock import MagicMock, patch, call


# ── Вспомогательные функции ───────────────────────────────────────────────────

def make_mock_conn(enabled_after_update: bool = True):
    """
    Возвращает (conn, cursor) где cursor.fetchone() имитирует ответ БД
    после UPDATE — возвращает текущее значение enabled.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {"enabled": enabled_after_update}

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    return mock_conn, mock_cursor


# ── Успешный фетч ─────────────────────────────────────────────────────────────

def test_success_executes_reset_query():
    """При успехе (error=None) выполняется UPDATE с обнулением error_count."""
    from src.tools.db_state import update_feed_status

    conn, cursor = make_mock_conn()
    update_feed_status(conn, url="https://example.com/rss", error=None)

    sql_called = cursor.execute.call_args[0][0]
    assert "error_count = 0" in sql_called
    assert "last_fetched_at = NOW()" in sql_called


def test_success_does_not_check_enabled_state():
    """При успехе не делается SELECT для проверки enabled — лишний запрос не нужен."""
    from src.tools.db_state import update_feed_status

    conn, cursor = make_mock_conn()
    update_feed_status(conn, url="https://example.com/rss", error=None)

    # При успехе только один execute — UPDATE, SELECT не делается
    assert cursor.execute.call_count == 1


# ── Ошибочный фетч ────────────────────────────────────────────────────────────

def test_error_executes_increment_query():
    """При ошибке выполняется UPDATE с инкрементом error_count."""
    from src.tools.db_state import update_feed_status

    conn, cursor = make_mock_conn(enabled_after_update=True)
    update_feed_status(conn, url="https://example.com/rss", error="Connection timeout")

    sql_called = cursor.execute.call_args_list[0][0][0]
    assert "error_count + 1" in sql_called


def test_error_passes_error_text_as_parameter():
    """Текст ошибки передаётся как параметр запроса, не подставляется в строку SQL."""
    from src.tools.db_state import update_feed_status

    conn, cursor = make_mock_conn(enabled_after_update=True)
    update_feed_status(conn, url="https://example.com/rss", error="404 Not Found")

    params = cursor.execute.call_args_list[0][0][1]
    assert "404 Not Found" in params


def test_error_checks_enabled_after_update():
    """После UPDATE при ошибке делается SELECT для проверки не отключилась ли лента."""
    from src.tools.db_state import update_feed_status

    conn, cursor = make_mock_conn(enabled_after_update=True)
    update_feed_status(conn, url="https://example.com/rss", error="timeout")

    # Два execute: UPDATE + SELECT
    assert cursor.execute.call_count == 2
    select_sql = cursor.execute.call_args_list[1][0][0]
    assert "SELECT enabled" in select_sql


# ── Авто-отключение: warning в лог ───────────────────────────────────────────

def test_auto_disable_logs_warning_when_feed_becomes_disabled():
    """
    Если после UPDATE лента стала disabled (enabled=False) —
    в лог пишется warning с URL ленты.
    """
    from src.tools.db_state import update_feed_status

    conn, cursor = make_mock_conn(enabled_after_update=False)

    with patch("src.tools.db_state.logger") as mock_logger:
        update_feed_status(conn, url="https://dead-feed.com/rss", error="timeout")
        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0]
        assert "https://dead-feed.com/rss" in warning_msg


def test_auto_disable_no_warning_when_feed_still_enabled():
    """
    Если лента осталась включённой после ошибки (условие не выполнено) —
    warning не пишется.
    """
    from src.tools.db_state import update_feed_status

    conn, cursor = make_mock_conn(enabled_after_update=True)

    with patch("src.tools.db_state.logger") as mock_logger:
        update_feed_status(conn, url="https://example.com/rss", error="timeout")
        mock_logger.warning.assert_not_called()


# ── SQL содержит оба условия авто-отключения ──────────────────────────────────

def test_error_sql_contains_disable_condition():
    """
    SQL при ошибке должен содержать условие авто-отключения:
    - last_fetched_at IS NOT NULL AND last_fetched_at < NOW() - INTERVAL '48 hours'
    Новые ленты (NULL) не отключаются с первой ошибки.
    """
    from src.tools.db_state import update_feed_status

    conn, cursor = make_mock_conn(enabled_after_update=True)
    update_feed_status(conn, url="https://example.com/rss", error="timeout")

    sql_called = cursor.execute.call_args_list[0][0][0]
    assert "48 hours" in sql_called
    assert "IS NOT NULL" in sql_called


# ── disabled_reason в SQL ─────────────────────────────────────────────────────

def test_error_sql_sets_disabled_reason_error():
    """SQL при ошибке должен проставлять disabled_reason = 'error' при автоотключении."""
    from src.tools.db_state import update_feed_status

    conn, cursor = make_mock_conn(enabled_after_update=True)
    update_feed_status(conn, url="https://example.com/rss", error="timeout")

    sql_called = cursor.execute.call_args_list[0][0][0]
    assert "disabled_reason" in sql_called
    assert "'error'" in sql_called


# ── None conn ─────────────────────────────────────────────────────────────────

def test_none_conn_returns_without_error():
    """Если conn=None — функция возвращается без исключения."""
    from src.tools.db_state import update_feed_status

    update_feed_status(None, url="https://example.com/rss", error=None)
    update_feed_status(None, url="https://example.com/rss", error="timeout")
