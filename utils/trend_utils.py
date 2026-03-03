import json


def parse_tags(tags_text: str | None) -> list[str]:
    if not tags_text:
        return []
    try:
        tags = json.loads(tags_text)
        return tags if isinstance(tags, list) else []
    except json.JSONDecodeError:
        return []
