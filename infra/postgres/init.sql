-- Runs once, on first container start, as the superuser.
-- Database-per-service pattern (ADR-02): one DB + one user per service.
DO $$
DECLARE svc TEXT;
BEGIN
  FOREACH svc IN ARRAY ARRAY['identity','profile','catalog','orders','wallet','trading','festival','achievements']
  LOOP
    EXECUTE format('CREATE USER %I WITH PASSWORD %L', svc || '_user', 'servicepass');
    EXECUTE format('CREATE DATABASE %I OWNER %I', svc, svc || '_user');
  END LOOP;
END $$;
