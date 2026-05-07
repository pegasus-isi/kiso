"""Kiso Ollama software configuration schema."""

SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Ollama Software Configuration",
    "type": "array",
    "items": {"$ref": "#/$defs/ollama"},
    "minItems": 1,
    "$defs": {
        "ollama": {
            "title": "Ollama Configuration",
            "description": "Specify on which resources the Ollama service should "
            "be installed and what models should be pulled",
            "type": "object",
            "properties": {
                "labels": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/labels"},
                "models": {
                    "description": "A list of Ollama models to be installed",
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "environment": {
                    "$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/variables"
                },
            },
            "required": ["labels", "models"],
            "additionalProperties": False,
        }
    },
}
