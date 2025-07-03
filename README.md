# miarka-processing-service
Microservice to perform operations like moving files and starting pipelines on miarka.

# Setup
## Setup in conda environment
After cloning the repository, do the following to setup the conda environment.

```
conda create -n miarka-processing-service python=3.10
conda activate miarka-processing-service
pip3 install -r requirements/dev
pip3 install --editable .
```

### setup.py
Note that the use of the python command with a setup.py is being deprecated in October 2025.
The information in setup.py can still be used as is but with pip instead.
TODO: Convert setup.py to pyproject.toml (recommended but nor required)
See, https://packaging.python.org/en/latest/guides/modernize-setup-py-project/#

```
# Deprecated commands...

python setup.py install
python setup.py develop

#...can be replaced by

python -m pip install .
python -m pip install --editable .
```

### Starting the service
Start the service with running the following command inside the conda environment:

```
miarka-processing-service --config config/ --port 8080 --debug
```
A service log will be created in miarka-processing-service.log

Make sure the service is responding by running the following command.

```
curl http://localhost:8080/api/1.0/version
```


### WIP: Transfer venv to miarka

```
#on marvin
python3.12 -m venv --copies venv
source venv/bin/activate
(venv) venv/bin/pip3.12 install -r requirements/prod
(venv) pip3.12 install venv-pack2
(venv) venv-pack -o venv.zip

#Rsync zip-file to miarka and unpack
python3.12 -m zipfile -e venv.zip venv/
source venv/bin/activate

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
```
apptainer build miarka-processing-service.sif docker-daemon://miarka-processing-service:latest

```

Start an instance of the image.
```
apptainer instance start miarka-processing-service.sif \
miarka-processing-service

```

Start service in instance
```
apptainer exec instance://miarka-processing-service miarka-processing-service --config /opt/miarka-processing-service/config/ --port 8080 --debug
```

Curl service
```
curl http://localhost:8080/api/1.0/version
```

Stop instance
```
apptainer instance stop miarka-processing-service
```