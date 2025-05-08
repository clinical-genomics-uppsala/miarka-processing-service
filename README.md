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

## setup.py
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

# Starting the service
Start the service with running the following command inside the conda environment:

```
miarka-processing-service --config config/ --port 8080 --debug
```
A service log will be created in miarka-processing-service.log

Make sure the service is responding by running the following command.

```
curl http://localhost:8080/api/1.0/version
```


