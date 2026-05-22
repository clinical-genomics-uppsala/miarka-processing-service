Bootstrap: docker
From: rockylinux/rockylinux:8.10

%help

Build image
```
apptainer build service.simg Singularity
```
Create instance and start service
```
apptainer instance start service.simg miarka-processing-service
```

Curl service
```
curl http://localhost:8080/api/1.0/version
```

Stop instance
```
apptainer instance stop miarka-processing-service
```

%files
./

%post
yum -y update 
yum -y upgrade
yum -y install python3.12
yum -y install python3.12-pip 

pip3 install backports.ssl_match_hostname 

pip3 install -r requirements/prod
python3.12 setup.py install

%environment
export PORT=8080
export CONF_DIR=./config/

%startscript
miarka-processing-service --config $CONF_DIR --port $PORT --debug