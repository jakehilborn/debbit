FROM instrumentisto/geckodriver
RUN apt-get update && \
  apt-get install -y --no-install-recommends --no-install-suggests \
  python3 python3-pip pipenv

ADD . /home/debbit

RUN cd /home/debbit/src && \
  ln -s /usr/local/bin/geckodriver ./program_files/geckodriver && \
  ln -s /opt/firefox/firefox /usr/local/bin/firefox && \
  cp ./debbit.py /opt/firefox/ && \
  pipenv install

# Overwrite entrypoint in base image with something innocuous
ENTRYPOINT ["/usr/bin/env"]

WORKDIR /home/debbit/src

CMD ["python3", "-m", "pipenv", "run", "python3", "./debbit.py"]
