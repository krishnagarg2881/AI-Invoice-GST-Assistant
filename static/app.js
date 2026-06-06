// Global Variables
let currentInvoices = [];
let categoryChart = null;
let taxChart = null;
let appSettings = {};

// On Load
document.addEventListener("DOMContentLoaded", () => {
    // Navigation setup
    const navItems = document.querySelectorAll(".nav-menu .nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const pageId = item.getAttribute("data-page");
            navigateToPage(pageId);
        });
    });

    // File Selector upload setup
    const fileSelector = document.getElementById("file-selector");
    fileSelector.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFilesUpload(e.target.files);
        }
    });

    // Drag and Drop upload setup
    const dropZone = document.getElementById("drop-zone");
    if (dropZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('dragover'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('dragover'), false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                handleFilesUpload(files);
            }
        });
    }

    // Load Initial Data
    loadSettings();
    navigateToPage("dashboard");
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

// Navigation Router
function navigateToPage(pageId) {
    // Update active nav item
    document.querySelectorAll(".nav-menu .nav-item").forEach(item => {
        if (item.getAttribute("data-page") === pageId) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });

    // Update active view
    document.querySelectorAll(".page-view").forEach(view => {
        if (view.id === `view-${pageId}`) {
            view.classList.add("active");
        } else {
            view.classList.remove("active");
        }
    });

    // Page Specific Refresh
    if (pageId === "dashboard") {
        refreshDashboard();
    } else if (pageId === "invoices") {
        loadInvoicesList();
    } else if (pageId === "gst-reports") {
        generateGSTReport();
    } else if (pageId === "chat") {
        loadChatHistory();
    } else if (pageId === "settings") {
        refreshSettingsForm();
    }
}

// --- API Calls Helper ---
async function apiCall(endpoint, method = "GET", body = null) {
    const options = { method };
    if (body) {
        if (body instanceof FormData) {
            options.body = body;
        } else {
            options.headers = { "Content-Type": "application/json" };
            options.body = JSON.stringify(body);
        }
    }
    try {
        const response = await fetch(endpoint, options);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "API Call failed");
        }
        return await response.json();
    } catch (error) {
        console.error(`API Error on ${endpoint}:`, error);
        alert(`Error: ${error.message}`);
        return null;
    }
}

// --- Settings Section ---
async function loadSettings() {
    const settings = await apiCall("/api/settings");
    if (settings) {
        appSettings = settings;
        
        // Update Sidebar GSTIN tag
        const sidebarGstin = document.getElementById("sidebar-gstin");
        sidebarGstin.textContent = settings.business_gstin || "Not Configured";
        
        // Update chat AI model display status
        const chatMode = document.getElementById("chat-mode-indicator");
        if (settings.gemini_api_key_configured) {
            chatMode.textContent = "● Google Gemini Online";
            chatMode.style.color = "var(--color-primary)";
        } else if (settings.openai_api_key_configured) {
            chatMode.textContent = "● OpenAI Online";
            chatMode.style.color = "var(--color-secondary)";
        } else {
            chatMode.textContent = "● Local Demo Mode";
            chatMode.style.color = "var(--color-warning)";
        }
    }
}

function refreshSettingsForm() {
    if (appSettings) {
        document.getElementById("set-gstin").value = appSettings.business_gstin || "";
        document.getElementById("set-db-url").value = appSettings.database_url || "";
        
        const geminiStatus = document.getElementById("gemini-key-status");
        if (appSettings.gemini_api_key_configured) {
            geminiStatus.textContent = "Status: API Key Active (Securely Hidden)";
            geminiStatus.style.color = "var(--color-success)";
        } else {
            geminiStatus.textContent = "Status: Not configured. Runs in Local Demo Mode.";
            geminiStatus.style.color = "var(--text-muted)";
        }

        const openaiStatus = document.getElementById("openai-key-status");
        if (appSettings.openai_api_key_configured) {
            openaiStatus.textContent = "Status: API Key Active (Securely Hidden)";
            openaiStatus.style.color = "var(--color-success)";
        } else {
            openaiStatus.textContent = "Status: Not configured.";
            openaiStatus.style.color = "var(--text-muted)";
        }
    }
}

async function saveSettings(e) {
    e.preventDefault();
    const gstin = document.getElementById("set-gstin").value.trim().toUpperCase();
    const geminiKey = document.getElementById("set-gemini-key").value.trim();
    const openaiKey = document.getElementById("set-openai-key").value.trim();
    
    const body = {};
    if (gstin) body.business_gstin = gstin;
    if (geminiKey) body.gemini_api_key = geminiKey;
    if (openaiKey) body.openai_api_key = openaiKey;
    
    const updated = await apiCall("/api/settings", "POST", body);
    if (updated) {
        alert("Settings saved successfully!");
        appSettings = updated;
        // Clean fields
        document.getElementById("set-gemini-key").value = "";
        document.getElementById("set-openai-key").value = "";
        loadSettings();
        refreshSettingsForm();
    }
}

// --- File Upload Module ---
async function handleFilesUpload(files) {
    const progressContainer = document.getElementById("upload-progress-container");
    const progressBar = document.getElementById("upload-progress-bar");
    const statusLabel = document.getElementById("upload-status");
    
    progressContainer.style.display = "block";
    
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        statusLabel.textContent = `Uploading & Analyzing: "${file.name}" (File ${i+1} of ${files.length})...`;
        progressBar.style.width = "30%";
        
        const formData = new FormData();
        formData.append("file", file);
        
        progressBar.style.width = "60%";
        const res = await apiCall("/api/invoices/upload", "POST", formData);
        
        progressBar.style.width = "100%";
        if (res) {
            statusLabel.textContent = `Successfully processed: "${file.name}"!`;
            setTimeout(() => {
                progressContainer.style.display = "none";
                loadInvoicesList();
            }, 1500);
        } else {
            statusLabel.textContent = `Failed to process: "${file.name}".`;
            progressBar.style.backgroundColor = "var(--color-danger)";
        }
    }
}

// --- Dashboard Module ---
async function refreshDashboard() {
    const invoices = await apiCall("/api/invoices");
    if (!invoices) return;
    
    currentInvoices = invoices.filter(i => i.status === "processed");
    
    // Compute KPIs
    let totalSpend = 0;
    let totalTaxable = 0;
    let totalGst = 0;
    
    let categorySpend = {};
    let taxBreakdown = { CGST: 0, SGST: 0, IGST: 0 };
    
    currentInvoices.forEach(inv => {
        totalSpend += inv.total_amount;
        totalTaxable += inv.taxable_amount;
        totalGst += (inv.cgst + inv.sgst_utgst + inv.igst);
        
        // Category spend mapping
        const cat = inv.expense_category || "Others";
        categorySpend[cat] = (categorySpend[cat] || 0) + inv.total_amount;
        
        // Taxes split mapping
        taxBreakdown.CGST += inv.cgst;
        taxBreakdown.SGST += inv.sgst_utgst;
        taxBreakdown.IGST += inv.igst;
    });
    
    // Render KPIs
    document.getElementById("kpi-total-spend").textContent = formatINR(totalSpend);
    document.getElementById("kpi-taxable-value").textContent = formatINR(totalTaxable);
    document.getElementById("kpi-gst-claimed").textContent = formatINR(totalGst);
    document.getElementById("kpi-count-invoices").textContent = currentInvoices.length;
    
    // Render Recent Invoices List (Limit to 5)
    const recentBody = document.getElementById("recent-invoices-body");
    recentBody.innerHTML = "";
    
    if (currentInvoices.length === 0) {
        recentBody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 40px;">No invoices scanned yet. Click "Scan New Invoice" to begin.</td></tr>`;
    } else {
        currentInvoices.slice(0, 5).forEach(inv => {
            const tr = document.createElement("tr");
            const taxClaim = inv.cgst + inv.sgst_utgst + inv.igst;
            tr.innerHTML = `
                <td>${inv.invoice_date || 'N/A'}</td>
                <td style="font-family: monospace;">${inv.invoice_number || 'N/A'}</td>
                <td class="vendor-cell">${inv.vendor_name || 'N/A'}</td>
                <td><span class="category-badge badge-${inv.expense_category}">${inv.expense_category}</span></td>
                <td>₹${inv.taxable_amount.toFixed(2)}</td>
                <td>₹${taxClaim.toFixed(2)}</td>
                <td style="font-weight: 600;">₹${inv.total_amount.toFixed(2)}</td>
                <td><span class="status-badge status-${inv.status}">${inv.status}</span></td>
            `;
            recentBody.appendChild(tr);
        });
    }
    
    // Draw Charts
    renderCharts(categorySpend, taxBreakdown);
}

function renderCharts(categorySpend, taxBreakdown) {
    // Destroy existing chart instances to re-draw
    if (categoryChart) categoryChart.destroy();
    if (taxChart) taxChart.destroy();
    
    const catCanvas = document.getElementById("categoryChart");
    if (!catCanvas) return;
    
    const catLabels = Object.keys(categorySpend);
    const catData = Object.values(categorySpend);
    
    categoryChart = new Chart(catCanvas, {
        type: 'doughnut',
        data: {
            labels: catLabels.length > 0 ? catLabels : ["No Data"],
            datasets: [{
                data: catData.length > 0 ? catData : [1],
                backgroundColor: [
                    '#00e5ff', '#bc6ff1', '#52de97', '#ffb037', '#ff5e7e', '#a5a9c5', '#8d44ad', '#34495e'
                ],
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#9499b3', font: { family: 'Inter', size: 11 } }
                }
            }
        }
    });
    
    const taxCanvas = document.getElementById("taxChart");
    if (!taxCanvas) return;
    
    taxChart = new Chart(taxCanvas, {
        type: 'bar',
        data: {
            labels: ['CGST', 'SGST/UTGST', 'IGST'],
            datasets: [{
                label: 'Taxes Accrued (₹)',
                data: [taxBreakdown.CGST, taxBreakdown.SGST, taxBreakdown.IGST],
                backgroundColor: ['rgba(0, 229, 255, 0.7)', 'rgba(188, 111, 241, 0.7)', 'rgba(82, 222, 151, 0.7)'],
                borderColor: ['#00e5ff', '#bc6ff1', '#52de97'],
                borderWidth: 1,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: '#9499b3' } },
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#9499b3' } }
            }
        }
    });
}

// --- Invoices Table / Filter Module ---
async function loadInvoicesList() {
    const vendor = document.getElementById("filter-vendor").value.trim();
    const category = document.getElementById("filter-category").value;
    
    let url = "/api/invoices?";
    if (vendor) url += `vendor=${encodeURIComponent(vendor)}&`;
    if (category) url += `category=${encodeURIComponent(category)}&`;
    
    const list = await apiCall(url);
    if (!list) return;
    
    const tbody = document.getElementById("invoices-list-body");
    tbody.innerHTML = "";
    
    if (list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 40px;">No matching invoices found.</td></tr>`;
        return;
    }
    
    list.forEach(inv => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${inv.invoice_date || 'N/A'}</td>
            <td style="font-family: monospace;">${inv.invoice_number || 'N/A'}</td>
            <td class="vendor-cell">${inv.vendor_name || 'N/A'}</td>
            <td><span class="category-badge badge-${inv.expense_category}">${inv.expense_category}</span></td>
            <td>₹${inv.taxable_amount.toFixed(2)}</td>
            <td>₹${inv.cgst.toFixed(2)}</td>
            <td>₹${inv.sgst_utgst.toFixed(2)}</td>
            <td>₹${inv.igst.toFixed(2)}</td>
            <td style="font-weight: 600;">₹${inv.total_amount.toFixed(2)}</td>
            <td>
                <div class="action-icons">
                    <button class="action-btn btn-edit" title="Edit Data" onclick="openEditDrawer(${inv.id})">
                        <svg viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                    </button>
                    <button class="action-btn btn-delete" title="Delete Invoice" onclick="deleteInvoice(${inv.id})">
                        <svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// --- Invoice Editor Drawer Module ---
async function openEditDrawer(invoiceId) {
    const inv = await apiCall(`/api/invoices/${invoiceId}`);
    if (!inv) return;
    
    document.getElementById("edit-invoice-id").value = inv.id;
    document.getElementById("edit-vendor").value = inv.vendor_name || "";
    document.getElementById("edit-date").value = inv.invoice_date || "";
    document.getElementById("edit-number").value = inv.invoice_number || "";
    document.getElementById("edit-vendor-gstin").value = inv.gstin_vendor || "";
    document.getElementById("edit-recipient-gstin").value = inv.gstin_recipient || "";
    document.getElementById("edit-category").value = inv.expense_category || "Others";
    document.getElementById("edit-taxable").value = inv.taxable_amount || 0;
    document.getElementById("edit-cgst").value = inv.cgst || 0;
    document.getElementById("edit-sgst").value = inv.sgst_utgst || 0;
    document.getElementById("edit-igst").value = inv.igst || 0;
    document.getElementById("edit-total").value = inv.total_amount || 0;
    
    document.getElementById("invoice-editor-drawer").classList.add("open");
}

function closeDrawer() {
    document.getElementById("invoice-editor-drawer").classList.remove("open");
}

function recalculateTotal() {
    const taxable = parseFloat(document.getElementById("edit-taxable").value) || 0;
    const cgst = parseFloat(document.getElementById("edit-cgst").value) || 0;
    const sgst = parseFloat(document.getElementById("edit-sgst").value) || 0;
    const igst = parseFloat(document.getElementById("edit-igst").value) || 0;
    
    const grandTotal = taxable + cgst + sgst + igst;
    document.getElementById("edit-total").value = grandTotal.toFixed(2);
}

async function saveInvoiceData() {
    const id = document.getElementById("edit-invoice-id").value;
    
    const body = {
        vendor_name: document.getElementById("edit-vendor").value.trim(),
        invoice_date: document.getElementById("edit-date").value || null,
        invoice_number: document.getElementById("edit-number").value.trim(),
        gstin_vendor: document.getElementById("edit-vendor-gstin").value.trim().toUpperCase(),
        gstin_recipient: document.getElementById("edit-recipient-gstin").value.trim().toUpperCase(),
        expense_category: document.getElementById("edit-category").value,
        taxable_amount: parseFloat(document.getElementById("edit-taxable").value) || 0,
        cgst: parseFloat(document.getElementById("edit-cgst").value) || 0,
        sgst_utgst: parseFloat(document.getElementById("edit-sgst").value) || 0,
        igst: parseFloat(document.getElementById("edit-igst").value) || 0,
        total_amount: parseFloat(document.getElementById("edit-total").value) || 0,
        status: "processed"
    };
    
    const updated = await apiCall(`/api/invoices/${id}`, "PUT", body);
    if (updated) {
        closeDrawer();
        loadInvoicesList();
    }
}

async function deleteInvoice(id) {
    if (confirm("Are you sure you want to delete this invoice permanently?")) {
        const deleted = await apiCall(`/api/invoices/${id}`, "DELETE");
        if (deleted) {
            loadInvoicesList();
        }
    }
}

// --- GST Reports Module ---
async function generateGSTReport() {
    const year = document.getElementById("report-year").value;
    const month = document.getElementById("report-month").value;
    
    let url = `/api/gst-report?year=${year}`;
    if (month) url += `&month=${month}`;
    
    const report = await apiCall(url);
    if (!report) return;
    
    const sum = report.summary;
    
    // Fill Cards
    const totalIntra = sum.cgst + sum.sgst_utgst;
    document.getElementById("gst-rep-intra").textContent = formatINR(totalIntra);
    document.getElementById("gst-rep-cgst").textContent = formatINR(sum.cgst);
    document.getElementById("gst-rep-sgst").textContent = formatINR(sum.sgst_utgst);
    
    document.getElementById("gst-rep-igst").textContent = formatINR(sum.igst);
    document.getElementById("gst-rep-total").textContent = formatINR(sum.total_gst);
    
    // Fill GSTR-3B Helper table values
    // Assume: local purchases are Intra (CGST/SGST), Import purchases are Inter (IGST).
    document.getElementById("gstr-import-igst").textContent = formatINR(sum.igst);
    document.getElementById("gstr-other-cgst").textContent = formatINR(sum.cgst);
    document.getElementById("gstr-other-sgst").textContent = formatINR(sum.sgst_utgst);
    
    document.getElementById("gstr-total-igst").innerHTML = `<strong>${formatINR(sum.igst)}</strong>`;
    document.getElementById("gstr-total-cgst").innerHTML = `<strong>${formatINR(sum.cgst)}</strong>`;
    document.getElementById("gstr-total-sgst").innerHTML = `<strong>${formatINR(sum.sgst_utgst)}</strong>`;
}

function exportGSTCSV() {
    const year = document.getElementById("report-year").value;
    const month = document.getElementById("report-month").value;
    const period = month ? `${year}-${month.padStart(2, '0')}` : `${year}`;
    
    // Let's call the report API first to get data
    let url = `/api/gst-report?year=${year}`;
    if (month) url += `&month=${month}`;
    
    apiCall(url).then(report => {
        if (!report || report.invoices.length === 0) {
            alert("No invoice records to export.");
            return;
        }
        
        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += "Invoice Date,Invoice Number,Supplier,Vendor GSTIN,Taxable Value,CGST,SGST,IGST,Total Amount\n";
        
        report.invoices.forEach(inv => {
            csvContent += `"${inv.invoice_date}","${inv.invoice_number}","${inv.vendor_name}","${inv.gstin_vendor}",${inv.taxable_amount},${inv.cgst},${inv.sgst_utgst},${inv.igst},${inv.total_amount}\n`;
        });
        
        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `GST_Report_Period_${period}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });
}

// --- AI Chat Assistant Module ---
async function loadChatHistory() {
    const history = await apiCall("/api/chat/history");
    if (!history) return;
    
    const container = document.getElementById("chat-messages-container");
    // Preserve first bubble greeting
    container.innerHTML = `
        <div class="chat-bubble bubble-assistant">
            <p>Hi there! I am your AI GST Assistant. Ask me anything about your scanned invoices and tax payments.</p>
            <p>Quick queries you can ask:</p>
            <div class="chat-suggestions">
                <div class="suggestion-chip" onclick="sendQuickQuery('How many invoices do I have?')">How many invoices do I have?</div>
                <div class="suggestion-chip" onclick="sendQuickQuery('How much did I spend on Transport?')">How much did I spend on Transport?</div>
                <div class="suggestion-chip" onclick="sendQuickQuery('What is my total GST tax credit?')">What is my total GST tax credit?</div>
            </div>
        </div>
    `;
    
    history.forEach(msg => {
        appendMessageBubble(msg.role, msg.content);
    });
    
    scrollToBottom(container);
}

function appendMessageBubble(role, content) {
    const container = document.getElementById("chat-messages-container");
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble bubble-${role}`;
    
    // Parse formatting like **bold** or *italic* into HTML
    const htmlText = content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
        
    bubble.innerHTML = `<p>${htmlText}</p>`;
    container.appendChild(bubble);
    scrollToBottom(container);
}

async function submitChatMessage(e) {
    e.preventDefault();
    const inputBox = document.getElementById("chat-input-box");
    const query = inputBox.value.trim();
    if (!query) return;
    
    inputBox.value = "";
    
    // Add user bubble
    appendMessageBubble("user", query);
    
    // Add pending assistant bubble loader
    const container = document.getElementById("chat-messages-container");
    const loaderBubble = document.createElement("div");
    loaderBubble.className = "chat-bubble bubble-assistant";
    loaderBubble.id = "chat-pending-loader";
    loaderBubble.innerHTML = `<p>Thinking... 🤖</p>`;
    container.appendChild(loaderBubble);
    scrollToBottom(container);
    
    // Call Chat API
    const response = await apiCall("/api/chat", "POST", { message: query });
    
    // Remove loader
    const loader = document.getElementById("chat-pending-loader");
    if (loader) loader.remove();
    
    if (response) {
        appendMessageBubble("assistant", response.content);
    }
}

function sendQuickQuery(queryText) {
    document.getElementById("chat-input-box").value = queryText;
    document.getElementById("chat-form").dispatchEvent(new Event("submit"));
}

async function clearChat() {
    if (confirm("Are you sure you want to clear conversation history?")) {
        const cleared = await apiCall("/api/chat/clear", "POST");
        if (cleared) {
            loadChatHistory();
        }
    }
}

// --- Helper Formatting ---
function formatINR(val) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 2
    }).format(val);
}

function scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
}
