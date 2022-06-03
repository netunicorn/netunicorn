FROM ubuntu:20.04
ENV DEBIAN_FRONTEND noninteractive

RUN apt update && apt upgrade -y

# SSH
RUN apt install openssh-server -y
RUN mkdir -p /var/run/sshd
RUN sed -i 's/^#PermitRootLogin .*/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN service ssh restart
RUN echo "root:docker" | chpasswd

RUN apt install -y python3-pip curl

# add salt repo
RUN curl -fsSL -o /usr/share/keyrings/salt-archive-keyring.gpg https://repo.saltproject.io/py3/ubuntu/20.04/amd64/latest/salt-archive-keyring.gpg
RUN echo "deb [signed-by=/usr/share/keyrings/salt-archive-keyring.gpg arch=amd64] https://repo.saltproject.io/py3/ubuntu/20.04/amd64/latest focal main" | tee /etc/apt/sources.list.d/salt.list
RUN apt update

CMD service ssh start && sleep infinity