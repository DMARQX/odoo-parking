import sys
from lxml import etree
import odoo
odoo.tools.config.parse_config([])
from odoo.modules.loading import _is_valid_data

formats = {
    "record+mix": b"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="test_action" model="ir.actions.act_window">
        <field name="name">Test</field>
        <field name="res_model">parking.spot</field>
        <field name="view_mode">list,form</field>
    </record>
    <menuitem id="test_menu" name="Test" action="test_action"/>
</odoo>""",
    "record_only": b"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <record id="test_action2" model="ir.actions.act_window">
        <field name="name">Test2</field>
        <field name="res_model">parking.spot</field>
        <field name="view_mode">list,form</field>
    </record>
    <record id="test_menu2" model="ir.ui.menu">
        <field name="name">Test Menu</field>
        <field name="action" ref="test_action2"/>
    </record>
</odoo>""",
    "menuitem_only": b"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <menuitem id="test_menu3" name="Test Menu"/>
</odoo>""",
    "act_window_shorthand": b"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <act_window id="test_act3" name="Test" res_model="parking.spot" view_mode="list,form"/>
</odoo>""",
}

for name, xml in formats.items():
    valid, err = _is_valid_data(f"/tmp/{name}.xml", xml)
    print(f"Format {name}: valid={valid}, err={err}")
