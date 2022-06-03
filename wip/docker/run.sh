docker run --rm --name salt --hostname salt -p 4022:22 -e SALT_SHARED_SECRET=mysecretpassword -d saltmaster:0.1
docker run --rm --name salt-minion --link salt:salt -p 4023:22 -d saltminion:0.1