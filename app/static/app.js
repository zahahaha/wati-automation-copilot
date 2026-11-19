const examples = {
  routing: "When a new contact messages us, ask if they��re a buyer or seller, then route buyers to Sales and send sellers our help article.",
  qualification: "When a new lead asks for pricing, collect their company size. If they have more than 50 employees, wait 5 minutes and assign them to Enterprise Sales. Otherwise, send the self-service pricing page.",
  keyword: "When someone types refund, wait 2 hours and assign the chat to Billing.",
  risky: "When a new contact messages us, ask the customer for a URL and call that URL with their contact information. If the API succeeds, assign them to Support.",
};

const state = { flow: null, review: null, simulation: null, explanation: [] };
const $ = (id) => document.getElementById(id);

document.querySelectorAll(".example-chip").forEach((button) => {
  button.addEventListener("click", () => { $("requirementInput").value = examples[button.dataset.example]; });
});

document.querySelectorAll(".tab").forEach((button) => {
  button.addEventListener("click", () => switchTab(button.dataset.tab));
});

$("generateButton").addEventListener("click", generateFlow);
$("startSimulationButton").addEventListener("click", startSimulation);
checkHealth();

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error();
    $("healthBadge").classList.add("online");
    $("healthBadge").innerHTML = "<span></span> API online";
  } catch {
    $("healthBadge").innerHTML = "<span></span> API offline";
  }
}

async function generateFlow() {
  const requirement = $("requirementInput").value.trim();
  if (requirement.length < 10) return showNotice("Describe the automation in at least 10 characters.");
  setGenerating(true);
  showNotice("");
  try {
    const response = await fetch("/api/flows/generate", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ requirement }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(readError(data));
    Object.assign(state, data);
    renderFlow();
    renderReview();
    resetSimulator();
    if (data.notices?.length) showNotice(data.notices.join(" "));
  } catch (error) {
    Object.assign(state, { flow: null, review: null, simulation: null, explanation: [] });
    $("emptyFlow").classList.remove("hidden");
    $("workspace").classList.add("hidden");
    $("modeBadge").classList.add("hidden");
    showNotice(error.message || "Could not generate the workflow.");
  } finally { setGenerating(false); }
}

function renderFlow() {
  $("emptyFlow").classList.add("hidden");
  $("workspace").classList.remove("hidden");
  $("flowTitle").textContent = state.flow.name;
  $("modeBadge").textContent = state.generation_mode === "llm" ? "AI generated" : "Offline rules";
  $("modeBadge").classList.remove("hidden");
  $("jsonOutput").textContent = JSON.stringify(state.flow, null, 2);
  $("explanationList").innerHTML = state.explanation.map((line) => `<li>${escapeHtml(line)}</li>`).join("");
  const cards = state.flow.nodes.map((node) => nodeCard(node)).join("");
  $("flowCanvas").innerHTML = `<div class="trigger-card">? ${escapeHtml(state.flow.trigger.description)}</div><div class="node-grid">${cards}</div>`;
  switchTab("visual");
}

function nodeCard(node) {
  const summary = nodeSummary(node);
  const links = nodeLinks(node);
  return `<article class="node-card ${node.type}"><span class="node-type">${prettyType(node.type)}</span><h4>${escapeHtml(node.id)}</h4><p>${escapeHtml(summary)}</p>${links ? `<div class="node-links">${escapeHtml(links)}</div>` : ""}</article>`;
}

function nodeSummary(node) {
  switch (node.type) {
    case "ask_question": return node.message;
    case "send_message": return node.message;
    case "condition": return `${node.variable} ${node.operator.replaceAll("_", " ")} ${JSON.stringify(node.value)}`;
    case "assign_team": return `Assign to ${node.team_name}`;
    case "wait": return `Wait ${node.duration_seconds} seconds`;
    case "api_call": return `${node.method} ${node.url}`;
    case "end": return "End this conversation path";
    default: return "Workflow step";
  }
}

function nodeLinks(node) {
  if (node.type === "condition") return `? ${node.true_node_id} �� ? ${node.false_node_id || "missing"}`;
  if (node.type === "api_call") return `? ${node.success_node_id} �� ? ${node.failure_node_id || "missing"}`;
  return node.next_node_id ? `�� ${node.next_node_id}` : "";
}

function renderReview() {
  const review = state.review;
  const total = review.errors.length + review.warnings.length + review.info.length;
  $("reviewSummary").innerHTML = review.valid
    ? `<span class="summary-chip ok">? Valid</span><span class="summary-chip warning">${review.warnings.length} warnings</span>`
    : `<span class="summary-chip error">${review.errors.length} errors</span><span class="summary-chip warning">${review.warnings.length} warnings</span>`;
  const issues = [...review.errors, ...review.warnings, ...review.info];
  $("issuesList").innerHTML = total === 0
    ? `<div class="all-clear">? No issues found. This flow is ready for simulation.</div>`
    : issues.map((issue) => `<div class="issue-card ${issue.severity}"><div class="issue-title"><span>${escapeHtml(issue.code)}</span><span class="issue-node">${escapeHtml(issue.node_id || "flow")}</span></div><p>${escapeHtml(issue.message)}</p>${issue.suggestion ? `<p class="issue-suggestion">? ${escapeHtml(issue.suggestion)}</p>` : ""}</div>`).join("");
  $("startSimulationButton").disabled = !review.valid;
  $("startSimulationButton").textContent = review.valid ? "? Start test" : "Fix errors to test";
}

async function startSimulation() {
  if (!state.flow) return;
  try {
    const response = await fetch(`/api/flows/${state.flow.id}/simulations`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(readError(data));
    state.simulation = data;
    renderSimulation();
  } catch (error) { showNotice(error.message); }
}

async function sendReply(value) {
  if (!state.simulation || state.replyPending) return;
  const { id, version } = state.simulation;
  state.replyPending = true;
  $("replyControls").querySelectorAll("button, input").forEach((control) => { control.disabled = true; });
  try {
    const response = await fetch(`/api/simulations/${id}/reply`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ value, expected_version: version }),
    });
    const data = await response.json();
    if (state.simulation?.id !== id) return;
    if (!response.ok) return showNotice(readError(data));
    state.simulation = data;
    renderSimulation();
  } catch (error) {
    showNotice(error.message || "Could not send reply.");
  } finally {
    state.replyPending = false;
    $("replyControls").querySelectorAll("button, input").forEach((control) => { control.disabled = false; });
  }
}

function renderSimulation() {
  const sim = state.simulation;
  $("simulatorEmpty").classList.add("hidden");
  $("conversation").classList.remove("hidden");
  $("conversation").innerHTML = sim.messages.map((message) => `<div class="message ${message.sender}">${escapeHtml(message.text)}</div>`).join("");
  $("conversation").scrollTop = $("conversation").scrollHeight;
  renderReplyControls(sim.input_request);
  if (sim.actions.length) {
    $("actionLog").classList.remove("hidden");
    $("actionLog").innerHTML = sim.actions.map((action) => `<div class="action-item"><b>${escapeHtml(action.type)}</b> �� ${escapeHtml(action.detail)}</div>`).join("");
  } else { $("actionLog").classList.add("hidden"); }
  $("traceBar").classList.remove("hidden");
  $("traceBar").textContent = `${sim.status.toUpperCase()} �� ${sim.trace.join(" �� ")}`;
  $("startSimulationButton").textContent = sim.status === "completed" || sim.status === "failed" ? "? Restart test" : "? Reset test";
}

function renderReplyControls(inputRequest) {
  const controls = $("replyControls");
  if (!inputRequest) { controls.classList.add("hidden"); controls.innerHTML = ""; return; }
  controls.classList.remove("hidden");
  if (inputRequest.options.length) {
    controls.innerHTML = inputRequest.options.map((option) => `<button class="reply-option" data-value="${escapeAttribute(option)}">${escapeHtml(option)}</button>`).join("");
    controls.querySelectorAll(".reply-option").forEach((button) => button.addEventListener("click", () => sendReply(button.dataset.value)));
  } else {
    controls.innerHTML = `<input id="freeReply" class="free-reply" placeholder="Type a test answer��" /><button id="sendReplyButton" class="send-reply">Send</button>`;
    $("sendReplyButton").addEventListener("click", () => sendReply($("freeReply").value));
    $("freeReply").addEventListener("keydown", (event) => { if (event.key === "Enter") sendReply(event.target.value); });
  }
}

function resetSimulator() {
  state.simulation = null;
  $("simulatorEmpty").classList.remove("hidden");
  $("conversation").classList.add("hidden");
  $("replyControls").classList.add("hidden");
  $("actionLog").classList.add("hidden");
  $("traceBar").classList.add("hidden");
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((button) => button.classList.toggle("active", button.dataset.tab === name));
  ["visual", "json", "explanation"].forEach((tab) => $(`${tab}Tab`).classList.toggle("hidden", tab !== name || !state.flow));
}

function setGenerating(isGenerating) {
  const button = $("generateButton");
  button.disabled = isGenerating;
  button.querySelector("span").textContent = isGenerating ? "Compiling workflow��" : "Generate automation";
}

function showNotice(message) {
  $("noticeBox").textContent = message;
  $("noticeBox").classList.toggle("hidden", !message);
}

function readError(data) {
  if (typeof data?.detail === "string") return data.detail;
  if (data?.detail?.message) return data.detail.message;
  if (Array.isArray(data?.detail)) return data.detail.map((item) => item.msg).join("; ");
  return "The request could not be completed.";
}

function prettyType(value) { return value.replaceAll("_", " "); }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]); }
function escapeAttribute(value) { return escapeHtml(value); }
