/** @odoo-module **/

import { registry } from "@web/core/registry";

let globalActionService = null;

// Register service to capture active Odoo ActionService
const hdsDashboardNavService = {
    dependencies: ["action"],
    start(env, { action }) {
        globalActionService = action;
        window.__hds_action = action;
        console.log("[HDS Dashboard] ActionService registered successfully.");
    },
};

registry.category("services").add("hds_dashboard_nav_service", hdsDashboardNavService);

(function () {
    "use strict";

    console.log("[HDS Dashboard Navigation] Script active.");

    function getActionService() {
        if (window.__hds_action) return window.__hds_action;
        if (globalActionService) return globalActionService;
        const owlEl = document.querySelector(".o_web_client, .o_action_manager, .o_form_view, .o_content, [class*='o_']");
        if (owlEl && owlEl.__owl__ && owlEl.__owl__.component && owlEl.__owl__.component.env) {
            const act = owlEl.__owl__.component.env.services?.action;
            if (act) return act;
        }
        return window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.action;
    }

    const ACTION_URL_MAP = {
        total_payroll_cost: "/odoo/action-273",
        total_net_pay: "/odoo/action-273",
        active_employee_count: "/odoo/action-197",
        tds_this_month: "/odoo/action-273",
        tds_withholding: "/odoo/action-273",
        pending_actions: "/odoo/action-687",
        missing_pan: "/odoo/action-687",
        missing_bank: "/odoo/action-688",
        pending_declarations: "/odoo/action-689",
        attendance_exceptions: "/odoo/action-690",
        new_joiners: "/odoo/action-691",
        final_settlements_due: "/odoo/action-197",
        pan_health: "/odoo/action-687",
        bank_health: "/odoo/action-688",
        aadhaar_health: "/odoo/action-197",
        contact_health: "/odoo/action-197",
        epf_status: "/odoo/action-694",
        esic_status: "/odoo/action-695",
        lwf_status: "/odoo/action-197",
        readiness_status: "/odoo/action-197",
        epf_liability: "/odoo/action-273",
        esic_liability: "/odoo/action-273",
        pt_liability: "/odoo/action-273",
        old_regime: "/odoo/action-692",
        new_regime: "/odoo/action-693",
        tds_ytd: "/odoo/action-566",
    };

    const CARD_ACTIONS = {
        total_payroll_cost: {
            name: "Total Payroll Cost Slips",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "!=", "cancel"]],
        },
        total_net_pay: {
            name: "Net Salary Disbursement",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "!=", "cancel"]],
        },
        active_employee_count: {
            name: "Active Employees",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true]],
        },
        tds_this_month: {
            name: "TDS Withholding Slips",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "!=", "cancel"]],
        },
        tds_withholding: {
            name: "TDS Withholding Slips",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "!=", "cancel"]],
        },
        pending_actions: {
            name: "Employees Requiring Action",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], "|", "|", ["hds_in_pan", "=", false], ["hds_in_pan", "=", ""], ["bank_account_id", "=", false]],
        },
        missing_pan: {
            name: "Employees Missing PAN",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], "|", ["hds_in_pan", "=", false], ["hds_in_pan", "=", ""]],
        },
        missing_bank: {
            name: "Employees Missing Bank Details",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["bank_account_id", "=", false]],
        },
        pending_declarations: {
            name: "Pending Tax Declarations",
            res_model: "tds.employee.declaration",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "in", ["submitted", "proof_submitted", "proof_under_review"]]],
        },
        attendance_exceptions: {
            name: "Draft Payslips & Exceptions",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "=", "draft"]],
        },
        new_joiners: {
            name: "New Joiners",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true]],
        },
        final_settlements_due: {
            name: "Exited / Inactive Employees",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", false]],
        },
        pan_health: {
            name: "Employees Missing PAN",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], "|", ["hds_in_pan", "=", false], ["hds_in_pan", "=", ""]],
        },
        bank_health: {
            name: "Employees Missing Bank Details",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["bank_account_id", "=", false]],
        },
        aadhaar_health: {
            name: "Employees Missing Aadhaar / ID",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], "|", ["identification_id", "=", false], ["identification_id", "=", ""]],
        },
        contact_health: {
            name: "Employees Missing Emergency Contact",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true]],
        },
        epf_status: {
            name: "EPF Applicable Employees",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["hds_in_epf_applicable", "=", true]],
        },
        esic_status: {
            name: "ESIC Applicable Employees",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["hds_in_esic_applicable", "=", true]],
        },
        lwf_status: {
            name: "LWF Registered Employees",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true]],
        },
        readiness_status: {
            name: "Payroll Ready Employees",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true]],
        },
        epf_liability: {
            name: "EPF Liability Slips",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "!=", "cancel"]],
        },
        esic_liability: {
            name: "ESIC Liability Slips",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "!=", "cancel"]],
        },
        pt_liability: {
            name: "Professional Tax Slips",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "!=", "cancel"]],
        },
        old_regime: {
            name: "Employees in Old Tax Regime",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["hds_in_tax_regime", "=", "old"]],
        },
        new_regime: {
            name: "Employees in New Tax Regime (115BAC)",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["hds_in_tax_regime", "=", "new"]],
        },
        tds_ytd: {
            name: "TDS Declarations",
            res_model: "tds.employee.declaration",
            views: [[false, "list"], [false, "form"]],
            domain: [],
        },
    };

    // Primary card click: Navigates on current page with breadcrumbs to return
    window.hdsCardClick = function (cardEl, cardType) {
        if (!cardType) return false;

        if (cardEl) {
            document.querySelectorAll(".hds-card-active").forEach(el => el.classList.remove("hds-card-active"));
            cardEl.classList.add("hds-card-active");
        }

        const actionDef = CARD_ACTIONS[cardType] || {
            name: "Employees",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true]],
        };

        const actionService = getActionService();
        if (actionService && actionService.doAction) {
            actionService.doAction({
                type: "ir.actions.act_window",
                name: actionDef.name,
                res_model: actionDef.res_model,
                views: actionDef.views,
                domain: actionDef.domain,
                target: "current",
            }, { clearBreadcrumbs: false });
            return false;
        } else {
            // Fallback: navigate in the current page
            const fallbackUrl = ACTION_URL_MAP[cardType] || "/odoo/action-197";
            window.location.href = fallbackUrl;
            return false;
        }
    };

    // Single record view (e.g. employee click)
    window.hdsRecordClick = function (el, recordId, model) {
        if (!recordId || !model) return;
        const actionService = getActionService();
        if (actionService && actionService.doAction) {
            actionService.doAction({
                type: "ir.actions.act_window",
                res_model: model,
                res_id: parseInt(recordId, 10),
                views: [[false, "form"]],
                target: "current",
            }, { clearBreadcrumbs: false });
        } else {
            window.location.href = `/odoo/${model}/${recordId}`;
        }
    };

    // Delegated click listener to catch card and record clicks
    document.addEventListener("click", function (ev) {
        const recBtn = ev.target.closest("[data-record-id]");
        if (recBtn) {
            const rid = recBtn.getAttribute("data-record-id");
            const rmod = recBtn.getAttribute("data-record-model");
            if (rid && rmod) {
                ev.preventDefault();
                ev.stopPropagation();
                window.hdsRecordClick(recBtn, rid, rmod);
                return;
            }
        }

        const card = ev.target.closest(".o_hds_dashboard_card_clickable, [data-card-type]");
        if (card) {
            const ctype = card.getAttribute("data-card-type");
            if (ctype && ctype !== "hr_employee_record") {
                ev.preventDefault();
                ev.stopPropagation();
                window.hdsCardClick(card, ctype);
            }
        }
    }, true);
})();
