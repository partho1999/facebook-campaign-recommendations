const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

export async function getMe() {
  const access = localStorage.getItem("access");

  const res = await fetch(`${API_BASE_URL}/auth/me/`, {
    method: "GET",
    headers: {
      "Authorization": `Bearer ${access}`,
      "Content-Type": "application/json",
    },
  });

  if (res.status === 401) {
    // Access expired → refresh token
    const refresh = localStorage.getItem("refresh");
    const refreshRes = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });

    if (refreshRes.ok) {
      const refreshData = await refreshRes.json();
      localStorage.setItem("access", refreshData.access);
      return getMe(); // retry with new token
    }
  }

  return res.json();
}

// Generic authenticated fetch with automatic token refresh and retry
export async function authFetch(url, options = {}, retry = true) {
  const access = localStorage.getItem("access");

  const headers = {
    ...(options.headers || {}),
    "Authorization": `Bearer ${access}`,
  };

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401 && retry) {
    const refresh = localStorage.getItem("refresh");
    const refreshRes = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });

    if (refreshRes.ok) {
      const refreshData = await refreshRes.json();
      localStorage.setItem("access", refreshData.access);
      return authFetch(url, options, false);
    }
  }

  return res;
}

export async function updateAdsetStatus(adset_id, is_active=false) {
  const access = localStorage.getItem("access");

  const res = await fetch(`${API_BASE_URL}/api/update-adset-status/`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${access}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ adset_id, is_active }),
  });

  if (res.status === 401) {
    // Access expired → refresh token
    const refresh = localStorage.getItem("refresh");
    const refreshRes = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
    });

    if (refreshRes.ok) {
      const refreshData = await refreshRes.json();
      localStorage.setItem("access", refreshData.access);
      return updateAdsetStatus(adset_id, is_active); // retry with new token
    }
  }

  if (!res.ok) {
    // Handle other errors
    const errorData = await res.json();
    throw new Error(errorData.error || "Failed to update adset status");
  }

  return res.json(); // Returns the updated adset object
}

  