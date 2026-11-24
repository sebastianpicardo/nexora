import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import { formatMoney, formatNumber } from "../lib/format";
import {
  CheckIcon,
  DocumentsIcon,
  EditIcon,
  PlusIcon,
  PricesIcon,
  SearchIcon,
  SparkIcon,
  TrashIcon,
  UploadIcon,
} from "../components/Icons";

export default function PriceCatalogPage({ embedded = false, onUpload }) {
  const { canManage, canOperate } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({
    sku: "",
    name: "",
    description: "",
    unit: "unidad",
    cost_price: "",
    sale_price: "",
    category: "",
    supplier_name: "",
    active: true,
  });
  const [pending, setPending] = useState(false);
  const [importing, setImporting] = useState("");
  const [success, setSuccess] = useState("");
  const [activeOnly, setActiveOnly] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        active_only: String(activeOnly),
      });
      if (search) params.set("search", search);
      const data = await api(`/api/price-catalog?${params.toString()}`);
      setItems(data || []);
    } catch (err) {
      setError(err.message || "No se pudieron cargar los precios.");
    } finally {
      setLoading(false);
    }
  }, [search, activeOnly]);

  useEffect(() => {
    load();
  }, [load]);

  async function importCatalog(source) {
    setImporting(source);
    setError("");
    setSuccess("");
    try {
      const result = await api("/api/price-catalog/import", {
        method: "POST",
        body: JSON.stringify({ source }),
      });
      setSuccess(result.message || "Catálogo actualizado.");
      await load();
    } catch (err) {
      setError(err.message || "No se pudo importar al catálogo.");
    } finally {
      setImporting("");
    }
  }

  function openCreate() {
    setSuccess("");
    setEditing(null);
    setForm({
      sku: "", name: "", description: "", unit: "unidad",
      cost_price: "", sale_price: "", category: "", supplier_name: "", active: true,
    });
    setShowForm(true);
  }

  function openEdit(item) {
    setEditing(item);
    setForm({
      sku: item.sku, name: item.name, description: item.description || "",
      unit: item.unit, cost_price: item.cost_price, sale_price: item.sale_price,
      category: item.category || "", supplier_name: item.supplier_name || "",
      active: item.active,
    });
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditing(null);
    setForm({
      sku: "", name: "", description: "", unit: "unidad",
      cost_price: "", sale_price: "", category: "", supplier_name: "", active: true,
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const body = {
        sku: form.sku,
        name: form.name,
        description: form.description,
        unit: form.unit,
        cost_price: Number(form.cost_price || 0),
        sale_price: Number(form.sale_price || 0),
        category: form.category,
        supplier_name: form.supplier_name,
      };
      if (editing) {
        await api(`/api/price-catalog/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      } else {
        await api("/api/price-catalog", {
          method: "POST",
          body: JSON.stringify(body),
        });
      }
      closeForm();
      setPending(false);
      load();
    } catch (err) {
      setError(err.message || "No se pudo guardar el ítem.");
      setPending(false);
    }
  }

  async function handleDelete(item) {
    if (!window.confirm(`¿Eliminar "${item.name}"?`)) return;
    setPending(true);
    setError("");
    try {
      await api(`/api/price-catalog/${item.id}`, { method: "DELETE" });
      setPending(false);
      load();
    } catch (err) {
      setError(err.message || "No se pudo eliminar el ítem.");
      setPending(false);
    }
  }

  const marginColor = (value) => {
    const n = Number(value || 0);
    if (n > 30) return "#15803d";
    if (n > 15) return "#16a34a";
    if (n > 0) return "#d97706";
    return "#b91c1c";
  };

  const filteredItems = items.filter((item) => {
    const term = search.toLowerCase();
    return (
      item.sku.toLowerCase().includes(term) ||
      item.name.toLowerCase().includes(term) ||
      (item.category || "").toLowerCase().includes(term)
    );
  });
  const isSearching = search.trim().length > 0;

  return (
    <div className="page-stack">
      <section className={`page-intro ${embedded ? "page-intro-embedded" : ""}`}>
        <div className={embedded ? "sr-only" : undefined}>
          <div className="eyebrow">Catálogo de precios</div>
          <h2>Tu catálogo, listo para comparar</h2>
          <p>
            Centraliza costos y precios de venta para ver tus márgenes y comparar cada factura
            contra tu propia referencia.
          </p>
        </div>
        {canManage ? (
          <button type="button" className="button primary" onClick={openCreate}>
            <PlusIcon /> Agregar producto
          </button>
        ) : null}
      </section>

      {error ? <div className="alert error">{error}</div> : null}
      {success ? <div className="alert success">{success}</div> : null}

      {loading ? (
        <div className="empty-state">Cargando catálogo…</div>
      ) : filteredItems.length === 0 && isSearching ? (
        <div className="empty-state-card">
          <div className="empty-state-icon">
            <SearchIcon />
          </div>
          <h3>No encontramos productos para “{search}”</h3>
          <p>Prueba con otro SKU, nombre o categoría.</p>
          <button type="button" className="button ghost" onClick={() => setSearch("")}>
            Limpiar búsqueda
          </button>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="empty-state-card catalog-empty">
          <div className="empty-state-icon">
            <PricesIcon />
          </div>
          <h3>Tu catálogo está listo para empezar</h3>
          <p>
            Importa el último costo de tus facturas aprobadas o carga productos de prueba para
            ver márgenes al instante.
          </p>
          <div className="empty-state-actions">
            {canOperate ? (
              <button type="button" className="button primary" onClick={onUpload}>
                <UploadIcon /> Subir primera factura
              </button>
            ) : null}
            {canManage ? (
              <>
                <button
                  type="button"
                  className="button ghost"
                  disabled={Boolean(importing)}
                  onClick={() => importCatalog("demo")}
                >
                  <SparkIcon />
                  {importing === "demo" ? "Cargando..." : "Cargar datos de demostración"}
                </button>
                <button
                  type="button"
                  className="button ghost"
                  disabled={Boolean(importing)}
                  onClick={() => importCatalog("approved")}
                >
                  <DocumentsIcon />
                  {importing === "approved" ? "Importando..." : "Importar facturas aprobadas"}
                </button>
                <button
                  type="button"
                  className="button ghost"
                  disabled={Boolean(importing)}
                  onClick={openCreate}
                >
                  <PlusIcon /> Agregar manualmente
                </button>
              </>
            ) : null}
          </div>
          {!canManage ? (
            <p className="muted small">
              Pide a un administrador que cargue productos de prueba o importe tus facturas aprobadas.
            </p>
          ) : null}
        </div>
      ) : (
        <div className="card">
          <div className="table-toolbar">
            <div className="card-head">
              <div>
                <h2>Productos del catálogo</h2>
                <p>{filteredItems.length} producto(s) registrado(s).</p>
              </div>
            </div>
            <label className="search-input">
              <SearchIcon />
              <input
                type="search"
                placeholder="Buscar por SKU, nombre o categoría…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
            <label className="page-size">
              <span>Mostrar</span>
              <select
                value={activeOnly ? "activos" : "todos"}
                onChange={(event) => setActiveOnly(event.target.value === "activos")}
              >
                <option value="activos">Solo activos</option>
                <option value="todos">Todos</option>
              </select>
            </label>
          </div>

          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Producto</th>
                  <th>Categoría</th>
                  <th>Costo</th>
                  <th>Venta</th>
                  <th>Margen</th>
                  <th>Proveedor</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => (
                  <tr key={item.id}>
                    <td className="mono">{item.sku}</td>
                    <td>
                      <strong>{item.name}</strong>
                      {item.description ? <div className="muted small">{item.description}</div> : null}
                    </td>
                    <td>{item.category || "—"}</td>
                    <td className="mono">{formatMoney(item.cost_price, "CLP")}</td>
                    <td className="mono">{formatMoney(item.sale_price, "CLP")}</td>
                    <td>
                      <span
                        className={`badge margin-${item.margin_pct > 0 ? "positive" : item.margin_pct < 0 ? "negative" : "neutral"}`}
                        style={{ color: marginColor(item.margin_pct) }}
                      >
                        {formatNumber(item.margin_pct, 1)}%
                      </span>
                    </td>
                    <td>{item.supplier_name || "—"}{item.supplier_name && item.supplier_name.toLowerCase().includes("demo") && <span className="badge badge-demo">DEMO</span>}</td>
                    <td>
                      <span className={`badge ${item.active ? "status-active" : "status-inactive"}`}>
                        {item.active ? "Activo" : "Inactivo"}
                      </span>
                    </td>
                    <td>
                      <div className="table-actions">
                        {canManage ? (
                          <div>
                            <button
                              type="button"
                              className="button ghost icon-only"
                              onClick={() => openEdit(item)}
                              title="Editar"
                            >
                              <EditIcon />
                            </button>
                            <button
                              type="button"
                              className="button ghost icon-only danger"
                              onClick={() => handleDelete(item)}
                              title="Eliminar"
                            >
                              <TrashIcon />
                            </button>
                          </div>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showForm && (
        <div className="modal-overlay" onClick={closeForm}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-head">
              <h3>{editing ? "Editar producto" : "Nuevo producto"}</h3>
              <button type="button" className="icon-button" onClick={closeForm}>
                <CheckIcon />
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {error && <div className="alert error">{error}</div>}
                <label className="form-field">
                  <span>SKU *</span>
                  <input
                    type="text"
                    value={form.sku}
                    onChange={(event) => setForm((f) => ({ ...f, sku: event.target.value }))}
                    placeholder="Ej: TORN-001"
                    disabled={pending}
                    required
                    autoFocus
                  />
                </label>
                <label className="form-field">
                  <span>Nombre *</span>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(event) => setForm((f) => ({ ...f, name: event.target.value }))}
                    placeholder="Ej: Tornillo acero inoxidable 6mm"
                    disabled={pending}
                    required
                  />
                </label>
                <label className="form-field">
                  <span>Descripción</span>
                  <input
                    type="text"
                    value={form.description}
                    onChange={(event) => setForm((f) => ({ ...f, description: event.target.value }))}
                    placeholder="Descripción opcional"
                    disabled={pending}
                  />
                </label>
                <label className="form-field">
                  <span>Unidad</span>
                  <input
                    type="text"
                    value={form.unit}
                    onChange={(event) => setForm((f) => ({ ...f, unit: event.target.value }))}
                    placeholder="unidad"
                    disabled={pending}
                  />
                </label>
                <label className="form-field">
                  <span>Categoría</span>
                  <input
                    type="text"
                    value={form.category}
                    onChange={(event) => setForm((f) => ({ ...f, category: event.target.value }))}
                    placeholder="Ej: Tornillería"
                    disabled={pending}
                  />
                </label>
                <label className="form-field">
                  <span>Proveedor</span>
                  <input
                    type="text"
                    value={form.supplier_name}
                    onChange={(event) => setForm((f) => ({ ...f, supplier_name: event.target.value }))}
                    placeholder="Ej: Ferretería del Norte"
                    disabled={pending}
                  />
                </label>
                <div className="form-grid">
                  <label className="form-field">
                    <span>Precio de costo *</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={form.cost_price}
                      onChange={(event) => setForm((f) => ({ ...f, cost_price: event.target.value }))}
                      placeholder="0.00"
                      disabled={pending}
                      required
                    />
                  </label>
                  <label className="form-field">
                    <span>Precio de venta *</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={form.sale_price}
                      onChange={(event) => setForm((f) => ({ ...f, sale_price: event.target.value }))}
                      placeholder="0.00"
                      disabled={pending}
                      required
                    />
                  </label>
                </div>
                <label className="form-field checkbox-field">
                  <input
                    type="checkbox"
                    checked={form.active}
                    onChange={(event) => setForm((f) => ({ ...f, active: event.target.checked }))}
                    disabled={pending}
                  />
                  <span>Producto activo</span>
                </label>
              </div>
              <div className="modal-actions">
                <button type="button" className="button ghost" onClick={closeForm} disabled={pending}>
                  Cancelar
                </button>
                <button type="submit" className="button primary" disabled={pending}>
                  {pending ? "Guardando…" : (editing ? "Actualizar" : "Crear producto")}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
