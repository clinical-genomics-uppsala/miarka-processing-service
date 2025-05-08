"""
Module dealing with interacting with Nextflow
"""

import copy
import logging
import datetime
from pathlib import Path
import json
import jsonschema
import yaml

log = logging.getLogger(__name__)


def nextflow_command(
    pipeline,
    runfolder_path,
    config_dir,
    input_samplesheet_content="",
    ext_args=None,
):
    """
    Generate a Nextflow command according to parameters specified in
    a configuration file. The file should be named after the pipeline eg.
    `pipeline_name.yml`.

    The following variables in the config file as well as in the input
    samplesheet will be interpolated with the parameters passed in to this
    function:
    - {runfolder_name}
    - {runfolder_path}
    - {current_year}
    - {input_samplesheet_path}

    Parameters
    ----------
    pipeline: str
        pipeline to use, there must be a corresponding {pipeline}.yml file in
        the config directory
    runfolder_path: str
        path to runfolder to process
    config_dir: str
        path to directory containing the pipeline config files
    input_samplesheet_content: str
        content of the pipeline's input samplesheet
    ext_args: [str]
        list of extra arguments to append to the command. These will override
        the arguments defined in the config file

    Returns
    -------
        command_with_env: dict
    """
    raw_config = get_config(config_dir, pipeline)
    input_samplesheet_content = (
        input_samplesheet_content
        or raw_config.get("input_samplesheet_content", "")
    )
    defaults = build_defaults(
        pipeline,
        runfolder_path,
        input_samplesheet_content
    )
    config = interpolate_variables(raw_config, defaults)

    env = config.get("environment", {})
    cmd = [
        'nextflow',
        'run', config['main_workflow_path'],
    ]

    cmd += [
        arg
        for key, value in config.get("nextflow_parameters", {}).items()
        for arg in ([f"-{key}", f"{value}"] if value else [f"-{key}"])
    ]

    cmd += [
        arg
        for key, value in config.get("pipeline_parameters", {}).items()
        for arg in ([f"--{key}", f"{value}"] if value else [f"--{key}"])
    ]

    if ext_args:
        cmd += ext_args

    log.debug("Generated command: %s", cmd)

    return {"command": cmd, "environment": env}


def get_config(config_dir, pipeline):
    """
    Load and validate the config file for the requested pipeline.

    Parameters
    ----------
    config_dir: str
        path to directory containing the config files
    pipeline: str
        pipeline to load

    Returns
    -------
        config: dict
    """
    config_dir = Path(config_dir)
    try:
        with open(config_dir / f"{pipeline}.yml", "r") as config_file:
            config = yaml.safe_load(config_file.read())
        with open(config_dir / "schema.json", "r") as pipeline_config_schema:
            schema = json.load(pipeline_config_schema)
        jsonschema.validate(config, schema)
    except (FileNotFoundError, jsonschema.ValidationError):
        log.exception('')
        raise

    return config


def build_defaults(pipeline, runfolder_path, input_samplesheet_content):
    """
    Fetch default values to be used with `interpolate_variables`.

    This will also write down the content of the input samplesheet to a file
    in the runfolder and set its path as one of the default fields.

    Parameters
    ----------
    pipeline: str
        pipeline to use
    runfolder_path: str
        path to the runfolder to process
    input_samplesheet_content: str
        content of the input samplesheet that will be given to the nextflow
        pipeline.

    Returns
    -------
    defaults: dict
    """
    runfolder_path = Path(runfolder_path)
    defaults = {
        "current_year": datetime.datetime.now().year,
        "runfolder_path": str(runfolder_path),
        "runfolder_name": runfolder_path.name,
    }

    if input_samplesheet_content:
        try:
            input_samplesheet_content = input_samplesheet_content.format(**defaults)
        except KeyError:
            log.exception('')
            raise

        input_samplesheet_path = runfolder_path / f"{pipeline}_samplesheet.csv"
        with open(input_samplesheet_path, "w") as f:
            f.write(input_samplesheet_content)
        defaults["input_samplesheet_path"] = str(input_samplesheet_path)

    return defaults


def interpolate_variables(config, defaults):
    """
    Interpolate variables from the `config` dictionary` with the values from
    `default`: values defined as `{variable_name}` will be replaced by the
    value at `variable_name` in the `default` dictionary.

    Parameters
    ----------
    config: dict
        dict where values need to be interpolated
    defaults: dict
        dict containing the new values

    Returns
    -------
    config: dict
        dictionaries with interpolated variables
    """
    config = copy.deepcopy(config)
    try:
        for section in [
                    "environment",
                    "pipeline_parameters",
                    "nextflow_parameters",
                ]:
            if section in config:
                for key, value in config[section].items():
                    config[section][key] = value.format(**defaults)
    except KeyError:
        # This may happen if some format strings contain keys that are not in
        # `defaults`.
        log.exception('')
        raise

    return config
