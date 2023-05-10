# change to your local settings
ARG python_version=3.10.9
FROM python:${python_version}-slim

ARG cloudpickle_version=2.2.0
ENV DEBIAN_FRONTEND=noninteractive

COPY ./netunicorn-base /netunicorn-base
COPY ./netunicorn-executor /netunicorn-executor
RUN pip install /netunicorn-base
RUN pip install /netunicorn-executor
RUN pip install cloudpickle==${cloudpickle_version}

CMD ["python", "-m", "netunicorn.executor"]