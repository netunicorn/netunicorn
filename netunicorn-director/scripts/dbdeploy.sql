CREATE TABLE IF NOT EXISTS Authentication (
    username TEXT NOT NULL,
    token TEXT NOT NULL,
    additional_info TEXT,
    PRIMARY KEY (username)
);

CREATE TABLE IF NOT EXISTS Experiments (
    username TEXT NOT NULL,
    experiment_name TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    data jsonb,
    status SMALLINT NOT NULL,
    result jsonb,
    PRIMARY KEY (experiment_id),
    UNIQUE (username, experiment_name)
);

CREATE TABLE IF NOT EXISTS Locks (
    minion_name TEXT NOT NULL,
    username TEXT,
    PRIMARY KEY (minion_name)
);

CREATE TABLE IF NOT EXISTS Compilations (
    experiment_id TEXT NOT NULL,
    compilation_id TEXT NOT NULL,
    status BOOLEAN,
    result TEXT,
    PRIMARY KEY (experiment_id, compilation_id)
);

CREATE TABLE IF NOT EXISTS Executors (
    experiment_id TEXT NOT NULL,
    executor_id TEXT NOT NULL,
    pipeline BYTEA,
    result BYTEA,
    keepalive TIMESTAMP
);
