-- Datos de ejemplo opcionales. Ejecuta este archivo DESPUÉS de tu primer login
-- con Google, porque la organización se crea automáticamente en ese momento.

-- Proveedor de ejemplo para la primera organización creada:
-- INSERT INTO suppliers (org_id, name, normalized_name, tax_id)
-- SELECT id, 'Aceros del Pacífico SpA', 'aceros del pacifico', '76.123.456-7'
-- FROM organizations
-- ORDER BY created_at ASC
-- LIMIT 1
-- ON CONFLICT (org_id, normalized_name) DO NOTHING;
