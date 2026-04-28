import os
import subprocess

from cement.core.controller import expose

from core.icarbasecontroller import ICarBaseController
from core.icarcommand import command
from lib.io import echo
from objects import registry
from resources.messages import messages, flag_message


class ImageController(ICarBaseController):
    """
    This class is not an isolated class and is written with ICAR Infra in mind.
    There are dependencies outside of the command (not documented for now) that are must for this to work
    """

    required = []
    scope = "cluster"

    project = ""
    # Will be used for base images
    image = ""
    # Default environment
    environment = "production"
    # FOR API's We don't need static container, pass f=false for that
    frontend = ""
    # For projects that don't have a build stage
    build = "true"
    # If generate final image, tag and push or not
    generate = "true"
    # If we want a new build directory every time
    new_build_directory = "true"
    # In case of debugging, can get the code from local machine, instead of cloning and using
    local = ""
    # To force this tag to be used
    tag = ""
    # If you want to use only a sub directory for the code and not the whole cloned directory
    subdirectory = ""
    # If GCP Config File is needed for the image
    use_gcp_config_file = "true"
    gcp_cluster = ""
    # In case of windows, need this flag to mount the volume, the location currently is not configurable, always c:\\temp
    win = "false"
    # The config file to use in case of base image
    config_file = 'Dockerfile'
    # The name to pass in case of base image
    name = ''
    # Copy the artifacts to current workspace
    artifacts = "false"
    # Label for deployment
    label = ""
    # Keep git files from the project
    keep_git = "false"

    class Meta:
        label = 'image'
        description = 'Build and Manage Docker Images'
        arguments = [
            (['-p', '--project'], dict(help=flag_message['common.project'])),
            (['-i', '--image'], dict(help="Image")),
            (['-b', '--branch'], dict(help=flag_message['common.branch'])),
            (['-f', '--front'], dict(help="Front")),
            (['-c', '--configfile'], dict(help="Config File", default="Dockerfile")),
            (['-n', '--name'], dict(help="Name")),
            (['-d', '--build'], dict(help="Build", default=True)),
            (['-g', '--generate'], dict(help="Generate", default=True)),
            (['-l', '--local'], dict(help="Local")),
            (['-lb', '--label'], dict(help="Label")),
            (['-r', '--artifacts'], dict(help="Artifacts", default=False)),
            (['-w', '--win'], dict(help="Windows", default=False)),
            (['-t', '--tag'], dict(help="Tag")),
            (['-sd', '--subdirectory'], dict(help="Sub directory")),
            (['-nbd', '--newbuilddirectory'], dict(help="New build directory", default=True)),
            (['-gcf', '--gcpconfigfile'], dict(help="GCP Config File", default=True)),
            (['-gclst', '--gcpcluster'], dict(help="GCP Cluster")),
            (['-kg', '--keepgit'], dict(help="Keep GIT Files", default=False))
        ]
        usage = 'icarcli image <command> [options]'
        epilog = messages['init.epilog']

    @command
    @expose(hide=True)
    def default(self):
        echo("This command is used to build and manage docker images")

    @command
    @expose(help="Build Docker Image for projects")
    def build(self):
        """Build Docker Image"""

        echo('Build Started', color='green', font='small')

        args = self.app.pargs

        # Check if git is installed
        try:
            subprocess.call(['git', '--version'])
        except OSError as e:
            if e.errno == os.errno.ENOENT:
                registry.notify.send('log', 'Oops! Git is missing. Failed to build.', 'error', True)
                return False

        # Check if docker is installed
        try:
            subprocess.call(['docker', '--version'])
        except OSError as e:
            if e.errno == os.errno.ENOENT:
                registry.notify.send('log', 'Oops! Docker is missing. Failed to build.', 'error', True)
                return False

        if args.project is None and args.image is None:
            registry.notify.send('log', 'Neither project nor base image type is given', 'error', True)

        if args.project is not None and args.image is not None:
            registry.notify.send('log', 'Cannot be both project %s and base image %s'
                                 % (args.project, args.image), 'error', True)

        if args.image is not None:
            echo('Image=%s' % args.image)

        """
                
        # CONSTANTS
        CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
        
        
        # Set this path based on google cloud SDK location
        #GCLOUD="/Users/zeeshankhan/Downloads/google-cloud-sdk/bin/gcloud"
        # Default is without path
        GCLOUD="gcloud"
        KUBECTL="kubectl"
        
        read -r -d '' TMP_STR<<'EOF'
        
        #   ___              _        _     ___    _                 _               _   #
        #  (  _`\         _ (_ )     ( )   (  _`\ ( )_              ( )_            ( )  #
        #  | (_) ) _   _ (_) | |    _| |   | (_(_)| ,_)   _ _  _ __ | ,_)   __     _| |  #
        #  |  _ <'( ) ( )| | | |  /'_` |   `\__ \ | |   /'_` )( '__)| |   /'__`\ /'_` |  #
        #  | (_) )| (_) || | | | ( (_| |   ( )_) || |_ ( (_| || |   | |_ (  ___/( (_| |  #
        #  (____/'`\___/'(_)(___)`\__,_)   `\____)`\__)`\__,_)(_)   `\__)`\____)`\__,_)  #
        #                                                                                #
        
        EOF
        
        notify "Build Started" info
        echo -e "${FONT_GREEN}${TMP_STR}${FONT_NC}"
        
        # check requirements
        # Req 1 GIT
        git --version 2>&1 >/dev/null
        GIT_IS_AVAILABLE=$?
        if [ ! ${GIT_IS_AVAILABLE} -eq 0 ]; then
          notify "Oops! Git is missing. Failed to build." error true
          exit 1
        fi
        
        # Req 2 DOCKER
        docker --version 2>&1 >/dev/null
        DOCKER_IS_AVAILABLE=$?
        if [ ! ${DOCKER_IS_AVAILABLE} -eq 0 ]; then
          notify "Oops! Docker is missing. Failed to build." error true
          exit 1
        fi
        
        
        if [ "$PROJECT" == "" ] && [ "$IMAGE" == "" ]; then
          notify "Neither project nor base image type is given" error true
          exit 1
        fi
        
        if [ "$PROJECT" != "" ] && [ "$IMAGE" != "" ]; then
          notify "Cannot be both project ${PROJECT} and base image ${IMAGE}" error true
          exit 1
        fi
        
        if [ "$IMAGE" != "" ]; then
          echo IMAGE = ${IMAGE}
          PROJECT='dockers'
          if [ "$NAME" == "" ]; then
            NAME=$IMAGE
          fi
          if [[ ${TAG} == "" ]]; then
            notify "Tag not defined using tag 'latest' instead" error true
            TAG="latest"
          fi
        fi
        
        PROJECT="$(tr [A-Z] [a-z] <<< "$PROJECT")"
        ENVIRONMENT="$(tr [A-Z] [a-z] <<< "$ENVIRONMENT")"
        FRONTEND="$(tr [A-Z] [a-z] <<< "$FRONTEND")"
        SUB_IMAGES=$(echo $FRONTEND | tr "," "\n")
        
        CONFIG_FOLDER='project'
        GCLOUD_ZONE="<GCP_REGION>-a"
        
        echo PROJECT = ${PROJECT}
        echo BRANCH = ${BRANCH}
        echo ENVIRONMENT = ${ENVIRONMENT}
        echo FRONTEND = ${FRONTEND}
        
        notify_elapsed_time "Setting up all build params"
        notify "Start $PROJECT - $BRANCH - $ENVIRONMENT" info true
        
        echo "$GCLOUD_ZONE $GCLOUD_CLUSTER $GCLOUD"
        
        DOCKER_DIRECTORY=${CURRENT_DIR}/../project/dockers/
        PROJECT_DIRECTORY=${CURRENT_DIR}/../${CONFIG_FOLDER}/${PROJECT}/
        
        # Set GCP Project
        GCP_PROJECT="<GCP_PROJECT_PREPROD>"
        GCP_ENV="preprod"
        GCLOUD_CLUSTER="<GCP_PROJECT_PREPROD>environment"
        
        if [[ "${ENVIRONMENT}" == "production" ]]; then
          GCP_PROJECT="<GCP_PROJECT_PROD>"
          GCP_ENV="production"
          GCLOUD_CLUSTER="<GCP_CLUSTER_NAME>"
        fi
        
        if [[ "${GCP_CLUSTER}" != "" ]]; then
          GCLOUD_CLUSTER=$GCP_CLUSTER
        fi
        
        echo "Setup GCloud Credentials ${GCP_ENV}"
        
        ${ICARCLI} auth cluster --environment ${ENVIRONMENT}
        
        echo "Project Directory -- ${PROJECT_DIRECTORY}"
        
        # Check if Folder exists
        if [ ! -d "${PROJECT_DIRECTORY}config" ]; then
          notify "Unknow project [${PROJECT}]" error true
          exit 1
        fi
        
        ####### KEEP THE ABOVE PORTION SAME FOR DEPLOY AND BUILD PROJECT SCRIPT #########
        
        REPSITORY_CONFIG_FILE=${PROJECT_DIRECTORY}config/repository.ini
        # Check if repository file exists
        if [ ! -f "${REPSITORY_CONFIG_FILE}" ]; then
          notify "Failed to find repository config file [${REPSITORY_CONFIG_FILE}]" error true
          exit 1
        fi
        
        WEBDIR_CONFIG_FILE=${PROJECT_DIRECTORY}config/webdirectory.ini
        # Check if repository file exists
        if [ ! -f "${WEBDIR_CONFIG_FILE}" ]; then
          notify "Failed to find web directory config file [${WEBDIR_CONFIG_FILE}]" error true
          exit 1
        fi
        
        notify_elapsed_time "Setting up remaining build params"
        
        # Only for build true
        if [[ "${BUILD}" == "true" ]]; then
          DOCKER_BUILD_FILE=${PROJECT_DIRECTORY}Dockerfile-Build
          # Check if Docker build file exists
          if [ ! -f "${DOCKER_BUILD_FILE}" ]; then
            notify "$Failed to find Docker Build file [${DOCKER_BUILD_FILE}]" error true
            exit 1
          fi
        fi
        
        notify_elapsed_time "Running Docker Build File"
        
        DOCKER_FILE=${PROJECT_DIRECTORY}${CONFIG_FILE}
        if [ "$IMAGE" == "" ]; then
          # Check if Docker file exists
          if [ ! -f "$DOCKER_FILE" ]; then
            notify "Failed to find Docker file [${DOCKER_FILE}]" error true
            exit 1
          fi
        fi
        
        uuid=''
        NEW_DIRECTORY="/${PROJECT}"
        
        if [[ ${NEW_BUILD_DIRECTORY} == "true" ]]; then
          uuid=$(uuidgen)
          uuid="$(tr [A-Z] [a-z] <<< "$uuid")"
          if [[ ${uuid} != "" ]]; then
            NEW_DIRECTORY="/$uuid"
          fi
          echo ${uuid}
        fi
        
        BUILD_ARGS=""
        
        TMP_DIRECTORY=/tmp
        if [[ ${WIN} == "true" ]]; then
          TMP_DIRECTORY=/c/tmp
        fi
        
        # @todo: Fix double slash issue if uuid is empty
        PROJECT_BUILD_DIRECTORY=${PROJECT_DIRECTORY}code${NEW_DIRECTORY}
        MOUNT_BUILD_DIRECTORY=${TMP_DIRECTORY}/code${NEW_DIRECTORY}
        
        mkdir -p ${PROJECT_BUILD_DIRECTORY}
        mkdir -p ${TMP_DIRECTORY}/code 
        
        # On any error after this point we should make sure we remove $PROJECT_BUILD_DIRECTORY to clean
        
        REPOSITORY=$(<${REPSITORY_CONFIG_FILE})
        WEB_DIR=$(<${WEBDIR_CONFIG_FILE})
        
        echo "[${REPOSITORY}] - [${PROJECT_BUILD_DIRECTORY}] - [${WEB_DIR}]"
        
        notify_elapsed_time "Setting code repo directory"
        
        # @todo: Won't need it if I start using ${TMP_DIRECTORY} directory as default, so will remove the extra copy step
        if [[ ${LOCAL} != "" ]]; then
        
          mkdir -p ${MOUNT_BUILD_DIRECTORY}
          notify "Copying ${CURRENT_DIR}/../${LOCAL}/* to ${MOUNT_BUILD_DIRECTORY}" info
          cp -Rf ${CURRENT_DIR}/../${LOCAL}/* ${MOUNT_BUILD_DIRECTORY}
        
        else
          echo "Making known_hosts file"
          mkdir -p ~/.ssh && ssh-keyscan -t rsa bitbucket.org >> ~/.ssh/known_hosts
        
          echo "Setting SSH Agent and cloning repo"
          ssh-agent bash -c "ssh-add ${DOCKER_DIRECTORY}config/keys/id_rsa; git clone --single-branch -b ${BRANCH} ${REPOSITORY} ${PROJECT_BUILD_DIRECTORY}; git -C "${PROJECT_BUILD_DIRECTORY}" pull origin ${BRANCH}"
        
          ls ${PROJECT_BUILD_DIRECTORY}
        
          if [ ! $? -eq 0 ]; then
            notify "Failed to clone repository ${REPOSITORY}" error true
            rm -Rf ${PROJECT_BUILD_DIRECTORY}
            exit 1
          fi
        
          mv $PROJECT_BUILD_DIRECTORY ${TMP_DIRECTORY}/code/
        
        fi
        
        notify_elapsed_time "Downloading directory from git"
        
        #git fetch --all && git checkout ${BRANCH}
        #if [ ! $? -eq 0 ]; then
        #    notify "Failed to checkout branch [${BRANCH}]" error true
            #rm -Rf ${PROJECT_BUILD_DIRECTORY}
        #    exit 1
        #fi
        
        BRANCH_SLUG="$(echo -n "${BRANCH}" | sed -e 's/[^[:alnum:]]/_/g' | tr -s '_' | tr A-Z a-z)"
        
        BUILD_COMPOSE_ENV=""
        IMAGE_NAME_POSTFIX="-${ENVIRONMENT}"
        
        if [[ ${ENVIRONMENT} == "production" ]]; then
          BUILD_COMPOSE_ENV=" --no-dev"
          IMAGE_NAME_POSTFIX=""
        fi
        
        cd ${PROJECT_DIRECTORY}
        
        IMAGE_NAME=${PROJECT}
        if [ "${NAME}" != "" ]; then
            IMAGE_NAME=${NAME}
        fi
        
        IMAGE_NAME="${IMAGE_NAME}${IMAGE_NAME_POSTFIX}"
        
        notify_elapsed_time "Setting up Docker build image params"
        
        if [[ "${BUILD}" == "true" ]]; then
          
          notify "Docker build <GCP_PROJECT>/build_${IMAGE_NAME}_${BRANCH_SLUG} ." info
        
          # replace repository to the environment provided
          sed -i -e "s#/<GCP_PROJECT_PREPROD>/#/${GCP_PROJECT}/#g" Dockerfile-Build
        
          # BUILD image to run composer &
          docker build -f Dockerfile-Build \
          --build-arg BUILD_COMPOSE_ENV="${BUILD_COMPOSE_ENV}" \
          --build-arg ENVIRONMENT=${ENVIRONMENT} \
          -t <GCP_PROJECT>/build_${IMAGE_NAME}_${BRANCH_SLUG} .
            
          if [ ! $? -eq 0 ]; then
              notify "Failed to build image [<GCP_PROJECT>/build_${IMAGE_NAME}_${BRANCH_SLUG}]" error true
              rm -Rf ${MOUNT_BUILD_DIRECTORY}
              exit 1
          fi
        
          # revert file changes
          sed -i -e "s#/${GCP_PROJECT}/#/<GCP_PROJECT_PREPROD>/#g" Dockerfile-Build
        
          # Touch a file
          # Entrypoint script will signal by remoing this file that
          # it has finished all the work needed for building image
          touch ${MOUNT_BUILD_DIRECTORY}/entrypointscript
        
        
          # Remove container if already running with same name
          if [ ! "$(docker ps -q -f name=build_${IMAGE_NAME}_${BRANCH_SLUG})" ]; then
            if [ "$(docker ps -aq -f status=exited -f name=build_${IMAGE_NAME}_${BRANCH_SLUG})" ]; then
                # cleanup
                docker rm build_${IMAGE_NAME}_${BRANCH_SLUG} -f
            fi
          fi
        
          MOUNT_BUILD_VOLUME=$MOUNT_BUILD_DIRECTORY
          if [[ ${WIN} == "true" ]]; then
            MOUNT_BUILD_VOLUME=C:\\tmp\\code\\${PROJECT}
          fi
        
          EXISTING_JOB_FINISHED="false"
          while [ "${EXISTING_JOB_FINISHED}" != "true" ]
          do
            if [ ! "$(docker ps | grep build_${IMAGE_NAME}_${BRANCH_SLUG})" ]; then 
              EXISTING_JOB_FINISHED="true"
            else
              echo "Waiting for existing build to finish ..."
              echo "Sleeping for half minute ..."
              sleep 30
            fi
          done
        
          mkdir -p /tmp/composer
          
          docker run --name build_${IMAGE_NAME}_${BRANCH_SLUG} -d \
          -v  ${MOUNT_BUILD_VOLUME}:/var/www/${WEB_DIR} \
          -v  /tmp/composer:/tmp/composer \
          <GCP_PROJECT>/build_${IMAGE_NAME}_${BRANCH_SLUG}
        
          # docker rm build_ubp_master
          # docker run --name build_ubp_master -d -v ${TMP_DIRECTORY}/code/144c7c12-6bb9-444e-b99a-226535e5bbda:/var/www/unified-web-portal -it <GCP_PROJECT>/build_ubp_master sh
        
          # --mount type=bind,source="${MOUNT_BUILD_DIRECTORY}",target="/var/www/${WEB_DIR}" \
          if [ ! $? -eq 0 ]; then
              notify "Failed to run image [<GCP_PROJECT>/build_${IMAGE_NAME}_${BRANCH_SLUG}]" error true
              rm -Rf ${MOUNT_BUILD_DIRECTORY}
              exit 1
          fi
        
          JOB_FINISHED="false"
          while [ "${JOB_FINISHED}" != "true" ]
          do
            if [ ! -f "${MOUNT_BUILD_DIRECTORY}/entrypointscript" ]; then
              JOB_FINISHED="true"
            else
              if [ ! "$(docker ps | grep build_${IMAGE_NAME}_${BRANCH_SLUG})" ]; then
                notify "Abnormal run termination [build_${IMAGE_NAME}_${BRANCH_SLUG}]" error true
                rm -Rf ${MOUNT_BUILD_DIRECTORY}
                exit 1
              fi
              echo "Waiting for build to finish ..."
              echo "Sleeping for half minute ..."
              sleep 30
            fi
          done
        
        fi
        
        notify_elapsed_time "Completing Docker build image"
        
        echo "### Artifacts: ${ARTIFACTS} ###"
        
        if [ "${ARTIFACTS}" != "false" ]; then
          # Artifacts will have the path where to move the file
          echo "Making $ARTIFACTS"
          mkdir -p $ARTIFACTS
          echo "Copy $MOUNT_BUILD_DIRECTORY"
          cp -Rf ${MOUNT_BUILD_DIRECTORY}/* $ARTIFACTS
        fi
        
        notify_elapsed_time "Generating Artifacts"
        
        mv $MOUNT_BUILD_DIRECTORY ${PROJECT_DIRECTORY}code/
        
        cd $PROJECT_BUILD_DIRECTORY
        
        if [[ "${KEEP_GIT}" == "false" ]]; then
          echo "Remove GIT Files"
          # Remove all git files & folders
          ( find . -type d -name ".git" \
            && find . -name ".gitignore" \
            && find . -name ".gitmodules" ) | xargs rm -rf
        fi
        
        notify_elapsed_time "Removing git folders"
        
        echo ${PROJECT_BUILD_DIRECTORY}
        
        if [ "${IMAGE}" == "" ]; then
        
          echo "cd ${PROJECT_DIRECTORY}"
          cd ${PROJECT_DIRECTORY}
        
          GCP_COPY_FILE=""
        
          if [[ "${USE_GCP_CONFIG_FILE}" == "true" ]]; then
            if [ -f "${PROJECT_DIRECTORY}config/${ENVIRONMENT}_gcp_cloud_configuration.json" ]; then
              GCP_COPY_FILE=" --build-arg GCP_CONFIG_FILE=${ENVIRONMENT}_gcp_cloud_configuration.json"
            elif [ -f "${PROJECT_DIRECTORY}config/gcp_cloud_configuration.json" ]; then
              GCP_COPY_FILE=" --build-arg GCP_CONFIG_FILE=gcp_cloud_configuration.json"
            fi
          fi
        
          echo $GCP_COPY_FILE
        
          if [[ ${SUBDIRECTORY} != "" ]]; then
            SUBDIRECTORY="/$SUBDIRECTORY"
          fi
        
          echo "Code Folder: code${NEW_DIRECTORY}${SUBDIRECTORY}"
          BUILD_ARGS="--build-arg FOLDER_PATH=code${NEW_DIRECTORY}${SUBDIRECTORY} $GCP_COPY_FILE --build-arg ENVIRONMENT=${ENVIRONMENT}"
        
          # replace repository to the environment provided
          sed -i -e "s#/<GCP_PROJECT_PREPROD>/#/${GCP_PROJECT}/#g" ${CONFIG_FILE}
        
          notify_elapsed_time "Setting up params for Docker code image"
        
          docker build -f ${CONFIG_FILE} \
          ${BUILD_ARGS} \
          -t <GCP_PROJECT>/${IMAGE_NAME}_${BRANCH_SLUG} .
        
          notify_elapsed_time "Building Docker code image"
        
          if [ ! $? -eq 0 ]; then
            notify "Failed to build image [<GCP_PROJECT>/${IMAGE_NAME}_${BRANCH_SLUG}]" error true
            rm -Rf ${PROJECT_BUILD_DIRECTORY}
            exit 1
          fi
        
          # revert file changes
          sed -i -e "s#/${GCP_PROJECT}/#/<GCP_PROJECT_PREPROD>/#g" ${CONFIG_FILE}
        
        
          ##### KEEP THE CODE BELOW SAME IN DEPLOY AND BUILD SCRIPT ######
        
          registry_target="<GCP_PROJECT>/${IMAGE_NAME}:${BRANCH_SLUG}"
        
          if [[ ${TAG} != "" ]]; then
            registry_target="<GCP_PROJECT>/${IMAGE_NAME}:${TAG}"
          fi
        
          registry_target="asia.gcr.io/${GCP_PROJECT}/${registry_target}"
        
          ###############################
        
          echo "Registry Target:: ${registry_target}"
          docker tag <GCP_PROJECT>/${IMAGE_NAME}_${BRANCH_SLUG} ${registry_target}
        
          notify_elapsed_time "Tagging Docker code image"
        
          ${GCLOUD} docker -- push ${registry_target}
        
          notify_elapsed_time "Pushing Docker code image to GCP Registry"
        
          if [ -n "$SUB_IMAGES" ]; then
            for img in $SUB_IMAGES
            do
                img_docker_file="${img}/Dockerfile"
        
                if [ -f ${img_docker_file} ]; then
                    img_registry_target="<GCP_PROJECT>/${IMAGE_NAME}_${img}:${BRANCH_SLUG}"
        
                    if [[ ${TAG} != "" ]]; then
                        img_registry_target="<GCP_PROJECT>/${IMAGE_NAME}_${img}:${TAG}"
                    fi
        
                    img_registry_target="asia.gcr.io/${GCP_PROJECT}/${img_registry_target}"
        
                    # replace repository to the environment provided
                    sed -i -e "s#/<GCP_PROJECT_PREPROD>/#/${GCP_PROJECT}/#g" ${img_docker_file}
        
                    tmp_env="$(tr [A-Z] [a-z] <<< "$ENVIRONMENT")"
                    if [ ${tmp_env} != "production" ]; then
                        tmp_env="preprod"
                    fi
        
                    notify_elapsed_time "Setting up params for Docker Sub image ${img}"
                    # Build image in sub directory
                    docker build -f ${img_docker_file} \
                    --build-arg FOLDER_PATH=code${NEW_DIRECTORY}${SUBDIRECTORY} \
                    --build-arg ENVIRONMENT=${tmp_env} $GCP_COPY_FILE \
                    -t <GCP_PROJECT>/${IMAGE_NAME}_${ENVIRONMENT}_${img}_${BRANCH_SLUG} .
        
                    notify_elapsed_time "Building Docker Sub image ${img}"
        
                    if [ ! $? -eq 0 ]; then
                      notify "Failed to build image for ${img} files [<GCP_PROJECT>/${IMAGE_NAME}_${img}_${BRANCH_SLUG}]" error true
                      rm -Rf ${PROJECT_BUILD_DIRECTORY}
                      exit 1
                    fi
        
                    # revert file changes
                    sed -i -e "s#/${GCP_PROJECT}/#/<GCP_PROJECT_PREPROD>/#g" ${img_docker_file}
        
                    echo "${img} Registry Target:: ${img_registry_target}"
                    docker tag <GCP_PROJECT>/${IMAGE_NAME}_${ENVIRONMENT}_${img}_${BRANCH_SLUG} ${img_registry_target}
        
                    notify_elapsed_time "Tagging Docker Sub image ${img}"
                    ${GCLOUD} docker -- push "${img_registry_target}"
        
        
                    notify_elapsed_time "Pushing Docker Sub image ${img} to GCP Registry"
                else
                    notify "Failed to build image for ${img} files [<GCP_PROJECT>/${IMAGE_NAME}_${img}_${BRANCH_SLUG}]. File not found in sub directory ${img_docker_file}" error true
                    rm -Rf ${PROJECT_BUILD_DIRECTORY}
                    exit 1
                fi
            done
          fi
        
          notify_elapsed_time "From last operation"
        
          if [[ "${BUILD}" == "true" ]]; then
        
        
            # Remove running container of the image
            docker rm build_${IMAGE_NAME}_${BRANCH_SLUG} -f
        
            # Remove build image
            docker image rm <GCP_PROJECT>/build_${IMAGE_NAME}_${BRANCH_SLUG} -f
        
            notify_elapsed_time "Removing Docker build images and containers"
          fi
        else
        
          notify "Generating Base Image ..." success
          bash ${PROJECT_BUILD_DIRECTORY}/scripts/build-image.sh -p=${IMAGE} -f=${CONFIG_FILE} -n=${NAME} -t=${TAG} -e=${ENVIRONMENT}
        
          if [ ! $? -eq 0 ]; then
              notify "Failed to build image ${IMAGE}" error true
              rm -Rf ${PROJECT_BUILD_DIRECTORY}
              exit 1
          fi
        
        fi
        
        # Clean folder at the very end
        rm -Rf $PROJECT_BUILD_DIRECTORY
        
        notify_elapsed_time "Removing Project Build Directory"
        
        notify "Stop $PROJECT - $BRANCH - $ENVIRONMENT" info true

        """
