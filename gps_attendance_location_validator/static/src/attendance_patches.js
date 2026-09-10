/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
import { rpc } from "@web/core/network/rpc";
import { isIosApp } from "@web/core/browser/feature_detection";
import { useService, useServiceProtectMethodHandling } from "@web/core/utils/hooks";
import { AttendanceActionHelper } from "@hr_attendance/views/attendance_helper_view";
import { _t } from "@web/core/l10n/translation";
import { actionService, ControllerNotFoundError } from "@web/webclient/actions/action_service";

// Prevent fatal unhandled rejections when an async task completes after component destruction
if (useServiceProtectMethodHandling) {
    useServiceProtectMethodHandling.fn = function () {
        return new Promise(() => {});
    };
    useServiceProtectMethodHandling.original = function () {
        return new Promise(() => {});
    };
}

// Global safeguard against benign Owl destroyed component promise rejections
window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    const msg = (reason && (reason.message || reason.cause?.message || String(reason))) || "";
    if (typeof msg === "string" && msg.includes("Component is destroyed")) {
        console.warn("Suppressed benign Owl lifecycle unhandled rejection:", msg);
        event.preventDefault();
        if (typeof event.stopImmediatePropagation === "function") {
            event.stopImmediatePropagation();
        }
    }
});

try {
    patch(AttendanceActionHelper.prototype, {
        setup() {
            super.setup(...arguments);
            const originalCall = this.orm?.call?.bind(this.orm);
            if (originalCall) {
                this.orm.call = async (...args) => {
                    if (this.__owl__ && (this.__owl__.status === 3 || this.__owl__.status === "destroyed")) {
                        return false;
                    }
                    try {
                        return await originalCall(...args);
                    } catch (e) {
                        if (e?.message?.includes("Component is destroyed")) {
                            return false;
                        }
                        throw e;
                    }
                };
            }
        },
    });
} catch (e) {
    console.warn("Could not patch AttendanceActionHelper:", e);
}

patch(ActivityMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.notification = useService("notification");
    },

    async signInOut() {
        this.dropdown.close();

        if (!isIosApp() && navigator.geolocation) {
            const getPosition = (options) =>
                new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject, options);
                });

            let coords = null;
            try {
                // Try high accuracy with timeout first
                const pos = await getPosition({ enableHighAccuracy: true, timeout: 5000, maximumAge: 60000 });
                coords = pos.coords;
            } catch (err) {
                console.warn("High accuracy geolocation failed, falling back to network/low accuracy:", err);
                try {
                    // Fallback to low accuracy (Wi-Fi / IP based)
                    const pos = await getPosition({ enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
                    coords = pos.coords;
                } catch (fallbackErr) {
                    console.warn("Geolocation failed completely:", fallbackErr);
                }
            }

            if (coords) {
                try {
                    this.employee = await rpc("/hr_attendance/systray_check_in_out", {
                        latitude: coords.latitude,
                        longitude: coords.longitude,
                    });
                    this._searchReadEmployeeFill();
                } catch (error) {
                    this.notification.add(
                        error.data?.message || _t("An error occurred during attendance change."),
                        { type: "danger" }
                    );
                }
            } else {
                try {
                    this.employee = await rpc("/hr_attendance/systray_check_in_out");
                    this._searchReadEmployeeFill();
                } catch (error) {
                    this.notification.add(
                        error.data?.message || _t("Location permission is required to perform check-in. Please enable location services in your browser and Windows settings."),
                        { type: "danger" }
                    );
                }
            }
        } else {
            try {
                this.employee = await rpc("/hr_attendance/systray_check_in_out");
                this._searchReadEmployeeFill();
            } catch (error) {
                this.notification.add(
                    error.data?.message || _t("An error occurred during attendance change."),
                    { type: "danger" }
                );
            }
        }
    },
});

patch(actionService, {
    start(env) {
        const actionManager = super.start(...arguments);
        const originalRestore = actionManager.restore;
        actionManager.restore = async function (jsId) {
            try {
                return await originalRestore.apply(this, arguments);
            } catch (error) {
                if (error instanceof ControllerNotFoundError) {
                    console.warn("Gracefully handling controller restore error:", error);
                    env.bus.trigger("WEBCLIENT:LOAD_DEFAULT_APP");
                    return;
                }
                throw error;
            }
        };
        return actionManager;
    }
});
