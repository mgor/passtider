FROM python:3.10-alpine

LABEL org.opencontainers.image.source https://github.com/mgor/passtider

RUN mkdir -p /app/passtider

COPY requirements.txt /tmp/

RUN pip3 install -r /tmp/requirements.txt

COPY --chown=nobody:nobody passtider/ /app/passtider

WORKDIR /app

USER nobody

ENV PYTHONPATH=.

CMD ["python3", "passtider"]
