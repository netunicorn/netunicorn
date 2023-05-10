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
    cleaned_up bool default FALSE,
    PRIMARY KEY (experiment_id),
    UNIQUE (username, experiment_name)
);

CREATE TABLE IF NOT EXISTS Locks (
    node_name TEXT NOT NULL,
    connector TEXT NOT NULL,
    username TEXT,
    PRIMARY KEY (node_name, connector)
);

CREATE TABLE IF NOT EXISTS Compilations (
    experiment_id TEXT NOT NULL,
    compilation_id TEXT NOT NULL,
    status BOOLEAN,
    result TEXT,
    architecture TEXT NOT NULL,
    pipeline bytea,
    environment_definition jsonb NOT NULL,
    PRIMARY KEY (experiment_id, compilation_id)
);

CREATE TABLE IF NOT EXISTS Executors (
    experiment_id TEXT NOT NULL,
    executor_id TEXT NOT NULL,
    node_name TEXT NOT NULL,
    connector TEXT NOT NULL,
    pipeline BYTEA,
    result BYTEA,
    keepalive TIMESTAMP,
    error TEXT,
    finished BOOLEAN NOT NULL,
    state INT,
    PRIMARY KEY (experiment_id, executor_id)
);

CREATE TABLE IF NOT EXISTS Flags (
    experiment_id TEXT NOT NULL,
    key TEXT NOT NULL,
    text_value TEXT,
    int_value INT NOT NULL DEFAULT 0,
    PRIMARY KEY (experiment_id, key)
)
