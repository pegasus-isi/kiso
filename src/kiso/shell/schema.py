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
    "required": ["kind", "name", "description", "scripts"],
    "additionalProperties": False,
    "$defs": {
        "script": {
            "title": "Shell Script Schema",
            "type": "object",
            "properties": {
                "labels": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/labels"},
                "executable": {
                    "description": "The executable (shebang) to be used to run the "
                    "script",
                    "type": "string",
                    "default": "/bin/bash",
                },
                "script": {
                    "description": "The script to be executed",
                    "type": "string",
                },
            },
            "required": ["labels", "script"],
            "additionalProperties": False,
        },
        "location": {
            "title": "File Upload/Download Location Schema",
            "type": "object",
            "properties": {
                "labels": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/labels"},
                "src": {"description": "The src file to be copied", "type": "string"},
                "dst": {
                    "description": "The dst where the src should be copied too. This "
                    "must be a directory",
                    "type": "string",
                },
            },
            "required": ["labels", "src", "dst"],
            "additionalProperties": False,
        },
    },
}
