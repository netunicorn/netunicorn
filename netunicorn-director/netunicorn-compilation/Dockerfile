FROM python:3.10-slim

# most likely you want to use docker.sock to run this image:
# docker run -v /var/run/docker.sock:/var/run/docker.sock compilation

RUN pip install --upgrade pip
RUN mkdir /app
WORKDIR /app
COPY pyproject.toml ./pyproject.toml
COPY src ./src
RUN pip install .

ENTRYPOINT ["python3", "-m", "netunicorn.director.compilation"]