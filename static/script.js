document.addEventListener('DOMContentLoaded', () => {
    const tableBody = document.getElementById('table-body');
    const metricTotal = document.getElementById('metric-total');
    const metricDue = document.getElementById('metric-due');
    const metricRenewed = document.getElementById('metric-renewed');
    
    const triggerBtn = document.getElementById('trigger-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const btnText = triggerBtn.querySelector('.btn-text');

    // Fetch and render renewals
    async function fetchRenewals() {
        try {
            renderSkeletons();
            const response = await fetch('/renewals');
            if (!response.ok) throw new Error('Failed to fetch data');
            
            const data = await response.json();
            updateDashboard(data);
        } catch (error) {
            console.error('Error fetching renewals:', error);
            showToast('Failed to load data. Is the server running?', 'error');
        }
    }

    function renderSkeletons() {
        tableBody.innerHTML = Array(3).fill(0).map(() => `
            <tr>
                <td><div class="skeleton" style="height: 20px; width: 120px;"></div></td>
                <td><div class="skeleton" style="height: 20px; width: 80px;"></div></td>
                <td><div class="skeleton" style="height: 20px; width: 100px;"></div></td>
                <td><div class="skeleton" style="height: 20px; width: 60px;"></div></td>
                <td><div class="skeleton" style="height: 24px; width: 80px; border-radius: 999px;"></div></td>
                <td><div class="skeleton" style="height: 20px; width: 150px;"></div></td>
            </tr>
        `).join('');
    }

    function updateDashboard(data) {
        // Update Metrics
        metricTotal.textContent = data.length;
        
        const todayStr = new Date().toISOString().split('T')[0];
        const dueToday = data.filter(r => r.renewal_due_date === todayStr).length;
        metricDue.textContent = dueToday;
        
        const renewed = data.filter(r => r.renewal_decision === 'renewed').length;
        metricRenewed.textContent = renewed;

        // Update Table
        if (data.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 2rem;">No memberships found in database.</td></tr>`;
            return;
        }

        tableBody.innerHTML = data.map(row => {
            const statusClass = row.renewal_decision ? row.renewal_decision.toLowerCase() : 'pending';
            const statusText = row.renewal_decision ? row.renewal_decision : 'Pending';
            const notes = row.cancellation_reason || (row.callback_date ? `Callback: ${row.callback_date}` : '—');
            
            return `
                <tr>
                    <td style="font-weight: 500;">${row.name} <br><span style="font-size: 0.8em; color: var(--text-muted)">${row.phone_number}</span></td>
                    <td>${row.plan_name}</td>
                    <td>${row.renewal_due_date}</td>
                    <td>$${row.amount_due}</td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    <td class="notes-cell" title="${notes}">${notes}</td>
                </tr>
            `;
        }).join('');
    }

    // Trigger calls action
    triggerBtn.addEventListener('click', async () => {
        triggerBtn.disabled = true;
        const originalText = btnText.textContent;
        btnText.textContent = 'Initiating Calls...';
        
        try {
            const response = await fetch('/trigger-calls', { method: 'POST' });
            if (!response.ok) throw new Error('API Error');
            
            showToast('AI calls have been successfully initiated.', 'info');
            
            // Wait 2 seconds and fetch to see any immediate status changes
            setTimeout(fetchRenewals, 2000);
            
        } catch (error) {
            console.error('Trigger error:', error);
            showToast('Failed to trigger calls.', 'error');
        } finally {
            triggerBtn.disabled = false;
            btnText.textContent = originalText;
        }
    });

    refreshBtn.addEventListener('click', () => {
        refreshBtn.style.transform = 'rotate(180deg)';
        setTimeout(() => refreshBtn.style.transform = 'none', 300);
        fetchRenewals();
    });

    // Toast Notification System
    function showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        const toastMessage = toast.querySelector('.toast-message');
        
        toast.className = `toast glass ${type}`;
        toastMessage.textContent = message;
        
        // Force reflow
        void toast.offsetWidth;
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 4000);
    }

    // Initial load
    fetchRenewals();
    
    // Auto refresh every 10 seconds to show live updates during a demo
    setInterval(fetchRenewals, 10000);
});
