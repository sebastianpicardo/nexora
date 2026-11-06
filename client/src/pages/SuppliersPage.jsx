import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatDate, labelize } from "../lib/format";
import { PlusIcon, SearchIcon, EditIcon, TrashIcon, CheckIcon, XIcon } from "../components/Icons";

export default function SuppliersPage() {
  const { canManage } = useAuth();
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: "", tax_id: "", email: "" });
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [supplierIntegrationRunning, setSupplierIntegrationRunning] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api(`/api/suppliers?search=${encodeURIComponent(search)}`);
      setSuppliers(data.items || []);
    } catch (err) {
      setError(err.message || "No se pudieron cargar los proveedores.");
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    load();
  }, [load]);

  function openCreate() {
    setEditing(null);
    setForm({ name: "", tax_id: "", email: "" });
    setShowModal(true);
  }

  function openEdit(supplier) {
    setEditing(supplier);
    setForm({ name: supplier.name, tax_id: supplier.tax_id || "", email: supplier.email || "" });
    setShowModal(true);
  }

  function closeModal() {
    setShowModal(false);
    setEditing(null);
    setForm({ name: "", tax_id: "", email: "" });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!form.name.trim()) {
      setError("El nombre es obligatorio.");
      return;
    }
    setPending(true);
    try {
      if (editing) {
        await api(`/api/suppliers/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(form),
        });
        setSuccess("Proveedor actualizado.");
      } else {
        await api("/api/suppliers", {
          method: "POST",
          body: JSON.stringify(form),
        });
        setSuccess("Proveedor creado.");
      }
      closeModal();
      load();
    } catch (err) {
      setError(err.message || "No se pudo guardar.");
    } finally {
      setPending(false);
    }
  }

  function confirmDelete(supplier) {
    setDeleteTarget(supplier);
  }

  async function executeDelete() {
    if (!deleteTarget) return;
    setError("");
    setSuccess("");
    setPending(true);
    try {
      await api(`/api/suppliers/${deleteTarget.id}`, { method: "DELETE" });
      setSuccess("Proveedor eliminado.");
      setDeleteTarget(null);
      load();
    } catch (err) {
      setError(err.message || "No se pudo eliminar.");
    } finally {
      setPending(false);
    }
  }

  async function handleSupplierIntegration(supplier, actionId) {
    if (actionId === "validate_rut" && !supplier.tax_id) {
      setError("El proveedor no tiene RUT registrado.");
      return;
    }
    setSupplierIntegrationRunning(`${supplier.id}:${actionId}`);
    setError("");
    setSuccess("");
    try {
      const provider = actionId === "validate_rut" ? "sii" : "chilecompra";
      const payload = actionId === "validate_rut" ? { rut: supplier.tax_id } : { name: supplier.name };
      await api(`/api/integrations/native/${provider}/${actionId}`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setSuccess(actionId === "validate_rut" ? "RUT validado en SII." : "Proveedor buscado en ChileCompra.");
      load();
    } catch (err) {
      setError(err.message || "No se pudo ejecutar la acción de integración.");
    } finally {
      setSupplierIntegrationRunning(null);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-intro">
        <div>
          <div className="eyebrow">Gestión</div>
          <h2>Proveedores</h2>
          <p>Administra la base de proveedores para asociar documentos y normalizar nombres.</p>
        </div>
        <button type="button" className="button primary" onClick={openCreate}>
          <PlusIcon /> Nuevo proveedor
        </button>
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      <div className="card">
        <div className="table-toolbar">
          <label className="search-input">
            <SearchIcon />
            <input
              type="search"
              placeholder="Buscar por nombre o RUT…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
        </div>

        {loading ? (
          <div className="empty-state">Cargando proveedores…</div>
        ) : suppliers.length === 0 ? (
          <div className="empty-state">
            <p>No hay proveedores registrados.</p>
            <button type="button" className="button primary" onClick={openCreate}>
              <PlusIcon /> Crear el primero
            </button>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>RUT / Tax ID</th>
                  <th>Email</th>
                  <th>Creado</th>
                  <th>Integraciones</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((s) => (
                  <tr key={s.id}>
                    <td>{s.name}</td>
                    <td className="mono">{s.tax_id || "—"}</td>
                    <td>{s.email || "—"}</td>
                    <td>{formatDate(s.created_at)}</td>
                    <td>
                      <div className="table-actions">
                        <button
                          type="button"
                          className="button ghost icon-only"
                          onClick={() => handleSupplierIntegration(s, "validate_rut")}
                          disabled={supplierIntegrationRunning?.startsWith(`${s.id}:validate_rut`)}
                          title="Validar RUT en SII"
                        >
                          <CheckIcon />
                        </button>
                        <button
                          type="button"
                          className="button ghost icon-only"
                          onClick={() => handleSupplierIntegration(s, "search_suppliers")}
                          disabled={supplierIntegrationRunning?.startsWith(`${s.id}:search_suppliers`)}
                          title="Buscar en ChileCompra"
                        >
                          <SearchIcon />
                        </button>
                      </div>
                    </td>
                    <td>
                      <div className="table-actions">
                        <button
                          type="button"
                          className="button ghost icon-only"
                          onClick={() => openEdit(s)}
                          title="Editar"
                        >
                          <EditIcon />
                        </button>
                        {canManage ? (
                          <button
                            type="button"
                            className="button ghost icon-only danger"
                            onClick={() => confirmDelete(s)}
                            title="Eliminar"
                          >
                            <TrashIcon />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>{editing ? "Editar proveedor" : "Nuevo proveedor"}</h3>
              <button type="button" className="icon-button" onClick={closeModal}>
                <XIcon />
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {error && <div className="alert error">{error}</div>}
                <label className="form-field">
                  <span>Nombre *</span>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Ej: Aceros del Pacífico SpA"
                    disabled={pending}
                    autoFocus
                    required
                  />
                </label>
                <label className="form-field">
                  <span>RUT / Tax ID</span>
                  <input
                    type="text"
                    value={form.tax_id}
                    onChange={(e) => setForm((f) => ({ ...f, tax_id: e.target.value }))}
                    placeholder="76.542.310-8"
                    disabled={pending}
                  />
                </label>
                <label className="form-field">
                  <span>Email</span>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    placeholder="contacto@proveedor.cl"
                    disabled={pending}
                  />
                </label>
              </div>
              <div className="modal-actions">
                <button type="button" className="button ghost" onClick={closeModal} disabled={pending}>
                  Cancelar
                </button>
                <button type="submit" className="button primary" disabled={pending}>
                  {pending ? "Guardando…" : editing ? "Actualizar" : "Crear"}
                  <CheckIcon />
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirm Modal */}
      {deleteTarget && (
        <div className="modal-overlay" onClick={() => setDeleteTarget(null)}>
          <div className="modal danger" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>Eliminar proveedor</h3>
            </div>
            <div className="modal-body">
              <p>¿Eliminar <strong>{deleteTarget.name}</strong>? Esta acción no se puede deshacer.</p>
              <p className="muted">Los documentos asociados quedarán sin proveedor.</p>
            </div>
            <div className="modal-actions">
              <button type="button" className="button ghost" onClick={() => setDeleteTarget(null)} disabled={pending}>
                Cancelar
              </button>
              <button type="button" className="button danger" onClick={executeDelete} disabled={pending}>
                {pending ? "Eliminando…" : "Sí, eliminar"}
                <TrashIcon />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}