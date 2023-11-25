# Users Management

Database table `Authentication` stores usernames, password hashes, and sudo privileges flags of the users. To add, delete, or modify users, you need to manually modify the database table.

- `username`: this field contains plaintext username of the user
- `hash`: this field contains the bcrypt hash of the user's password. See "Adding a user" section for more information.
- `sudo`: this field contains a boolean flag indicating whether the user has sudo privileges or not. Sudo privileges allows to provide arbitrary flags to the Docker containers of experiments, allowing possible destructive behavior (e.g., mounting local folders inside of the container). `sudo` flag also allows access to the monitoring webpage of the netUnicorn (see [Monitoring](monitoring.md)).
- `accesstags`: this field contains a comma-separated list of access tags. Access tags are used to restrict access to experiments. See [Access Tags](#access-tags) section for more information.

## Adding a user

To add a user, you need to generate a bcrypt hash of the user's password. You can use the following Python code to generate the hash:

```python
import bcrypt

def hash_password(plaintext_password):
    # Convert the plaintext password to bytes
    password_bytes = plaintext_password.encode('utf-8')
    
    # Generate a random salt
    salt = bcrypt.gensalt()
    
    # Hash the password with the salt
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    
    return hashed_password

# Example usage
password = "my_secure_password"
hashed_password = hash_password(password)
print("Hashed Password:", hashed_password)
```

The username, hash, and sudo flags should be inserted into the `Authentication` table. You can use the following SQL query to insert a new user:

```sql
INSERT INTO Authentication (username, hash, sudo) VALUES ('some_username', 'hashed_password', FALSE);
```

## Access Tags

Access tags are used to restrict user access to nodes. Access tags are stored in the `accesstags` field of the `Authentication` table. Access tags are comma-separated strings. For example, if a user has `accesstags` field set to `tag1,tag2`, then the user will be able to access nodes that have `accesstags` field set to `tag1` or `tag2`.

Access tags rules:
- If user has no access tags, then the user can access all nodes.
- If node has no access tags, then all users can access the node.
- If user has access tags, then it has access to all nodes which either have no access tags or have at least one access tag that is present in the user's access tags list.

Access tags on the node level are presented as a list of strings in "netunicorn-access-tags" property of the node.