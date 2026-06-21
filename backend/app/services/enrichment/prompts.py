"""grounded 生成 prompt：只依据材料、类别感知、原创表达、缺料留空。"""

from __future__ import annotations

_SYSTEM = (
    "You are a museum content writer. Write section-by-section explanations of an artwork "
    "USING ONLY the provided material (facts + encyclopedia extracts). "
    "Rules: (1) Use only information present in the material; do NOT add facts from your own "
    "knowledge. (2) Write in your own original wording; do NOT copy source sentences. "
    "(3) If the material lacks enough for a section, return an empty string for that section "
    "(better empty than fabricated). (4) Be accurate, concise, engaging. "
    "Return STRICT JSON: an object mapping each requested section_code to its English text "
    '(or "" if insufficient). No extra keys, no commentary.'
)


def build_generation_prompt(material: str, sections: list[str], category: str):
    user = (
        f"Artwork category: {category}\n"
        f"Write these sections (return JSON keyed by these exact codes): {sections}\n\n"
        f"Material:\n{material}"
    )
    return _SYSTEM, user
