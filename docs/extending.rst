Extending Kiso with New Experiment Types
========================================

Kiso supports adding new experiment types. The Pegasus workflow experiment is builtin.

To create a custom experiment type, you need to create a Python module with three attributes, `SCHEMA`, `DATACLASS`, and `RUNNER`.
Kiso will read the experiment configuration, validate it against the JSON Schema defined by the `SCHEMA` attribute. Kiso will load the configuration into the class defined by the `DATACLASS` attribute.
Kiso then instantiate the class defined by the `RUNNER` attrobute and then invoke the `__call__`.

method to run the experiment.

1. The `SCHEMA` should be a Python dictionary defining your experiment configuration.

.. code-block:: python

    SCHEMA = {
        "title": "My Experiment Configuration Schema",
        "type": "object",
        "properties": {
            "kind": {
                "const": "my-experiment"
            },
            ...
        }
    }

.. note::

    The `kind` property should be a constant string that uniquely identifies your experiment type. This value will aslo be used to register the experiment type with Kiso.

1. The `DATACLASS` should be a Python class of type `dataclasses.dataclass` defining your experiment configuration.

.. code-block:: python

    DATACLASS = MyExperimentConfiguration

    @dataclass
    class MyExperimentConfiguration:
        """My Experiment configuration."""

        kind: str = "my-experiment"

        ...


1. The `RUNNER` should be a Python class implements how to run your experiment.

+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Name       | Type                                   | Default | Description                                                                                                                                                                                                                        |
+============+========================================+=========+====================================================================================================================================================================================================================================+
| experiment | MyExperimentConfiguration              |         | The experiment configuration validated against the JSON Schema defined in the `SCHEMA` attribute and loaded in the data class defined in the `DATACLASS` attribute.                                                                |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| index      | int                                    |         | The `experiment.yml` file can define multiple experiments. The `index` is the int index of this experiment.                                                                                                                        |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| wd         | str                                    |         | Working directory, i.e., in which the `experiment.yml` is located.                                                                                                                                                                 |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| remote_wd  | str                                    |         | Remote working directory, i.e., where the experiment directory is available on the provisioned resources.  is located.                                                                                                             |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| resultdir  | str                                    |         | The directory where the results from the experiment can be placed.                                                                                                                                                                 |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| labels      | Roles                                  |         | A map of label names to Host objects of the provisioned resources.                                                                                                                                                                |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| env        | Environment                            |         | A map whose values will be persisted. The `env` can be used to preserver experiment state.                                                                                                                                         |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| console    | Console \| None                        | None    | The Python `rich.console.Console` object that should be used to render the state of your experiment.                                                                                                                               |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| log        | logging.Logger \| None                 | None    | The Python `logging.Logger` object to use for logging.                                                                                                                                                                             |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| variables  | dict[str, str \| int \| float] \| None | None    | Not used currently. A map of variables defined globally in the experiment.yml. If a `variables` key exists in your experiment configuration, then this will hold variables defined in both globally and at the experiment level.   |
+------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

.. code-block:: python

    RUNNER = MyExperimentRunner

    class MyExperimentRunner:
        """My Experiment runner."""

        #:
        kind: str = "my-experiment"

        def __init__(
            self,
            experiment: MyExperimentConfiguration,
            index: int,
            wd: str,
            remote_wd: str,
            resultdir: str,
            labels: Roles,
            env: Environment,
            console: Console | None = None,
            log: logging.Logger | None = None,
            variables: dict[str, str | int | float] | None = None,
        ) -> None:
            ...

        def __call__(self) -> None:
            """Implement steps to run your experiment."""
            ...


.. note::

    The `kind` property should be a constant string that uniquely identifies your experiment type. This value will aslo be used to register the experiment type with Kiso.

1. Register your experiment type under the entrypoint group `kiso.experiment` with a suitable name (should match the `kind` value above) in your project's `pyproject.toml`, `setup.cfg`, or `setup.py` file.

.. tabs::

    .. tab:: pyproject.toml

        .. code-block:: toml

            [project.entry-points."kiso.experiment"]

            my-experiment = "my.experiment.module"

    .. tab:: setup.cfg

        .. code-block:: ini

            [options.entry_points]

            my-experiment = my.experiment.module

    .. tab:: setup.py

        .. code-block:: python

            setup(
                entry_points = {
                    "kiso.experiment": [
                        "my-experiment = my.experiment.module",
                    ]
                }
            )

Example
-------

The builtin Pegasus workflow experiment type is implemented using the above approach. You can see the code in `src/kiso/workflow` directory of Kiso.
