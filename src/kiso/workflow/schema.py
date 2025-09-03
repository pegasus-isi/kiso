"""Kiso Pegasus workflow experiment configuration schema."""

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Pegasus Workflow Experiment Schema",
    "type": "object",
    "properties": {
        "kind": {"const": "pegasus"},
        "name": {
            "description": "A suitable name for the experiment",
            "type": "string",
        },
        "variables": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/variables"},
        "count": {
            "type": "integer",
            "description": "The number of times the experiment should be run",
            "minimum": 1,
            "default": 1,
        },
        "main": {
            "description": "A script which execute teh experiment",
            "type": "string",
        },
        "args": {
            "description": "A list of arguments to be passed to the main script",
            "type": "array",
            "items": {"type": "string"},
        },
        "poll-interval": {
            "description": "Checks the status of the experiment every poll-interval "
            "seconds",
            "type": "integer",
            "default": 60,
        },
        "timeout": {
            "description": "If the experiment takes longer than timeout seconds, it is "
            "considered failed",
            "type": "integer",
            "default": 600,
        },
        "inputs": {
            "description": "Define all input files to be copied to the remote machine",
            "type": "array",
            "items": {"$ref": "#/$defs/location"},
        },
        "setup": {
            "description": "Define all setup scripts to be executed on the remote "
            "machine",
            "type": "array",
            "items": {"$ref": "#/$defs/setup"},
        },
        "submit-node-labels": {
            "$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/labels"
        },
        "post-scripts": {
            "description": "Define all scripts to be executed after the experiment",
            "type": "array",
            "items": {"$ref": "#/$defs/setup"},
        },
        "outputs": {
            "description": "Define all output files to be copied from the remote "
            "machine",
            "type": "array",
            "items": {"$ref": "#/$defs/location"},
        },
    },
    "required": ["kind", "name", "main", "submit-node-labels"],
    "additionalProperties": False,
    "$defs": {
        "setup": {
            "title": "Script Setup Schema",
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
            "title": "File Upload/Download Schema",
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
