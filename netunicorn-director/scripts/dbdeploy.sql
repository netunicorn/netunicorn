CREATE TABLE IF NOT EXISTS Authentication (
    username TEXT NOT NULL,
    token TEXT NOT NULL,
    additional_info TEXT,
    PRIMARY KEY (username)
)