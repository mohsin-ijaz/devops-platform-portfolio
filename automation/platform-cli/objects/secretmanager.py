# Import the Secret Manager client library.
import os
import sys
import traceback

from google.cloud import secretmanager

env_config = {
    'preprod': {'project': '<GCP_PROJECT_PREPROD>', 'cluster': '<GCP_PROJECT_PREPROD>environment'},
    'production': {'project': '<GCP_PROJECT_PROD>', 'cluster': '<GCP_CLUSTER_NAME>'},
    'new_car': {'project': '<GCP_PROJECT_NEWCAR>', 'cluster': '<GCP_CLUSTER_NEWCAR>'}
}


class SecretManager(object):

    def __init__(self):

        print("ENVIRONMENT FOR POD %s" % os.environ.get('ENV_ICARCLI'))
        print("ENVIRONMENT FOR POD %s" % os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))
        os.system("gcloud config list")
        os.system("gcloud auth list")

        if os.environ.get('ENV_ICARCLI', '') == "development":
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] \
                = "<LOCAL_KEYFILE_PATH>"
        else:
            if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '') != "":
                del os.environ['GOOGLE_APPLICATION_CREDENTIALS']

        # if os.environ.get('ENV_ICARCLI', '') == "production":
        #     print("Force account")
        #     os.system("gcloud auth login <CI_SERVICE_ACCOUNT>@<GCP_PROJECT_PREPROD>.iam.gserviceaccount.com")
        #     # os.system("gcloud config set project <GCP_PROJECT_PREPROD>"
        #
        # print("After Changes---------------------------------")
        # print("ENVIRONMENT FOR POD %s" % os.environ.get('ENV_ICARCLI'))
        # print("ENVIRONMENT FOR POD %s" % os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))
        # os.system("gcloud config list")
        # os.system("gcloud auth login")

        # Create the Secret Manager client.
        try:
            self.client = secretmanager.SecretManagerServiceClient()
        except:
            self.client = None
            print("Secret Manager Client Creation Failed")

    def update_secrets(self):

        app_path = ""
        if os.environ.get('ENV_ICARCLI', '') == "production":
            app_path = "/app/"
        else:
            return

        if self.client is None:
            return

        for env_name, env in env_config.items():
            project_id = env_config.get(env_name, {}).get('project', '')
            jenkins_secret = f"nano-{env_name}-jenkins"
            secret_name = f"projects/{project_id}/secrets/{jenkins_secret}/versions/latest"
            try:
                response = self.client.access_secret_version(name=secret_name)
                secret_key = response.payload.data.decode("UTF-8")

                key_file = f"{app_path}project/dockers-beta/config/keys/{env_name}-service-account.json"
                fd = os.open(key_file, os.O_CREAT | os.O_RDWR)
                os.write(fd, bytearray(secret_key, "utf-8"))

                print(f"Secret Key [{secret_name}] Written Successfully")

            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print('log', "%s %s %s %s" % (str(e), exc_type, fname, exc_tb.tb_lineno), "error", True)
                traceback.print_tb(e.__traceback__)
