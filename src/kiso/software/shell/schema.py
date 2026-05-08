"""Kiso Shell software configuration schema."""

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Shell Software Configuration",
    "description": "Run shell scripts on the specified resources",
    "type": "array",
    "items": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/script"},
    "minItems": 1,
}
