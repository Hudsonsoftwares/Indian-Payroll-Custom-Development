/** @odoo-module **/

import { registry } from "@web/core/registry";

let globalActionService = null;

// Register service to capture the active Odoo ActionService
const hdsDashboardNavService = {
    dependencies: ["action"],
    start(env, { action }) {
        globalActionService = action;
    },
};

registry.category("services").add("hds_dashboard_nav_service", hdsDashboardNavService);

(function () {
    "use strict";

    if (window.__hds_dashboard_nav_initialized) return;
    window.__hds_dashboard_nav_initialized = true;

    const DASHBOARD_ACTION_XMLID = "hudson_in_payroll.action_hds_payroll_dashboard";
    const DASHBOARD_ACTION_URL = "/odoo/action-hudson_in_payroll.action_hds_payroll_dashboard";
    const SESSION_KEY = "hds_from_payroll_dashboard";

    function isDashboardPage() {
        return (
            window.location.href.includes("action_hds_payroll_dashboard") ||
            window.location.href.includes("hds.payroll.dashboard") ||
            Boolean(document.querySelector(".o_hds_payroll_dashboard_form"))
        );
    }

    function isNavigatedFromDashboard() {
        if (isDashboardPage()) {
            return false;
        }

        // 1. URL parameters
        const href = window.location.href;
        if (href.includes("from_hds_dashboard=1") || href.includes("from_dashboard=1")) {
            return true;
        }

        // 2. Dashboard-specific window actions
        if (href.includes("action_dashboard_")) {
            return true;
        }

        // 3. Document referrer
        if (
            document.referrer &&
            (document.referrer.includes("action_hds_payroll_dashboard") ||
             document.referrer.includes("hds.payroll.dashboard"))
        ) {
            return true;
        }

        // 4. sessionStorage (same tab SPA navigation)
        if (sessionStorage.getItem(SESSION_KEY) === "true") {
            return true;
        }

        // 5. localStorage (cross-tab navigation within 1 hour)
        const lastNavTime = parseInt(localStorage.getItem("hds_last_dashboard_nav") || "0", 10);
        if (lastNavTime && (Date.now() - lastNavTime < 60 * 60 * 1000)) {
            if (localStorage.getItem(SESSION_KEY) === "true") {
                return true;
            }
        }

        return false;
    }

    function removeBackButtons() {
        const cpBtn = document.getElementById("hds_back_to_dashboard_cp_btn");
        if (cpBtn) cpBtn.remove();
        const floatBtn = document.getElementById("hds_floating_back_btn");
        if (floatBtn) floatBtn.remove();
    }

    function navigateBackToDashboard(ev) {
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }
        sessionStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(SESSION_KEY);
        removeBackButtons();

        // 1. Single Page Application (SPA) in-place navigation via Odoo ActionService
        if (globalActionService) {
            try {
                globalActionService.doAction(DASHBOARD_ACTION_XMLID, {
                    clearBreadcrumbs: true,
                });
                return;
            } catch (err) {
                console.warn("[HDS Dashboard] Error in globalActionService.doAction:", err);
            }
        }

        // 2. Fallback to WOWL debug root service
        try {
            if (
                window.odoo &&
                window.odoo.__WOWL_DEBUG__ &&
                window.odoo.__WOWL_DEBUG__.root &&
                window.odoo.__WOWL_DEBUG__.root.env &&
                window.odoo.__WOWL_DEBUG__.root.env.services &&
                window.odoo.__WOWL_DEBUG__.root.env.services.action
            ) {
                window.odoo.__WOWL_DEBUG__.root.env.services.action.doAction(
                    DASHBOARD_ACTION_XMLID,
                    { clearBreadcrumbs: true }
                );
                return;
            }
        } catch (err) {
            // Ignore error and proceed to location fallback
        }

        // 3. Fallback to URL navigation
        window.location.href = DASHBOARD_ACTION_URL;
    }

    function injectBackButtons() {
        if (isDashboardPage()) {
            sessionStorage.removeItem(SESSION_KEY);
            localStorage.removeItem(SESSION_KEY);
            removeBackButtons();
            return;
        }

        if (!isNavigatedFromDashboard()) {
            removeBackButtons();
            return;
        }

        // 1. Control Panel Button (Placed directly before breadcrumbs / title)
        const cpTarget = document.querySelector(
            ".o_control_panel_breadcrumbs, .o_breadcrumb, .o_cp_top_left, .o_control_panel"
        );
        if (cpTarget && !document.getElementById("hds_back_to_dashboard_cp_btn")) {
            const btn = document.createElement("button");
            btn.id = "hds_back_to_dashboard_cp_btn";
            btn.type = "button";
            btn.className = "btn btn-sm btn-primary d-inline-flex align-items-center gap-1 me-2 my-auto shadow-sm";
            btn.style.cssText = "font-weight: 600; border-radius: 6px; padding: 4px 12px; cursor: pointer; flex-shrink: 0; text-decoration: none; z-index: 100;";
            btn.innerHTML = '<i class="fa fa-arrow-left me-1"></i> <span>Back to Dashboard</span>';
            btn.addEventListener("click", navigateBackToDashboard);

            if (cpTarget.firstChild) {
                cpTarget.insertBefore(btn, cpTarget.firstChild);
            } else {
                cpTarget.appendChild(btn);
            }
        }

        // 2. Floating Action Pill (Always visible across scrolling & table rows in any view)
        if (!document.getElementById("hds_floating_back_btn")) {
            const floatBtn = document.createElement("div");
            floatBtn.id = "hds_floating_back_btn";
            floatBtn.className = "shadow-lg d-flex align-items-center gap-2";
            floatBtn.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 99999;
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                color: #ffffff;
                padding: 10px 18px;
                border-radius: 25px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                border: 1px solid rgba(255, 255, 255, 0.25);
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
                transition: transform 0.18s ease, box-shadow 0.18s ease;
                user-select: none;
            `;
            floatBtn.innerHTML = '<i class="fa fa-arrow-left" style="color: #38bdf8;"></i> <span>Back to Dashboard</span>';
            floatBtn.addEventListener("mouseenter", () => {
                floatBtn.style.transform = "translateY(-2px) scale(1.02)";
                floatBtn.style.boxShadow = "0 12px 28px rgba(0, 0, 0, 0.45)";
            });
            floatBtn.addEventListener("mouseleave", () => {
                floatBtn.style.transform = "none";
                floatBtn.style.boxShadow = "0 8px 24px rgba(0, 0, 0, 0.35)";
            });
            floatBtn.addEventListener("click", navigateBackToDashboard);
            document.body.appendChild(floatBtn);
        }
    }

    function getActionFromLink(link) {
        const href = link.getAttribute("href") || "";
        if (!href || href.startsWith("#")) return null;

        // Pattern 1: /odoo/action-<xml_id> or /odoo/action-<xml_id>?...
        const actionMatch = href.match(/\/odoo\/action-([^?#]+)/);
        if (actionMatch && actionMatch[1]) {
            return actionMatch[1];
        }

        // Pattern 2: /odoo/hr.employee/<id>
        const recordMatch = href.match(/\/odoo\/([^/?#]+)\/(\d+)/);
        if (recordMatch && recordMatch[1] && recordMatch[2]) {
            return {
                type: "ir.actions.act_window",
                res_model: recordMatch[1],
                res_id: parseInt(recordMatch[2], 10),
                views: [[false, "form"]],
                target: "current",
            };
        }

        return null;
    }

    // Intercept card clicks on dashboard: PREVENT page navigation & LOAD IN-PLACE (SPA)
    document.addEventListener("click", function (ev) {
        const link = ev.target.closest("a.o_hds_dashboard_card_clickable, a[href*='/odoo/action-'], a[href*='/odoo/hr.employee/']");
        if (!link) {
            // If user clicked top navbar to navigate to another module, clean up flags
            const navItem = ev.target.closest(".o_navbar, .o_menu_brand, .o_nav_entry");
            if (navItem && !navItem.closest(".o_hds_payroll_dashboard_form")) {
                const text = (navItem.textContent || "").toLowerCase();
                if (!text.includes("payroll") && !text.includes("dashboard")) {
                    sessionStorage.removeItem(SESSION_KEY);
                    localStorage.removeItem(SESSION_KEY);
                    removeBackButtons();
                }
            }
            return;
        }

        const dashboard = link.closest(".o_hds_payroll_dashboard_form, [name='dashboard_html']");
        if (!dashboard) return;

        const action = getActionFromLink(link);
        if (!action) return;

        // PREVENT browser full-page reload or new tab!
        ev.preventDefault();
        ev.stopPropagation();

        sessionStorage.setItem(SESSION_KEY, "true");
        localStorage.setItem(SESSION_KEY, "true");
        localStorage.setItem("hds_last_dashboard_nav", Date.now().toString());

        // Perform Single Page (SPA) action execution in-place
        if (globalActionService) {
            globalActionService.doAction(action, {
                clearBreadcrumbs: false,
            });
        } else {
            // Fallback if action service is not ready
            try {
                if (window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.action) {
                    window.odoo.__WOWL_DEBUG__.root.env.services.action.doAction(action, {
                        clearBreadcrumbs: false,
                    });
                    return;
                }
            } catch (e) {}
            window.location.href = link.getAttribute("href");
        }
    }, true);

    // Watch DOM mutations to ensure buttons persist across Owl SPA transitions
    const observer = new MutationObserver(function () {
        injectBackButtons();
    });

    if (document.body) {
        observer.observe(document.body, {
            childList: true,
            subtree: true,
        });
        injectBackButtons();
    } else {
        document.addEventListener("DOMContentLoaded", () => {
            observer.observe(document.body, {
                childList: true,
                subtree: true,
            });
            injectBackButtons();
        });
    }
})();
