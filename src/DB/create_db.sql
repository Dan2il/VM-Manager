CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    password_hash text NOT NULL
);

CREATE TABLE IF NOT EXISTS virtual_machines (
    id SERIAL PRIMARY KEY,
    vm_id INTEGER NOT NULL UNIQUE,
    ram INTEGER NOT NULL CHECK (ram > 0),
    cpu INTEGER NOT NULL CHECK (cpu > 0)
);

CREATE TABLE IF NOT EXISTS disks (
    id SERIAL PRIMARY KEY,
    disk_id UUID NOT NULL UNIQUE,
    vm_id UUID REFERENCES virtual_machines(vm_id) ON DELETE CASCADE,
    size INTEGER NOT NULL CHECK(size > 0)
);

CREATE TABLE IF NOT EXISTS vm_sessions (
    id serial PRIMARY KEY,
    vm_id UUID REFERENCES virtual_machines(vm_id) ON DELETE CASCADE
);
