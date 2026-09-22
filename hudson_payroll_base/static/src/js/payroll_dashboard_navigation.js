/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

window.__hds_rpc = rpc;

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
        const selectors = [".o_web_client", ".o_action_manager", ".o_main_navbar", ".o_content", "[class*='o_']"];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.__owl__?.component?.env?.services?.action) {
                globalActionService = el.__owl__.component.env.services.action;
                window.__hds_action = globalActionService;
                return globalActionService;
            }
        }
        if (window.odoo?.__WOWL_DEBUG__?.root?.env?.services?.action) {
            globalActionService = window.odoo.__WOWL_DEBUG__.root.env.services.action;
            window.__hds_action = globalActionService;
            return globalActionService;
        }
        return null;
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
            name: "Payslips to Validate",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "in", ["draft", "verify"]]],
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
            name: "Employees Missing Aadhaar",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], "|", ["hds_in_aadhaar", "=", false], ["hds_in_aadhaar", "=", ""]],
        },
        contact_health: {
            name: "Employees Missing Emergency Contact",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], "&", "|", ["emergency_contact", "=", false], ["emergency_contact", "=", ""], "|", ["emergency_phone", "=", false], ["emergency_phone", "=", ""]],
        },
        epf_status: {
            name: "Employees Missing EPF UAN",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["hds_in_epf_applicable", "=", true], "|", ["hds_in_uan", "=", false], ["hds_in_uan", "=", ""]],
        },
        esic_status: {
            name: "Employees Missing ESIC IP Number",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["hds_in_esic_applicable", "=", true], "|", ["hds_in_esic_ip", "=", false], ["hds_in_esic_ip", "=", ""]],
        },
        lwf_status: {
            name: "Employees Missing LWF Registration",
            res_model: "hr.employee",
            views: [[false, "list"], [false, "form"]],
            domain: [["active", "=", true], ["hds_in_lwf_applicable", "=", true]],
        },
        readiness_status: {
            name: "Employees with Statutory Data Errors",
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
            name: "Employer ESIC Contribution Slips",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "!=", "cancel"]],
        },
        lwf_liability: {
            name: "Employer LWF Contribution Slips",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "!=", "cancel"]],
        },
        total_employer_statutory: {
            name: "Employer Statutory Contribution Slips",
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

        const executeAction = (actionDef) => {
            const actionService = getActionService();
            if (actionService && actionService.doAction) {
                actionService.doAction({
                    type: "ir.actions.act_window",
                    name: actionDef.name,
                    res_model: actionDef.res_model,
                    views: actionDef.views || [[false, "list"], [false, "form"]],
                    domain: actionDef.domain || [],
                    target: actionDef.target || "current",
                }, { clearBreadcrumbs: false });
            } else {
                console.warn("[HDS Dashboard] ActionService not available yet for card click, retrying...");
                setTimeout(() => {
                    const retryService = getActionService();
                    if (retryService && retryService.doAction) {
                        retryService.doAction({
                            type: "ir.actions.act_window",
                            name: actionDef.name,
                            res_model: actionDef.res_model,
                            views: actionDef.views || [[false, "list"], [false, "form"]],
                            domain: actionDef.domain || [],
                            target: actionDef.target || "current",
                        }, { clearBreadcrumbs: false });
                    }
                }, 100);
            }
        };

        function fallbackLocal() {
            const baseDef = CARD_ACTIONS[cardType] || {
                name: "Employees",
                res_model: "hr.employee",
                views: [[false, "list"], [false, "form"]],
                domain: [["active", "=", true]],
            };

            const rootEl = (cardEl && cardEl.closest) ? (cardEl.closest(".o_hds_dashboard_root") || cardEl.closest("[data-hds-dashboard-root]")) : document.querySelector(".o_hds_dashboard_root");
            const dateFrom = cardEl?.dataset?.dateFrom || rootEl?.dataset?.dateFrom;
            const dateTo = cardEl?.dataset?.dateTo || rootEl?.dataset?.dateTo;

            let domain = Array.isArray(baseDef.domain) ? [...baseDef.domain] : [];
            if (baseDef.res_model === "hr.payslip" && dateFrom && dateTo) {
                domain.push(["date_from", "<=", dateTo]);
                domain.push(["date_to", ">=", dateFrom]);
            }

            executeAction({
                name: baseDef.name,
                res_model: baseDef.res_model,
                views: baseDef.views,
                domain: domain,
            });
        }

        const rootEl = (cardEl && cardEl.closest) ? (cardEl.closest(".o_hds_dashboard_root") || cardEl.closest("[data-hds-dashboard-root]")) : document.querySelector(".o_hds_dashboard_root");
        const monthSelect = document.querySelector("[name='payroll_month_num'] select, select[name='payroll_month_num']");
        const selectedMonth = (monthSelect && monthSelect.value) ? monthSelect.value : (cardEl?.dataset?.monthNum || rootEl?.dataset?.monthNum);

        const actionService = getActionService();
        if (rpc && actionService) {
            rpc("/web/dataset/call_kw/hds.payroll.dashboard/get_card_action", {
                model: "hds.payroll.dashboard",
                method: "get_card_action",
                args: [],
                kwargs: {
                    card_type: cardType,
                    month_num: selectedMonth,
                },
            }).then(backendAction => {
                if (backendAction && backendAction.res_model) {
                    executeAction(backendAction);
                } else {
                    fallbackLocal();
                }
            }).catch(err => {
                console.warn("[HDS Dashboard] get_card_action RPC error, using local fallback:", err);
                fallbackLocal();
            });
            return false;
        }

        fallbackLocal();
        return false;
    };

    // Single record view (e.g. employee click)
    window.hdsRecordClick = function (el, recordId, model) {
        if (!recordId || !model) return;
        const executeRecordAction = () => {
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
                console.warn("[HDS Dashboard] ActionService not available yet for record click, retrying...");
                setTimeout(() => {
                    const retryService = getActionService();
                    if (retryService && retryService.doAction) {
                        retryService.doAction({
                            type: "ir.actions.act_window",
                            res_model: model,
                            res_id: parseInt(recordId, 10),
                            views: [[false, "form"]],
                            target: "current",
                        }, { clearBreadcrumbs: false });
                    }
                }, 100);
            }
        };
        executeRecordAction();
    };

    // Delegated click listener to catch card and record clicks exclusively inside dashboard containers
    document.addEventListener("click", function (ev) {
        const dashboardRoot = ev.target.closest(".o_hds_dashboard_root, [data-hds-dashboard-root], .hds-dashboard-container");
        if (!dashboardRoot) {
            return;
        }

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

    // Dynamic Period Update without Full Window / Browser Reload
    window.hdsUpdatePeriod = function (monthNum, fyId) {
        const rootEl = document.querySelector(".o_hds_dashboard_root, [data-hds-dashboard-root]");
        if (rootEl) {
            rootEl.style.transition = "opacity 0.15s ease";
            rootEl.style.opacity = "0.45";
            rootEl.style.pointerEvents = "none";
        }

        const rpcService = window.__hds_rpc || rpc;
        if (!rpcService) {
            console.warn("[HDS Dashboard] RPC service unavailable for dynamic period update.");
            return;
        }

        console.log("[HDS Dashboard] Dynamic period update requested: Month =", monthNum, "FY =", fyId);

        rpcService("/web/dataset/call_kw/hds.payroll.dashboard/set_dashboard_period_and_get_html", {
            model: "hds.payroll.dashboard",
            method: "set_dashboard_period_and_get_html",
            args: [],
            kwargs: {
                month_num: monthNum,
                fy_id: fyId,
            },
        }).then(result => {
            if (result && result.html) {
                const currentRoot = document.querySelector(".o_hds_dashboard_root, [data-hds-dashboard-root]");
                if (currentRoot) {
                    const tempDiv = document.createElement("div");
                    tempDiv.innerHTML = result.html;
                    const newRoot = tempDiv.firstElementChild || tempDiv;
                    newRoot.style.opacity = "0";
                    newRoot.style.transition = "opacity 0.2s ease";
                    currentRoot.replaceWith(newRoot);
                    requestAnimationFrame(() => {
                        newRoot.style.opacity = "1";
                    });
                }

                // Sync top form fields if present in Form View
                if (result.payroll_month_num) {
                    const formMonthSelect = document.querySelector("[name='payroll_month_num'] select, select[name='payroll_month_num']");
                    if (formMonthSelect) formMonthSelect.value = result.payroll_month_num;
                    const monthToggler = document.querySelector("[name='payroll_month_num'] .o_select_menu_toggler_slot");
                    const monthMap = {
                        "1": "January", "2": "February", "3": "March", "4": "April",
                        "5": "May", "6": "June", "7": "July", "8": "August",
                        "9": "September", "10": "October", "11": "November", "12": "December"
                    };
                    if (monthToggler && monthMap[result.payroll_month_num]) {
                        monthToggler.textContent = monthMap[result.payroll_month_num];
                    }
                }

                if (result.financial_year_name) {
                    const fyToggler = document.querySelector("[name='financial_year_id'] .o_select_menu_toggler_slot, [name='financial_year_id'] input");
                    if (fyToggler) {
                        if (fyToggler.value !== undefined) fyToggler.value = result.financial_year_name;
                        else fyToggler.textContent = result.financial_year_name;
                    }
                }

                // Sync Workforce badge
                if (result.active_employee_count !== undefined) {
                    const empBadge = document.querySelector("[name='active_employee_count']");
                    if (empBadge) empBadge.textContent = result.active_employee_count;
                }

                console.log("[HDS Dashboard] Dynamic period update completed successfully!");
            }
        }).catch(err => {
            console.error("[HDS Dashboard] set_dashboard_period_and_get_html error:", err);
            if (rootEl) {
                rootEl.style.opacity = "1";
                rootEl.style.pointerEvents = "auto";
            }
        });
    };

    // Auto-update when Payroll Month or Tax Year form view dropdown changes
    let periodChangeDebounce = null;
    document.addEventListener("change", function (ev) {
        const target = ev.target;
        if (!target) return;

        // Skip internal dashboard selectors (they use explicit onchange)
        if (target.id === "hds_dashboard_month_picker" || target.id === "hds_dashboard_fy_picker") {
            return;
        }

        const isMonth = target.matches("[name='payroll_month_num'] select, select[name='payroll_month_num']") ||
                        target.closest("[name='payroll_month_num']");
        const isYear = target.matches("[name='financial_year_id'] select, select[name='financial_year_id']") ||
                       target.closest("[name='financial_year_id']");

        if (isMonth || isYear) {
            clearTimeout(periodChangeDebounce);
            periodChangeDebounce = setTimeout(() => {
                const monthSelect = document.querySelector("[name='payroll_month_num'] select, select[name='payroll_month_num'], [name='payroll_month_num'] input");
                const monthVal = monthSelect ? (monthSelect.value || (monthSelect.dataset && monthSelect.dataset.value)) : null;

                const yearSelect = document.querySelector("[name='financial_year_id'] select, select[name='financial_year_id'], [name='financial_year_id'] input");
                const yearVal = yearSelect ? (yearSelect.value || (yearSelect.dataset && yearSelect.dataset.value)) : null;

                window.hdsUpdatePeriod(monthVal, yearVal);
            }, 80);
        }
    }, true);

    // Support Odoo 19 OWL SelectMenu item selection clicks in FormView
    document.addEventListener("click", function (ev) {
        const choiceItem = ev.target.closest(".o_select_menu_menu .dropdown-item, .o_field_selection_menu .dropdown-item, [data-choice-index]");
        if (choiceItem) {
            setTimeout(() => {
                const monthToggler = document.querySelector("[name='payroll_month_num'] .o_select_menu_toggler_slot, [name='payroll_month_num'] button");
                if (monthToggler) {
                    const text = monthToggler.textContent.trim();
                    const monthMap = {
                        "January": "1", "February": "2", "March": "3", "April": "4",
                        "May": "5", "June": "6", "July": "7", "August": "8",
                        "September": "9", "October": "10", "November": "11", "December": "12"
                    };
                    if (monthMap[text]) {
                        window.hdsUpdatePeriod(monthMap[text], null);
                    }
                }
            }, 60);
        }
    }, true);
})();

