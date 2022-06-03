FROM saltcommon:0.1

# Install salt-master
RUN apt install -y salt-master salt-api

CMD service ssh start && sleep infinity