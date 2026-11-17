const API_URL = import.meta.env.VITE_API_URL || "";

function errorMessage(data, status) {
  if (!data) return `Error ${status}`;
  if (typeof data.error === "string") return data.error;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail.map((item) => item.msg || "Dato inválido").join(", ");
  }
  return `Error ${status}`;
}

export async function api(path, options = {}) {
  const { timeoutMs, ...fetchOptions } = options;
  const headers = { ...(fetchOptions.headers || {}) };
  const isFormData = fetchOptions.body instanceof FormData;
  if (fetchOptions.body && !isFormData) {
    headers["Content-Type"] = "application/json";
  }

  const controller = timeoutMs ? new AbortController() : null;
  const timer = timeoutMs
    ? window.setTimeout(() => controller.abort(), timeoutMs)
    : null;

  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      credentials: "include",
      ...fetchOptions,
      headers,
      signal: controller ? controller.signal : fetchOptions.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      const timeoutError = new Error(
        "La operación tardó demasiado. Revisa tu conexión e inténtalo nuevamente."
      );
      timeoutError.code = "timeout";
      throw timeoutError;
    }
    throw error;
  } finally {
    if (timer) window.clearTimeout(timer);
  }

  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const error = new Error(errorMessage(data, response.status));
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

async function raw(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    ...options,
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : null;
    const error = new Error(errorMessage(data, response.status));
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return response.blob();
}

api.raw = raw;

export async function downloadFile(path, filename, options = {}) {
  const blob = await raw(path, options);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
  return blob;
}

export function googleLoginUrl() {
  return `${API_URL}/api/auth/google`;
}

export default API_URL;
