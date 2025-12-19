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
        "description": {
            "description": "A description name for the experiment",
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
        "poll_interval": {
            "description": "Checks the status of the experiment every poll_interval "
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
        "submit_node_labels": {
            "$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/labels"
        },
        "post_scripts": {
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
    "required": ["kind", "name", "main", "submit_node_labels"],
    "additionalProperties": False,
    "$defs": {
        "setup": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/script"},
        "location": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/location"},
    },
}
