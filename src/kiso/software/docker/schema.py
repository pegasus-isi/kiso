"""Kiso Docker software configuration schema."""

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Docker Software Configuration",
    "description": "Specify on which resources the Docker runtime should be installed",
    "type": "object",
    "properties": {
        "labels": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/labels"},
        "version": {"type": "string"},
    },
    "required": ["labels"],
    "additionalProperties": False,
}
