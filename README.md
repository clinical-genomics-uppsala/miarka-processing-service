# miarka-processing-service
Microservice to perform operations like moving files and starting pipelines on miarka.

# Setup
## Setup in conda environment (on local machine)
After cloning the repository, do the following to setup the conda environment.

```
conda create -n miarka-processing-service python=3.12
conda activate miarka-processing-service
pip3 install -r requirements/dev #skip this if to run code in production
pip3 install --editable .
```
Run unit tests in dev environment.

```
python3.12 -m pytest tests/
```

### Starting the service
Start the service by running the following command inside the conda environment:

```
miarka-processing-service --config config/ --port 9999 --debug
```
A service log will be created in miarka-processing-service.log

Make sure the service is responding by running the following command.

```
curl http://localhost:9999/api/1.0/version
```

## Create directory

```
curl -X POST -w '\n' --data '{"path": "/absolute/path/to/directory/to/be/created" }' \
http://localhost:9999/api/1.0/jobs/create_directory/
```
## Start a runscript

A dummy script is available in the tests directory in this repository.
```
curl -X POST -w '\n' --data '{"runscript": "/path/to/miarka-processing-service/tests/resources/scripts/start_wp1_GMS560.sh", "inbox_path": "/path/to/miarka-processing-service/tests/resources/inbox/project1"}' \
http://localhost:9999/api/1.0/jobs/start_analysis/
```

## Get status of job/jobs

POST operations like create directory and start run script will both return a json-object containing a job id.
The job id is an int that can be used to get the status of the job.

```
{"link": "http://localhost:9999/api/1.0/jobs/12", "version": "1.5.2"}
```

To get info on a specific job and its status:

```
curl "http://localhost:9999/api/1.0/jobs/12" | python3 -m json.tool
```

To get info on a all jobs and their status:

```
curl "http://localhost:9999/api/1.0/jobs/" | python3 -m json.tool
```

### Transfer to miarka

Download/copy the script build/build_conda.sh to an empty directory on your local computer. Run with bash.

```
bash build_conda.sh
```
The script will clone the given branch (set in script, dev is default) of the repo.
Create a conda environment, install requirements, pack the environment and finally also pack the service code.
Everything needed is in the file miarka-processing-service.tar.gz. Rsync miarka-processing-service.tar.gz to miarka.

Extract the compressed archives on miarka.

```
tar -xvf miarka-processing-service.tar.gz
cd miarka-processing-service
mkdir env
tar -xvf env.tar.gz -C env
```

Unpack the environment and start service

```
source env/bin/activate
conda-unpack
miarka-processing-service --config config/ --port 11010 --debug

```

## Set-up using the Dockerfile
-------------
```
docker build -f miarka-processing-service.Dockerfile \
-t miarka-processing-service .

docker run --name miarka-processing-service \
-v ./miarka_processing_service/scripts:/opt/miarka-processing-service/scripts \
-d -p 8080:8080 miarka-processing-service:latest

```

To see the service log, omit the -d-flag or re-direct the container to a log-file using the command below. This command will write all existing  and future log messages to the file  miarka-processing-service.log.

```
docker logs -f miarka-processing-service &> miarka-processing-service.log &
```

Use `docker inspect` to find the IP of your running container to use in the commands below.

```

curl http://<container IP>:8080/api/1.0/version

```

## Run service in apptainer
---------------------------
Build a .sif from the local docker cache. Requires that the image is built with docker build first.
Or build from Singularity file (preferred).
```
apptainer build miarka-processing-service.sif docker-daemon://miarka-processing-service:latest
apptainer build service.sif Singularity

```

Start an instance of the image.
```
apptainer instance start service.sif \
miarka-processing-service

```

Curl service
```
curl http://localhost:8080/api/1.0/version
```

Stop instance
```
apptainer instance stop miarka-processing-service
```
