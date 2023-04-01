FROM python:slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt upgrade -y && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip
RUN pip install netunicorn-base netunicorn-executor