FROM python:3.10-slim

RUN pip install --upgrade pip
RUN mkdir /app
WORKDIR /app
COPY pyproject.toml ./pyproject.toml
COPY src ./src
RUN pip install .

# add connectors
RUN pip install --no-cache-dir \
    netunicorn-connector-aci  \
    netunicorn-connector-salt \
    netunicorn-connector-ssh \
    netunicorn-connector-kubernetes \
    netunicorn-connector-aws \
    netunicorn-connector-docker

ENTRYPOINT ["python3", "-m", "netunicorn.director.infrastructure"]
