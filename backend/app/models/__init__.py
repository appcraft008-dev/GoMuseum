"""Models module initialization"""

from app.models.ai_service_log import AIServiceLog
from app.models.content import CategorySection, ObjectContentSection, SectionType
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.models.recognition_result import RecognitionResult
from app.models.recognition_stats import RecognitionStats
from app.models.user_benefits import UserBenefits

__all__ = [
    "RecognitionResult",
    "RecognitionStats",
    "AIServiceLog",
    "UserBenefits",
]
__all__ += [
    "Museum",
    "MuseumObject",
    "ObjectImage",
    "SectionType",
    "CategorySection",
    "ObjectContentSection",
]
