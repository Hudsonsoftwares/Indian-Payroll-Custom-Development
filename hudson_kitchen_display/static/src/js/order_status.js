(function () {
    "use strict";

    const root = document.getElementById("order_status_root");
    if (!root) {
        return; // Not on the order-status page
    }

    const orderId = root.dataset.orderId;

    async function rpc(route, params) {
        const res = await fetch(route, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {}, id: Date.now() }),
        });
        const data = await res.json();
        return data.result;
    }

    function render(status) {
        const pct = status.total_stages > 1 ? Math.round((status.sequence / (status.total_stages - 1)) * 100) : 100;
        const finished = status.sequence >= status.total_stages - 1;
        root.innerHTML = `
        <div class="os-wrap ${finished ? "os-done" : ""}">
            <div class="os-stage">${status.stage_name}</div>
            <div class="os-bar"><div class="os-bar-fill" style="width:${Math.min(100, pct)}%"></div></div>
            <div class="os-sub">${finished ? "Enjoy your meal!" : "Almost there"}</div>
            <div class="os-logo">Odoo</div>
        </div>`;
    }

    async function poll() {
        try {
            const status = await rpc("/hudson_kitchen_display/get_order_status", { order_id: orderId });
            render(status);
        } catch (e) {
            // keep last rendered state on transient network errors
        }
    }

    poll();
    setInterval(poll, 4000);
})();
