const messages = document.getElementById("messages");
const input = document.getElementById("messageInput");
const form = document.getElementById("chatForm");

let customerId = localStorage.getItem("dealerCustomerId");
if (!customerId) {
  customerId = "web-" + crypto.randomUUID();
  localStorage.setItem("dealerCustomerId", customerId);
}

function addMessage(text, type) {
  const el = document.createElement("div");
  el.className = `message ${type}`;
  el.textContent = text;
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage(text) {
  addMessage(text, "user");
  input.value = "";
  input.disabled = true;

  try {
    const res = await fetch("/api/v1/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        customer_id: customerId,
        channel: "web",
        message: text
      })
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const data = await res.json();
    addMessage(data.response, "agent");

    if (data.status === "handoff") {
      addMessage("A dealership colleague can continue from this handoff.", "system");
    }
  } catch (err) {
    addMessage("The service assistant is temporarily unavailable. Please try again.", "system");
    console.error(err);
  } finally {
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (text) sendMessage(text);
});

document.querySelectorAll("[data-msg]").forEach(btn => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.msg));
});
