import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import platform
from subprocess import PIPE

from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from objects import registry
from objects.profiler import profile


class BuildController(ICarBaseController):
    projects = {
        'preprod': '<GCP_PROJECT_PREPROD>',
        'stag0': '<GCP_PROJECT_PREPROD>',
        'stag1': '<GCP_PROJECT_PREPROD>',
        'stag2': '<GCP_PROJECT_PREPROD>',
        'stag3': '<GCP_PROJECT_PREPROD>',
        'stag4': '<GCP_PROJECT_PREPROD>',
        'stag5': '<GCP_PROJECT_PREPROD>',
        'staging': '<GCP_PROJECT_PREPROD>',
        'qa': '<GCP_PROJECT_PREPROD>',
        'production': '<GCP_PROJECT_PROD>',
        'new-car': '<GCP_PROJECT_NEWCAR>'
    }

    # Number is the numer of images to keep, i.e. last 5 images for preprod and last 10 images for new-car
    clean_registry = {
        '<GCP_PROJECT_PREPROD>': 5,
        'new-car': 10,
        '<GCP_PROJECT_PROD>': 20
    }

    default_clusters = {
        'preprod': '<GCP_CLUSTER_PREPROD>',
        'stag0': '<GCP_CLUSTER_PREPROD>',
        'stag1': '<GCP_CLUSTER_PREPROD>',
        'stag2': '<GCP_CLUSTER_PREPROD>',
        'stag3': '<GCP_CLUSTER_PREPROD>',
        'stag4': '<GCP_CLUSTER_PREPROD>',
        'stag5': '<GCP_CLUSTER_PREPROD>',
        'staging': '<GCP_CLUSTER_PREPROD>',
        'production': '<GCP_CLUSTER_NAME>',
        'new-car': '<GCP_CLUSTER_NEWCAR>'
    }

    required = {
        'image': ['directory', 'name'],
        'project': ['directory', 'branch'],
        'deploy': ['directory'],
        'test': []
    }

    scope = "cluster"

    class Meta:
        label = 'build'
        description = 'Build docker images'
        arguments = [
            (['-a', '--artifacts'], dict(help="Build with artifacts - TRUE|FALSE, default FALSE")),
            (['-b', '--branch'], dict(help="Code branch name, default master")),
            (['-d', '--directory'], dict(help="Project directory")),
            (['-dt', '--deployment-type'], dict(help="Canary or anyother")),
            (['-f', '--file'], dict(help="Docker file name, default Dockerfile")),
            (['-i', '--image'], dict(help="Used for base images, default empty")),
            (['-n', '--name'], dict(help="Name of the build image")),
            (['-r', '--repo'], dict(help="Repository, default <GCP_PROJECT>")),
            (['-t', '--tag'], dict(help="Tag of the build image, default latest")),
            (['-bv', '--build-version'], dict(help="Specify build version")),
            (['-sdp', '--sub-deployment-postfix'], dict(help="Sub deployment postfix")),
            (['-fmd', '--force-main-deployment'], dict(help="Force main deployment, even though its a sub deployment")),
            (['-uld', '--use-local-directory'],
             dict(help="If true it will use local directory and not checkout new code - TRUE|FALSE, default FALSE"))
        ]
        usage = 'icarcli build <service_name> [options ...]'
        epilog = 'Build container steps'

    @profile
    @command
    @expose(help="Testing")
    def test(self):

        # environment = self._get_env()
        # project = self.projects.get(environment)
        # arguments = str(self.app.pargs)

        new_relic_app = "test"
        tag = "tag"
        mark_command = """curl -X POST 'https://api.newrelic.com/v2/applications/%s/deployments.json' -H 'X-Api-Key:<NEWRELIC_API_KEY>' -i -H 'Content-Type: application/json' -d  '{
                                           \"deployment\": {
                                           \"revision\": \"%s\",
                                           \"user\": \"Deployment script\"
                                         }
                                        }'""" % (new_relic_app, tag)

        echo(mark_command)
        # self._send_message("", "Testing %s" % arguments, 'success')

    '''
        # OLD vs NEW arguments
        ENVIRONMENT = ENVIRONMENT
        PROJECT     = DIRECTORY
        FILE        = FILE
        -           = GCP-PROJECT
        NAME        = NAME
        TAG         = TAG
    '''

    @profile
    @command
    @expose(help="Build base images, from base-images folder")
    def image(self):
        base_image_directory = os.path.join(registry.dockers_dir, "base-images")

        environment = self._get_env()
        project = self.projects.get(environment)
        directory = self._set_lower(self.app.pargs.directory)
        docker_file = self._set_default(self._set_lower(self.app.pargs.file), 'Dockerfile').capitalize()
        name = self._set_lower(self.app.pargs.name)
        tag = self._set_default(self._set_lower(self.app.pargs.tag), 'latest')
        platform_arch = ""

        # Sending notification to slack
        # log_message = 'Starting build image with following params: Project: %s, Environment: %s, Directory: %s,
        # File: %s, Name: %s, Tag: %s' % (project, environment, directory, docker_file, name, tag)
        log_message = 'Starting image build'
        self._send_message(directory, log_message, 'success')

        image_directory = os.path.join(base_image_directory, directory)
        if not os.path.exists(image_directory):
            self._on_process_end("Failed to find project %s" % image_directory)

        env_docker_file = docker_file + "-" + environment
        env_docker_file_path = os.path.join(image_directory, env_docker_file)
        if os.path.isfile(env_docker_file_path):
            docker_file = env_docker_file

        docker_file_path = os.path.join(image_directory, docker_file)
        if not os.path.isfile(docker_file_path):
            self._on_process_end("Failed to find docker file %s" % docker_file_path)

        # Check dependencies i.e. gcloud and docker
        self._check_dependencies('gcloud')
        self._check_dependencies('docker')

        print("")
        print("Project: %s, Env: %s, Dir: %s, File: %s, Name: %s, Tag: %s" % (
            project, environment, directory, docker_file, name, tag))

        os.chdir(image_directory)

        # To get image from respective project repo
        self._replace_in_file(docker_file, '<GCP_PROJECT_PREPROD>', project)
        # if project == "<GCP_PROJECT_PREPROD>":
        self._replace_in_file(docker_file, "asia.gcr.io", "asia-docker.pkg.dev")

        # To detect ARM64 based CPU
        if "arm64" in platform.version().lower():
            platform_arch = "--platform=linux/amd64"

        build_command = "docker build %s -f %s --build-arg ENVIRONMENT=%s -t <GCP_PROJECT>/%s:%s ." % (
            platform_arch ,docker_file, environment, name, tag)
        print(build_command)
        build_command_call = os.system(build_command)
        if build_command_call != 0:
            self._on_process_end("Failed to build image %s" % build_command)

        # Revert project repo
        self._replace_in_file(docker_file, project, '<GCP_PROJECT_PREPROD>')
        # if project == "<GCP_PROJECT_PREPROD>":
        self._replace_in_file(docker_file, "asia-docker.pkg.dev", "asia.gcr.io")
        self._push(project, name, tag)

        # If here everything works well
        self._send_message("", "SUCCESS! Image has been built successfully.", "success")

    '''
        # OLD vs NEW arguments
        ARTIFACTS           = ARTIFACTS
        BRANCH              = BRANCH
        BUILD               = -
        SUBDIRECTORY        = -
        LABEL               = -
        PROJECT             = DIRECTORY
        CONFIG_FILE         = -
        USE_GCP_CONFIG_FILE = -
        IMAGE               = -
        KEEP_GIT            = -
        NAME                = -
        FRONTEND            = -
        TAG                 = TAG
        NEW_BUILD_DIRECTORY = -
        LOCAL               = USE-LOCAL-DIRECTORY
    '''

    @profile
    @command
    @expose(help="Build project images from project directory - i.e. ubp, lapi")
    def project(self):

        print(self.app.pargs)

        environment = self._get_env()
        project = self.projects.get(environment)

        # Build version
        build_version = self._set_lower(self.app.pargs.build_version)

        # Mandatory arguments
        directory = self._set_lower(self.app.pargs.directory)
        branch = self._set_default(self.app.pargs.branch, 'master')

        # Project directory & config validation
        build_directory = os.path.join(registry.dockers_dir, 'project')
        docker_directory = os.path.join(build_directory, 'dockers-beta')

        project_directory = os.path.join(build_directory, directory)
        if not os.path.exists(project_directory):
            self._on_process_end("Failed to find project %s" % project_directory)

        # Load configuration file
        config_file = os.path.join(project_directory, 'config', 'config.json')
        config = self._load_config(config_file)

        # Optional parameters
        artifacts = self._set_default(self._set_lower(self.app.pargs.artifacts), 'false')
        tag = self._set_default(self._set_lower(self.app.pargs.tag), '')
        use_local_directory = self._set_default(self.app.pargs.use_local_directory, '')

        # input_str = 'Starting build project with following params: Project: %s, Environment: %s, Artifacts: %s,
        # Branch: %s, HasBuildStage: %s, SubDirectoryOnly: %s, Unique: %s, Directory: %s, File: %s, GCPConfig; %s,
        # Image: %s, KeepGit: %s, Name: %s, SubDirectories: %s, Tag: %s, Local: %s' % (project, environment,
        # artifacts, branch, config.get('build'), config.get('copy_sub_directory'), config.get('unique'), directory,
        # config.get('file'), config.get('gcp_config_file'), config.get('image'), config.get('keep_git'),
        # config.get('name'), config.get('sub_directories'), tag, use_local_directory)
        input_str = 'Starting project build'

        self._send_message(directory, input_str, 'success')

        # Check dependencies
        self._check_dependencies('gcloud')
        self._check_dependencies('docker')
        self._check_dependencies('kubectl', '')

        unique_directory = directory
        if config.get('unique') == "true":
            unique_directory = uuid.uuid4().hex[:20]

        code_build_directory = os.path.join('code', unique_directory)
        temp_build_directory = os.path.join(registry.data_dir, code_build_directory)
        composer_directory = os.path.join(registry.data_dir, 'composer')

        # On any error after this point we should make sure we remove temp_build_directory to clean
        os.system("mkdir -p %s" % temp_build_directory)
        os.system("mkdir -p %s" % composer_directory)

        if use_local_directory != "":
            print("Using local directory %s" % use_local_directory)
            if not os.path.exists(use_local_directory):
                self._on_process_end("Local directory argument must be a valid directory %s" % use_local_directory)

            os.system("cp -Rf %s %s" % (use_local_directory, temp_build_directory))
        else:
            print("Cloning repository %s" % config.get('repository'))
            os.system("mkdir -p ~/.ssh")
            os.system("ssh-keyscan -t rsa bitbucket.org >> ~/.ssh/known_hosts")

            # Check if reference repo exists, reference makes cloning a bit faster
            repository_directory = os.path.join(registry.data_dir, "git", directory, config.get('repository_directory'))

            repository_reference_path = ""
            if os.path.exists(repository_directory):
                print("repostory_directory" + repository_directory)
                repository_reference_path = " --reference " + repository_directory

            print("repostory_directory" + repository_directory)
            repo_source = self._set_lower(self.app.pargs.repo)
            ssh_key = os.path.join(docker_directory, 'config', 'keys', 'id_rsa')

            # If repo is other than <GCP_PROJECT>, change ssh key (i.e. for new-car it is tenflares)
            if repo_source is not None:
                env_ssh_key = os.path.join(docker_directory, 'config', 'keys', repo_source, 'id_rsa')

                echo("Env SSH Key: " + env_ssh_key, "green")
                if os.path.isfile(env_ssh_key):
                    ssh_key = env_ssh_key

            os.system("chmod 400 " + ssh_key)
            echo("SSH key:" + ssh_key, "green")
            clone_command = "ssh-agent bash -c 'ssh-add " + ssh_key + '; git clone ' + repository_reference_path + ' --single-branch -b ' + branch + ' ' + config.get(
                'repository') + ' ' + temp_build_directory + '/; git -C "' + temp_build_directory + '/" pull origin ' + branch + ";" + \
                            "export PD=`pwd`; cd " + temp_build_directory + "; git submodule update --init --recursive; cd $PD';"

            # WSL - Windows Subsystem Linux, uncomment this command instead of normal one
            # clone_command = "sudo ssh-agent bash -c 'ssh-add " + ssh_key + '; git clone --recurse-submodules -j8 ' + repository_reference_path + ' --single-branch -b ' + branch + ' ' + config.get(
            #     'repository') + ' ' + temp_build_directory + '/; git -C "' + temp_build_directory + '/" pull origin ' + branch + "' && sudo chmod -R 777 " + temp_build_directory

            echo(clone_command, "green")
            clone_command_call = subprocess.run(clone_command, shell=True, stdout=PIPE, stderr=PIPE)
            registry.profiler.record("ssh-agent", "clone")

            if clone_command_call.returncode != 0:
                echo(clone_command_call.stderr.decode('utf-8'), 'green')
                error_message = "Failed to clone repository %s, attempt retry" % config.get('repository')
                echo(error_message, "red")

                echo("Retry the command %s" % clone_command, "yellow")
                clone_command_call = subprocess.run(clone_command, shell=True, stdout=PIPE, stderr=PIPE)
                registry.profiler.record("ssh-agent-retry", "clone")

                if clone_command_call.returncode != 0:
                    echo(clone_command_call.stderr.decode('utf-8'), 'green')
                    error_message = "Failed to clone repository %s" % config.get('repository')
                    self._send_message(directory, error_message, 'error')
                    self._on_process_end(error_message,
                                         del_directory=temp_build_directory)

            echo(clone_command_call.stdout.decode('utf-8'), 'green')

        # All checks done, code cloned... Start building project image from here
        branch_slug = self._slugify(branch)

        name_postfix = "-" + environment
        build_with_compose = ""
        if (environment == 'production') or (environment == 'new-car'):
            name_postfix = ""
            build_with_compose = " --no-dev "

        if tag == '':
            tag = branch_slug

        image_name = config.get('name') + name_postfix
        final_build_name = image_name + '_' + branch_slug
        build_name = 'build_' + final_build_name

        # If project needs build step
        if config.get('build') == 'true':

            build_file = os.path.join(project_directory, 'Dockerfile-Build')
            if not os.path.isfile(build_file):
                self._on_process_end("Failed to find Build Docker file in project %s" % build_file,
                                     del_directory=temp_build_directory)

            self._send_message(directory, 'Starting to build image - %s' % image_name, 'success')

            os.chdir(project_directory)

            # To get image from respective project repo
            self._replace_in_file(build_file, '<GCP_PROJECT_PREPROD>', project)
            # if project == "<GCP_PROJECT_PREPROD>":
            self._replace_in_file(build_file, "asia.gcr.io", "asia-docker.pkg.dev")

            docker_build_command = "docker build -f Dockerfile-Build " \
                                   + ' --build-arg BUILD_COMPOSE_ENV="' + build_with_compose + '"' \
                                   + ' --build-arg ENVIRONMENT="' + environment + '"' \
                                   + ' -t <GCP_PROJECT>/' + build_name + ' .'

            echo(docker_build_command, "green")
            docker_build_command_call = subprocess.run(docker_build_command, shell=True, stdout=PIPE, stderr=PIPE)
            registry.profiler.record("docker-build", build_name)

            # Revert File changes to docker build
            self._replace_in_file(build_file, project, '<GCP_PROJECT_PREPROD>')
            # if project == "<GCP_PROJECT_PREPROD>":
            self._replace_in_file(build_file, "asia-docker.pkg.dev", "asia.gcr.io")
            if docker_build_command_call.returncode != 0:
                echo(docker_build_command_call.stderr.decode('utf-8'), 'red')
                self._on_process_end("Failed to build docker image %s" % build_name, del_directory=temp_build_directory)

            echo(docker_build_command_call.stdout.decode('utf-8'), 'green')

            # Create a temporary file
            # Each docker build entrypoint script MUST signal job finish (by removing this file) just before
            # finishing script
            temp_file_path = os.path.join(temp_build_directory, 'entrypointscript')
            open(temp_file_path, 'w')

            # Check if build with same name exited previously but container is still there
            check_build_running_command = 'docker ps -aq -f status=exited -f name="' + build_name + '"'
            echo(check_build_running_command, "green")
            check_build_running_command_call = subprocess.run(check_build_running_command, shell=True, stdout=PIPE, stderr=PIPE)
            registry.profiler.record("docker-ps", "exited")

            if (check_build_running_command_call.returncode == 0) and (check_build_running_command_call.stdout.decode('utf-8') != ''):
                echo("Build container already with same name %s running... Removing it" % build_name, "green")
                os.system('docker rm ' + build_name + ' -f')
                registry.profiler.record("docker-rm", "old:" + build_name)

            # Wait for the build to finish
            while True:
                check_build_running_command = 'docker ps -q -f status=running -f name="' + build_name + '"'
                echo(check_build_running_command, "green")
                check_build_running_command_call = subprocess.run(check_build_running_command, shell=True, stdout=PIPE, stderr=PIPE)

                if (check_build_running_command_call.returncode == 0) and (check_build_running_command_call.stdout.decode('utf-8') == ''):
                    break

                echo("Waiting for build to finish ... %s" % build_name, "green")
                echo("Sleeping for 30 seconds", "green")
                time.sleep(30)

            docker_run_command = "docker run --name " + build_name + " -d " \
                                 + ' -v ' + temp_build_directory + ':/var/www/' + config.get('web_directory') \
                                 + ' -v ' + composer_directory + ':/tmp/composer' \
                                 + ' <GCP_PROJECT>/' + build_name

            echo(docker_run_command, "green")
            docker_run_command_call = subprocess.run(docker_run_command, shell=True, stdout=PIPE, stderr=PIPE)
            registry.profiler.record("docker-run", build_name)

            if docker_run_command_call.returncode != 0:
                echo(docker_run_command_call.stderr.decode('utf-8'), 'red')
                self._on_process_end("Failed to run docker image %s" % build_name, del_directory=temp_build_directory)

            echo(docker_run_command_call.stdout.decode('utf-8'), 'green')
            echo('Waiting for docker to finish all tasks', 'green')

            # Wait for the run to finish, i.e. composer update
            while True:

                if not os.path.isfile(temp_file_path):
                    echo("Docker build finished", "green")
                    os.system("docker logs " + build_name)
                    break

                check_build_exited_command = 'docker ps -aq -f status=exited -f name="' + build_name + '"'
                echo(check_build_exited_command, "green")
                check_build_exited_command_call = subprocess.run(check_build_exited_command, shell=True, stdout=PIPE, stderr=PIPE)
                ps_id = check_build_exited_command_call.stdout.decode('utf-8')
                if (check_build_exited_command_call.returncode == 0) and (ps_id != ''):
                    echo(check_build_exited_command_call.stderr.decode('utf-8'), "red")

                    log_command = 'docker logs ' + ps_id
                    echo(log_command, "green")
                    log_command_call = subprocess.run(log_command, shell=True, stdout=PIPE, stderr=PIPE)
                    echo(log_command_call.stdout.decode('utf-8'), "green")
                    echo(log_command_call.stderr.decode('utf-8'), "red")

                    self._on_process_end("Abnormal run termination for the build %s" % build_name,
                                         del_directory=temp_build_directory)

                echo("Waiting for build to finish ... %s" % build_name, "green")
                echo("Sleeping for 30 seconds", "green")
                time.sleep(30)

            registry.profiler.record("docker-run-exit", build_name)

        echo('Docker build file process finished', 'green')

        echo('Checking artifacts: ' + artifacts, 'green')
        if artifacts != 'false':
            echo('Making artifacts', 'green')
            os.system('mkdir -p ' + artifacts)
            os.system("cp -Rf %s %s" % (temp_build_directory, artifacts))

        registry.profiler.record("make-artifacts", artifacts)

        # @todo: In testing
        new_hash = uuid.uuid4().hex[:20]
        unique_project_directory = os.path.join(project_directory, new_hash)
        # @todo: Have to make it easier to read - sorry about this, jenkins breaking
        os.system("cp -Rf %s %s/../%s" % (project_directory, project_directory, new_hash))
        os.system("cp -Rf %s/../%s %s" % (project_directory, new_hash, unique_project_directory))
        project_build_directory = os.path.join(unique_project_directory, 'code', directory)

        # project_build_directory = os.path.join(project_directory, 'code', unique_directory)
        echo("Moving directory %s to %s" % (temp_build_directory, project_build_directory), "green")
        shutil.move(temp_build_directory, project_build_directory)
        registry.profiler.record("move-to-build-directory", project_build_directory)

        os.chdir(project_build_directory)
        echo('Checking if have to remove git files', 'green')
        if config.get('keep_git') == 'false':
            echo("Removing git files & folders from code directory", "green")
            os.system(
                '( find . -type d -name ".git" && find . -name ".gitignore" && find . -name ".gitmodules" ) '
                '| xargs rm -rf')
            registry.profiler.record("remove-git", "git-modules")

        echo("Changing directory to project: %s" % unique_project_directory, "green")
        os.chdir(unique_project_directory)

        gcp_copy_argument = ""
        echo('Checking if have to copy gcp config files', 'green')
        if config.get('gcp_config_file') == 'true':
            echo('Copying gcp config files', 'green')
            gcp_config_file = 'gcp_cloud_configuration.json'
            gcp_config_file_path = os.path.join(unique_project_directory, 'config',
                                                environment + '_gcp_cloud_configuration.json')
            if os.path.isfile(gcp_config_file_path):
                gcp_config_file = environment + '_gcp_cloud_configuration.json'

            gcp_copy_argument = " --build-arg GCP_CONFIG_FILE=" + gcp_config_file

        echo("GCP Config file argument: %s" % gcp_copy_argument, "green")

        code_directory = os.path.join("code", directory)
        # code_directory = os.path.join("code", unique_directory)
        if config.get('copy_sub_directory') != "":
            code_directory = os.path.join(code_directory, config.get('copy_sub_directory'))

        build_arguments = ' --build-arg FOLDER_PATH="./' + code_directory + '"' + gcp_copy_argument + \
                          ' --build-arg ENVIRONMENT=' + environment

        docker_file = os.path.join(unique_project_directory, config.get('file'))
        if not os.path.isfile(docker_file):
            self._on_process_end("Failed to find Docker file in project %s" % docker_file)

        # To get base image from respective project repo
        self._replace_in_file(docker_file, '<GCP_PROJECT_PREPROD>', project)
        # if project == "<GCP_PROJECT_PREPROD>":
        self._replace_in_file(docker_file, "asia.gcr.io", "asia-docker.pkg.dev")

        print(os.getcwd())

        build_script_dev = os.path.join(os.getcwd(), "../build_script-dev.sh")
        build_script_prod = os.path.join(os.getcwd(), "../build_script-prod.sh")
        # print(build_script_dev)
        # print(build_script_prod)

        # print(build_version)

        if build_version is not None:
            if os.path.exists(build_script_dev) and environment != 'production':
                echo("BUILD_SCRIP-DEV EXISTS & BUILD VERSION IS SPECIFY. EXECUTING BUILD_SCRIPT-DEV", "green")

                build_script_args = build_version

                if (build_script_args is None):
                    build_script_args = ''

                print('Build version: ', build_script_args)
                run_build_script_command = build_script_dev + " " + build_script_args
                echo(run_build_script_command, "green")
                run_build_script_command_call = subprocess.call(run_build_script_command, shell=True)
                print(run_build_script_command_call)
                if run_build_script_command_call != 0:
                    echo("RUNNING BUILD_SCRIPT-DEV FAILED, DID YOU SPECIFY CORRECT VERSION ?", 'yellow')
                    self._on_process_end("build_script-dev.sh return an ERROR")
                    
            if os.path.exists(build_script_prod) and environment == 'production':
                echo("BUILD_SCRIP-DEV EXISTS & BUILD VERSION IS SPECIFY. EXECUTING BUILD_SCRIPT-PROD", "green")

                build_script_args = build_version

                if (build_script_args is None):
                    build_script_args = ''

                print('Build version: ', build_script_args)
                run_build_script_command = build_script_prod + " " + build_script_args
                echo(run_build_script_command, "green")
                run_build_script_command_call = subprocess.call(run_build_script_command, shell=True)
                print(run_build_script_command_call)
                if run_build_script_command_call != 0:
                    echo("RUNNING BUILD_SCRIPT-PROD FAILED, DID YOU SPECIFY CORRECT VERSION ?", 'yellow')
                    self._on_process_end("build_script-prod.sh return an ERROR")

        if config.get('buildkit', None) is None:
            # normal build
            print('location: ',os.getcwd())
            docker_build_command = "docker build -f " + config.get(
                'file') + build_arguments + ' -t <GCP_PROJECT>/' + final_build_name + ' .'
        else:
            docker_build_command = "DOCKER_BUILDKIT=1 docker build -f " + config.get(
                'file') + build_arguments + ' -t <GCP_PROJECT>/' + final_build_name + ' .'
        echo(docker_build_command, "green")
        docker_build_command_call = subprocess.run(docker_build_command, shell=True, stdout=PIPE, stderr=PIPE)
        registry.profiler.record("docker-build", final_build_name)

        # Reverse the change
        self._replace_in_file(docker_file, project, '<GCP_PROJECT_PREPROD>')
        # if project == "<GCP_PROJECT_PREPROD>":
        self._replace_in_file(docker_file, "asia-docker.pkg.dev", "asia.gcr.io")

        if docker_build_command_call.returncode != 0:
            echo(docker_build_command_call.stdout.decode('utf-8'), 'green')
            echo(docker_build_command_call.stderr.decode('utf-8'), 'yellow')
            self._on_process_end("Failed to build docker image %s" % build_name, del_directory=unique_project_directory)

        echo(docker_build_command_call.stdout.decode('utf-8'), 'green')
        echo('Waiting for docker to finish all tasks', 'green')

        self._push(project, image_name, tag, final_build_name, True)

        # Get Push Latest Version Map
        push_to_latest_tag = config.get('push_to_latest_tag', {})
        if push_to_latest_tag.get(directory, None) is not None:
            self._push(project, image_name, 'latest', final_build_name, True)

        # @todo: Need to remove default sub_directories from projects' config, as not I have set the default value here
        sub_directories = config.get('sub_directories', [])

        if config.get('copy_env', None) is None:
            # Pass tmp environment as all our dev environments have single nginx config file
            if (environment == "production") or (environment == "new-car"):
                tmp_env = "production"
            else:
                tmp_env = "preprod"
        else:
            # copy nginx from environment specific folder
            if (environment == "production") or (environment == "new-car"):
                tmp_env = "production"
            else:
                tmp_env = environment

        build_arguments = ' --build-arg FOLDER_PATH="./' + code_directory + '"' + gcp_copy_argument + \
                          ' --build-arg ENVIRONMENT=' + tmp_env + ' --build-arg ARTIFACTS=<GCP_PROJECT>/' + final_build_name

        # Build images for sub directories
        sub_directories_commands = {}
        sub_directories_image_push = {}
        for sub_directory in sub_directories:
            sub_docker_file = os.path.join(unique_project_directory, sub_directory, config.get('file'))
            if not os.path.isfile(sub_docker_file):
                self._send_message(directory, "Failed to find docker file at %s" % sub_docker_file, 'error')
                continue

            sub_image_name = "<GCP_PROJECT>/%s_%s" % (final_build_name, sub_directory)
            # sub_registry_target = "asia.gcr.io/%s/<GCP_PROJECT>/%s_%s:%s" % (project, image_name, dir, tag)

            # To get image from respective project repo
            self._replace_in_file(sub_docker_file, '<GCP_PROJECT_PREPROD>', project)
            # if project == "<GCP_PROJECT_PREPROD>":
            self._replace_in_file(sub_docker_file, "asia.gcr.io", "asia-docker.pkg.dev")

            docker_sub = os.path.join(sub_directory, config.get('file'))
            docker_build_command = "docker build -f " + docker_sub + build_arguments + ' -t ' + sub_image_name + ' .'
            echo(docker_build_command, "green")
            docker_build_command_call = subprocess.Popen(docker_build_command, shell=True)
            sub_directories_commands[sub_image_name] = {
                'command': docker_build_command_call,
                'docker_file_project_replace': {
                    'sub_docker_file': sub_docker_file,
                    'project': project,
                    'new_project': '<GCP_PROJECT_PREPROD>',
                }
            }
            sub_directories_image_push[sub_image_name] = {
                'project': project,
                'image_name': "%s_%s" % (image_name, sub_directory),
                'tag': tag,
                'special_image_name': "%s_%s" % (final_build_name, sub_directory),
                'push_to_latest_tag': push_to_latest_tag,
                'sub_directory': sub_directory

            }

            # registry.profiler.record("docker-build", sub_image_name)

            # Revert back to default
            # self._replace_in_file(sub_docker_file, project, '<GCP_PROJECT_PREPROD>')

            # echo(docker_build_command_call.stdout.decode('utf-8'), 'green')

            # if docker_build_command_call.returncode != 0:
            #     echo(docker_build_command_call.stderr.decode('utf-8'), 'red')
            #     self._on_process_end("Failed to build sub directory docker image %s" % sub_image_name,
            #                          del_directory=unique_project_directory)

            # i_name = "%s_%s" % (image_name, sub_directory)
            # s_name = "%s_%s" % (final_build_name, sub_directory)
            # self._push(project, i_name, tag, s_name, clean=True)
            #
            # if push_to_latest_tag.get(sub_directory, None) is not None:
            #     self._push(project, i_name, 'latest', s_name, clean=True)

        while True:
            for sub_image_name, sd_command in sub_directories_commands.copy().items():
                time.sleep(1)
                status = sd_command.get('command').poll()
                if status is None:
                    continue
                if status == 0:
                    #############
                    df_pr = sd_command.get('docker_file_project_replace')
                    self._replace_in_file(df_pr.get('sub_docker_file'), df_pr.get('project'), df_pr.get('new_project'))

                    # img_push = sd_command.get('image_push')
                    # self._push(img_push.get('project'), img_push.get('image_name'), img_push.get('tag'),
                    #            img_push.get('special_image_name'), clean=True)
                    #
                    # if img_push.get('push_to_latest_tag').get(img_push.get('sub_directory'), None) is not None:
                    #     self._push(img_push.get('project'), img_push.get('image_name'), 'latest',
                    #                img_push.get('special_image_name'), clean=True)
                    #############
                    sub_directories_commands.pop(sub_image_name)
                if status != 0:
                    echo(docker_build_command_call.stderr.decode('utf-8'), 'red')
                    self._on_process_end("Failed to build sub directory docker image %s" % sub_image_name,
                                         del_directory=unique_project_directory)
            if len(sub_directories_commands) <= 0:
                break

        for sub_image_name, img_push in sub_directories_image_push.copy().items():
            self._push(img_push.get('project'), img_push.get('image_name'), img_push.get('tag'),
                       img_push.get('special_image_name'), clean=True)

            if img_push.get('push_to_latest_tag').get(img_push.get('sub_directory'), None) is not None:
                self._push(img_push.get('project'), img_push.get('image_name'), 'latest',
                           img_push.get('special_image_name'), clean=True)

        # If project needs build step
        if config.get('build') == 'true':
            os.system('docker rm %s -f' % build_name)
            os.system('docker rmi <GCP_PROJECT>/%s -f' % build_name)
            registry.profiler.record("docker-rm", build_name)

        if (unique_project_directory != '') and (os.path.exists(unique_project_directory)):
            echo("Deleting directory: " + unique_project_directory, 'green')
            shutil.rmtree(unique_project_directory)

        # If here everything works well
        self._send_message(directory, "SUCCESS! Project image has been built successfully!", 'success')
        self._on_process_end("SUCCESS! Project image has been built successfully.", 0, project_build_directory)

    @profile
    @command
    @expose(help="Deploy build for project director - i.e. ubp, lapi")
    def deploy(self):

        print(self.app.pargs)

        environment = self._get_env()
        project = self.projects.get(environment)

        # Mandatory argument
        directory = self._set_lower(self.app.pargs.directory)

        check_status = True if directory != "ubp" and directory != "accounts" and directory != "adhoc-scripts" and \
                               environment == "production" else False

        # Optional argument
        tag = self._set_default(self._set_lower(self.app.pargs.tag), '')
        branch = self._set_default(self.app.pargs.branch, 'master')
        deployment_type = self._set_default(self._set_lower(self.app.pargs.deployment_type), '')

        # Load configuration file
        config_file = os.path.join(registry.dockers_dir, 'project', directory, 'config', 'config.json')
        config = self._load_config(config_file)

        # input_str = 'Starting deploy project with following params: Project: %s, Environment: %s, Directory: %s,
        # Branch: %s, Name: %s, SubDirectories: %s, Tag: %s' % (project, environment, directory, branch,
        # config.get('name'), config.get('sub_directories'), tag)
        input_str = 'Deploying project'
        self._send_message(directory, input_str, 'success')

        # Check dependencies
        self._check_dependencies('kubectl', '')

        # All checks done, deploy code
        name_postfix = "-" + environment
        label = config.get('deployment_label')
        if label == "":
            label = environment + "-"

        if (environment == 'production') or (environment == 'new-car'):
            name_postfix = ""
            label = ""

            # For canary deployment pass prefix i.e. www1
            if deployment_type != "":
                label = deployment_type + "-"

        label = label + directory

        custom_label = config.get('custom_label', '')
        if custom_label != "":
            label = custom_label

        image_name = config.get('name') + name_postfix

        if tag == "":
            tag = self._slugify(branch)
            
            
        registry_target = "asia-docker.pkg.dev/%s/<GCP_PROJECT>/%s:%s" % (project, image_name, tag)

        sub_deployment_postfix = self.app.pargs.sub_deployment_postfix
        sub_deployments = config.get('sub_deployments')

        # Sub deployments are main deployments broken down into smaller deployments based on a parameter
        # which can be country or domain or label etc
        if sub_deployment_postfix is None or self.app.pargs.force_main_deployment == "true":
            sub_directories = config.get('sub_directories', [])
            skip_sub_directory = config.get('skip_sub_directory', {})
            # Deploy sub directories first
            sub_directory_registry_targets = {}
            for sub_directory in sub_directories:
                skip_environments = skip_sub_directory.get(sub_directory, [])
                if environment in skip_environments:
                    continue
                sub_label = label + '-' + sub_directory
                sub_registry_target = "asia-docker.pkg.dev/%s/<GCP_PROJECT>/%s_%s:%s" % ( project, image_name, sub_directory, tag)
                sub_directory_registry_targets[sub_directory] = sub_registry_target
                self._deploy(sub_label, sub_registry_target)

                # In case of nginx, check status
                # @todo: cleanup the nginx rule, its easy to miss this check
                self._patch(sub_label,
                            (True if check_status is False and environment == 'production' and sub_directory == 'nginx'
                             else check_status))

            deploy_extra = config.get('deploy_extra')

            if deploy_extra is not None:
                for deployment in deploy_extra:
                    sub_label = label + '-' + deployment
                    self._deploy(sub_label, registry_target)
                    self._patch(sub_label, check_status)

            # Deploy extras using sub images
            deploy_extra_sub = config.get('deploy_extra_sub')
            deploy_extra_sub_optional = config.get('deploy_extra_sub_optional')

            if deploy_extra_sub is not None:
                for deployment, sub_directory in deploy_extra_sub.items():
                    sub_label = label + '-' + deployment
                    sub_registry_target = sub_directory_registry_targets.get(sub_directory, "")
                    if sub_registry_target != "":
                        self._deploy(sub_label, sub_registry_target)
                        self._patch(sub_label, check_status)

            if deploy_extra_sub_optional is not None:
                for deployment, sub_directory in deploy_extra_sub_optional.items():
                    sub_label = label + '-' + deployment
                    sub_registry_target = sub_directory_registry_targets.get(sub_directory, "")
                    if sub_registry_target != "":
                        time.sleep(1)
                        get_pod_commmand = "kubectl get deploy %s" % sub_label
                        get_pod_commmand_call = subprocess.run(get_pod_commmand, shell=True, stdout=PIPE, stdin=PIPE)
                        if get_pod_commmand_call.returncode == 0:
                            self._deploy(sub_label, sub_registry_target)
                            self._patch(sub_label, check_status)
                        else:
                            echo(f"Skipped deploying {sub_label} as deployment not found.", "red")

            # If there are no sub deployments, then do the one deployment
            # deployment type only canary has
            if config.get('skip_main_deployment', None) == "true" and environment == "preprod":
                # added option for preprod environment to skip main deployment. In use by preprod lapi & preprod eapi
                pass
            else:
                if sub_deployments is None or self.app.pargs.force_main_deployment == "true" \
                        or (environment != "production" or deployment_type != ""):
                    self._deploy(label, registry_target)
                    self._patch(label, check_status)

            new_relic_apps = config.get('new_relic_apps')
            if (environment == 'production') and (new_relic_apps is not None):
                for new_relic_app in new_relic_apps:
                    mark_command = """curl -X POST 'https://api.newrelic.com/v2/applications/%s/deployments.json' -H 'X-Api-Key:<NEWRELIC_API_KEY>' -i -H 'Content-Type: application/json' -d  '{
                                                               \"deployment\": {
                                                               \"revision\": \"%s\",
                                                               \"user\": \"Deployment script\"
                                                             }
                                                            }'""" % (new_relic_app, tag)

                    mark_command_call = subprocess.run(mark_command, shell=True, stdout=PIPE, stderr=PIPE)
                    if mark_command_call.returncode == 0:
                        echo("Marked deployment in New Relic", 'green')
                    else:
                        echo(mark_command_call.stderr.decode('utf-8'), 'red')
        if sub_deployment_postfix is not None:
            if sub_deployment_postfix is not None and sub_deployment_postfix in sub_deployments:
                sub_deployment = '%s-%s' % (label, sub_deployment_postfix)
                self._deploy(sub_deployment, registry_target)
                self._patch(sub_deployment, check_status)
            else:
                self._on_process_end("FAILED! Invalid Sub Deployment postfix.")

        # If here everything works well
        self._send_message(directory, "SUCCESS! Deployment has been done.", 'success')
        self._on_process_end("SUCCESS! Deployment has been done.", 0)
    
    @profile
    @command
    @expose(help = "Display ")
    def trivy(self):
        print(self.app.pargs)

        environment = self._get_env()
        project = self.projects.get(environment)

        # Mandatory argument
        directory = self._set_lower(self.app.pargs.directory)

        # Optional argument
        tag = self._set_default(self._set_lower(self.app.pargs.tag), '')
        branch = self._set_default(self.app.pargs.branch, 'master')
        deployment_type = self._set_default(self._set_lower(self.app.pargs.deployment_type), '')

        # Load configuration file
        config_file = os.path.join(registry.dockers_dir, 'project', directory, 'config', 'config.json')
        config = self._load_config(config_file)

        # input_str = 'Starting deploy project with following params: Project: %s, Environment: %s, Directory: %s,
        # Branch: %s, Name: %s, SubDirectories: %s, Tag: %s' % (project, environment, directory, branch,
        # config.get('name'), config.get('sub_directories'), tag)
        input_str = 'Deploying project'
        self._send_message(directory, input_str, 'success')

        # Check dependencies
        self._check_dependencies('kubectl', '')

        # All checks done, deploy code
        name_postfix = "-" + environment
        label = config.get('deployment_label')
        if label == "":
            label = environment + "-"

        if (environment == 'production') or (environment == 'new-car'):
            name_postfix = ""
            label = ""

            # For canary deployment pass prefix i.e. www1
            if deployment_type != "":
                label = deployment_type + "-"

        label = label + directory

        custom_label = config.get('custom_label', '')
        if custom_label != "":
            label = custom_label

        image_name = config.get('name') + name_postfix

        if tag == "":
            tag = self._slugify(branch)

        registry_target = "asia-docker.pkg.dev/%s/<GCP_PROJECT>/%s:%s" % (project, image_name, tag)
        reg_value = 'print("%s")' % (registry_target)
        file_path = "./image.py"

        with open(file_path, "w") as file:
            file.write(reg_value)

    @profile
    def _push(self, project, name, tag, special_tag_name="", clean=False):
        tag_name = "%s:%s" % (name, tag)
        registry_target = "asia-docker.pkg.dev/%s/<GCP_PROJECT>/%s" % (project, tag_name)

        # if (clean == True) and project in self.clean_registry:
            # self._clean("asia-docker.pkg.dev/%s/<GCP_PROJECT>/%s" % (project, name), self.clean_registry.get(project))

        if special_tag_name != "":
            tag_name = special_tag_name

        tag_command = "docker tag <GCP_PROJECT>/%s %s" % (tag_name, registry_target)
        echo('Tagged: %s' % tag_command, 'green')

        tag_command_call = os.system(tag_command)
        if tag_command_call != 0:
            self._on_process_end("Failed to Tag image %s" % tag_command)

        push_command = "docker push %s" % registry_target
        push_command_call = subprocess.Popen(push_command, shell=True)

        # Check for push status
        # This is done to reduce time by running the commands in parallel
        while True:
            time.sleep(1)
            status_call = push_command_call.poll()

            if status_call is None:
                continue

            if status_call == 0:
                echo('Pushed: %s' % (push_command), 'green')
                break

            if status_call != 0:
                self._on_process_end("Failed to push image to repository %s" % (push_command))

    # @profile
    # def _clean(self, registry, keep=5):
    #     # return False
    #     echo("Cleaning registry: %s" % registry, 'green')
    #     echo("Keeping %d" % keep, 'green')
    #     if "asia.gcr.io" in registry:
    #     # do not delete images with develop & master tags as API team uses it with docker compose locally
    #         images_command = "gcloud container images list-tags %s --format='get(digest)' --filter='NOT tags:develop AND  NOT tags:master' " \
    #                         "--limit=unlimited" % registry
    #         images_command_call = subprocess.run(images_command, shell=True, stdout=PIPE, stderr=PIPE)
    #         if images_command_call.returncode == 0:
    #             response = images_command_call.stdout.decode('utf-8').splitlines()
    #             i = 0
    #             for digest in response:
    #                 i += 1
    #                 # Keep last keep images
    #                 if i <= keep:
    #                     continue
            #         command = "gcloud container images delete --quiet --force-delete-tags %s@%s" % (registry, digest)
            #         echo(command, 'green')
            #         os.system(command)
            # else:
            #     echo(images_command_call.stderr.decode('utf-8'), 'red')
        # Will use Artifacts Registry Cleanup policy in GCP
        # else:
        #     images_command_preprod = "gcloud artifacts docker images list %s --include-tags  --sort-by='~CREATE_TIME' --format='value(DIGEST)' --filter='NOT tags:develop AND  NOT tags:master AND  NOT tags:latest' " \
        #                     "--limit=unlimited" % (registry)
        #     images_command_preprod_call = subprocess.run(images_command_preprod, shell=True, stdout=PIPE, stderr=PIPE)
        #     if images_command_preprod_call.returncode == 0:
        #         response = images_command_preprod_call.stdout.decode('utf-8').splitlines()
        #         echo(response, 'yellow')
        #         i = 0
        #         for digest in response:
        #             i += 1
        #             # Keep last keep images
        #             if i <= keep:
        #                 continue

        #             command = "gcloud artifacts docker images delete --quiet --delete-tags %s@%s" % (registry, digest)
        #             echo(command, 'green')
        #             os.system(command)
        #     else:
        #         echo(images_command_preprod_call.stderr.decode('utf-8'), 'red')

    def _slugify(self, stri):
        return re.sub('[^0-9a-zA-Z]+', '_', stri).lower()

    @profile
    def _deploy(self, deployment, target):
        deploy_command = "kubectl set image deployment/" + deployment + ' ' + deployment + '=' + target
        echo("Deploying: " + deploy_command, "green")
        deploy_command_call = subprocess.run(deploy_command, shell=True, stdout=PIPE, stderr=PIPE)

        if deploy_command_call.returncode != 0:
            echo(deploy_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Deployment failed for %s" % deployment)

        echo(deploy_command_call.stdout.decode('utf-8'), "green")

    @profile
    def _patch(self, deployment, check_status):
        timestamp = int(time.time())
        patch_command = "kubectl patch deployment " + deployment + " -p '{\"spec\":{\"template\":{\"metadata\":{" \
                                                                   "\"labels\":{\"date\":\"%d\"}}}}}'" % timestamp
        echo("Applying patch for Deployment: " + patch_command, "green")
        patch_command_call = subprocess.run(patch_command, shell=True, stdout=PIPE, stderr=PIPE)

        if patch_command_call.returncode != 0:
            echo(patch_command_call.stderr.decode('utf-8'), 'red')
            self._on_process_end("Failed to patch deployment for %s" % deployment)

        echo(patch_command_call.stdout.decode('utf-8'), "green")

        if check_status is True:
            echo("Check deployment state for %s:" % deployment, "blue")
            while True:
                time.sleep(1)
                # get_replica_sets_commmand = "kubectl describe deploy %s | grep OldReplicaSets:" % deployment
                # get_replica_sets_commmand_call = subprocess.run(get_replica_sets_commmand, shell=True, stdout=PIPE, stdin=PIPE)

                get_replica_sets_commmand = "kubectl rollout status deploy/%s --timeout=50s" % deployment
                get_replica_sets_commmand_call = subprocess.run(get_replica_sets_commmand, shell=True, stdout=PIPE, stdin=PIPE)

                command_result = get_replica_sets_commmand_call.stdout.decode('utf-8')
                if "successfully rolled out" in command_result:
                    echo("Deployment done!", "green")
                    break

    def _set_default(self, str, default):
        if str is None:
            str = default

        return str

    def _set_lower(self, str):
        if str is not None:
            str = str.lower()

        return str

    @profile
    def _get_env(self):
        environment = self._set_lower(self.app.pargs.environment)

        # Parameter validation
        if environment not in self.projects:
            self._on_process_end("Failed to identify environment %s" % environment)

        return environment

    @profile
    def _load_config(self, file_path):
        if not os.path.isfile(file_path):
            self._on_process_end("Failed to find configuration file %s" % file_path)

        config = {}
        with open(file_path) as f:
            config = json.load(f)

        print("Loaded configuration file: %s" % file_path)
        print(config)
        return config

    @profile
    def _on_process_end(self, message, exitcode=1, del_directory=''):
        echo('Ending process with %s' % del_directory, 'green')
        message_type = 'error'
        color = 'red'
        if exitcode == 0:
            message_type = 'success'
            color = 'green'

        echo(message, color)
        self._send_message('', message, message_type)

        if (del_directory != '') and (os.path.exists(del_directory)):
            echo("Deleting directory: " + del_directory, 'green')
            shutil.rmtree(del_directory)

        sys.exit(exitcode)

    def _replace_in_file(self, file_path, search, replace):
        # Read in the file
        with open(file_path, 'r') as file:
            filedata = file.read()

        # Replace the target string
        filedata = filedata.replace(search, replace)

        # Write the file out again
        with open(file_path, 'w') as file:
            file.write(filedata)

    def _check_dependencies(self, dependency, flag='--'):
        # Check if dependency is installed
        try:
            subprocess.call([dependency, flag + "version"])
        except OSError as e:
            echo("Missing dependency %s" % dependency, "red")
            self._send_message("", "Missing dependency %s" % dependency, 'error')
            sys.exit()

        return True

    @profile
    def _send_message(self, project, message, message_type):
        # , 'icarsuite-dealerships'
        channels = ['labs', 'academy', '<GCP_PROJECT>', 'datadashboard', 'meetari', 'auctions', 'newcar', 'cloudpol',
                    'front-leadmarket', 'api-leadmarket', 'dealerships', 'accounts', 'shared-services', 'lapi', 'eapi',
                    'icardata']
        channel = project if project in channels else 'log'

        # echo("Channel: %s" % channel, "green")
        registry.notify.send(channel, message, message_type, send_as_attachment=True)