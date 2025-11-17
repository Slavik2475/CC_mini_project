const apiClient = {
  async get(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`GET ${path} failed`);
    return response.json();
  },
  async post(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`POST ${path} failed`);
    return response.json();
  },
  async put(path, body) {
    const response = await fetch(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`PUT ${path} failed`);
    return response.json();
  },
  async delete(path) {
    const response = await fetch(path, { method: "DELETE" });
    if (!response.ok) throw new Error(`DELETE ${path} failed`);
    return response.json();
  },
};

const state = {
  categories: [],
  chart: null,
  profile: null,
};

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = Number(value).toFixed(2);
  }
}

function populateCategorySelects() {
  const transactionSelect = document.getElementById("transaction-category");
  const budgetSelect = document.getElementById("budget-category");
  if (!transactionSelect || !budgetSelect) return;

  transactionSelect.innerHTML = "";
  budgetSelect.innerHTML = '<option value="">Overall</option>';

  state.categories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category.id;
    option.textContent = `${category.name} (${category.type})`;

    transactionSelect.appendChild(option.cloneNode(true));
    budgetSelect.appendChild(option);
  });
}

function renderTransactions(transactions) {
  const tbody = document.getElementById("transactions-body");
  tbody.innerHTML = "";
  const template = document.getElementById("row-actions-template");

  transactions.forEach((transaction) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${transaction.transaction_date ?? "-"}</td>
      <td>${transaction.description ?? ""}</td>
      <td>${transaction.category_name ?? "-"}</td>
      <td>${transaction.type}</td>
      <td>${Number(transaction.amount).toFixed(2)}</td>
      <td></td>
    `;

    const actions = template.content.cloneNode(true);
    const deleteButton = actions.querySelector(".delete");
    deleteButton.addEventListener("click", async () => {
      await apiClient.delete(`/api/transactions/${transaction.id}`);
      await refreshData();
    });
    tr.lastElementChild.appendChild(actions);
    tbody.appendChild(tr);
  });
}

function renderBudgets(budgets) {
  const tbody = document.getElementById("budgets-body");
  tbody.innerHTML = "";
  const template = document.getElementById("row-actions-template");

  budgets.forEach((budget) => {
    const tr = document.createElement("tr");
    const categoryName = budget.category_name ?? "Overall";
    tr.innerHTML = `
      <td>${budget.month}/${budget.year}</td>
      <td>${categoryName}</td>
      <td>${Number(budget.limit_amount).toFixed(2)}</td>
      <td>${Number(budget.spent).toFixed(2)}</td>
      <td>${Number(budget.remaining).toFixed(2)}</td>
      <td></td>
    `;

    const actions = template.content.cloneNode(true);
    const deleteButton = actions.querySelector(".delete");
    deleteButton.addEventListener("click", async () => {
      await apiClient.delete(`/api/budgets/${budget.id}`);
      await refreshData();
    });
    tr.lastElementChild.appendChild(actions);
    tbody.appendChild(tr);
  });
}

function renderChart(byCategory) {
  const ctx = document.getElementById("category-chart").getContext("2d");
  const labels = byCategory.map((item) => `${item.category_name} (${item.type})`);
  const data = byCategory.map((item) => item.total);

  if (state.chart) {
    state.chart.destroy();
  }

  state.chart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Amount",
          data,
          backgroundColor: labels.map((label) =>
            label.includes("income") ? "#22c55e" : "#ef4444"
          ),
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
    },
  });
}

async function refreshData() {
  try {
    const [summary, transactions, budgets, profile] = await Promise.all([
      apiClient.get("/api/summary/monthly"),
      apiClient.get("/api/transactions"),
      apiClient.get("/api/budgets"),
      apiClient.get("/api/profile"),
    ]);

    setText("income-total", summary.total_income);
    setText("expense-total", summary.total_expense);
    setText("net-total", summary.net);
    renderChart(summary.by_category);
    renderTransactions(transactions);
    renderBudgets(summary.budgets);
    renderProfile(profile);

    document.getElementById("filter-month").value = summary.month;
    document.getElementById("filter-year").value = summary.year;
  } catch (error) {
    console.error(error);
    alert("Failed to load data. Check console for details.");
  }
}

async function initCategories() {
  state.categories = await apiClient.get("/api/categories");
  populateCategorySelects();
}

function renderProfile(profile) {
  state.profile = profile;
  const nameEl = document.getElementById("profile-name");
  const emailEl = document.getElementById("profile-email");
  const imgEl = document.getElementById("profile-photo");
  if (nameEl) nameEl.textContent = profile.name ?? "Demo User";
  if (emailEl) emailEl.textContent = profile.email ?? "demo@example.com";
  if (imgEl && profile.profile_photo_url) imgEl.src = profile.profile_photo_url;
}

function setupForms() {
  const transactionForm = document.getElementById("transaction-form");
  transactionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(transactionForm);
    const payload = Object.fromEntries(formData.entries());
    payload.amount = parseFloat(payload.amount);
    if (!payload.transaction_date) delete payload.transaction_date;
    if (!payload.category_id) payload.category_id = null;
    await apiClient.post("/api/transactions", payload);
    transactionForm.reset();
    await refreshData();
  });

  const budgetForm = document.getElementById("budget-form");
  budgetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(budgetForm);
    const payload = Object.fromEntries(formData.entries());
    payload.month = parseInt(payload.month, 10);
    payload.year = parseInt(payload.year, 10);
    payload.limit_amount = parseFloat(payload.limit_amount);
    if (!payload.category_id) payload.category_id = null;
    await apiClient.post("/api/budgets", payload);
    budgetForm.reset();
    await refreshData();
  });
}

function setupFilters() {
  document.getElementById("apply-filters").addEventListener("click", async () => {
    const month = document.getElementById("filter-month").value;
    const year = document.getElementById("filter-year").value;
    const params = new URLSearchParams();
    if (month) params.append("month", month);
    if (year) params.append("year", year);

    const summary = await apiClient.get(`/api/summary/monthly?${params}`);
    setText("income-total", summary.total_income);
    setText("expense-total", summary.total_expense);
    setText("net-total", summary.net);
    renderChart(summary.by_category);
    renderBudgets(summary.budgets);
  });

  document.getElementById("refresh-button").addEventListener("click", refreshData);
}

async function init() {
  await initCategories();
  setupForms();
  setupFilters();
  await refreshData();
}

window.addEventListener("DOMContentLoaded", init);
