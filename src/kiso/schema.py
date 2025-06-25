"""_summary_.

_extended_summary_
"""

import enoslib as en

_roles_schema: dict = {
    "type": "array",
    "items": {"type": "string", "pattern": "^[a-zA-Z0-9._-]+$"},
    "minItems": 1,
    "uniqueItems": True,
}


SCHEMA: dict = {
    "type": "object",
    "title": "Kiso experiment configuration",
    "properties": {
        "name": {"type": "string"},
        "variables": {"$ref": "#/definitions/variables"},
        "sites": {
            "type": "array",
            "items": {"$ref": "#/definitions/site"},
            "minItems": 1,
        },
        "experiments": {
            "type": "array",
            "items": {"$ref": "#/definitions/experiment"},
            "minItems": 1,
        },
        "docker": {
            "type": "object",
            "properties": {
                "roles": {"$ref": "#/definitions/roles"},
                "version": {"type": "string"},
            },
            "required": ["roles"],
            "additionalProperties": False,
        },
        "apptainer": {
            "type": "object",
            "properties": {
                "roles": {"$ref": "#/definitions/roles"},
                "version": {"type": "string"},
            },
            "required": ["roles"],
            "additionalProperties": False,
        },
        "condor": {
            "type": "object",
            "properties": {
                "central-manager": {
                    "type": "object",
                    "properties": {
                        "roles": {"$ref": "#/definitions/roles"},
                        "config-file": {"type": "string"},
                    },
                }
            },
            "patternProperties": {
                "^personal(-\\d{1,})?$": {
                    "type": "object",
                    "properties": {
                        "roles": {"$ref": "#/definitions/roles"},
                        "config-file": {"type": "string"},
                    },
                },
                "^execute(-\\d{1,})?$": {
                    "type": "object",
                    "properties": {
                        "roles": {"$ref": "#/definitions/roles"},
                        "config-file": {"type": "string"},
                    },
                },
                "^submit(-\\d{1,})?$": {
                    "type": "object",
                    "properties": {
                        "roles": {"$ref": "#/definitions/roles"},
                        "config-file": {"type": "string"},
                    },
                },
            },
            "additionalProperties": False,
        },
    },
    "required": ["name", "sites", "experiments"],
    "additionalProperties": False,
    "definitions": {
        "variables": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_]+$": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "integer"},
                        {"type": "number"},
                    ]
                },
            },
            "additionalProperties": False,
        },
        "site": {
            "title": "Site definition",
            "oneOf": [],
        },
        "experiment": {
            "title": "Pegasus workflow experiment definition",
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "name": {"type": "string"},
                "variables": {"$ref": "#/definitions/variables"},
                "count": {"type": "integer", "minimum": 1, "default": 1},
                "main": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
                "inputs": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/location"},
                },
                "setup": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/setup"},
                },
                "submit-node-roles": {"$ref": "#/definitions/roles"},
                "post-scripts": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/setup"},
                },
                "outputs": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/location"},
                },
            },
            "required": ["kind", "name", "main", "submit-node-roles"],
            "additionalProperties": False,
        },
        "setup": {
            "type": "object",
            "properties": {
                "roles": {"$ref": "#/definitions/roles"},
                "executable": {"type": "string", "default": "/bin/bash"},
                "script": {"type": "string"},
            },
            "required": ["roles", "script"],
            "additionalProperties": False,
        },
        "location": {
            "type": "object",
            "properties": {
                "roles": {"$ref": "#/definitions/roles"},
                "src": {"type": "string"},
                "dst": {"type": "string"},
            },
            "required": ["roles", "src", "dst"],
            "additionalProperties": False,
        },
        "roles": _roles_schema,
    },
}


_roles_schema = _roles_schema.copy()
_roles_schema["items"] = _roles_schema["items"].copy()
_roles_schema["items"]["pattern"] = "^(?!kiso\\.)[a-zA-Z0-9._-]+$"


if hasattr(en, "Vagrant"):
    from enoslib.infra.enos_vagrant.schema import SCHEMA as VAGRANT_SCHEMA

    VAGRANT_SCHEMA["properties"]["kind"] = {"const": "vagrant"}
    VAGRANT_SCHEMA["definitions"]["machine"]["properties"]["roles"] = _roles_schema
    VAGRANT_SCHEMA["definitions"]["network"]["properties"]["roles"] = _roles_schema
    SCHEMA["definitions"]["site"]["oneOf"].append(
        {
            "allOf": [
                {"required": ["kind"]},
                {"$ref": "py-obj:kiso.schema.VAGRANT_SCHEMA"},
            ]
        }
    )

if hasattr(en, "CBM"):
    from enoslib.infra.enos_chameleonkvm.schema import SCHEMA as CBM_SCHEMA

    CBM_SCHEMA["properties"]["kind"] = {"const": "chameleon"}
    CBM_SCHEMA["machine"]["properties"]["roles"] = _roles_schema
    SCHEMA["definitions"]["site"]["oneOf"].append(
        {
            "allOf": [
                {"required": ["kind"]},
                {"$ref": "py-obj:kiso.schema.CBM_SCHEMA"},
            ]
        }
    )

if hasattr(en, "ChameleonEdge"):
    from enoslib.infra.enos_chameleonedge.schema import SCHEMA as CHAMELEON_EDGE_SCHEMA

    CHAMELEON_EDGE_SCHEMA["properties"]["kind"] = {"const": "chameleon-edge"}
    CHAMELEON_EDGE_SCHEMA["deviceCluster"]["properties"]["roles"] = _roles_schema
    CHAMELEON_EDGE_SCHEMA["device"]["properties"]["roles"] = _roles_schema
    CHAMELEON_EDGE_SCHEMA["network"]["properties"]["roles"] = _roles_schema
    SCHEMA["definitions"]["site"]["oneOf"].append(
        {
            "allOf": [
                {"required": ["kind"]},
                {"$ref": "py-obj:kiso.schema.CHAMELEON_EDGE_SCHEMA"},
            ]
        }
    )

if hasattr(en, "Fabric"):
    from enoslib.infra.enos_fabric.schema import SCHEMA as FABRIC_SCHEMA

    FABRIC_SCHEMA["properties"]["kind"] = {"const": "fabric"}
    FABRIC_SCHEMA["definitions"]["machine"]["properties"]["roles"] = _roles_schema
    SCHEMA["definitions"]["site"]["oneOf"].append(
        {
            "allOf": [
                {"required": ["kind"]},
                {"$ref": "py-obj:kiso.schema.FABRIC_SCHEMA"},
            ]
        }
    )
