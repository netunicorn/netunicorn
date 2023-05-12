FROM python:slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get upgrade -y && apt-get install -y iproute2 iputils-ping && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip
RUN pip install netunicorn-base netunicorn-executor
ENTRYPOINT ["python3"]
CMD ["-m", "netunicorn.executor"]