import enum


class CourseLevel(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class CourseAudience(str, enum.Enum):
    everyone = "everyone"
    installer = "installer"
    seller = "seller"
    serviceman = "serviceman"
    buyer = "buyer"


class CourseStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"
