import logging
import os
import json
from configs import (
    DeployCredentials,
    AppConfig,
    RunConfig
)
from cognite.client import CogniteClient
from setup_logging import configure_logging
from yaml import safe_load  # type: ignore

configure_logging()
logger = logging.getLogger(__name__)

def create_app_file(config: AppConfig) -> None:
    # current directory
    
    current_dir = os.getcwd()
    files = []
    for root, _, filenames in os.walk(config.folder):
        for filename in filenames:
            if filename.endswith(".py"):
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, start=config.folder)
                files.append(relative_path)
    app_obj = {}
    
    # Read requirements.txt and put into 'requirements'
    with open(os.path.join(config.folder, "requirements.txt"), "r") as fh:
        app_obj["requirements"] = fh.read().splitlines()
    app_obj['entrypoint'] = config.entrypoint
    app_obj['files'] = {}
    for file in files:
        with open(os.path.join(config.folder, file), "r") as fh:
            content = fh.read()
        app_obj['files'][file] = {
            "content": {
                "$case": "text",
                "text": content
            }
        }
    
    return app_obj

def upload_app_file(config: AppConfig, app_obj, deploy_client: CogniteClient):
    data_set_id = None
    
    metadata = {
        'name': config.name,
        'description': config.description,
        'creator': config.creator,
        'published': config.published,
        'version': config.version
    }

    app_obj_json_string = json.dumps(app_obj)
    
    # The requirements for a Streamlit app is
    # external id starts with `stapp-`
    # file name is the external id + `-source.json`
    # directory is `/streamlit-apps/`

    external_id = "stapp-"+config.external_id
    file_name = config.external_id + "-source.json"
    directory = '/streamlit-apps/'

    response = deploy_client.files.upload_bytes(
        content=app_obj_json_string, 
        external_id=external_id,
        directory=directory,
        name=file_name, 
        metadata=metadata,
        overwrite=True,
        data_set_id=data_set_id)
    return response.external_id

def main(config: RunConfig) -> None:
    deploy_client = config.deploy_creds.client
    app_obj = create_app_file(config.app)
    external_id = upload_app_file(config.app, app_obj, deploy_client)
    
    # Return output parameter:
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            print(f"app_external_id={external_id}", file=fh)
    

if __name__ == "__main__":
    deploy_creds = DeployCredentials.from_envvars()

    config = RunConfig(
        deploy_creds=deploy_creds,
        app=AppConfig.from_file(),
    )
    
    main(config)