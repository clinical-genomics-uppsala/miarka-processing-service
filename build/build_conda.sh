#!/usr/bin/env bash
set -e

eval "$(conda shell.bash hook)"

TAG_OR_BRANCH="dev" 
SERVICE_NAME="miarka-processing-service" 
PYTHON_VERSION="3.12" 
SERVICE_GITHUB_REPO="https://github.com/clinical-genomics-uppsala/miarka-processing-service.git"

# Clone git
git clone --branch ${TAG_OR_BRANCH} ${SERVICE_GITHUB_REPO}
cd ${SERVICE_NAME}

# Create and activate conda envrionmnet in the current directory, then install pipeline requirements
mamba create --prefix ./${SERVICE_NAME}_env python=${PYTHON_VERSION} -y
conda activate ./${SERVICE_NAME}_env

# install the service and the requirements needed in production
./${SERVICE_NAME}_env/bin/pip3 install -I . 
# pack the environment with the requriements installed
conda pack --prefix ./${SERVICE_NAME}_env -o env.tar.gz

conda deactivate

if [ -d ${SERVICE_NAME}_env ];
then
    rm -fr ${SERVICE_NAME}_env
fi

cd ..
tar -czvf ${SERVICE_NAME}.tar.gz ${SERVICE_NAME}/

if [ -d ${SERVICE_NAME} ];
then
    rm -fr ${SERVICE_NAME}
fi