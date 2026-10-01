/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { onMounted } from "@odoo/owl";

export class PurchaseDownPaymentFormController extends FormController {
    setup() {
        super.setup();
        onMounted(() => this._setPurchaseOrderFromBreadcrumb());
    }

    async _setPurchaseOrderFromBreadcrumb() {
        const record = this.model.root;
        if (!record?.isNew || record.data.purchase_order_id) {
            return;
        }
        const stack =
            this.env.services.action.currentController?.state?.actionStack || [];
        const parentPo = [...stack].reverse().find(
            (item) =>
                item.resId &&
                item.resId !== "new" &&
                (item.action === "purchase" || item.model === "purchase.order")
        );
        if (parentPo?.resId) {
            await record.update({ purchase_order_id: parentPo.resId });
        }
    }
}

registry.category("views").add("purchase_down_payment_form", {
    ...formView,
    Controller: PurchaseDownPaymentFormController,
});
