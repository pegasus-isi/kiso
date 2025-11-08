Extending Kiso
==============

In Kiso, one can add new, software, deployment, and experiment types.

Adding New Software Types
-------------------------

Kiso supports adding new types of software for installation. Docker, Apptainer, and Ollama software are builtin.

To create a custom software, you need to create a Python module with three attributes, `SCHEMA`, `DATACLASS`, and `INSTALLER`.
Kiso will read the software configuration, validate it against the JSON Schema defined by the `SCHEMA` attribute. Kiso will load the configuration into the class defined by the `DATACLASS` attribute.
Kiso then instantiate the class defined by the `INSTALLER` attribute and then invoke either the `check` method to check the configuration or the `__call__` method to install the software.

1. The `SCHEMA` should be a Python dictionary defining your experiment configuration.

.. code-block:: python

    SCHEMA = {
        "title": "My Software Configuration Schema",
        "type": "object",
        "properties": {
            "version": {
                "type": "string",
            },
            ...
        }
    }

1. The `DATACLASS` should be a Python class of type `dataclasses.dataclass` defining your software configuration.

.. code-block:: python

    DATACLASS = MySoftwareConfiguration

    @dataclass
    class MySoftwareConfiguration:
        """My Software configuration."""

        version: str = "0.0.1"

        ...


1. The `INSTALLER` should be a Python class implements how to check and install your software.

+-------------------+----------------------------------------+---------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Name              | Type                                   | Default | Description                                                                                                                                                         |
+===================+========================================+=========+=====================================================================================================================================================================+
| config            | MySoftwareConfiguration                |         | The software configuration validated against the JSON Schema defined in the `SCHEMA` attribute and loaded in the data class defined in the `DATACLASS` attribute.   |
+-------------------+----------------------------------------+---------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| console           | Console \| None                        | None    | The Python `rich.console.Console` object that should be used to render the state of your software.                                                                  |
+-------------------+----------------------------------------+---------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| log               | logging.Logger \| None                 | None    | The Python `logging.Logger` object to use for logging.                                                                                                              |
+-------------------+----------------------------------------+---------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| label_to_machines | enoslib.objects.Roles                  | None    | A map of label names to Host objects of the provisioned resources.                                                                                                  |
+-------------------+----------------------------------------+---------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| env               | enoslib.task.Environment               | None    | A map whose values will be persisted. The `env` can be used to preserve installation state.                                                                         |
+-------------------+----------------------------------------+---------+---------------------------------------------------------------------------------------------------------------------------------------------------------------------+

.. code-block:: python

    INSTALLER = MySoftwareInstaller

    class MySoftwareInstaller:
        """My software installer."""

        def __init__(
            self,
            config: MySoftwareConfiguration,
            console: Console | None = None,
            log: logging.Logger | None = None,
        ) -> None:
            ...

        def check(self, label_to_machines: Roles) -> None:
            """Implement steps to check the configuration."""
            ...

        def __call__(self, env: Environment) -> None:
            """Implement steps to install your software."""
            ...

1. Register your software type under the entrypoint group `kiso.software` with a suitable EntryPoint name in your project's `pyproject.toml`, `setup.cfg`, or `setup.py` file.

.. tabs::

    .. tab:: pyproject.toml

        .. code-block:: toml

            [project.entry-points."kiso.software"]

            mysoftware = "my.software.module"

    .. tab:: setup.cfg

        .. code-block:: ini

            [options.entry_points]

            mysoftware = my.software.module

    .. tab:: setup.py

        .. code-block:: python

            setup(
                entry_points = {
                    "kiso.software": [
                        "mysoftware = my.software.module",
                    ]
                }
            )

.. note::

    The `name` of the EntryPoint used here will be the configuration key in the software section of the experiment configuration.

    .. code-block:: yaml

        sites:
            ...

        software:
            mysoftware:
                version: 5.1.0
                ...

        experiments:
            ...

Example
~~~~~~~

The builtin Apptainer software type is implemented using the above approach. You can see the code in `src/kiso/apptainer <https://github.com/pegasus-isi/kiso/blob/main/src/kiso/apptainer/__init__.py>`_ directory of Kiso.

Adding New Deployment Types
---------------------------

Kiso supports adding new types of deployment for installation. HTCondor deployment type is builtin.

To create a custom deployment, you need to create a Python module with three attributes, `SCHEMA`, `DATACLASS`, and `INSTALLER`.
Kiso will read the deployment configuration, validate it against the JSON Schema defined by the `SCHEMA` attribute. Kiso will load the configuration into the class defined by the `DATACLASS` attribute.
Kiso then instantiate the class defined by the `INSTALLER` attribute and then invoke either the `check` method to check the configuration or the `__call__` method to install the deployment software.

1. The `SCHEMA` should be a Python dictionary defining your experiment configuration.

.. code-block:: python

    SCHEMA = {
        "title": "My Deployment Configuration Schema",
        "type": "object",
        "properties": {
            "version": {
                "type": "string",
            },
            ...
        }
    }

1. The `DATACLASS` should be a Python class of type `dataclasses.dataclass` defining your deployment configuration.

.. code-block:: python

    DATACLASS = MyDeploymentConfiguration

    @dataclass
    class MyDeploymentConfiguration:
        """My Deployment configuration."""

        version: str = "0.0.1"

        ...


1. The `INSTALLER` should be a Python class implements how to check and install your deployment.

+-------------------+----------------------------------------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Name              | Type                                   | Default | Description                                                                                                                                                           |
+===================+========================================+=========+=======================================================================================================================================================================+
| config            | MyDeploymentConfiguration              |         | The deployment configuration validated against the JSON Schema defined in the `SCHEMA` attribute and loaded in the data class defined in the `DATACLASS` attribute.   |
+-------------------+----------------------------------------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| console           | Console \| None                        | None    | The Python `rich.console.Console` object that should be used to render the state of your deployment.                                                                  |
+-------------------+----------------------------------------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| log               | logging.Logger \| None                 | None    | The Python `logging.Logger` object to use for logging.                                                                                                                |
+-------------------+----------------------------------------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| label_to_machines | enoslib.objects.Roles                  | None    | A map of label names to Host objects of the provisioned resources.                                                                                                    |
+-------------------+----------------------------------------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| env               | enoslib.task.Environment               | None    | A map whose values will be persisted. The `env` can be used to preserve installation state.                                                                           |
+-------------------+----------------------------------------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------+


.. code-block:: python

    INSTALLER = MyDeploymentInstaller

    class MyDeploymentInstaller:
        """My deployment installer."""

        def __init__(
            self,
            config: MyDeploymentConfiguration,
            console: Console | None = None,
            log: logging.Logger | None = None,
        ) -> None:
            ...

        def check(self, label_to_machines: Roles) -> None:
            """Implement steps to check the configuration."""
            ...

        def __call__(self, env: Environment) -> None:
            """Implement steps to install your deployment."""
            ...

1. Register your deployment type under the entrypoint group `kiso.deployment` with a suitable EntryPoint name in your project's `pyproject.toml`, `setup.cfg`, or `setup.py` file.

.. tabs::

    .. tab:: pyproject.toml

        .. code-block:: toml

            [project.entry-points."kiso.deployment"]

            mydeployment = "my.deployment.module"

    .. tab:: setup.cfg

        .. code-block:: ini

            [options.entry_points]

            mydeployment = my.deployment.module

    .. tab:: setup.py

        .. code-block:: python

            setup(
                entry_points = {
                    "kiso.deployment": [
                        "mydeployment = my.deployment.module",
                    ]
                }
            )

.. note::

    The `name` of the EntryPoint used here will be the configuration key in the deployment section of the experiment configuration.

    .. code-block:: yaml

        sites:
            ...

        deployment:
            mydeployment:
                version: 5.1.0
                ...

        experiments:
            ...

Example
~~~~~~~

The builtin HTCondor deployment type is implemented using the above approach. You can see the code in `src/kiso/htcondor <https://github.com/pegasus-isi/kiso/blob/main/src/kiso/htcondor/__init__.py>`_ directory of Kiso.


Adding New Experiment Types
---------------------------

Kiso supports adding new experiment types. The Pegasus workflow experiment is builtin.

To create a custom experiment type, you need to create a Python module with three attributes, `SCHEMA`, `DATACLASS`, and `RUNNER`.
Kiso will read the experiment configuration, validate it against the JSON Schema defined by the `SCHEMA` attribute. Kiso will load the configuration into the class defined by the `DATACLASS` attribute.
Kiso then instantiate the class defined by the `RUNNER` attribute and then invoke either the `check` method to check the configuration or the the `__call__` method to run the experiment.

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

    The `kind` property should be a constant string that uniquely identifies your experiment type. This value will also be used to register the experiment type with Kiso.

1. The `DATACLASS` should be a Python class of type `dataclasses.dataclass` defining your experiment configuration.

.. code-block:: python

    DATACLASS = MyExperimentConfiguration

    @dataclass
    class MyExperimentConfiguration:
        """My Experiment configuration."""

        kind: str = "my-experiment"

        ...


1. The `RUNNER` should be a Python class implements how to check and to run your experiment.

+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| Name              | Type                                   | Default | Description                                                                                                                                                                                                                        |
+===================+========================================+=========+====================================================================================================================================================================================================================================+
| experiment        | MyExperimentConfiguration              |         | The experiment configuration validated against the JSON Schema defined in the `SCHEMA` attribute and loaded in the data class defined in the `DATACLASS` attribute.                                                                |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| index             | int                                    |         | The `experiment.yml` file can define multiple experiments. The `index` is the int index of this experiment.                                                                                                                        |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| console           | Console \| None                        | None    | The Python `rich.console.Console` object that should be used to render the state of your experiment.                                                                                                                               |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| log               | logging.Logger \| None                 | None    | The Python `logging.Logger` object to use for logging.                                                                                                                                                                             |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| variables         | dict[str, str \| int \| float] \| None | None    | Not used currently. A map of variables defined globally in the experiment.yml. If a `variables` key exists in your experiment configuration, then this will hold variables defined in both globally and at the experiment level.   |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| config            | MyExperimentConfiguration              |         | The experiment configuration validated against the JSON Schema defined in the `SCHEMA` attribute and loaded in the data class defined in the `DATACLASS` attribute.                                                                |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| label_to_machines | enoslib.objects.Roles                  | None    | A map of label names to Host objects of the provisioned resources.                                                                                                                                                                 |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| wd                | str                                    |         | Working directory, i.e., in which the `experiment.yml` is located.                                                                                                                                                                 |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| remote_wd         | str                                    |         | Remote working directory, i.e., where the experiment directory is available on the provisioned resources.  is located.                                                                                                             |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| resultdir         | str                                    |         | The directory where the results from the experiment can be placed.                                                                                                                                                                 |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| labels             | Roles                                 |         | A map of label names to Host objects of the provisioned resources.                                                                                                                                                                 |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| env               | Environment                            |         | A map whose values will be persisted. The `env` can be used to preserve experiment state.                                                                                                                                          |
+-------------------+----------------------------------------+---------+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+

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
            console: Console | None = None,
            log: logging.Logger | None = None,
            variables: dict[str, str | int | float] | None = None,
        ) -> None:
            ...

        def check(self, config: Kiso, label_to_machines: Roles) -> None:
            """Implement steps to check your experiment."""

        def __call__(self, wd: str, remote_wd: str, resultdir: str, labels: Roles, env: Environment) -> None:
            """Implement steps to run your experiment."""
            ...


.. note::

    The `kind` property should be a constant string that uniquely identifies your experiment type. This value will also be used to register the experiment type with Kiso.

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
~~~~~~~

The builtin Pegasus workflow experiment type is implemented using the above approach. You can see the code in `src/kiso/workflow <https://github.com/pegasus-isi/kiso/blob/main/src/kiso/workflow/__init__.py>`_ directory of Kiso.
