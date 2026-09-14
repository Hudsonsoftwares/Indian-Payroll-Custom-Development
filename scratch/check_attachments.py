with open(r'C:\Program Files\Odoo 19.0.20260717\server\odoo\addons\web\static\src\views\kanban\kanban_controller.scss', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'KanbanRecord-width' in line:
            for j in range(max(0, i-5), min(len(lines), i+15)):
                print(lines[j], end='')
