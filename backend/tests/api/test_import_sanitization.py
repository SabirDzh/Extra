from Repository.common import sanitize_import_text
from Repository.error import parse_error_csv_file
from Repository.faq import parse_faq_csv_file
from Repository.recommendation import parse_recommendation_csv_file
from Repository.term import parse_csv_file as parse_term_csv_file


def test_sanitize_import_text_normalizes_whitespace_newlines_and_slashes():
    raw = "  Foo\\bar\r\n\tBaz   \x0bQux  "
    assert sanitize_import_text(raw) == "Foo/bar Baz Qux"


def test_parse_faq_csv_file_sanitizes_question_and_answer():
    csv_text = 'question,answer,order_index,is_published\n"Какой\\\\вопрос?","Ответ\\tс переносом",3,false\n'

    rows = parse_faq_csv_file(csv_text.encode("utf-8"))
    assert len(rows) == 1
    assert rows[0]["question"] == "Какой/вопрос?"
    assert rows[0]["answer"] == "Ответ с переносом"
    assert rows[0]["order_index"] == 3
    assert rows[0]["is_published"] is False


def test_parse_term_csv_file_sanitizes_title_and_description():
    csv_text = 'title,description\n"  Термин\\\\1  "," Описание термина\\t "\n'

    rows = parse_term_csv_file(csv_text.encode("utf-8"))
    assert len(rows) == 1
    assert rows[0]["title"] == "Термин/1"
    assert rows[0]["description"] == "Описание термина"


def test_parse_recommendation_and_error_csv_sanitizes_values():
    rec_csv = 'title,description\n"  Рекомендация\\\\A  ","Текст рекомендации"\n'
    err_csv = 'title,description,order_index,is_published\n" Ошибка\\\\A ","Описание ошибки",2,yes\n'

    rec_rows = parse_recommendation_csv_file(rec_csv.encode("utf-8"))
    err_rows = parse_error_csv_file(err_csv.encode("utf-8"))

    assert rec_rows[0]["title"] == "Рекомендация/A"
    assert rec_rows[0]["description"] == "Текст рекомендации"

    assert err_rows[0]["title"] == "Ошибка/A"
    assert err_rows[0]["description"] == "Описание ошибки"
    assert err_rows[0]["order_index"] == 2
    assert err_rows[0]["is_published"] is True
