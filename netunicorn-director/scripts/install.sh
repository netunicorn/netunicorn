# make directories
mkdir scripts
mkdir development

# download configuration files
wget https://raw.githubusercontent.com/netunicorn/netunicorn/main/netunicorn-director/development/users.sql -O development/users.sql
wget https://raw.githubusercontent.com/netunicorn/netunicorn/main/netunicorn-director/scripts/infrastructure-example-config.yaml -O scripts/infrastructure-example-config.yaml
wget https://raw.githubusercontent.com/netunicorn/netunicorn/main/netunicorn-director/scripts/dbdeploy.sql -O scripts/dbdeploy.sql

# download docker compose file
wget https://raw.githubusercontent.com/netunicorn/netunicorn/main/netunicorn-director/docker-compose-stable.yml -O docker-compose.yml