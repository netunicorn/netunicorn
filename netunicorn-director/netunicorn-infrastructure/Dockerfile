FROM python:3.10-slim

RUN pip install --upgrade pip
RUN mkdir /app
WORKDIR /app
COPY pyproject.toml ./pyproject.toml
COPY src ./src
RUN pip install .

# add some connectors that can work in container without problems
# like cloud connectors
RUN pip install netunicorn-connector-aci
RUN pip install netunicorn-connector-salt

ENTRYPOINT ["python3", "-m", "netunicorn.director.infrastructure"]