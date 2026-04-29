import enum


class BlockType(str, enum.Enum):
    lesson = "lesson"
    auto_test = "auto_test"
    manual_test = "manual_test"
    mixed_test = "mixed_test"
