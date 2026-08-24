# miarka-processing-service
Microservice to perform operations like moving files and starting pipelines on miarka.

# Setup
## Setup in conda environment (on local machine)
After cloning the repository, do the following to setup the conda environment.

```
conda create -n miarka-processing-service python=3.12
conda activate miarka-processing-service
pip3 install --editable .[dev] # For dev environment
pip3 install -I . # For production environment
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
{"link": "http://localhost:9999/api/1.0/jobs/12", "version": "1.0.0"}
```

To get info on a specific job and its status:

```
curl "http://localhost:9999/api/1.0/jobs/12" | python3 -m json.tool
```

To get info on a all jobs and their status:

```
curl "http://localhost:9999/api/1.0/jobs/" | python3 -m json.tool
```

### Logging configuration

Logging is configured in `config/logger.config` (or whichever directory is passed via `--config`).
The default setup writes to `miarka-processing-service.log` in the working directory with midnight rotation.

**Log file path** — set `filename` to the full absolute path of the log file in `file_handler`:
```yaml
filename: /var/log/miarka-processing-service/miarka-processing-service.log
```
The default is a relative path, which places the file in whatever directory the service is started from — use an absolute path in production.

**Time-based rotation** (default) — controlled by `when`, `interval`, and `backupCount`:
```yaml
class: logging.handlers.TimedRotatingFileHandler
when: midnight   # S, M, H, D, midnight, W0-W6
interval: 1
backupCount: 30
```

**Size-based rotation** — replace the `file_handler` block with:
```yaml
class: logging.handlers.RotatingFileHandler
maxBytes: 10485760  # 10 MB
backupCount: 20
```

A commented-out size-based example is included in `config/logger.config` for reference.

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

## Configure database

The database location is set via `db_connection_string` in `config/app.config`. The config file and database must both survive deployments and should not live inside the application source tree.

Migrations are applied automatically on service startup — no manual migration step is needed after deployment.

### SQLite

The default config uses a relative path which will be overwritten on redeploy. Use an absolute path outside the deployment directory:

```yaml
db_connection_string: sqlite:////var/lib/miarka-processing-service/jobs.db
```

Note the four slashes: `sqlite://` followed by the absolute path `/var/lib/...`. The directory must exist and be writable before starting the service.

### PostgreSQL

Install the driver and update the connection string:

```bash
pip install psycopg2-binary
```

```yaml
db_connection_string: postgresql://user:password@host:5432/miarka_db
```

The database must be created beforehand (`CREATE DATABASE miarka_db`). Tables will be created automatically on first startup.

### MySQL / MariaDB

```bash
pip install mysqlclient
```

```yaml
db_connection_string: mysql://user:password@host:3306/miarka_db
```

## Set-up as a system service

When running directly on the host (not in a container), the database and configuration must be stored in a dedicated directory outside the application source tree so they are not overwritten when a new version is deployed. A suitable location is `/var/lib/miarka-processing-service/`.

Point `db_connection_string` in the config to that location (see [Configure database](#configure-database)):

```yaml
db_connection_string: sqlite:////var/lib/miarka-processing-service/jobs.db
```

Keep the active config file there as well, and start the service pointing to it:

```bash
miarka-processing-service --config /var/lib/miarka-processing-service/config/ --port 11010
```

### Backup before deployment

Before deploying a new version, take a backup of the current database. Name the copy with the running version and today's date so it can be identified and restored if needed:

```bash
VERSION=$(python -c "from miarka_processing_service import __version__; print(__version__)")
DATE=$(date +%Y-%m-%d)
cp /var/lib/miarka-processing-service/jobs.db \
   /var/lib/miarka-processing-service/jobs_v${VERSION}_${DATE}.db
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
