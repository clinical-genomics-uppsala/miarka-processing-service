FROM rockylinux/rockylinux:8.10

RUN yum -y update 
RUN yum -y upgrade
RUN yum -y install python3.12
RUN yum -y install python3.12-pip 

RUN mkdir -p /opt/miarka-processing-service/ 

COPY ./ /opt/miarka-processing-service/

WORKDIR /opt/miarka-processing-service/

RUN pip3 install backports.ssl_match_hostname 

RUN pip3 install -r requirements/prod

RUN python3.12 setup.py install

ENTRYPOINT ["miarka-processing-service","--config","./config/","--port","8080","--debug"]
