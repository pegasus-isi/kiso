"""Kiso HTCondor deployment configuration schema."""

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "HTCondor Deployment Configuration",
    "description": "Specify how and on which resources HTCondor should be installed",
    "type": "array",
    "items": {"$ref": "#/$defs/htcondor"},
    "minItems": 1,
    "$defs": {
        "htcondor": {
            "title": "HTCondor Daemon Configuration",
            "description": "Specify how and on which resources HTCondor should "
            "be installed",
            "type": "object",
            "properties": {
                "kind": {
                    "description": "Specify which resource will have the "
                    "central manager and it's configuration",
                    "type": "string",
                    "enum": ["central-manager", "execute", "submit", "personal"],
                },
                "labels": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/labels"},
                "config-file": {"type": "string"},
            },
            "required": ["kind", "labels"],
            "additionalProperties": False,
        }
    },
}
