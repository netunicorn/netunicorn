FROM python:3.10-slim

RUN mkdir /app
WORKDIR /app
COPY pyproject.toml src ./
RUN pip install .

ENTRYPOINT ["python3 -m netunicorn.director.gateway"]