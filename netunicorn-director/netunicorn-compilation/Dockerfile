FROM python:3.10-slim

# most likely you want to use docker.sock to run this image:
# docker run -v /var/run/docker.sock:/var/run/docker.sock compilation

# install docker-ce-cli
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
WORKDIR /app
COPY pyproject.toml ./pyproject.toml
COPY src ./src
RUN pip install .

ENTRYPOINT ["python3", "-m", "netunicorn.director.compilation"]