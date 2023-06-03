# Authentication
This service provides basic authentication capabilities to the system.   

Current implementation of this service authenticate users by checking login and password hash in the database.  

Any administrator of the system can substitute this service with their own to provide different capabilities (LDAP, Kerberos, etc.)

## Authentication procedure
Authentication check happens each time a user calls a remote method from the client.  

During client instantiation, user provides system endpoint, and authentication credentials: `login` and `password`. Both these are text values without any restioctions, and both of them are provided as `Basic Authentication` in the header of each remote call to director services. On director services side, the mediator layer extracts these fields from the header and asks authentication service to validate these credentials before continuing executing the request.

## Default service implementation
Default service implementation checks for `username` and `hash` fields from the default database, and for given `login == username` check whether `hash(password) == stored_hash`. Passwords are hashed with `bcrypt` algorithm with randomly generated salt. Service returns code 200 if hashes are equal, and 401 otherwise.