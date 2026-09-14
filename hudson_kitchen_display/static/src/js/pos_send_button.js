/* EXPERIMENTAL / best-effort. The bundle this file is loaded from
 * ('point_of_sale._assets_pos') is the one thing most likely to have a
 * different name across Odoo versions - see README "In-POS button" section.
 *
 * Rather than patching Odoo's OWL POS components (which change shape often
 * enough between releases to break silently), this injects one plain,
 * floating button on top of the POS screen. It asks the backend to
 * (re)send the current cashier's most recent order to the kitchen - safe
 * to click more than once, it never duplicates lines already sent. */
(function () {
    "use strict";

    async function rpc(route, params) {
        const res = await fetch(route, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {}, id: Date.now() }),
        });
        return res.json();
    }

    function createButton() {
        if (document.getElementById("hkd-send-btn")) {
            return;
        }
        const btn = document.createElement("button");
        btn.id = "hkd-send-btn";
        btn.textContent = "Send to Kitchen";
        btn.style.cssText =
            "position:fixed;bottom:16px;right:16px;z-index:9999;background:#4a90d9;" +
            "color:#fff;border:none;border-radius:24px;padding:12px 20px;font-size:14px;" +
            "box-shadow:0 2px 8px rgba(0,0,0,0.3);cursor:pointer;font-family:inherit;";
        btn.onclick = async () => {
            btn.disabled = true;
            const original = btn.textContent;
            btn.textContent = "Sending...";
            try {
                const data = await rpc("/hudson_kitchen_display/manual_send_last_order", {});
                if (data.result && data.result.ok) {
                    btn.textContent = "Sent \u2713";
                } else {
                    btn.textContent = "No recent order found";
                }
            } catch (e) {
                btn.textContent = "Failed - check connection";
            }
            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = original;
            }, 2000);
        };
        document.body.appendChild(btn);
    }

    // The POS single-page app can take a moment to finish mounting.
    let tries = 0;
    const interval = setInterval(() => {
        tries += 1;
        if (document.body) {
            createButton();
        }
        if (tries > 20) {
            clearInterval(interval);
        }
    }, 500);
})();
