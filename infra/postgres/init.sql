-- Runs once on first Postgres container start (as superuser).
-- Database-per-service (ADR-02): one DB + one user per relational service.
-- NOTE: CREATE DATABASE cannot run inside a DO/function block in PostgreSQL.

CREATE USER identity_user WITH PASSWORD 'servicepass';
CREATE DATABASE identity OWNER identity_user;

CREATE USER profile_user WITH PASSWORD 'servicepass';
CREATE DATABASE profile OWNER profile_user;

CREATE USER catalog_user WITH PASSWORD 'servicepass';
CREATE DATABASE catalog OWNER catalog_user;

CREATE USER orders_user WITH PASSWORD 'servicepass';
CREATE DATABASE orders OWNER orders_user;

CREATE USER wallet_user WITH PASSWORD 'servicepass';
CREATE DATABASE wallet OWNER wallet_user;

CREATE USER trading_user WITH PASSWORD 'servicepass';
CREATE DATABASE trading OWNER trading_user;

CREATE USER festival_user WITH PASSWORD 'servicepass';
CREATE DATABASE festival OWNER festival_user;

CREATE USER achievements_user WITH PASSWORD 'servicepass';
CREATE DATABASE achievements OWNER achievements_user;
