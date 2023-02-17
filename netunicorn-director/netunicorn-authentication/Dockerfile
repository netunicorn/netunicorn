FROM python:3.10-slim

RUN pip install --upgrade pip
RUN mkdir /app
WORKDIR /app
COPY pyproject.toml ./pyproject.toml
COPY src ./src
RUN pip install .

ENTRYPOINT ["python3", "-m", "netunicorn.director.authentication"]