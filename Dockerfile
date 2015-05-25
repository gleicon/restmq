FROM debian:latest

RUN apt-get update && apt-get install -y  python-pip \
   libffi-dev \
   python-dev \
   redis-server \ 
   supervisor \
   libssl-dev && apt-get clean 

ADD src /srv/restmq/src
ADD setup.py /srv/restmq/setup.py
ADD ez_setup.py /srv/restmq/ez_setup.py
ADD requirements.txt /srv/restmq/requirements.txt

WORKDIR /srv/restmq 
RUN pip install -e . 

ADD start_scripts /srv/restmq/start_scripts
# Supervisor config
ADD dockerfiles/supervisor/redis.conf /etc/supervisor/conf.d/redis.conf
ADD dockerfiles/supervisor/restmq.conf /etc/supervisor/conf.d/restmq.conf
ADD dockerfiles/supervisor/acl.conf /etc/restmq/acl.conf

EXPOSE 8888 6379
CMD ["supervisord", "-n"]
