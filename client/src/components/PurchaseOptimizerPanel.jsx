import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { formatMoney } from "../lib/format";
import { PlusIcon, PricesIcon, SearchIcon, TrashIcon } from "./Icons";

export default function PurchaseOptimizerPanel() {
  const [catalog, setCatalog] = useState(null);
  const [selected, setSelected] = useState("");
  const [cart, setCart] = useState([]);
  const [settings, setSettings] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setCatalog(await api("/api/leaks/comparator?limit=100"));
    } catch (err) {
      setError(err.message || "No se pudo cargar el comparador.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const items = catalog?.items || [];
  const currency = catalog?.currency || "CLP";

  const suppliers = useMemo(() => {
    const names = new Set();
    for (const line of cart) {
      const match = items.find((item) => (item.sku || item.product) === line.key);
      for (const supplier of match?.suppliers || []) names.add(supplier.name);
    }
    return Array.from(names).sort();
  }, [cart, items]);

  const supplierIsDemo = useMemo(() => {
    const map = {};
    for (const name of suppliers) {
      map[name] = name.toLowerCase().includes("demo");
    }
    return map;
  }, [suppliers]);

  function addProduct() {
    const match = items.find((item) => (item.sku || item.product) === selected);
    if (!match || cart.some((line) => line.key === (match.sku || match.product))) return;
    setCart((current) => [
      ...current,
      {
        key: match.sku || match.product,
        product: match.product,
        sku: match.sku,
        unit: match.unit,
        quantity: 1,
      },
    ]);
    setSelected(match.sku || match.product);
    setResult(null);
  }

  function updateQuantity(key, quantity) {
    setCart((current) =>
      current.map((line) => (line.key === key ? { ...line, quantity: Number(quantity) || 1 } : line)),
    );
    setResult(null);
  }

  function removeLine(key) {
    setCart((current) => current.filter((line) => line.key !== key));
    setResult(null);
  }

  function updateSetting(supplier, field, value) {
    setSettings((current) => ({
      ...current,
      [supplier]: { ...(current[supplier] || {}), [field]: Number(value) || 0 },
    }));
    setResult(null);
  }

  async function optimize() {
    if (!cart.length) return;
    setBusy(true);
    setError("");
    try {
      const freight_by_supplier = {};
      const min_order_by_supplier = {};
      for (const supplier of suppliers) {
        const row = settings[supplier] || {};
        if (row.freight) freight_by_supplier[supplier] = row.freight;
        if (row.min_order) min_order_by_supplier[supplier] = row.min_order;
      }
      const data = await api("/api/leaks/optimal-purchase", {
        method: "POST",
        body: JSON.stringify({
          items: cart.map((line) => ({
            sku: line.sku,
            product: line.product,
            quantity: line.quantity,
          })),
          currency,
          freight_by_supplier,
          min_order_by_supplier,
        }),
      });
      setResult(data);
    } catch (err) {
      setError(err.message || "No se pudo calcular la compra óptima.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="card">
        <div className="card-head">
          <div>
            <h2>Compra óptima por proveedor</h2>
            <p>
              Arma tu reposición y deja que NEXORA elija el proveedor más conveniente por ítem,
              considerando flete y monto mínimo.
            </p>
          </div>
        </div>

        {error ? <div className="alert error">{error}</div> : null}

        <div className="optimizer-add">
          <label className="search-field">
            <SearchIcon />
            <select value={selected} onChange={(event) => setSelected(event.target.value)}>
              <option value="">Selecciona un producto…</option>
              {items.map((item) => (
                <option key={item.sku || item.product} value={item.sku || item.product}>
                  {item.product} · {item.unit}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="button primary" onClick={addProduct} disabled={!selected}>
            <PlusIcon /> Agregar
          </button>
        </div>

        {loading && !catalog ? <p className="muted small">Cargando precios…</p> : null}

        {cart.length ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Unidad</th>
                  <th className="right">Cantidad</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {cart.map((line) => (
                  <tr key={line.key}>
                    <td>
                      <strong>{line.product}</strong>
                      <div className="muted small">{line.sku || "Sin SKU"}</div>
                    </td>
                    <td>{line.unit}</td>
                    <td className="right">
                      <input
                        className="quantity-input"
                        type="number"
                        min="1"
                        value={line.quantity}
                        onChange={(event) => updateQuantity(line.key, event.target.value)}
                      />
                    </td>
                    <td>
                      <button type="button" className="icon-button" onClick={() => removeLine(line.key)}>
                        <TrashIcon />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="audit-empty">
            <PricesIcon />
            <h3>Tu carrito está vacío</h3>
            <p>Agrega productos para calcular a qué proveedor conviene comprar cada uno.</p>
          </div>
        )}

        {suppliers.length ? (
          <div className="optimizer-settings">
            <h3>Costos logísticos por proveedor</h3>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Proveedor</th>
                    <th className="right">Flete</th>
                    <th className="right">Monto mínimo</th>
                  </tr>
                </thead>
                <tbody>
{suppliers.map((supplier) => (
                    <tr key={supplier}>
                      <td>{supplier}{supplierIsDemo[supplier] && <span className="badge badge-demo">DEMO</span>}</td>
                      <td className="right">
                        <input
                          className="quantity-input"
                          type="number"
                          min="0"
                          value={settings[supplier]?.freight ?? ""}
                          onChange={(event) => updateSetting(supplier, "freight", event.target.value)}
                          disabled={supplierIsDemo[supplier]}
                        />
                      </td>
                      <td className="right">
                        <input
                          className="quantity-input"
                          type="number"
                          value={settings[supplier]?.min_order ?? ""}
                          onChange={(event) => updateSetting(supplier, "min_order", event.target.value)}
                          disabled={supplierIsDemo[supplier]}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        <div className="optimizer-actions">
          <button type="button" className="button primary" disabled={!cart.length || busy} onClick={optimize}>
            {busy ? "Calculando…" : "Calcular compra óptima"}
          </button>
        </div>
      </section>

      {result ? (
        <section className="card">
          <div className="card-head">
            <div>
              <h2>Resultado</h2>
              <p>
                {result.suppliers.length} proveedor(es) · flete{" "}
                {formatMoney(result.total_freight, result.currency)}
              </p>
            </div>
            <span className="badge">{formatMoney(result.total_purchase, result.currency)}</span>
          </div>

          {result.warnings?.length ? (
            <div className="alert warning">{result.warnings.join(" ")}</div>
          ) : null}

          <div className="audit-suppliers">
            {result.suppliers.map((supplier) => (
              <div key={supplier.supplier} className="audit-supplier">
                <div className="audit-supplier-head">
                  <div>
                    <strong>{supplier.supplier}</strong>
                    <div className="muted small">
                      {supplier.meets_minimum
                        ? "Cumple monto mínimo"
                        : `Mínimo ${formatMoney(supplier.minimum_order, result.currency)}`}
                    </div>
                  </div>
                  <div className="audit-supplier-total">
                    <span className="muted small">Subtotal + flete</span>
                    <strong>
                      {formatMoney(supplier.subtotal + supplier.freight, result.currency)}
                    </strong>
                  </div>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Producto</th>
                      <th className="right">Cantidad</th>
                      <th className="right">Precio unitario</th>
                      <th className="right">Subtotal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.lines
                      .filter((line) => line.supplier === supplier.supplier)
                      .map((line) => (
                        <tr key={`${supplier.supplier}-${line.product}`}>
                          <td>{line.product}</td>
                          <td className="right">{line.quantity}</td>
                          <td className="right mono">
                            {formatMoney(line.unit_price, result.currency)}
                          </td>
                          <td className="right mono">
                            {formatMoney(line.subtotal, result.currency)}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>

          <div className="verified-summary">
            <div>
              <span>Costo total optimizado</span>
              <strong>{formatMoney(result.total_purchase, result.currency)}</strong>
            </div>
            <div>
              <span>Mejor proveedor único</span>
              <strong>{formatMoney(result.cheapest_single_supplier_total, result.currency)}</strong>
            </div>
            <div>
              <span>Ahorro vs proveedor único</span>
              <strong>{formatMoney(result.savings_vs_single_supplier, result.currency)}</strong>
            </div>
          </div>
          {result.missing?.length ? (
            <p className="muted small">
              Sin costo registrado: {result.missing.map((line) => line.product).join(", ")}
            </p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
