import gogs_client
import environment as env
from json import loads
from base64 import b64encode


        
def push_pv_to_git(yaml, pv_file_name, FILE_PATH = env.PV_FILE_PATH, REPO_NAME = env.REPO_NAME):
    gogs_token = gogs_client.Token(env.GITEA_TOKEN)
    api = gogs_client.GogsApi(env.GITEA_API_URL)
    _path = f"/repos/{env.REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}/{pv_file_name}?ref=main"
    _body = {
        "content": b64encode(yaml.encode("utf-8")).decode("utf-8"),
        "message": f"Add {pv_file_name}",
        "branch": "main",  
    }
    content = api.post(path = _path, auth = gogs_token, data = _body)
    return loads(content.text)
        
    