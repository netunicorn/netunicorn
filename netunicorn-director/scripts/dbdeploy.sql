CREATE TABLE IF NOT EXISTS Authentication (
    username TEXT NOT NULL,
    hash TEXT NOT NULL,
    sudo BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (username)
);

CREATE TABLE IF NOT EXISTS Experiments (
    username TEXT NOT NULL,
    experiment_name TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    data jsonb,
    status SMALLINT NOT NULL,
    error TEXT,
    execution_results jsonb[],
    creation_time TIMESTAMP NOT NULL,
    start_time TIMESTAMP,
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
    minion_name TEXT NOT NULL,
    pipeline BYTEA,
    result BYTEA,
    keepalive TIMESTAMP,
    error TEXT,
    finished BOOLEAN NOT NULL,
    PRIMARY KEY (experiment_id, executor_id)
);
