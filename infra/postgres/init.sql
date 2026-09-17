-- PostgreSQL initialization script
-- Runs once on first container startup (when data directory is empty)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
