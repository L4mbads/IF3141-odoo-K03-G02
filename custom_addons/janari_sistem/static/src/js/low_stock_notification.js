/** @odoo-module **/

import { registry } from "@web/core/registry";

const lowStockNotificationService = {
    dependencies: ["bus_service", "notification"],
    start(env, { bus_service, notification }) {
        bus_service.addChannel("janari_low_stock");
        bus_service.subscribe("janari_low_stock_alert", (payload) => {
            notification.add(payload.message, {
                title: payload.title,
                type: "warning",
                sticky: true,
            });
        });
    },
};

registry.category("services").add("janari_low_stock_notification", lowStockNotificationService);
