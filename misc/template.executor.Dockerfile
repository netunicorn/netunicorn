FROM python:slim
ENV DEBIAN_FRONTEND=noninteractive
RUN apt update && apt install -y iproute2 iputils-ping net-tools && apt clean && rm -rf /var/lib/apt/lists/*
RUN pip install netunicorn-base netunicorn-executor
ENTRYPOINT ["python3"]
CMD ["-m", "netunicorn.executor"]