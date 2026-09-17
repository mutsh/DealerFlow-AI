const keyInput = document.getElementById("managerKey");
const statusText = document.getElementById("statusText");

const storedKey = sessionStorage.getItem("managerKey");
if (storedKey) keyInput.value = storedKey;

function badge(status) {
  const klass = status === "confirmed" ? "ok" :
                status === "cancelled" ? "danger" : "warn";
  return `<span class="badge ${klass}">${status}</span>`;
}

async function api(path) {
  const key = keyInput.value.trim();
  if (!key) throw new Error("Enter the manager API key.");

  sessionStorage.setItem("managerKey", key);

  const res = await fetch(path, {
    headers: {"X-Manager-Key": key}
  });

  if (!res.ok) {
    if (res.status === 401) throw new Error("Invalid manager API key.");
    throw new Error(`Request failed: ${res.status}`);
  }
  return res.json();
}

async function loadDashboard() {
  statusText.textContent = "Loading…";
  try {
    const [summary, bookings, handoffs] = await Promise.all([
      api("/api/v1/manager/summary"),
      api("/api/v1/manager/bookings"),
      api("/api/v1/manager/handoffs")
    ]);

    document.getElementById("mTotal").textContent = summary.bookings_total;
    document.getElementById("mConfirmed").textContent = summary.confirmed_bookings;
    document.getElementById("mCancelled").textContent = summary.cancelled_bookings;
    document.getElementById("mHandoffs").textContent = summary.handoffs_total;
    document.getElementById("mOpen").textContent = summary.open_handoffs;

    const bookingRows = document.getElementById("bookingRows");
    bookingRows.innerHTML = bookings.bookings.length
      ? bookings.bookings.map(b => `
          <tr>
            <td>${b.booking_id}</td>
            <td>${b.customer_id}</td>
            <td>${b.service.replaceAll("_", " ")}</td>
            <td>${b.appointment_date}</td>
            <td>${b.appointment_time}</td>
            <td>${badge(b.status)}</td>
          </tr>`).join("")
      : `<tr><td colspan="6" class="empty">No bookings yet.</td></tr>`;

    const handoffRows = document.getElementById("handoffRows");
    handoffRows.innerHTML = handoffs.handoffs.length
      ? handoffs.handoffs.map(h => `
          <tr>
            <td>${h.handoff_id}</td>
            <td>${h.customer_id}</td>
            <td>${h.reason}</td>
            <td>${badge(h.status)}</td>
            <td>${h.created_at}</td>
          </tr>`).join("")
      : `<tr><td colspan="5" class="empty">No handoffs yet.</td></tr>`;

    statusText.textContent = "Updated.";
  } catch (err) {
    statusText.textContent = err.message;
  }
}

document.getElementById("loadBtn").addEventListener("click", loadDashboard);
document.getElementById("refreshBtn").addEventListener("click", loadDashboard);
