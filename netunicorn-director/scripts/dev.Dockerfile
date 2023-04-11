# context should be the whole project folder
FROM python:3.10-slim

# install docker cli
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    && mkdir -m 0755 -p /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo \
    "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN mkdir /app

# base
RUN mkdir /app/netunicorn-base
WORKDIR /app/netunicorn-base
COPY netunicorn-base/pyproject.toml ./pyproject.toml
COPY netunicorn-base/src ./src
RUN pip install .

# authentication
RUN mkdir /app/netunicorn-authentication
WORKDIR /app/netunicorn-authentication
COPY netunicorn-director/netunicorn-authentication/pyproject.toml ./pyproject.toml
COPY netunicorn-director/netunicorn-authentication/src ./src
RUN pip install .

# compilation
RUN mkdir /app/netunicorn-compilation
WORKDIR /app/netunicorn-compilation
COPY netunicorn-director/netunicorn-compilation/pyproject.toml ./pyproject.toml
COPY netunicorn-director/netunicorn-compilation/src ./src
RUN pip install .

# gateway
RUN mkdir /app/netunicorn-gateway
WORKDIR /app/netunicorn-gateway
COPY netunicorn-director/netunicorn-gateway/pyproject.toml ./pyproject.toml
COPY netunicorn-director/netunicorn-gateway/src ./src
RUN pip install .

# infrastructure
RUN mkdir /app/netunicorn-infrastructure
WORKDIR /app/netunicorn-infrastructure
COPY netunicorn-director/netunicorn-infrastructure/pyproject.toml ./pyproject.toml
COPY netunicorn-director/netunicorn-infrastructure/src ./src
RUN pip install .

# mediator
RUN mkdir /app/netunicorn-mediator
WORKDIR /app/netunicorn-mediator
COPY netunicorn-director/netunicorn-mediator/pyproject.toml ./pyproject.toml
COPY netunicorn-director/netunicorn-mediator/src ./src
RUN pip install .

# processor
RUN mkdir /app/netunicorn-processor
WORKDIR /app/netunicorn-processor
COPY netunicorn-director/netunicorn-processor/pyproject.toml ./pyproject.toml
COPY netunicorn-director/netunicorn-processor/src ./src
RUN pip install .

# connectors
RUN pip install netunicorn-connector-aci
RUN pip install netunicorn-connector-salt
RUN pip install netunicorn-connector-docker

WORKDIR /app

ENTRYPOINT ["python3"]