FROM saltcommon:0.1

# Install salt-minion
RUN apt install -y salt-minion

CMD service ssh start && sleep infinity