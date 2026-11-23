-- 020_rls_app_policies.sql
-- Garantiza que el rol de aplicación (nexora_app) pueda leer y escribir todas las
-- tablas públicas que tienen Row Level Security habilitado.
--
-- Contexto: varias migraciones (006, 007, 010, 011, 012, 017, 018) activaron RLS
-- sin crear la política "nexora_app_all". Con RLS activo y sin política, el rol
-- nexora_app recibe "new row violates row-level security policy" al insertar y ve
-- 0 filas al leer. Este script es idempotente y debe ejecutarse como dueño de la
-- base (Supabase SQL Editor), no con el rol nexora_app.

DO $$
DECLARE
    table_name TEXT;
    has_app BOOLEAN;
BEGIN
    SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexora_app') INTO has_app;
    IF NOT has_app THEN
        RAISE NOTICE 'Rol nexora_app no existe; nada que hacer.';
        RETURN;
    END IF;

    GRANT USAGE ON SCHEMA public TO nexora_app;

    FOR table_name IN
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND c.relrowsecurity
        ORDER BY c.relname
    LOOP
        EXECUTE format(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO nexora_app',
            table_name
        );
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies p
            WHERE p.schemaname = 'public'
              AND p.tablename = table_name
              AND p.policyname = 'nexora_app_all'
        ) THEN
            EXECUTE format(
                'CREATE POLICY nexora_app_all ON public.%I FOR ALL TO nexora_app '
                'USING (true) WITH CHECK (true)',
                table_name
            );
        END IF;
    END LOOP;

    EXECUTE 'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nexora_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nexora_app';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
            'GRANT USAGE, SELECT ON SEQUENCES TO nexora_app';
END $$;
