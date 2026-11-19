// Shared helpers for the grievance router UI.
const $ = id => document.getElementById(id);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) node.append(child);
  return node;
}

const pretty = value => String(value ?? '—').replaceAll('_', ' ');

function validationMessage(detail) {
  if (typeof detail === 'string') return detail;
  const labels = {
    entity_complaint_date: 'Complaint date', entity_response_date: 'Response date', incident_date: 'Incident date',
    complaint_text: 'Complaint', entity_name: 'Entity name', amount_involved_inr: 'Amount',
  };
  if (Array.isArray(detail)) return detail.map(error => {
    const field = (error.loc || []).filter(part => part !== 'body').pop();
    const label = labels[field] || field;
    return (label ? label + ': ' : '') + (error.msg || 'Check your input').replace(/^Value error, /, '');
  }).join('\n');
  return 'Unable to submit the complaint. Please check your input and try again.';
}

async function json(url, options) {
  const response = await fetch(url, options);
  let body = {};
  try { body = await response.json(); } catch { /* non-JSON error body */ }
  if (!response.ok) {
    const error = Error(validationMessage(body.detail) || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}

async function refreshHealth() {
  const pill = $('health-pill');
  if (!pill) return;
  const [dot, label] = [pill.querySelector('.dot'), pill.querySelector('span:last-child')];
  try {
    const response = await fetch('/health');
    const health = await response.json();
    const ok = health.status === 'healthy';
    dot.className = 'dot ' + (ok ? 'ok' : 'warn');
    label.textContent = ok ? 'All systems operational' : 'Degraded: ' + (health.worker === false ? 'worker offline' : 'check services');
    if (health.index) document.querySelectorAll('[data-chunks]').forEach(n => n.textContent = health.index.chunks);
  } catch {
    dot.className = 'dot bad';
    label.textContent = 'API unreachable';
  }
}

function storage(key, value) {
  try {
    if (value === undefined) return JSON.parse(sessionStorage.getItem(key) || 'null');
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch { return null; }
}

document.addEventListener('DOMContentLoaded', () => {
  refreshHealth();
  setInterval(refreshHealth, 15000);
});
