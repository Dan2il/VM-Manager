CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    login TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS virtual_machines (
    id SERIAL PRIMARY KEY,
    vm_id UUID NOT NULL UNIQUE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    ram INTEGER NOT NULL CHECK (ram > 0),
    cpu INTEGER NOT NULL CHECK (cpu > 0)
);

CREATE TABLE IF NOT EXISTS disks (
    id SERIAL PRIMARY KEY,
    disk_id UUID NOT NULL UNIQUE,
    size INTEGER NOT NULL CHECK (size > 0)
);

CREATE TABLE IF NOT EXISTS vm_disks (
    vm_id UUID REFERENCES virtual_machines(vm_id) ON DELETE CASCADE,
    disk_id UUID REFERENCES disks(disk_id) ON DELETE CASCADE,
    PRIMARY KEY (vm_id, disk_id)
);

CREATE TABLE IF NOT EXISTS vm_sessions (
    id SERIAL PRIMARY KEY,
    vm_id UUID REFERENCES virtual_machines(vm_id) ON DELETE CASCADE
);

