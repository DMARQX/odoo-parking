/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

export const PortalHomeCounters = publicWidget.Widget.extend({
    selector: '.o_portal_my_home',

    start: function () {
        const def = this._super.apply(this, arguments);
        // التأكد من أن الـ element موجود قبل بدء التحديث
        if (this.el && this.el.querySelectorAll) {
            this._updateCounters().catch((error) => {
                console.error('Error starting portal counters:', error);
            });
        } else {
            console.warn('Portal element not found, skipping counter updates');
        }
        return def;
    },

    _getCountersAlwaysDisplayed() {
        return [];
    },

    async _updateCounters() {
        try {
            // يفضل عدم استخدام Object.values على NodeList
            const nodes = this.el.querySelectorAll('[data-placeholder_count]');
            if (!nodes || nodes.length === 0) {
                console.info('No counter elements found in DOM');
                return;
            }
            
            const needed = Array.from(nodes).map(
                (el) => el.dataset['placeholder_count']
            ).filter(Boolean); // فلترة القيم الفارغة
            
            if (needed.length === 0) {
                console.info('No valid counter names found');
                return;
            }

        const numberRpc = Math.min(Math.ceil(needed.length / 5), 3);
        const counterByRpc = Math.ceil(needed.length / (numberRpc || 1));
        const countersAlwaysDisplayed = this._getCountersAlwaysDisplayed();

        const proms = [...Array(Math.min(numberRpc, needed.length)).keys()].map(async (i) => {
            try {
                const slice = needed.slice(i * counterByRpc, (i + 1) * counterByRpc);
                if (!slice.length) return {};
                
                // التحقق من صحة الطلب قبل الإرسال
                if (!slice.every(counter => counter && typeof counter === 'string')) {
                    console.warn('Invalid counter names found:', slice);
                    return {};
                }
                
                const documentsCountersData = await rpc("/my/counters", { counters: slice });
                
                if (!documentsCountersData || typeof documentsCountersData !== 'object') {
                    console.warn('Invalid response from /my/counters');
                    return {};
                }

            Object.keys(documentsCountersData).forEach((counterName) => {
                const documentsCounterEl = this.el.querySelector(
                    `[data-placeholder_count='${counterName}']`
                );
                if (!documentsCounterEl) {
                    // العنصر مش موجود في الـ DOM (اتشال من التمبليت؟) نتجاهل بأمان
                    console.warn(`Counter element not found for: ${counterName}`);
                    return;
                }
                // التأكد من أن العنصر موجود قبل تعديل textContent
                if (documentsCounterEl && typeof documentsCountersData[counterName] !== 'undefined') {
                    documentsCounterEl.textContent = documentsCountersData[counterName];
                }

                if (
                    documentsCountersData[counterName] !== 0 ||
                    countersAlwaysDisplayed.includes(counterName)
                ) {
                    const card = documentsCounterEl.closest('.o_portal_index_card');
                    if (card) {
                        card.classList.remove('d-none');
                    }
                }
            });
            return documentsCountersData;
            } catch (rpcError) {
                console.error('RPC error in portal counters:', rpcError);
                return {};
            }
        });

        return Promise.all(proms).then(() => {
            const spinner = this.el.querySelector('.o_portal_doc_spinner');
            if (spinner && spinner.remove) spinner.remove();
        }).catch((error) => {
            console.error('Error updating portal counters:', error);
            // إخفاء الـ spinner في حالة الخطأ أيضاً
            const spinner = this.el.querySelector('.o_portal_doc_spinner');
            if (spinner && spinner.remove) spinner.remove();
        });
        } catch (error) {
            console.error('Fatal error in _updateCounters:', error);
            // إخفاء الـ spinner في حالة الخطأ الفادح
            const spinner = this.el.querySelector('.o_portal_doc_spinner');
            if (spinner && spinner.remove) spinner.remove();
        }
    },
});

publicWidget.registry.PortalHomeCounters = PortalHomeCounters;
