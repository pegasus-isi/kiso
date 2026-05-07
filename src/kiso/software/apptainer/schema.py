"""Kiso Apptainer software configuration schema."""

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Apptainer Software Configuration",
    "description": "Specify on which resources the Apptainer runtime "
    "should be installed",
    "type": "object",
    "properties": {
        "labels": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/labels"},
        "version": {"type": "string"},
    },
    "required": ["labels"],
    "additionalProperties": False,
}
