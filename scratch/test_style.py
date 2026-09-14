import xml.etree.ElementTree as ET

xml_data = """<kanban class="o_kanban_dashboard" create="1">
    <field name="name"/>
    <templates>
        <t t-name="menu">
            <a name="action_configure" type="object" class="dropdown-item">Configure</a>
        </t>
        <t t-name="card" class="o_prep_display_card">
            <style>
                .o_prep_display_card { min-width: 500px !important; }
            </style>
            <div>Test</div>
        </t>
    </templates>
</kanban>"""

tree = ET.fromstring(xml_data)
print("Parsed XML successfully:", tree.tag)
