export function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem('scinova_user') || '{}');
  } catch {
    return {};
  }
}

export function saveCurrentUser(user) {
  localStorage.setItem('scinova_user', JSON.stringify(user));
}

export function isAdmin(user = getCurrentUser()) {
  return user?.role === 'admin';
}

export function displayName(user = getCurrentUser()) {
  return user?.full_name || user?.username || 'User';
}

export function logout() {
  localStorage.removeItem('scinova_token');
  localStorage.removeItem('scinova_user');
  window.location.href = '/login';
}

export function apiErrorMessage(err, fallback = 'Request failed') {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || String(d)).join(', ');
  }
  return fallback;
}
