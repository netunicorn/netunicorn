FROM python:3.10-slim

RUN mkdir /app
WORKDIR /app
COPY pyproject.toml src ./
RUN pip install .

# add some connectors that can work in container without problems
# like cloud connectors
RUN pip install netunicorn-connector-aci

ENTRYPOINT ["python3 -m netunicorn.director.infrastructure"]