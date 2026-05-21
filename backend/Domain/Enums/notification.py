import enum

class NotificationType(str, enum.Enum):
    new_course = "new_course"
    manual_test_check = "manual_test_check"
    other = "other"
