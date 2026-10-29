"""Generate high-resolution SVG figures comparing Model A and Model B."""

import json
from pathlib import Path

FINAL_DIR = Path(__file__).resolve().parents[1] / "data" / "final_experiment"

# 1. Overview Comparison Bar Chart
def generate_overview_svg():
    metrics = [
        ("Accuracy", 0.1900, 0.5700),
        ("Macro Precision", 0.3116, 0.5467),
        ("Macro Recall", 0.3409, 0.5532),
        ("Macro F1", 0.1186, 0.5455),
    ]
    
    width = 720
    height = 420
    margin_left = 80
    margin_top = 70
    chart_width = 580
    chart_height = 280
    
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '  <style>',
        '    .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 16px; font-weight: 700; fill: #1e293b; }',
        '    .subtitle { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 12px; fill: #64748b; }',
        '    .axis-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 11px; fill: #475569; font-weight: 600; }',
        '    .tick { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10px; fill: #94a3b8; }',
        '    .grid { stroke: #e2e8f0; stroke-width: 1; stroke-dasharray: 3,3; }',
        '    .bar-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10px; font-weight: 600; fill: #0f172a; text-anchor: middle; }',
        '    .legend { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 11px; fill: #334155; }',
        '  </style>',
        '  <rect width="100%" height="100%" fill="#ffffff" rx="8" />',
        '  <text x="360" y="30" text-anchor="middle" class="title">Model A vs. Model B Overall Performance Benchmark</text>',
        '  <text x="360" y="48" text-anchor="middle" class="subtitle">Held-Out 300 Fin-Fact Claims (Zero Leakage Test Set)</text>',
    ]
    
    # Legend
    svg.append('  <g transform="translate(420, 20)">')
    svg.append('    <rect x="0" y="0" width="14" height="14" rx="3" fill="#64748b" />')
    svg.append('    <text x="20" y="11" class="legend">Model A (Qwen2.5:3b Zero-Shot)</text>')
    svg.append('    <rect x="0" y="18" width="14" height="14" rx="3" fill="#2563eb" />')
    svg.append('    <text x="20" y="29" class="legend">Model B (MPNet Classifier)</text>')
    svg.append('  </g>')
    
    # Grid & Y ticks
    for tick_val in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = margin_top + chart_height - (tick_val * chart_height)
        svg.append(f'  <line x1="{margin_left}" y1="{y}" x2="{margin_left + chart_width}" y2="{y}" class="grid" />')
        svg.append(f'  <text x="{margin_left - 10}" y="{y + 3}" text-anchor="end" class="tick">{tick_val:.1f}</text>')
        
    group_width = chart_width / len(metrics)
    bar_width = 38
    
    for idx, (label, val_a, val_b) in enumerate(metrics):
        group_center = margin_left + idx * group_width + group_width / 2
        
        # Bar A
        x_a = group_center - bar_width - 3
        h_a = val_a * chart_height
        y_a = margin_top + chart_height - h_a
        svg.append(f'  <rect x="{x_a}" y="{y_a}" width="{bar_width}" height="{h_a}" rx="4" fill="#94a3b8" />')
        svg.append(f'  <text x="{x_a + bar_width/2}" y="{y_a - 5}" class="bar-label">{val_a:.4f}</text>')
        
        # Bar B
        x_b = group_center + 3
        h_b = val_b * chart_height
        y_b = margin_top + chart_height - h_b
        svg.append(f'  <rect x="{x_b}" y="{y_b}" width="{bar_width}" height="{h_b}" rx="4" fill="#2563eb" />')
        svg.append(f'  <text x="{x_b + bar_width/2}" y="{y_b - 5}" class="bar-label" fill="#1d4ed8">{val_b:.4f}</text>')
        
        # X label
        svg.append(f'  <text x="{group_center}" y="{margin_top + chart_height + 22}" text-anchor="middle" class="axis-label">{label}</text>')
        
    svg.append('</svg>')
    (FINAL_DIR / "model_comparison_overview.svg").write_text("\n".join(svg), encoding="utf-8")
    print("Saved model_comparison_overview.svg")

# 2. Per-Class F1 Comparison Bar Chart
def generate_per_class_svg():
    classes = [
        ("SUPPORTED", 0.0000, 0.6226, "n=113"),
        ("REFUTED", 0.0438, 0.6077, "n=133"),
        ("UNVERIFIABLE", 0.3121, 0.4062, "n=54"),
    ]
    
    width = 680
    height = 380
    margin_left = 70
    margin_top = 70
    chart_width = 540
    chart_height = 250
    
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '  <style>',
        '    .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 16px; font-weight: 700; fill: #1e293b; }',
        '    .subtitle { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 12px; fill: #64748b; }',
        '    .axis-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 12px; fill: #475569; font-weight: 600; }',
        '    .tick { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10px; fill: #94a3b8; }',
        '    .grid { stroke: #e2e8f0; stroke-width: 1; stroke-dasharray: 3,3; }',
        '    .bar-label { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10px; font-weight: 600; fill: #0f172a; text-anchor: middle; }',
        '    .legend { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 11px; fill: #334155; }',
        '    .subtext { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 10px; fill: #94a3b8; }',
        '  </style>',
        '  <rect width="100%" height="100%" fill="#ffffff" rx="8" />',
        '  <text x="340" y="30" text-anchor="middle" class="title">Per-Class F1-Score: Model A vs. Model B</text>',
        '  <text x="340" y="48" text-anchor="middle" class="subtitle">Comparison of F1 Across All 3 Factuality Categories</text>',
    ]
    
    # Legend
    svg.append('  <g transform="translate(430, 20)">')
    svg.append('    <rect x="0" y="0" width="14" height="14" rx="3" fill="#94a3b8" />')
    svg.append('    <text x="20" y="11" class="legend">Model A (Qwen2.5:3b)</text>')
    svg.append('    <rect x="0" y="18" width="14" height="14" rx="3" fill="#0d9488" />')
    svg.append('    <text x="20" y="29" class="legend">Model B (MPNet)</text>')
    svg.append('  </g>')
    
    for tick_val in [0.0, 0.2, 0.4, 0.6, 0.8]:
        y = margin_top + chart_height - (tick_val * chart_height)
        svg.append(f'  <line x1="{margin_left}" y1="{y}" x2="{margin_left + chart_width}" y2="{y}" class="grid" />')
        svg.append(f'  <text x="{margin_left - 10}" y="{y + 3}" text-anchor="end" class="tick">{tick_val:.1f}</text>')
        
    group_width = chart_width / len(classes)
    bar_width = 46
    
    for idx, (label, f1_a, f1_b, n_info) in enumerate(classes):
        group_center = margin_left + idx * group_width + group_width / 2
        
        # Bar A
        x_a = group_center - bar_width - 4
        h_a = max(f1_a * chart_height, 2)
        y_a = margin_top + chart_height - h_a
        svg.append(f'  <rect x="{x_a}" y="{y_a}" width="{bar_width}" height="{h_a}" rx="4" fill="#94a3b8" />')
        svg.append(f'  <text x="{x_a + bar_width/2}" y="{y_a - 5}" class="bar-label">{f1_a:.4f}</text>')
        
        # Bar B
        x_b = group_center + 4
        h_b = f1_b * chart_height
        y_b = margin_top + chart_height - h_b
        svg.append(f'  <rect x="{x_b}" y="{y_b}" width="{bar_width}" height="{h_b}" rx="4" fill="#0d9488" />')
        svg.append(f'  <text x="{x_b + bar_width/2}" y="{y_b - 5}" class="bar-label" fill="#0f766e">{f1_b:.4f}</text>')
        
        # X label
        svg.append(f'  <text x="{group_center}" y="{margin_top + chart_height + 20}" text-anchor="middle" class="axis-label">{label}</text>')
        svg.append(f'  <text x="{group_center}" y="{margin_top + chart_height + 34}" text-anchor="middle" class="subtext">({n_info})</text>')
        
    svg.append('</svg>')
    (FINAL_DIR / "model_comparison_per_class.svg").write_text("\n".join(svg), encoding="utf-8")
    print("Saved model_comparison_per_class.svg")

# 3. Model B Confusion Matrix Heatmap
def generate_confusion_matrix_svg():
    matrix = [
        [66, 26, 21],  # SUPPORTED
        [27, 79, 27],  # REFUTED
        [6,  22, 26],  # UNVERIFIABLE
    ]
    labels = ["SUPPORTED", "REFUTED", "UNVERIFIABLE"]
    
    width = 540
    height = 450
    margin_left = 140
    margin_top = 80
    cell_size = 90
    
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">',
        '  <style>',
        '    .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 15px; font-weight: 700; fill: #1e293b; }',
        '    .subtitle { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 11px; fill: #64748b; }',
        '    .lbl { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 11px; font-weight: 600; fill: #334155; }',
        '    .cell-txt { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 14px; font-weight: 700; text-anchor: middle; }',
        '    .hdr { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; font-size: 11px; font-weight: 700; fill: #0f172a; text-anchor: middle; }',
        '  </style>',
        '  <rect width="100%" height="100%" fill="#ffffff" rx="8" />',
        '  <text x="270" y="28" text-anchor="middle" class="title">Model B (MPNet) Confusion Matrix</text>',
        '  <text x="270" y="45" text-anchor="middle" class="subtitle">Held-Out 300 Claims (Overall Accuracy: 57.00%)</text>',
        f'  <text x="{margin_left + cell_size * 1.5}" y="70" class="hdr">PREDICTED CLASS</text>',
        f'  <text x="25" y="{margin_top + cell_size * 1.5}" class="lbl" transform="rotate(-90 25 {margin_top + cell_size * 1.5})" text-anchor="middle">ACTUAL CLASS</text>',
    ]
    
    for j, col_lbl in enumerate(labels):
        x = margin_left + j * cell_size + cell_size / 2
        svg.append(f'  <text x="{x}" y="{margin_top - 5}" class="lbl" text-anchor="middle">{col_lbl}</text>')
        
    for i, row_lbl in enumerate(labels):
        y = margin_top + i * cell_size + cell_size / 2
        svg.append(f'  <text x="{margin_left - 10}" y="{y + 4}" class="lbl" text-anchor="end">{row_lbl}</text>')
        
        row_sum = sum(matrix[i])
        for j, col_lbl in enumerate(labels):
            val = matrix[i][j]
            ratio = val / row_sum
            # Color intensity: teal gradient
            fill_color = f'rgba(13, 148, 136, {0.15 + 0.85 * ratio:.2f})'
            text_color = '#ffffff' if ratio > 0.45 else '#0f172a'
            cell_x = margin_left + j * cell_size
            cell_y = margin_top + i * cell_size
            
            svg.append(f'  <rect x="{cell_x + 2}" y="{cell_y + 2}" width="{cell_size - 4}" height="{cell_size - 4}" rx="6" fill="{fill_color}" stroke="#0d9488" stroke-width="1" />')
            svg.append(f'  <text x="{cell_x + cell_size/2}" y="{cell_y + cell_size/2 - 4}" class="cell-txt" fill="{text_color}">{val}</text>')
            svg.append(f'  <text x="{cell_x + cell_size/2}" y="{cell_y + cell_size/2 + 14}" font-size="10" font-family="sans-serif" font-weight="500" fill="{text_color}" text-anchor="middle">{ratio*100:.1f}%</text>')
            
    svg.append('</svg>')
    (FINAL_DIR / "model_b_mpnet_confusion_matrix.svg").write_text("\n".join(svg), encoding="utf-8")
    print("Saved model_b_mpnet_confusion_matrix.svg")

if __name__ == "__main__":
    generate_overview_svg()
    generate_per_class_svg()
    generate_confusion_matrix_svg()
