CREATE TYPE starping_node_type AS ENUM ('planet', 'comet');

-- StarPing_Nodes stores nodes(planet or comet).
-- Specially, name can't be 'planet' or 'comet', as these to indicate
-- all the nodes of corresponding type.
CREATE TABLE StarPing_Nodes (
    name text PRIMARY KEY NOT NULL,
    shown_name text,
    secret text NOT NULL,
    type starping_node_type NOT NULL
);

-- StarPing_PingTargets stores ping targets.
CREATE TABLE StarPing_PingTargets (
    name text PRIMARY KEY NOT NULL,
    shown_name text,
    ip inet UNIQUE NOT NULL,
    nodes text ARRAY
);

-- We send ip to the nodes, and store the corresponding name in our database.
-- This index is used to do the reverse lookup.
-- Comets shouldn't do ping so name should never equals to any comet's name.
CREATE INDEX StarPing_PingTargets_IPIndex ON StarPing_PingTargets (ip);

-- StarPing_MTRTargets stores mtr targets.
-- For the case target is a planet/comet, the name should be the same
-- of name to the node, so that we can pick node out to render info.
CREATE TABLE StarPing_MTRTargets (
    name text PRIMARY KEY NOT NULL,
    shown_name text,
    ip inet UNIQUE NOT NULL,
    nodes text ARRAY
);

CREATE INDEX StarPing_MTRTargets_IPIndex ON StarPing_MTRTargets (ip);

-- we don't store ip directly but store target name, to support target ip change without modifying existing records.
CREATE TABLE StarPing_PingData (
    node text REFERENCES StarPing_Nodes(name) ON DELETE CASCADE, -- disallow record with non-exist node
    time timestamptz NOT NULL,
    name text REFERENCES StarPing_PingTargets(name) ON DELETE CASCADE, -- disallow record with non-exist target
    timeout bool NOT NULL,
    avg real CHECK ( avg >= 0 ),
    min real CHECK ( min >= 0 ),
    max real CHECK ( max >= 0 ),
    std_dev real CHECK ( std_dev >= 0 ),
    drop smallint CHECK ( drop >= 0 ),
    total smallint CHECK ( total > 0 ), -- meaningless to send over 32767 probes once
    PRIMARY KEY (node, time, name)
) PARTITION BY LIST (node);

CREATE INDEX StarPing_PingData_Index ON StarPing_PingData(name, time);

CREATE TABLE StarPing_MTRData (
    node text REFERENCES StarPing_Nodes(name) ON DELETE CASCADE,
    time timestamptz NOT NULL,
    name text REFERENCES StarPing_MTRTargets(name) ON DELETE CASCADE,
    hop_count smallint CHECK ( hop_count >= 0 ),
    data jsonb,
    PRIMARY KEY (node, time, name)
) PARTITION BY LIST (node);

CREATE INDEX StarPing_MTRData_Index ON StarPing_MTRData(name, time);

CREATE TABLE StarPing_L1TargetGroup (
    name text PRIMARY KEY NOT NULL,
    shown_name text
);

CREATE TABLE StarPing_L2TargetGroup (
    name text PRIMARY KEY NOT NULL,
    shown_name text,
    parent text REFERENCES StarPing_L1TargetGroup(name) ON DELETE CASCADE DEFAULT 'default'
);

create or replace function drop_array_item(array1 anyarray, item text)
returns anyarray language sql immutable as $$
    select coalesce(array_agg(elem), '{}')
    from unnest(array1) elem
    where elem <> item
$$;