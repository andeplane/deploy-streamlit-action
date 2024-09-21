import logging
from os import getenv
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, root_validator
from yaml import safe_load  # type: ignore

from access import verify_deploy_capabilites, verify_schedule_creds_capabilities

from utils import (
    FnFileString,
    NonEmptyString,
    NonEmptyStringMax32,
    NonEmptyStringMax128,
    NonEmptyStringMax500,
    ToLowerStr,
    YamlFileString,
    create_oidc_client_from_dct,
    decode_and_parse,
    verify_path_is_directory,
)

logger = logging.getLogger(__name__)
RUNNING_IN_AZURE_PIPE = False
RUNNING_IN_GITHUB_ACTION = False

if RUNNING_IN_GITHUB_ACTION := getenv("GITHUB_ACTIONS") == "true":
    logger.info("Inferred current runtime environment to be 'Github Actions'.")
if RUNNING_IN_AZURE_PIPE := getenv("TF_BUILD") == "True":
    logger.info("Inferred current runtime environment to be 'Azure Pipelines'.")

if RUNNING_IN_GITHUB_ACTION is RUNNING_IN_AZURE_PIPE:  # Hacky XOR
    raise RuntimeError(
        "Unable to unambiguously infer the current runtime environment. Please create an "
        "issue on Github: https://github.com/cognitedata/streamlit-action/"
    )

def get_parameter(key, prefix=""):
    return getenv(key) # Todo: remove this

    if RUNNING_IN_AZURE_PIPE:
        prefix = ""  # Just to point out no prefix in Azure (is protected)
    elif RUNNING_IN_GITHUB_ACTION:
        prefix = "INPUT_"
    # Missing args passed as empty strings, load as `None` instead:
    return getenv(f"{prefix}{key.upper()}", "").strip() or None

class GithubActionModel(BaseModel):
    class Config:
        allow_population_by_field_name = True

    @classmethod
    def from_envvars(cls):
        """Magic parameter-load from env.vars. (Github Action Syntax)"""

        expected_params = cls.schema()["properties"]
        obj = {k: v for k, v in zip(expected_params, map(get_parameter, expected_params)) if v}
        return cls.parse_obj(obj)

class CredentialsModel(BaseModel):
    @property
    def credentials(self) -> Dict[str, str]:
        return self.dict(include={"client_id", "client_secret"})

    @property
    def client(self):
        return create_oidc_client_from_dct(self.dict(by_alias=False))


class DeployCredentials(GithubActionModel, CredentialsModel):
    cdf_project: NonEmptyString
    cdf_cluster: NonEmptyString
    client_id: NonEmptyString = Field(alias="deployment_client_id")
    tenant_id: NonEmptyString = Field(alias="deployment_tenant_id")
    client_secret: NonEmptyString = Field(alias="deployment_client_secret")
    data_set_id: Optional[int]  # For acl/capability checks only

    @root_validator(skip_on_failure=True)
    def verify_credentials_and_capabilities(cls, values):
        client = create_oidc_client_from_dct(values)
        project = values["cdf_project"]
        data_set_id = values["data_set_id"]
        # TODO: Perform verification
        # verify_deploy_capabilites(client, project, ds_id=data_set_id)
        return values


class AppConfig(GithubActionModel):
    name: NonEmptyString
    folder: Path
    description: NonEmptyString
    external_id: NonEmptyString
    version: NonEmptyString
    creator: NonEmptyString
    entrypoint: NonEmptyString
    published: bool
    data_set_id: Optional[int]
    
    @root_validator(skip_on_failure=True)
    def check_function_folders(cls, values):
        app_folder = Path(get_parameter("app_folder"))
        
        # First check that path exists
        verify_path_is_directory(app_folder, "app_folder")
        
        # Check that config.yaml is present
        if not (config_file := app_folder / "config.yaml").is_file():
            raise ValueError(f"Missing 'config.yaml' file in app folder: '{app_folder}'")
        
        # Verify the contents of the config.yaml
        with open(config_file, "r") as fh:
            config = safe_load(fh)
        if not isinstance(config, dict):
            raise ValueError(f"Invalid 'config.yaml' file in app folder: '{app_folder}'")
        required_fields = ["name", "version", "description", "creator", "entrypoint", "published", "external_id"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing '{field}' in 'config.yaml' file in app folder: '{app_folder}'")
            
        # Check that requirements.txt is present
        if not (req_file := app_folder / "requirements.txt").is_file():
            raise ValueError(f"Missing 'requirements.txt' file in app folder: '{app_folder}'")
        
        return values

    @classmethod
    def from_file(cls):
        app_folder = get_parameter("app_folder")
        app_config_file = Path(get_parameter("app_folder")) / "config.yaml"
        with open(app_config_file, "r") as fh:
            config = safe_load(fh)
        config['folder'] = app_folder
        return cls.parse_obj(config)


class RunConfig(BaseModel):
    deploy_creds: DeployCredentials
    app: AppConfig