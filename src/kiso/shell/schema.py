"""Kiso Pegasus workflow experiment configuration schema."""

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Shell Experiment Schema",
    "type": "object",
    "properties": {
        "kind": {"const": "shell"},
        "name": {
            "description": "A suitable name for the experiment",
            "type": "string",
        },
        "description": {
            "description": "A description name for the experiment",
            "type": "string",
        },
        "scripts": {
            "description": "Define all scripts to be executed on the remote machine",
            "type": "array",
            "items": {"$ref": "#/$defs/script"},
        },
        "outputs": {
            "description": "Define all output files to be copied from the remote "
            "machine",
            "type": "array",
            "items": {"$ref": "#/$defs/location"},
        },
    },
    "required": ["kind", "name", "scripts"],
    "additionalProperties": False,
    "$defs": {
        "script": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/script"},
        "location": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/location"},
    },
}
