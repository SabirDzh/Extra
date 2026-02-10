from enum import StrEnum


class QuestionType(StrEnum):
    SINGLE = "SINGLE_CHOICE"
    MULTI = "MULTI_CHOICE"
    OPNE = "OPEN_TEXT"
