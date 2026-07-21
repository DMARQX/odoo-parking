/** @odoo-module **/

import { url } from '@web/core/utils/urls';
import { useService } from '@web/core/utils/hooks';
import { Component, onWillUnmount } from '@odoo/owl';

export class AppsBar extends Component {
    static template = 'code_solution_theme.AppsBar';
    static props = {};
    
    setup() {
        this.companyService = useService('company');
        this.appMenuService = useService('app_menu');
        
        // Listen for menu changes to re-render
        const renderAfterMenuChange = () => {
            this.render();
        };
        this.env.bus.addEventListener('MENUS:APP-CHANGED', renderAfterMenuChange);
        
        onWillUnmount(() => {
            this.env.bus.removeEventListener('MENUS:APP-CHANGED', renderAfterMenuChange);
        });
    }
    
    _onAppClick(app) {
        return this.appMenuService.selectApp(app);
    }
}
